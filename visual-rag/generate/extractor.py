import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gemini_client
import config
from .prompter import generate_visual_json, SCHEMAS

def validate_schema(data: dict, visual_type: str) -> tuple[bool, str]:
    """
    Validates if the dictionary conforms to the schema required for the visual_type.
    Returns (True, "") or (False, "error message").
    """
    if not isinstance(data, dict):
        return False, "Root elements must be a JSON object (dictionary)."
        
    template = data.get("template")
    if template != visual_type:
        return False, f"Expected template to be '{visual_type}', got '{template}'."
        
    title = data.get("title")
    if not title or not isinstance(title, str):
        return False, "Missing or invalid 'title' string."

    if visual_type == "mind_map":
        center = data.get("center")
        if not center or not isinstance(center, str):
            return False, "Missing or invalid 'center' string."
            
        branches = data.get("branches")
        if not isinstance(branches, list) or not branches:
            return False, "'branches' must be a non-empty list."
            
        for idx, branch in enumerate(branches):
            if not isinstance(branch, dict):
                return False, f"Branch at index {idx} must be an object."
            if "label" not in branch or not isinstance(branch["label"], str):
                return False, f"Branch at index {idx} missing or invalid 'label'."
            if "children" not in branch or not isinstance(branch["children"], list):
                return False, f"Branch at index {idx} missing or invalid 'children' list."
            color = branch.get("color")
            if color not in ("purple", "teal", "coral", "blue", "amber"):
                return False, f"Branch at index {idx} has invalid color '{color}'. Must be purple, teal, coral, blue, or amber."

    elif visual_type == "flashcard":
        cards = data.get("cards")
        if not isinstance(cards, list) or not cards:
            return False, "'cards' must be a non-empty list."
            
        for idx, card in enumerate(cards):
            if not isinstance(card, dict):
                return False, f"Card at index {idx} must be an object."
            if "front" not in card or not isinstance(card["front"], str):
                return False, f"Card at index {idx} missing or invalid 'front' string."
            if "back" not in card or not isinstance(card["back"], str):
                return False, f"Card at index {idx} missing or invalid 'back' string."
            if "tag" not in card or not isinstance(card["tag"], str):
                return False, f"Card at index {idx} missing or invalid 'tag' string."

    elif visual_type == "flowchart":
        steps = data.get("steps")
        if not isinstance(steps, list) or not steps:
            return False, "'steps' must be a non-empty list."
            
        step_ids = set()
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                return False, f"Step at index {idx} must be an object."
            if "id" not in step or not isinstance(step["id"], int):
                return False, f"Step at index {idx} missing or invalid 'id' integer."
            if "label" not in step or not isinstance(step["label"], str):
                return False, f"Step at index {idx} missing or invalid 'label' string."
            if "type" not in step or step["type"] not in ("step", "decision", "outcome"):
                return False, f"Step at index {idx} has invalid type '{step.get('type')}'. Must be step, decision, or outcome."
            step_ids.add(step["id"])
            
        for idx, step in enumerate(steps):
            nxt = step.get("next")
            if nxt is not None and not isinstance(nxt, int):
                return False, f"Step at index {idx} 'next' field must be an integer or null."
            if nxt is not None and nxt not in step_ids:
                return False, f"Step at index {idx} 'next' field references non-existent step id {nxt}."

    elif visual_type == "timeline":
        events = data.get("events")
        if not isinstance(events, list) or not events:
            return False, "'events' must be a non-empty list."
            
        for idx, event in enumerate(events):
            if not isinstance(event, dict):
                return False, f"Event at index {idx} must be an object."
            if "time" not in event or not isinstance(event["time"], str):
                return False, f"Event at index {idx} missing or invalid 'time' string."
            if "label" not in event or not isinstance(event["label"], str):
                return False, f"Event at index {idx} missing or invalid 'label' string."
            if "detail" not in event or not isinstance(event["detail"], str):
                return False, f"Event at index {idx} missing or invalid 'detail' string."

    elif visual_type == "comparison_table":
        items = data.get("items")
        criteria = data.get("criteria")
        comp_data = data.get("data")
        
        if not isinstance(items, list) or not items:
            return False, "'items' must be a non-empty list."
        if not isinstance(criteria, list) or not criteria:
            return False, "'criteria' must be a non-empty list."
        if not isinstance(comp_data, dict):
            return False, "'data' must be a dictionary mapping row items."
            
        for row in items:
            if row not in comp_data:
                return False, f"Row item '{row}' missing from 'data' mapping."
            if not isinstance(comp_data[row], dict):
                return False, f"Data mapping for '{row}' must be a dictionary."
            for col in criteria:
                if col not in comp_data[row]:
                    return False, f"Criterion value '{col}' missing from data row '{row}'."

    elif visual_type == "ddx_matrix":
        symptoms = data.get("symptoms")
        diseases = data.get("diseases")
        matrix = data.get("matrix")
        
        if not isinstance(symptoms, list) or not symptoms:
            return False, "'symptoms' must be a non-empty list."
        if not isinstance(diseases, list) or not diseases:
            return False, "'diseases' must be a non-empty list."
        if not isinstance(matrix, dict):
            return False, "'matrix' must be a dictionary mapping diseases."
            
        for d in diseases:
            if d not in matrix:
                return False, f"Disease '{d}' missing from 'matrix' mapping."
            if not isinstance(matrix[d], dict):
                return False, f"Matrix mapping for '{d}' must be a dictionary."
            for s in symptoms:
                val = matrix[d].get(s)
                if val not in ("present", "absent", "variable"):
                    return False, f"Symptom check '{s}' for disease '{d}' must be 'present', 'absent', or 'variable'. Got '{val}'."

    elif visual_type == "cycle_diagram":
        steps = data.get("steps")
        if not isinstance(steps, list) or not steps:
            return False, "'steps' must be a non-empty list."
            
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                return False, f"Step at index {idx} must be an object."
            if "label" not in step or not isinstance(step["label"], str):
                return False, f"Step at index {idx} missing or invalid 'label' string."
            if "detail" not in step or not isinstance(step["detail"], str):
                return False, f"Step at index {idx} missing or invalid 'detail' string."

    elif visual_type == "drag_drop":
        desc = data.get("description")
        if not desc or not isinstance(desc, str):
            return False, "Missing or invalid 'description' string."
        cats = data.get("categories")
        if not isinstance(cats, list) or not cats:
            return False, "'categories' must be a non-empty list of bucket names."
        items = data.get("items")
        if not isinstance(items, list) or not items:
            return False, "'items' must be a non-empty list of draggable items."
            
        cat_set = set(cats)
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                return False, f"Item at index {idx} must be an object."
            if "id" not in item or not isinstance(item["id"], int):
                return False, f"Item at index {idx} missing or invalid 'id' integer."
            if "text" not in item or not isinstance(item["text"], str):
                return False, f"Item at index {idx} missing or invalid 'text' string."
            cat = item.get("category")
            if cat not in cat_set:
                return False, f"Item at index {idx} category '{cat}' must match one of the categories: {cats}."

    return True, ""

def extract_visual_json(context: str, visual_type: str, max_retries: int = 3) -> dict:
    """
    Calls the prompter, parses the JSON, and runs schema validation.
    If validation fails, it triggers a correction loop up to max_retries.
    """
    raw_response = generate_visual_json(context, visual_type)
    
    for attempt in range(max_retries + 1):
        try:
            # Locate first '{' and last '}' to strip extra text if LLM hallucinated wrapper text
            start = raw_response.find("{")
            end = raw_response.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("Response does not contain a JSON object.")
                
            clean_json = raw_response[start:end+1]
            data = json.loads(clean_json)
            
            # Validate schema
            success, err_msg = validate_schema(data, visual_type)
            if success:
                return data
                
            print(f"[Extractor] Validation error on attempt {attempt}: {err_msg}")
            if attempt == max_retries:
                raise ValueError(f"Schema validation failed: {err_msg}")
                
        except Exception as e:
            err_msg = str(e)
            print(f"[Extractor] Parsing error on attempt {attempt}: {err_msg}")
            if attempt == max_retries:
                raise ValueError(f"JSON extraction failed: {err_msg}")

        # Corrective prompt retry
        print(f"[Extractor] Retrying generation (Attempt {attempt+1}/{max_retries})...")
        schema = SCHEMAS.get(visual_type)
        retry_prompt = f"""You previously returned an invalid JSON response.
Here is the error encountered:
{err_msg}

Please correct your output.
Ensure you return ONLY valid JSON conforming strictly to the requested schema:
{json.dumps(schema, indent=2)}

Do NOT wrap inside markdown block code fences or include explanations. Begin directly with {{.

INVALID RESPONSE:
{raw_response}

CORRECTED JSON:"""

        try:
            raw_response = gemini_client.generate_json(retry_prompt)
        except Exception as rex:
            print(f"[WARN] Correction request failed: {rex}")
            
    raise ValueError("Failed to extract valid JSON after retries.")
