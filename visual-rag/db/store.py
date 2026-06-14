import json
import chromadb
import config
from tqdm import tqdm

# Persistent client
_client = None
_collection = None

def get_db():
    global _client, _collection
    if _client is None:
        _client = chromadb.PersistentClient(path=config.DB_PATH)
        _collection = _client.get_or_create_collection(
            name="study_notes_gemini",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def embed_text(text: str) -> list[float]:
    """Generate embedding using text-embedding-004 (separate quota pool from generative models)."""
    import time
    from gemini_client import get_rotator, get_gemini_client
    rotator = get_rotator()
    rotator.reload_keys()

    embed_model = getattr(config, "TEXT_EMBED_MODEL", "gemini-embedding-2")
    sleep_secs  = getattr(config, "EMBED_SLEEP_SECS", 0.2)
    max_attempts = len(rotator.keys) or 1
    last_error = None

    for attempt in range(max_attempts):
        key = rotator.get_next_key()
        masked_key = f"...{key[-6:]}" if len(key) > 6 else "InvalidKey"
        try:
            time.sleep(sleep_secs)  # Stay within RPM: 3 keys × 5 RPM = 15 RPM headroom
            client = get_gemini_client(key)
            res = client.models.embed_content(
                model=embed_model,
                contents=text
            )
            return res.embeddings[0].values
        except Exception as e:
            last_error = e
            rotator.report_failure(key, is_rate_limit="429" in str(e))
            print(f"[WARN] Embedding failed using key {masked_key}: {e}")
            time.sleep(2.0)

    raise RuntimeError(f"All available Gemini keys failed to generate embedding. Last error: {last_error}")

def embed_texts_batch(texts: list[str], batch_size: int = 250) -> list[list[float]]:
    """Generate embeddings in batches using text-embedding-004 with key rotation and backoff."""
    import time
    from gemini_client import get_rotator, get_gemini_client
    rotator = get_rotator()

    embed_model = getattr(config, "TEXT_EMBED_MODEL", "gemini-embedding-2")
    sleep_secs  = getattr(config, "EMBED_SLEEP_SECS", 0.2)

    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        batch_success = False
        last_error = None

        # Retry the entire batch up to 3 times if all keys fail
        for batch_attempt in range(3):
            rotator.reload_keys()
            max_attempts = len(rotator.keys) or 1

            for attempt in range(max_attempts):
                key = rotator.get_next_key()
                masked_key = f"...{key[-6:]}" if len(key) > 6 else "InvalidKey"
                try:
                    time.sleep(sleep_secs)  # 0.2s × 3 keys = ~15 embeds/min headroom
                    client = get_gemini_client(key)
                    res = client.models.embed_content(
                        model=embed_model,
                        contents=batch
                    )
                    embeddings = [emb.values for emb in res.embeddings]
                    all_embeddings.extend(embeddings)
                    batch_success = True
                    break  # Success on this batch, move to next batch
                except Exception as e:
                    last_error = e
                    is_429 = "429" in str(e) or "resource_exhausted" in str(e).lower()
                    rotator.report_failure(key, is_rate_limit=is_429)
                    print(f"[WARN] Batch embedding failed using key {masked_key}: {e}. Retrying next key...")
                    time.sleep(2.0)

            if batch_success:
                break
            else:
                print(f"[WARN] All keys failed for batch at index {i}. Sleeping 10s and clearing cooldowns (attempt {batch_attempt+1}/3)...")
                time.sleep(10.0)
                rotator.cool_downs.clear()

        if not batch_success:
            raise RuntimeError(f"Failed to embed batch at index {i} after all retries. Last error: {last_error}")

    return all_embeddings

def store_chunks(chunks: list[dict], file_id: str):
    """Embed and store chunks in ChromaDB. Skips already stored chunks for this file_id."""
    collection = get_db()
    
    # Retrieve existing document IDs for this source file
    try:
        existing = collection.get(where={"source": file_id})
        existing_ids = set(existing.get("ids", []))
    except Exception:
        existing_ids = set()

    # Filter out already indexed chunks
    new_chunks = []
    for i, c in enumerate(chunks):
        chunk_id = f"{file_id}_{i}"
        if chunk_id not in existing_ids:
            new_chunks.append((chunk_id, c))
            
    if not new_chunks:
        print(f"[DB] {file_id} is already fully indexed. Skipping store.")
        return

    print(f"[DB] Embedding and storing {len(new_chunks)} new chunks for {file_id}...")
    
    ids = [item[0] for item in new_chunks]
    texts = [
        item[1].text if hasattr(item[1], "text")
        else (item[1].get("text", "") if isinstance(item[1], dict) else getattr(item[1], "text", ""))
        for item in new_chunks
    ]
    
    # Batch embedding
    embeddings = embed_texts_batch(texts)
    
    # Prepare metadata (ensure all values are primitives: string, int, float, bool)
    metadatas = []
    for _, c in new_chunks:
        if hasattr(c, "model_dump"):
            c_dict = c.model_dump()
        elif isinstance(c, dict):
            c_dict = c
        else:
            c_dict = getattr(c, "__dict__", {})
            
        meta = {
            "source": str(c_dict.get("source", "")),
            "page": int(c_dict.get("page", 1)),
            "section": str(c_dict.get("section", "Introduction")),
            "label": str(c_dict.get("label", "")),
            "knowledge_type": str(c_dict.get("knowledge_type", "mixed")),
            "concept_name": str(c_dict.get("concept_name", "General")),
            "key_entities": json.dumps(c_dict.get("key_entities", []))
        }
        metadatas.append(meta)

    # Add to ChromaDB
    collection.add(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )
    print(f"[DB] Successfully stored {len(new_chunks)} chunks.")
