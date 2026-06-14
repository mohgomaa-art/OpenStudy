from collections import Counter

# Candidate arrays mapping dominant knowledge types to multiple template options
TYPE_TO_TEMPLATES = {
    "concept":    ["flashcard", "mnemonic_card", "cloze_passage"],
    "process":    ["flowchart", "sequence_builder", "pathophysiology_flow"],
    "comparison": ["comparison_table", "ddx_matrix"],
    "timeline":   ["timeline"],
    "cause":      ["mind_map", "concept_tree"],
    "mixed":      ["mind_map", "summary_sheet"],
}

def route(query: str, retrieved_chunks: list[dict], recent_for_source: list[str] = None) -> tuple[str, str]:
    """
    Given student query, retrieved chunks containing knowledge_type metadata,
    and a list of recently used templates for the source, returns (template_name, rationale_string).
    """
    q = query.lower()
    
    # Explicit interactive overrides (takes absolute priority as user explicitly requested them)
    if any(k in q for k in ("summary", "cheat sheet", "bullet points", "high yield", "facts")):
        return "summary_sheet", "User requested high-yield summary cheat sheet."

    if any(k in q for k in ("mnemonic", "acronym", "memory hook")):
        return "mnemonic_card", "User requested acronym mnemonic card."

    if any(k in q for k in ("vignette", "case study", "patient", "clinical case", "reasoning", "scenario")):
        return "clinical_vignette", "User requested interactive patient clinical case study vignette."

    if any(k in q for k in ("boss", "battle", "fight", "rpg", "mcq game", "monster")):
        return "boss_battle", "User requested interactive RPG boss battle MCQ game."

    if any(k in q for k in ("wordle", "vocabulary", "word guess", "terminology")):
        return "wordle_game", "User requested medical Wordle vocabulary game."

    if any(k in q for k in ("sequence", "order", "step-by-step", "chronological", "pathway steps")):
        return "sequence_builder", "User requested interactive sequence builder."

    if any(k in q for k in ("game", "quiz", "match", "drag", "drop")):
        return "drag_drop", "User requested active recall matching game."
        
    if any(k in q for k in ("ddx", "differential", "symptom grid")):
        return "ddx_matrix", "Differential diagnosis keyword override."

    if any(k in q for k in ("pathophysiology", "cascade", "pathogenesis", "etiology", "insult")):
        return "pathophysiology_flow", "User requested disease pathophysiology cascade flow."

    if any(k in q for k in ("anatomy", "cross section", "layer", "structure of", "wall of")):
        return "anatomy_cross_section", "User requested interactive anatomical cross section."

    if any(k in q for k in ("tree", "hierarchy", "structure", "classification", "taxonomy")):
        return "concept_tree", "User requested hierarchical concept tree."

    if any(k in q for k in ("mcq", "multiple choice", "sba", "single best", "question")):
        return "mcq_single_best", "User requested multiple choice question quiz."

    if any(k in q for k in ("true false", "t/f", "streak", "fact check", "statement speedrun")):
        return "true_false_streak", "User requested True/False streak speedrun game."
        
    if not retrieved_chunks:
        return "mind_map", "No documents found. Defaulting to mind map."

    # Tally the knowledge types
    types = []
    for c in retrieved_chunks:
        meta = c.get("meta", {})
        k_type = str(meta.get("knowledge_type", "mixed")).lower()
        
        # Clean any raw class prefixes like "knowledgetype.concept"
        if "knowledgetype." in k_type:
            k_type = k_type.split(".")[-1]
            
        types.append(k_type)
        
    counts = Counter(types)
    dominant, count = counts.most_common(1)[0]
    
    candidates = TYPE_TO_TEMPLATES.get(dominant, ["mind_map"])
    recent_for_source = recent_for_source or []
    
    # Filter candidates to prefer one not recently generated
    fresh = [t for t in candidates if t not in recent_for_source]
    template = (fresh or candidates)[0]
    
    # Sub-rule refinement for process loops
    if template in ["flowchart", "sequence_builder", "pathophysiology_flow"] and any(k in q or k in str(retrieved_chunks).lower() for k in ("cycle", "loop", "krebs", "raas")):
        template = "cycle_diagram"
        return template, f"Dominant type is '{dominant}' ({count}/{len(retrieved_chunks)}), refined to cycle diagram due to loop terminology."

    # Sub-rule refinement for ddx matrices
    if template in ["comparison_table", "ddx_matrix"] and any(k in q for k in ("symptom", "disease", "matrix")):
        template = "ddx_matrix"
        return template, f"Dominant type is '{dominant}' ({count}/{len(retrieved_chunks)}), refined to DDX matrix due to symptom/disease comparison."

    rationale = f"Dominant knowledge type is '{dominant}' ({count}/{len(retrieved_chunks)} chunks). Selected template '{template}' with rotation."
    return template, rationale
