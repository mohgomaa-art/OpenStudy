import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gemini_client
import config

SCHEMAS = {
    "mind_map": {
        "template": "mind_map",
        "title": "str (e.g. 'Heart Failure Pathophysiology')",
        "center": "str (central topic, e.g. 'Heart Failure')",
        "branches": [
            {
                "label": "str (e.g. 'Left-sided', 'Right-sided')",
                "color": "purple|teal|coral|blue|amber (select one)",
                "children": ["str (sub-concept 1)", "str (sub-concept 2)"]
            }
        ]
    },

    "flashcard": {
        "template": "flashcard",
        "title": "str (topic of cards)",
        "cards": [
            {"front": "str (question/term)", "back": "str (answer/explanation)", "tag": "str (sub-topic/category)"}
        ]
    },

    "flowchart": {
        "template": "flowchart",
        "title": "str (algorithm title)",
        "steps": [
            {
                "id": "int (1-based index)",
                "label": "str (action/question)",
                "sublabel": "str (extra context, or empty string)",
                "next": "int|null (id of next step, or null if end)",
                "type": "step|decision|outcome (select one)"
            }
        ]
    },

    "timeline": {
        "template": "timeline",
        "title": "str (timeline title)",
        "events": [
            {
                "time": "str (stage/phase/time marker)",
                "label": "str (event/landmark)",
                "detail": "str (detailed description)",
                "color": "purple|teal|coral|blue|amber (select one)"
            }
        ]
    },

    "comparison_table": {
        "template": "comparison_table",
        "title": "str (comparison title)",
        "items": ["str (row names)"],
        "criteria": ["str (column headers)"],
        "data": {
            "item_name": {
                "criterion": "str (value)"
            }
        }
    },

    "ddx_matrix": {
        "template": "ddx_matrix",
        "title": "str (differential diagnosis title)",
        "symptoms": ["str (symptom 1)"],
        "diseases": ["str (disease 1)"],
        "matrix": {
            "disease_name": {
                "symptom_name": "present|absent|variable (select one)"
            }
        }
    },

    "cycle_diagram": {
        "template": "cycle_diagram",
        "title": "str (cycle name)",
        "steps": [
            {
                "label": "str (step title)",
                "detail": "str (step details)"
            }
        ]
    },

    "drag_drop": {
        "template": "drag_drop",
        "title": "str (matching exercise title)",
        "description": "str (instructions)",
        "categories": ["str (bucket names)"],
        "items": [
            {
                "id": "int (1-based index)",
                "text": "str (term/fact to drag)",
                "category": "str (must match one of the categories exactly)"
            }
        ]
    }
}


def _trim_context(context: str) -> str:
    """Trim context to MAX_CONTEXT_CHARS to keep prompts fast."""
    limit = getattr(config, "MAX_CONTEXT_CHARS", 1200)
    if len(context) > limit:
        return context[:limit] + "\n[...truncated for brevity]"
    return context


def generate_visual_json(context: str, visual_type: str) -> str:
    """
    Sends trimmed context to Ollama and requests structured JSON.
    Uses tight num_predict budget to cap output length and dramatically
    reduce latency.
    """
    schema = SCHEMAS.get(visual_type, SCHEMAS["mind_map"])
    trimmed = _trim_context(context)

    # Minimal, focused prompt — no verbose explanations
    prompt = f"""Convert the study content below into a {visual_type} JSON.

CONTENT:
\"\"\"
{trimmed}
\"\"\"

Return ONLY valid JSON matching this schema exactly:
{json.dumps(schema, indent=2)}

Rules: mandatory fields only, max 8 items per list, no markdown fences.
Start with {{"""

    response_text = gemini_client.generate_json(prompt)
    return response_text
