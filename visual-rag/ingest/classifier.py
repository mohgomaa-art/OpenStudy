from enum import Enum
import json
from pydantic import BaseModel
from tqdm import tqdm
import config
import gemini_client

class KnowledgeType(str, Enum):
    CONCEPT    = "concept"     # definition, what-is, anatomy overview
    PROCESS    = "process"     # steps, sequence, algorithm, pathway
    COMPARISON = "comparison"  # vs, differences, table comparison
    TIMELINE   = "timeline"    # stages, phases, history
    CAUSE      = "cause"       # pathophysiology, etiology, mechanism
    MIXED      = "mixed"       # fallback

class ChunkClassification(BaseModel):
    knowledge_type: KnowledgeType
    concept_name:   str
    key_entities:   list[str]

class ClassifiedChunk(BaseModel):
    text:           str
    knowledge_type: KnowledgeType
    concept_name:   str
    key_entities:   list[str]
    source:         str
    page:           int
    section:        str

def get_active_model() -> str:
    """Mock/Fallback function to maintain backward compatibility if imported elsewhere."""
    return getattr(config, "GEMINI_MODEL", "gemini-2.0-flash")

import re

def classify_chunk(chunk: dict) -> ClassifiedChunk:
    """Classifies a single chunk into cognitive knowledge type locally to avoid API rate limiting."""
    text = chunk["text"]
    text_lower = text.lower()
    
    # 1. Heuristic for Knowledge Type
    k_type = "mixed"
    if any(w in text_lower for w in [" vs ", "versus", "compared to", "comparison", "difference between", "contrasted with"]):
        k_type = "comparison"
    elif any(w in text_lower for w in ["pathophysiology", "etiology", "leads to", "cause of", "mechanism", "resulting in", "due to"]):
        k_type = "cause"
    elif any(w in text_lower for w in ["timeline", "chronology", "stages of", "history of", "years", "century"]):
        k_type = "timeline"
    elif any(w in text_lower for w in ["step ", "stage ", "phase ", "then ", "next ", "after that", "procedure", "flowchart"]):
        k_type = "process"
    elif any(w in text_lower for w in ["is defined as", "definition", "refer to", "anatomy", "overview", "structure"]):
        k_type = "concept"
        
    # 2. Extract concept name: use the active section name from the parser
    concept_name = chunk.get("section", "General")
    if len(concept_name) > 60:
        concept_name = concept_name[:60] + "..."
        
    # 3. Extract key entities: extract capitalized phrases as a simple heuristic
    entities = re.findall(r'\b[A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,})*\b', text)
    stop_words = {"The", "And", "For", "This", "That", "With", "From", "Here", "There", "When", "What", "Who", "How", "Why"}
    filtered_entities = []
    seen = set()
    for ent in entities:
        if ent not in seen and ent not in stop_words:
            seen.add(ent)
            filtered_entities.append(ent)
            
    key_entities = filtered_entities[:5]
    
    return ClassifiedChunk(
        text=text,
        knowledge_type=KnowledgeType(k_type),
        concept_name=concept_name,
        key_entities=key_entities,
        source=chunk["source"],
        page=chunk["page"],
        section=chunk["section"]
    )

def classify_batch(chunks: list[dict]) -> list[ClassifiedChunk]:
    """Classifies chunks sequentially and rapidly using the local heuristic classifier."""
    print(f"[Classifier] Local fast classification of {len(chunks)} chunks...")
    results = []
    for chunk in chunks:
        results.append(classify_chunk(chunk))
    print("[Classifier] Completed fast classification.")
    return results
