import config
from .store import get_db, embed_text

def search(query: str, n: int = 5, source_filter: str = None, knowledge_type_filter: str = None) -> list[dict]:
    """
    Search the ChromaDB collection using vector similarity with an optional source filter
    and/or knowledge type filter. Includes keyword search fallback if vector search returns low similarity.
    """
    collection = get_db()
    
    # 1. Vector Search
    q_embed = embed_text(query)
    
    kwargs = {
        "query_embeddings": [q_embed],
        "n_results": n,
        "include": ["documents", "metadatas", "distances"]
    }
    
    where_clause = {}
    if source_filter and knowledge_type_filter:
        where_clause = {"$and": [{"source": source_filter}, {"knowledge_type": knowledge_type_filter}]}
    elif source_filter:
        where_clause = {"source": source_filter}
    elif knowledge_type_filter:
        where_clause = {"knowledge_type": knowledge_type_filter}
        
    if where_clause:
        kwargs["where"] = where_clause
        
    results = collection.query(**kwargs)
    
    # Check if results exist
    vector_hits = []
    if results and "documents" in results and results["documents"] and len(results["documents"][0]) > 0:
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]
        ids = results["ids"][0]
        
        for doc, meta, dist, doc_id in zip(documents, metadatas, distances, ids):
            # Cosine distance to similarity: 1 - dist
            # For other spaces, limit to range
            similarity = max(0.0, min(1.0, 1.0 - dist))
            vector_hits.append({
                "id": doc_id,
                "text": doc,
                "meta": meta,
                "score": similarity,
                "type": "vector"
            })

    # 2. Keyword Fallback/Hybrid Search
    # If vector hits are sparse or have low score (< 0.25), run a keyword fallback query
    best_vector_score = max([h["score"] for h in vector_hits]) if vector_hits else 0.0
    
    if best_vector_score < 0.25:
        # Extract keywords (split query and keep words longer than 3 chars)
        keywords = [w.strip("?,.:;!\"'()").lower() for w in query.split() if len(w) > 3]
        if keywords:
            keyword_hits = []
            # We can search ChromaDB using where_document contains for the primary keyword
            primary_kw = keywords[0]
            kw_kwargs = {
                "where_document": {"$contains": primary_kw},
                "limit": n,
                "include": ["documents", "metadatas"]
            }
            if where_clause:
                kw_kwargs["where"] = where_clause
                
            try:
                kw_results = collection.get(**kw_kwargs)
                if kw_results and "documents" in kw_results and kw_results["documents"]:
                    kw_docs = kw_results["documents"]
                    kw_metas = kw_results["metadatas"]
                    kw_ids = kw_results["ids"]
                    
                    for doc, meta, doc_id in zip(kw_docs, kw_metas, kw_ids):
                        # Calculate simple keyword matching frequency score
                        match_count = sum(1 for kw in keywords if kw in doc.lower())
                        score = 0.5 + (0.1 * match_count) # Base score for keyword match
                        keyword_hits.append({
                            "id": doc_id,
                            "text": doc,
                            "meta": meta,
                            "score": min(0.9, score),
                            "type": "keyword"
                        })
            except Exception as e:
                print(f"[WARN] Keyword fallback search failed: {e}")
                
            # Merge and deduplicate, preferring higher score
            merged = {h["id"]: h for h in vector_hits}
            for kh in keyword_hits:
                if kh["id"] not in merged or merged[kh["id"]]["score"] < kh["score"]:
                    merged[kh["id"]] = kh
                    
            # Sort by score descending and return top n
            results_list = list(merged.values())
            results_list.sort(key=lambda x: x["score"], reverse=True)
            return results_list[:n]

    # Return vector hits sorted by similarity score
    vector_hits.sort(key=lambda x: x["score"], reverse=True)
    return vector_hits[:n]
