import os
import json
from pathlib import Path
import config

# SUBJECT_PALETTES has been replaced by the CSS-variable runtime theme system.

def detect_subject(visual_json: dict) -> str:
    subject = visual_json.get("subject", "").lower()
    valid_subjects = ["pharmacology", "cardiology", "physiology", "obgyn", "emergency", "neurology"]
    if subject in valid_subjects:
        return subject
        
    # Check text fields for auto-detection
    text_to_check = (
        visual_json.get("title", "") + " " + 
        visual_json.get("topic", "") + " " + 
        visual_json.get("query", "") + " " +
        visual_json.get("center", "")
    ).lower()
    
    if any(w in text_to_check for w in ["heart", "cardio", "valvular", "murmur", "artery", "cardiology", "ecg", "ekg", "ventricle", "atrial", "coronary", "blood pressure", "aorta", "myocardial"]):
        return "cardiology"
    elif any(w in text_to_check for w in ["brain", "neuro", "neurology", "nerve", "stroke", "cerebral", "synapse", "cognitive", "dementia", "reflex", "cortex", "neural", "spinal"]):
        return "neurology"
    elif any(w in text_to_check for w in ["drug", "pharm", "pharmacology", "dose", "dosing", "treatment", "medication", "agonist", "antagonist", "absorption", "pharmacokinetics", "toxin", "toxicology", "prescription"]):
        return "pharmacology"
    elif any(w in text_to_check for w in ["pregnancy", "uterus", "fetal", "maternal", "contraceptive", "gynecology", "obstetrics", "obgyn", "menstrual"]):
        return "obgyn"
    elif any(w in text_to_check for w in ["emergency", "trauma", "triage", "acls", "shock", "cpr", "resuscitation"]):
        return "emergency"
    elif any(w in text_to_check for w in ["physiology", "homeostasis", "metabolism", "renal", "pulmonary", "endocrine", "hormone", "digestive", "kidney", "lung"]):
        return "physiology"
        
    return "default"

def choose_variant(visual_json: dict) -> str:
    template_name = visual_json.get("template")
    
    if template_name == "timeline":
        events = visual_json.get("events", [])
        if len(events) > 8:
            return "vertical_feed"
        title_topic = (visual_json.get("title", "") + " " + visual_json.get("topic", "")).lower()
        if any(w in title_topic for w in ["branch", "parallel", "track", "vs", "versus", "maternal", "fetal"]):
            return "branching"
        return "horizontal_scroll"
        
    elif template_name == "mind_map":
        branches = visual_json.get("branches", [])
        total_children = sum(len(b.get("children", [])) for b in branches if isinstance(b, dict))
        if len(branches) > 6 or total_children > 15:
            return "bubble_cluster"
        title_topic = (visual_json.get("title", "") + " " + visual_json.get("topic", "")).lower()
        if any(w in title_topic for w in ["hierarchy", "org", "classification", "tree"]):
            return "horizontal_tree"
        return "radial"
        
    elif template_name == "flashcard":
        cards = visual_json.get("cards", [])
        if len(cards) > 6:
            return "peek"
        title_hash = hash(visual_json.get("title", ""))
        return "slide_reveal" if title_hash % 2 == 0 else "flip_3d"
        
    elif template_name in ["comparison_table", "ddx_matrix"]:
        items = visual_json.get("items", [])
        if template_name == "comparison_table" and 2 <= len(items) <= 3:
            return "venn"
        criteria = visual_json.get("criteria", [])
        if len(criteria) > 5 or len(items) > 4:
            return "stacked_cards"
        return "grid"
        
    elif template_name in ["flowchart", "pathophysiology_flow"]:
        title_topic = (visual_json.get("title", "") + " " + visual_json.get("topic", "")).lower()
        if any(w in title_topic for w in ["compare", "pathway", "side by side", "swimlane"]):
            return "swimlane"
        if any(w in title_topic for w in ["left to right", "horizontal", "lr"]):
            return "left_right"
        return "top_down"
        
    return "default"

def render(visual_json: dict, output_path: str = None) -> str:
    """
    Renders the structured visual JSON data into a fully interactive HTML file.
    Combines templates/_base.html with the selected template component or variant.
    """
    template_name = visual_json.get("template")
    if not template_name:
        raise ValueError("JSON data must specify a 'template' name.")
        
    # 1. Determine variant
    variant = visual_json.get("variant")
    if not variant:
        variant = choose_variant(visual_json)
        visual_json["variant"] = variant
        
    base_file = Path(config.TEMPLATE_DIR) / "_base.html"
    
    # 2. Locate template file (directory structure first, fallback to flat file)
    dir_path = Path(config.TEMPLATE_DIR) / template_name
    template_file = None
    if dir_path.is_dir():
        variant_file = dir_path / f"{variant}.html"
        if variant_file.exists():
            template_file = variant_file
        else:
            template_file = dir_path / "default.html"
            
    if not template_file or not template_file.exists():
        template_file = Path(config.TEMPLATE_DIR) / f"{template_name}.html"
        
    if not base_file.exists():
        raise FileNotFoundError(f"Base HTML file not found at {base_file}")
    if not template_file.exists():
        raise FileNotFoundError(f"Template HTML file not found at {template_file}")
        
    # Read files
    base_html = base_file.read_text(encoding="utf-8")
    template_content = template_file.read_text(encoding="utf-8")
    
    # Parse template components (sequential parsing by markers)
    parts = {"head": "", "body": "", "script": ""}
    current_part = None
    current_lines = []
    
    for line in template_content.splitlines():
        if "<!-- HEAD -->" in line:
            if current_part:
                parts[current_part] = "\n".join(current_lines)
            current_part = "head"
            current_lines = []
        elif "<!-- BODY -->" in line:
            if current_part:
                parts[current_part] = "\n".join(current_lines)
            current_part = "body"
            current_lines = []
        elif "<!-- SCRIPT -->" in line:
            if current_part:
                parts[current_part] = "\n".join(current_lines)
            current_part = "script"
            current_lines = []
        else:
            current_lines.append(line)
            
    if current_part:
        parts[current_part] = "\n".join(current_lines)
        
    # Stitch everything together into the base HTML template
    html = base_html
    
    title = visual_json.get("title", "Study Aid")
    template_name_clean = template_name.replace("_", " ").title()
    variant_clean = variant.replace("_", " ").title()
    window_title = f"OpenStudy — Visualizer: {template_name_clean} ({variant_clean}) · {title}"
    html = html.replace("{{TITLE}}", window_title)
    
    html = html.replace("<!-- TEMPLATE_HEAD -->", parts.get("head", ""))
    html = html.replace("<!-- TEMPLATE_BODY -->", parts.get("body", ""))
    html = html.replace("<!-- TEMPLATE_SCRIPT -->", parts.get("script", ""))
    
    # Inject dataset as a global Javascript constant
    data_script = f"<script>\nconst VISUAL_DATA = {json.dumps(visual_json, indent=2)};\n</script>"
    html = html.replace("<!-- DATA_INJECT -->", data_script)
    
    # 3. Determine and apply visual theme
    settings_path = Path(config.BASE_DIR).parent / "data" / "settings.json"
    user_theme = "auto"
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                user_theme = json.load(f).get("visual_theme", "auto")
        except Exception:
            pass

    valid_themes = {"clinical", "nightshift", "botanica", "bloom", "solstice", "arcane"}
    
    if user_theme in valid_themes:
        selected_theme = user_theme
    else:
        # Fallback to subject-mapping suggestion
        SUBJECT_THEME_HINTS = {
            "pharmacology": "botanica",
            "cardiology":   "clinical",
            "physiology":   "clinical",
            "obgyn":        "bloom",
            "emergency":    "solstice",
            "neurology":    "nightshift",
        }
        subj = detect_subject(visual_json)
        selected_theme = SUBJECT_THEME_HINTS.get(subj, "clinical")
        
    html = html.replace("{{THEME}}", selected_theme)
    
    # Determine output file path
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        
    if not output_path:
        # Generate safe title filename
        safe_title = "".join([c if c.isalnum() else "_" for c in title.replace(" ", "_")])[:30]
        out_file = os.path.join(config.OUTPUT_DIR, f"{safe_title}_{template_name}.html")
    else:
        out_file = output_path
        
    # Write output
    Path(out_file).write_text(html, encoding="utf-8")
    
    return out_file
