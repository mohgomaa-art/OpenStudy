import os
import re
import threading
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from services.config import config_service

# Global fallback for ONNXMiniLM_L6_V2 to prevent import-time failures in
# some packaged ChromaDB builds where the symbol lookup raises NameError.
try:
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
except Exception:
    ONNXMiniLM_L6_V2 = None

# P-12 FIX: Unify ChromaDB data paths to prevent duplicates across directories
CHROMA_PATH = os.getenv("CHROMA_PATH", "")
if not CHROMA_PATH:
    # Default to data/chroma_db at the root of the project
    CHROMA_PATH = str(config_service.data_path / "data" / "chroma_db")

EMBED_MODEL  = os.getenv(
    "EMBED_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
MAX_CHUNKS   = int(os.getenv("MAX_CONTEXT_CHUNKS", "5"))
CHUNK_SIZE   = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# ── Singleton Client ──────────────────────────────────────────────────────────
_client = None
_collection = None
_rag_enabled = True  # Circuit breaker
_lock = threading.Lock()


def _init_collection_blocking():
    global _client, _collection, _rag_enabled
    try:
        return _init_collection_blocking_inner()
    except BaseException as e:
        print(f"[RAG] Unhandled crash: {e}")
        _client = None
        _collection = None
        _rag_enabled = False
        return None


def _init_collection_blocking_inner():
    global _client, _collection, _rag_enabled
    if not _rag_enabled:
        return None
        
    with _lock:
        if _collection is not None:
            return _collection
            
        try:
            import chromadb
            # Lazy-load transformer only when needed, inside the thread
            from chromadb.utils.embedding_functions import (
                SentenceTransformerEmbeddingFunction
            )

            print(f"[RAG] Initializing ChromaDB at: {CHROMA_PATH}")
            Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
            
            _client = chromadb.PersistentClient(path=CHROMA_PATH)

            print(f"[RAG] Loading embedding model: {EMBED_MODEL}")
            ef = SentenceTransformerEmbeddingFunction(
                model_name=EMBED_MODEL,
                device="cpu",
                tokenizer_kwargs={"model_max_length": 512},
            )

            print("[RAG] Connecting to 'vault' collection...")
            _collection = _client.get_or_create_collection(
                name="vault",
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
            print("[RAG] Collection ready")
        except Exception as e:
            print(f"[RAG] Initialization failed: {e}")

            # Check for version mismatch via exception class or substring fallback
            is_version_mismatch = False
            try:
                import chromadb.errors
                if isinstance(e, chromadb.errors.VersionMismatchError):
                    is_version_mismatch = True
            except Exception:
                pass

            if not is_version_mismatch:
                # Substring fallback for older Chroma versions without
                # VersionMismatchError. Keep markers SPECIFIC enough that
                # an unrelated exception (e.g. a KeyError naming "_type"
                # in some other library's payload) cannot trick us into
                # wiping the vector DB.
                err_str = str(e)
                err_lower = err_str.lower()
                migration_markers = (
                    "'_type'",                  # KeyError: '_type' (canonical signature)
                    "schema migration",
                    "schema upgrade",
                    "version mismatch",
                    "incompatible chroma",
                    "chroma_segment",
                )
                if any(m in err_lower for m in migration_markers):
                    is_version_mismatch = True

            if is_version_mismatch:
                print("[RAG] ChromaDB version mismatch detected — attempting auto-recovery...")
                try:
                    import shutil
                    import time
                    # Use timestamp so each recovery creates a unique backup (not overwritten)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    backup_path = f"{CHROMA_PATH}_backup_{timestamp}"
                    
                    # Fail closed: Do NOT clear database if the backup step fails
                    try:
                        shutil.copytree(CHROMA_PATH, backup_path)
                        print(f"[RAG] Backup created at: {backup_path}")
                    except Exception as backup_err:
                        print(f"[RAG] Backup failed: {backup_err}. Aborting auto-recovery to prevent data loss.")
                        _rag_enabled = False
                        _collection = None
                        return None

                    # Try to clear it with retries
                    for attempt in range(3):
                        try:
                            shutil.rmtree(CHROMA_PATH)
                            break
                        except Exception:
                            print(f"[RAG] Attempt {attempt+1} to clear locked DB failed...")
                            time.sleep(1)
                    
                    Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
                    import chromadb
                    from chromadb.utils.embedding_functions import (
                        SentenceTransformerEmbeddingFunction
                    )
                    _client = chromadb.PersistentClient(path=CHROMA_PATH)
                    ef = SentenceTransformerEmbeddingFunction(
                        model_name=EMBED_MODEL,
                        device="cpu",
                        tokenizer_kwargs={"model_max_length": 512},
                    )
                    _collection = _client.get_or_create_collection(
                        name="vault",
                        embedding_function=ef,
                        metadata={"hnsw:space": "cosine"},
                    )
                    print("[RAG] Auto-recovery successful — fresh ChromaDB created.")
                    return _collection
                except Exception as recovery_err:
                    print(f"[RAG] Auto-recovery failed: {recovery_err}. RAG disabled.")

            _rag_enabled = False
            _collection = None
            return None
            
    return _collection

def _get_collection():
    """Synchronous getter for legacy sync functions. Will block if first time, but normally called in a thread."""
    return _init_collection_blocking()

def prewarm_rag():
    """Background init for RAG. Called during startup."""
    import threading
    threading.Thread(target=_init_collection_blocking, daemon=True, name="RAG-Prewarm").start()


# ── Text Chunking ─────────────────────────────────────────────────────────────
def _chunk_text(text: str, source: str) -> list[dict]:
    """يقسّم النص لـ chunks متداخلة مع metadata."""
    words = text.split()
    chunks = []
    i = 0
    chunk_idx = 0

    while i < len(words):
        chunk_words = words[i:i + CHUNK_SIZE]
        chunk_text = " ".join(chunk_words)

        if len(chunk_text.strip()) > 50:
            chunks.append({
                "id":       f"{source}__chunk_{chunk_idx}",
                "text":     chunk_text,
                "source":   source,
                "chunk_idx": chunk_idx,
            })
            chunk_idx += 1

        i += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


# ── Add Documents ─────────────────────────────────────────────────────────────
def add_document(text: str, source: str, metadata: dict = None) -> int:
    """
    يضيف document للـ ChromaDB.
    يرجع عدد الـ chunks المضافة.
    """
    col = _get_collection()
    if col is None:
        return 0
    chunks = _chunk_text(text, source)

    if not chunks:
        return 0

    try:
        existing = col.get(where={"source": source})
        if existing["ids"]:
            col.delete(ids=existing["ids"])
    except Exception:
        pass

    meta = metadata or {}
    col.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[{**meta, "source": c["source"], "chunk_idx": c["chunk_idx"]} for c in chunks],
    )
    return len(chunks)


# ── Query ─────────────────────────────────────────────────────────────────────
def query(text: str, n_results: int = None, source_filter: str = None) -> str:
    """
    يبحث في الـ vault ويرجع context string جاهز للـ LLM.
    source_filter: لو عايز تبحث في ملف معين بس.
    """
    col = _get_collection()
    if col is None:
        return ""
    n = n_results or MAX_CHUNKS

    where = {"source": source_filter} if source_filter else None

    try:
        results = col.query(
            query_texts=[text],
            n_results=min(n, col.count()),
            where=where,
        )
    except Exception:
        return ""

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    if not docs:
        return ""

    parts = []
    for doc, meta in zip(docs, metas):
        source = meta.get("source", "Unknown")
        parts.append(f"[From: {Path(source).name}]\n{doc}")

    return "\n\n---\n\n".join(parts)


# ── Stats ─────────────────────────────────────────────────────────────────────
def get_chunk_count() -> int:
    try:
        return _get_collection().count()
    except Exception:
        return 0


def get_sources() -> list[str]:
    try:
        result = _get_collection().get(include=["metadatas"])
        sources = list({m["source"] for m in result["metadatas"] if "source" in m})
        return sorted(sources)
    except Exception:
        return []


# ── Delete Document (BUG-06 FIX) ─────────────────────────────────────────────
def delete_document(source: str) -> int:
    """
    Removes all ChromaDB chunks for the given source path.
    Call this when a vault file is deleted so stale results don't appear in search.
    Returns number of chunks deleted.
    """
    col = _get_collection()
    if col is None:
        return 0
    try:
        existing = col.get(where={"source": source})
        if existing["ids"]:
            col.delete(ids=existing["ids"])
            return len(existing["ids"])
    except Exception as e:
        print(f"[RAG] delete_document error: {e}")
    return 0


# ── Async Wrappers (WASTE-09 FIX) ────────────────────────────────────────────
import asyncio

async def query_async(text: str, n_results: int = None, source_filter: str = None) -> str:
    """Non-blocking wrapper for query() — use in async route handlers."""
    return await asyncio.to_thread(query, text, n_results, source_filter)


async def add_document_async(text: str, source: str, metadata: dict = None) -> int:
    """Non-blocking wrapper for add_document() — use during vault indexing."""
    return await asyncio.to_thread(add_document, text, source, metadata)


async def delete_document_async(source: str) -> int:
    """Non-blocking wrapper for delete_document()."""
    return await asyncio.to_thread(delete_document, source)


# ── Singleton export ──────────────────────────────────────────────────────────
class RAGService:
    add_document        = staticmethod(add_document)
    add_document_async  = staticmethod(add_document_async)
    query               = staticmethod(query)
    query_async         = staticmethod(query_async)
    delete_document     = staticmethod(delete_document)
    delete_document_async = staticmethod(delete_document_async)
    get_chunk_count     = staticmethod(get_chunk_count)
    get_sources         = staticmethod(get_sources)

rag_service = RAGService()
