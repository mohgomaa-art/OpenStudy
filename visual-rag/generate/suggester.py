import os
import config
from .router import route

def suggest(query: str, retrieved_chunks: list[dict]) -> dict:
    """
    Given a query and retrieved chunks, returns a recommendation,
    rationale, and alternative templates.
    """
    recommended, rationale = route(query, retrieved_chunks)
    
    # Dynamically scan the templates directory for directories and HTML files
    all_templates = []
    template_dir = getattr(config, "TEMPLATE_DIR", "visual-rag/templates")
    if os.path.exists(template_dir):
        for name in os.listdir(template_dir):
            if name.startswith("_") or name.startswith("."):
                continue
            path = os.path.join(template_dir, name)
            if os.path.isdir(path):
                all_templates.append(name)
            elif name.endswith(".html"):
                all_templates.append(name[:-5])
                
    # Fallback list if directory is empty or missing
    if not all_templates:
        all_templates = [
            "mind_map", "flashcard", "flowchart", 
            "comparison_table", "timeline", 
            "ddx_matrix", "cycle_diagram", "drag_drop"
        ]
        
    # Ensure list is unique and sorted
    all_templates = sorted(list(set(all_templates)))
    
    alternatives = [t for t in all_templates if t != recommended]
    
    return {
        "recommended": recommended,
        "rationale": rationale,
        "alternatives": alternatives[:3]
    }
