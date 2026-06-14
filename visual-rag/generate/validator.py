import json
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field, ValidationError
import config
import gemini_client

# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class Branch(BaseModel):
    label: str
    color: Literal["purple", "teal", "coral", "blue", "amber"]
    children: List[str]

class MindMapSchema(BaseModel):
    template: Literal["mind_map"] = "mind_map"
    title: str
    center: str
    branches: List[Branch]

class Card(BaseModel):
    front: str
    back: str
    tag: str
    difficulty: Optional[Literal["easy", "medium", "hard"]] = "medium"

class FlashcardSchema(BaseModel):
    template: Literal["flashcard"] = "flashcard"
    title: str
    cards: List[Card]

class Step(BaseModel):
    id: int
    label: str
    sublabel: str
    next: Optional[int] = None
    type: Literal["step", "decision", "outcome"]

class FlowchartSchema(BaseModel):
    template: Literal["flowchart"] = "flowchart"
    title: str
    steps: List[Step]

class TimelineEvent(BaseModel):
    time: str
    label: str
    detail: str
    color: Optional[Literal["purple", "teal", "coral", "blue", "amber"]] = "purple"

class TimelineSchema(BaseModel):
    template: Literal["timeline"] = "timeline"
    title: str
    events: List[TimelineEvent]

class ComparisonSchema(BaseModel):
    template: Literal["comparison_table"] = "comparison_table"
    title: str
    items: List[str]
    criteria: List[str]
    data: Dict[str, Dict[str, str]]

class DdxMatrixSchema(BaseModel):
    template: Literal["ddx_matrix"] = "ddx_matrix"
    title: str
    symptoms: List[str]
    diseases: List[str]
    matrix: Dict[str, Dict[str, Literal["present", "absent", "variable"]]]

class CycleStep(BaseModel):
    label: str
    detail: str

class CycleDiagramSchema(BaseModel):
    template: Literal["cycle_diagram"] = "cycle_diagram"
    title: str
    steps: List[CycleStep]

class DragDropItem(BaseModel):
    id: int
    text: str
    category: str

class DragDropSchema(BaseModel):
    template: Literal["drag_drop"] = "drag_drop"
    title: str
    description: str
    categories: List[str]
    items: List[DragDropItem]

class SequenceStep(BaseModel):
    id: int
    text: str

class SequenceBuilderSchema(BaseModel):
    template: Literal["sequence_builder"] = "sequence_builder"
    title: str
    steps: List[SequenceStep]

class WordleWord(BaseModel):
    word: str = Field(..., description="The medical/scientific word to guess, in uppercase. Must be between 3 and 10 characters.")
    hint: str = Field(..., description="A clear, educational definition or clue describing the word.")
    category: str = Field("General", description="The sub-topic or medical category of the word.")

class WordleGameSchema(BaseModel):
    template: Literal["wordle_game"] = "wordle_game"
    title: str
    words: List[WordleWord]

class BattleQuestion(BaseModel):
    question: str
    options: List[str] = Field(..., description="Exactly 4 options to choose from.")
    answer: str = Field(..., description="The correct option string. Must match one of the options exactly.")
    explanation: str = Field(..., description="Detailed explanation of the correct choice.")

class BossBattleSchema(BaseModel):
    template: Literal["boss_battle"] = "boss_battle"
    title: str
    boss_name: str = Field(..., description="A creative name for the boss matching the theme (e.g. 'Dr. Acidosis', 'The Keto-Monster').")
    questions: List[BattleQuestion]

class PatientProfile(BaseModel):
    demographics: str = Field(..., description="Age, gender, and basic background (e.g. '54-year-old female').")
    presentation: str = Field(..., description="History of present illness and chief complaints.")
    vitals: str = Field(..., description="Vitals signs (BP, HR, RR, Temp, O2 sat).")
    exam: str = Field(..., description="Physical exam findings or relevant lab tests.")

class VignetteQuestion(BaseModel):
    stage: int = Field(..., description="The sequence stage number (1, 2, 3, etc.).")
    question: str = Field(..., description="The clinical question for this stage.")
    options: List[str] = Field(..., description="Exactly 4 clinical choice options.")
    answer: str = Field(..., description="The correct choice. Must match one of the options exactly.")
    rationale: str = Field(..., description="Detailed clinical reasoning explaining the correct option and ruling out distractors.")

class ClinicalVignetteSchema(BaseModel):
    template: Literal["clinical_vignette"] = "clinical_vignette"
    title: str
    patient_profile: PatientProfile
    questions: List[VignetteQuestion]

class SummarySection(BaseModel):
    heading: str
    summary: str
    bullets: List[str]

class SummarySheetSchema(BaseModel):
    template: Literal["summary_sheet"] = "summary_sheet"
    title: str
    sections: List[SummarySection]

class MnemonicItem(BaseModel):
    letter: str = Field(..., description="A single uppercase letter of the acronym.")
    concept: str = Field(..., description="The clinical term/concept this letter stands for.")
    detail: str = Field(..., description="Detailed definition or clinical significance.")

class MnemonicCardSchema(BaseModel):
    template: Literal["mnemonic_card"] = "mnemonic_card"
    title: str
    mnemonic: str = Field(..., description="The full acronym word in uppercase (e.g. 'MONA', 'AEIOU').")
    description: str = Field(..., description="Description of what this mnemonic represents.")
    items: List[MnemonicItem]

# New Pydantic models for Concept Tree, Pathophysiology Flow, Anatomy Cross-section
class ConceptNode(BaseModel):
    id: str = Field(..., description="Unique short string ID for the node, e.g. 'root', 'node_1'.")
    label: str = Field(..., description="The concept name or label.")
    detail: Optional[str] = Field(None, description="Detailed explanation shown on hover/click.")
    parent_id: Optional[str] = Field(None, description="ID of the parent node. Root node must have null parent.")
    color: Optional[Literal["purple", "teal", "coral", "blue", "amber"]] = "purple"

class ConceptTreeSchema(BaseModel):
    template: Literal["concept_tree"] = "concept_tree"
    title: str
    nodes: List[ConceptNode]

class PathoStep(BaseModel):
    stage: Literal["Trigger", "Mechanism", "Pathology", "Clinical"]
    title: str
    description: str
    key_mediators: Optional[List[str]] = Field(None, description="Key biological/chemical mediators, e.g., cytokines, hormones.")

class PathophysiologyFlowSchema(BaseModel):
    template: Literal["pathophysiology_flow"] = "pathophysiology_flow"
    title: str
    disease: str
    flow: List[PathoStep]

class AnatomyLayer(BaseModel):
    name: str = Field(..., description="Name of the layer or anatomical structure, e.g., 'Tunica Media'.")
    description: str = Field(..., description="Anatomical description.")
    function: str = Field(..., description="Normal physiological function.")
    clinical_notes: str = Field(..., description="Pathologies or clinical relevance associated with this layer.")
    components: List[str] = Field(..., description="Key structures/cells/fibers in this layer.")

class AnatomyCrossSectionSchema(BaseModel):
    template: Literal["anatomy_cross_section"] = "anatomy_cross_section"
    title: str
    organ_or_structure: str = Field(..., description="The anatomical structure name, e.g. 'Artery Wall', 'Skin Layer'.")
    layers: List[AnatomyLayer]

class MCQQuestion(BaseModel):
    question: str = Field(..., description="The multiple choice question query.")
    options: List[str] = Field(..., description="Exactly 4 options to choose from.")
    answer: str = Field(..., description="The correct option string. Must match one of the options exactly.")
    explanation: str = Field(..., description="Detailed explanation/rationale behind the correct choice.")

class MCQSingleBestSchema(BaseModel):
    template: Literal["mcq_single_best"] = "mcq_single_best"
    title: str
    questions: List[MCQQuestion]

class TFStatement(BaseModel):
    statement: str = Field(..., description="A clear scientific statement that is definitively True or False.")
    is_true: bool = Field(..., description="True if the statement is factually correct, False otherwise.")
    explanation: str = Field(..., description="Educational explanation explaining why it is True or False.")

class TrueFalseStreakSchema(BaseModel):
    template: Literal["true_false_streak"] = "true_false_streak"
    title: str
    statements: List[TFStatement]

class Hotspot(BaseModel):
    x: float = Field(..., description="X coordinate percentage (0-100)")
    y: float = Field(..., description="Y coordinate percentage (0-100)")
    label: str = Field(..., description="Name of the structure/hotspot")
    description: str = Field(..., description="Clinical or anatomical significance")

class HotspotImageSchema(BaseModel):
    template: Literal["hotspot_image"] = "hotspot_image"
    title: str
    image_path: str = Field(..., description="Name of the image file in the vault")
    hotspots: List[Hotspot]

class DrugDoseCalculatorSchema(BaseModel):
    template: Literal["drug_dose_calculator"] = "drug_dose_calculator"
    title: str
    drug_name: str
    indication: str
    recommended_dose: str = Field(..., description="Recommended dosage text, e.g. '5-8 mg/kg'")
    min_dose_mg_kg: float
    max_dose_mg_kg: float
    worked_example: str = Field(..., description="Worked step-by-step example calculation text")

class DecisionNode(BaseModel):
    id: int
    question_or_action: str
    options: Optional[List[str]] = None
    next_ids: Optional[Dict[str, int]] = None
    feedback: Optional[Dict[str, str]] = None
    is_terminal: bool = False

class DecisionAlgorithmSchema(BaseModel):
    template: Literal["decision_algorithm"] = "decision_algorithm"
    title: str
    start_node_id: int
    nodes: List[DecisionNode]

class LabItem(BaseModel):
    name: str
    value: float
    unit: str
    normal_min: float
    normal_max: float
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    clinical_significance: str

class LabValuePanelSchema(BaseModel):
    template: Literal["lab_value_panel"] = "lab_value_panel"
    title: str
    labs: List[LabItem]

class ClozePassageSchema(BaseModel):
    template: Literal["cloze_passage"] = "cloze_passage"
    title: str
    passage: str = Field(..., description="Passage text containing blanks formatted as [[1]], [[2]], etc.")
    blanks: Dict[str, str] = Field(..., description="Map of blank keys (e.g., '1', '2') to correct answers")
    word_bank: List[str] = Field(..., description="List of terms containing correct answers and distractors")

class HeatmapDataPoint(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD format date")
    value: int = Field(..., description="Score/study count")

class MasteryHeatmapSchema(BaseModel):
    template: Literal["mastery_heatmap"] = "mastery_heatmap"
    title: str
    subject: str
    data_points: List[HeatmapDataPoint]

class AudioQuestion(BaseModel):
    id: int
    audio_filename: str = Field(..., description="Audio file name in assets, e.g. 'murmur.mp3'")
    question: str
    options: List[str]
    answer: str
    explanation: str

class AudioIdQuizSchema(BaseModel):
    template: Literal["audio_id_quiz"] = "audio_id_quiz"
    title: str
    questions: List[AudioQuestion]

# Schema Registry
SCHEMAS = {
    "mind_map":         MindMapSchema,
    "flashcard":        FlashcardSchema,
    "flowchart":        FlowchartSchema,
    "comparison_table": ComparisonSchema,
    "timeline":         TimelineSchema,
    "ddx_matrix":       DdxMatrixSchema,
    "cycle_diagram":    CycleDiagramSchema,
    "drag_drop":        DragDropSchema,
    "sequence_builder": SequenceBuilderSchema,
    "wordle_game":      WordleGameSchema,
    "boss_battle":      BossBattleSchema,
    "clinical_vignette": ClinicalVignetteSchema,
    "summary_sheet":    SummarySheetSchema,
    "mnemonic_card":    MnemonicCardSchema,
    "concept_tree":     ConceptTreeSchema,
    "pathophysiology_flow": PathophysiologyFlowSchema,
    "anatomy_cross_section": AnatomyCrossSectionSchema,
    "mcq_single_best":   MCQSingleBestSchema,
    "true_false_streak": TrueFalseStreakSchema,
    "hotspot_image":         HotspotImageSchema,
    "drug_dose_calculator":  DrugDoseCalculatorSchema,
    "decision_algorithm":    DecisionAlgorithmSchema,
    "lab_value_panel":       LabValuePanelSchema,
    "cloze_passage":         ClozePassageSchema,
    "mastery_heatmap":       MasteryHeatmapSchema,
    "audio_id_quiz":         AudioIdQuizSchema
}

# Clean Mock Examples for prompt guidance (ADHD/1B-friendly)
MOCK_SCHEMAS = {
    "mind_map": {
        "template": "mind_map",
        "title": "Heart Failure Pathophysiology",
        "center": "Heart Failure",
        "branches": [
            {
                "label": "Left-Sided Failure",
                "color": "purple",
                "children": ["Pulmonary congestion", "Dyspnea on exertion", "Orthopnea"]
            }
        ]
    },
    "flashcard": {
        "template": "flashcard",
        "title": "Cardiology Definitions",
        "cards": [
            {
                "front": "Orthopnea",
                "back": "Difficulty breathing when lying flat, relieved by sitting up.",
                "tag": "Symptoms",
                "difficulty": "medium"
            }
        ]
    },
    "flowchart": {
        "template": "flowchart",
        "title": "Heart Failure Diagnosis Path",
        "steps": [
            {
                "id": 1,
                "label": "Measure BNP levels",
                "sublabel": "Normal is < 100 pg/mL",
                "next": 2,
                "type": "step"
            },
            {
                "id": 2,
                "label": "Is BNP elevated?",
                "sublabel": "Check threshold > 100",
                "next": None,
                "type": "decision"
            }
        ]
    },
    "timeline": {
        "template": "timeline",
        "title": "Course of Clinical Treatment",
        "events": [
            {
                "time": "Day 1",
                "label": "Initiate GDMT",
                "detail": "Start low-dose ACE inhibitor and Beta-blocker.",
                "color": "teal"
            }
        ]
    },
    "comparison_table": {
        "template": "comparison_table",
        "title": "Left vs Right Heart Failure",
        "items": ["Left-Sided", "Right-Sided"],
        "criteria": ["Primary Cause", "Key Symptoms"],
        "data": {
            "Left-Sided": {
                "Primary Cause": "Ischemic heart disease",
                "Key Symptoms": "Pulmonary congestion, dyspnea"
            },
            "Right-Sided": {
                "Primary Cause": "Left-sided heart failure",
                "Key Symptoms": "JVD, peripheral edema"
            }
        }
    },
    "ddx_matrix": {
        "template": "ddx_matrix",
        "title": "Cardiovascular Differentials",
        "symptoms": ["Dyspnea", "JVD", "Peripheral Edema"],
        "diseases": ["Left HF", "Right HF"],
        "matrix": {
            "Left HF": {
                "Dyspnea": "present",
                "JVD": "absent",
                "Peripheral Edema": "absent"
            },
            "Right HF": {
                "Dyspnea": "variable",
                "JVD": "present",
                "Peripheral Edema": "present"
            }
        }
    },
    "cycle_diagram": {
        "template": "cycle_diagram",
        "title": "RAAS Activation Loop",
        "steps": [
            {
                "label": "Renin Release",
                "detail": "Kidneys release renin in response to low renal blood pressure."
            },
            {
                "label": "Angiotensin conversion",
                "detail": "Renin converts angiotensinogen to Angiotensin I in blood."
            }
        ]
    },
    "drag_drop": {
        "template": "drag_drop",
        "title": "Symptom Classification",
        "description": "Drag the symptom into the correct heart failure column.",
        "categories": ["Left-Sided", "Right-Sided"],
        "items": [
            {
                "id": 1,
                "text": "Bilateral pulmonary crackles",
                "category": "Left-Sided"
            },
            {
                "id": 2,
                "text": "Jugular venous distention",
                "category": "Right-Sided"
            }
        ]
    },
    "sequence_builder": {
        "template": "sequence_builder",
        "title": "RAAS Activation Sequence",
        "steps": [
            {"id": 1, "text": "Low renal blood pressure triggers Renin release from kidneys."},
            {"id": 2, "text": "Renin cleaves circulating Angiotensinogen to form Angiotensin I."},
            {"id": 3, "text": "ACE in pulmonary capillaries converts Angiotensin I to Angiotensin II."},
            {"id": 4, "text": "Angiotensin II stimulates aldosterone release and system-wide vasoconstriction."}
        ]
    },
    "wordle_game": {
        "template": "wordle_game",
        "title": "Clinical Terminology Challenge",
        "words": [
            {
                "word": "DYSPNEA",
                "hint": "Difficult or labored breathing; shortness of breath.",
                "category": "Symptoms"
            },
            {
                "word": "RENIN",
                "hint": "An enzyme secreted by and stored in the kidneys which promotes blood pressure regulation.",
                "category": "Endocrine"
            }
        ]
    },
    "boss_battle": {
        "template": "boss_battle",
        "title": "Diabetes Mellitus Challenge",
        "boss_name": "Hyper-Glycemia",
        "questions": [
            {
                "question": "Which of the following insulin types is considered rapid-acting?",
                "options": ["Glargine", "Lispro", "Detemir", "NPH"],
                "answer": "Lispro",
                "explanation": "Lispro, Aspart, and Glulisine are rapid-acting insulins with an onset of 10-30 minutes."
            }
        ]
    },
    "clinical_vignette": {
        "template": "clinical_vignette",
        "title": "Shortness of Breath Case Study",
        "patient_profile": {
            "demographics": "65-year-old male",
            "presentation": "Presents with acute onset of shortness of breath and left-sided chest pain that worsens with deep inspiration. He recently returned from a 12-hour flight.",
            "vitals": "BP: 130/85 mmHg, HR: 110 bpm, RR: 24 bpm, Temp: 37.2C, O2 Sat: 91% on room air",
            "exam": "Tachycardia present, lungs are clear to auscultation bilaterally. Left calf is swollen, tender, and erythematous."
        },
        "questions": [
            {
                "stage": 1,
                "question": "What is the most likely diagnosis?",
                "options": ["Acute Myocardial Infarction", "Pulmonary Embolism", "Pneumothorax", "Community-Acquired Pneumonia"],
                "answer": "Pulmonary Embolism",
                "rationale": "The acute dyspnea, pleuritic chest pain, recent travel-induced immobilization, tachycardia, hypoxia, and signs of DVT (calf swelling/tenderness) are a classic presentation of pulmonary embolism."
            }
        ]
    },
    "summary_sheet": {
        "template": "summary_sheet",
        "title": "Aortic Stenosis Summary Sheet",
        "sections": [
            {
                "heading": "Clinical Presentation",
                "summary": "Classic triad of symptoms: Angina, Syncope, and Dyspnea (SAD).",
                "bullets": [
                    "Angina: occurs due to increased myocardial oxygen demand.",
                    "Syncope: exertional, due to fixed cardiac output.",
                    "Dyspnea: indicates heart failure; carries the worst prognosis."
                ]
            }
        ]
    },
    "mnemonic_card": {
        "template": "mnemonic_card",
        "title": "Dialysis Indications Mnemonic",
        "mnemonic": "AEIOU",
        "description": "Parameters for initiating urgent dialysis.",
        "items": [
            {"letter": "A", "concept": "Acidemia", "detail": "Severe metabolic acidosis (pH < 7.1) refractory to therapy."},
            {"letter": "E", "concept": "Electrolytes", "detail": "Refractory hyperkalemia (K > 6.5 mEq/L) with ECG changes."},
            {"letter": "I", "concept": "Intoxication", "detail": "Poisoning with dialyzable toxins (e.g., lithium, aspirin)."},
            {"letter": "O", "concept": "Overload", "detail": "Volume overload (pulmonary edema) refractory to diuretics."},
            {"letter": "U", "concept": "Uremia", "detail": "Uremic complications like pericarditis or encephalopathy."}
        ]
    },
    "concept_tree": {
        "template": "concept_tree",
        "title": "Nervous System Hierarchy",
        "nodes": [
            {"id": "ns", "label": "Nervous System", "detail": "Master controlling and communicating system of the body.", "parent_id": None, "color": "purple"},
            {"id": "cns", "label": "Central Nervous System (CNS)", "detail": "Brain and spinal cord; processes signals.", "parent_id": "ns", "color": "blue"},
            {"id": "pns", "label": "Peripheral Nervous System (PNS)", "detail": "Nerves outside CNS.", "parent_id": "ns", "color": "teal"},
            {"id": "brain", "label": "Brain", "detail": "Primary CNS organ.", "parent_id": "cns", "color": "blue"},
            {"id": "spinal_cord", "label": "Spinal Cord", "detail": "Signal pathway between brain and body.", "parent_id": "cns", "color": "blue"}
        ]
    },
    "pathophysiology_flow": {
        "template": "pathophysiology_flow",
        "title": "Atherosclerosis Cascade",
        "disease": "Atherosclerosis",
        "flow": [
            {
                "stage": "Trigger",
                "title": "Endothelial Dysfunction",
                "description": "Shear stress or smoking damages the endothelial lining.",
                "key_mediators": ["LDL cholesterol", "ROS"]
            },
            {
                "stage": "Mechanism",
                "title": "Lipid Oxidation",
                "description": "LDL particles enter the intima and become oxidized, triggering inflammation.",
                "key_mediators": ["Ox-LDL", "MCP-1"]
            },
            {
                "stage": "Pathology",
                "title": "Foam Cell & Plaque Formation",
                "description": "Macrophages engulf Ox-LDL to form foam cells. Smooth muscle cells form a fibrous cap.",
                "key_mediators": ["PDGF", "Collagen"]
            },
            {
                "stage": "Clinical",
                "title": "Plaque Rupture",
                "description": "Thinning fibrous cap ruptures, inducing thrombus formation leading to ischemia.",
                "key_mediators": ["Metalloproteinases", "Tissue Factor"]
            }
        ]
    },
    "anatomy_cross_section": {
        "template": "anatomy_cross_section",
        "title": "Blood Vessel Wall Structure",
        "organ_or_structure": "Artery Wall",
        "layers": [
            {
                "name": "Tunica Adventitia",
                "description": "Outermost layer made of connective tissue containing collagen and elastic fibers.",
                "function": "Anchors the vessel to surrounding tissues.",
                "clinical_notes": "Contains the vasa vasorum which can be affected in syphilitic aortitis.",
                "components": ["Collagen fibers", "Vasa vasorum"]
            },
            {
                "name": "Tunica Media",
                "description": "Middle layer composed of smooth muscle cells and elastic tissue.",
                "function": "Regulates vessel diameter and controls blood pressure.",
                "clinical_notes": "Hypertrophies in hypertension; undergoes cystic medial necrosis in Marfan syndrome.",
                "components": ["Smooth muscle cells", "Elastic lamellae"]
            },
            {
                "name": "Tunica Intima",
                "description": "Innermost layer in contact with blood flow, lined by endothelial cells.",
                "function": "Provides a smooth surface and regulates permeability.",
                "clinical_notes": "Atherogenesis starts here with lipid accumulation.",
                "components": ["Endothelial cells", "Subendothelial tissue"]
            }
        ]
    },
    "mcq_single_best": {
        "template": "mcq_single_best",
        "title": "Hypertension Management MCQ",
        "questions": [
            {
                "question": "Which of the following drug classes is recommended as initial therapy for a hypertensive patient with diabetes and microalbuminuria?",
                "options": ["Loop diuretics", "ACE inhibitors", "Beta-blockers", "Direct vasodilators"],
                "answer": "ACE inhibitors",
                "explanation": "ACE inhibitors or ARBs are preferred for initial therapy in patients with microalbuminuria because they provide renal protective benefits beyond blood pressure control."
            }
        ]
    },
    "true_false_streak": {
        "template": "true_false_streak",
        "title": "Hematology Facts Speedrun",
        "statements": [
            {
                "statement": "Adult hemoglobin (HbA) consists of two alpha and two beta globin chains.",
                "is_true": True,
                "explanation": "HbA is the dominant adult hemoglobin type and consists of a tetramer of two alpha chains and two beta chains."
            },
            {
                "statement": "Erythropoietin is primarily produced by the liver in response to tissue hypoxia.",
                "is_true": False,
                "explanation": "Erythropoietin is primarily produced by the interstitial cells of the kidneys (approx 90%), not the liver."
            }
        ]
    },
    "hotspot_image": {
        "template": "hotspot_image",
        "title": "Renal Histology Hotspots",
        "image_path": "renal_cortex.png",
        "hotspots": [
            {
                "x": 34.5,
                "y": 56.2,
                "label": "Glomerulus",
                "description": "Site of initial blood filtration. Podocytes wrap around glomerular capillaries."
            }
        ]
    },
    "drug_dose_calculator": {
        "template": "drug_dose_calculator",
        "title": "Gentamicin Pediatric Dosing",
        "drug_name": "Gentamicin",
        "indication": "Pediatric sepsis",
        "recommended_dose": "2.5 mg/kg every 8 hours",
        "min_dose_mg_kg": 2.0,
        "max_dose_mg_kg": 3.0,
        "worked_example": "For a 10 kg child: 10 kg * 2.5 mg/kg = 25 mg IV every 8 hours."
    },
    "decision_algorithm": {
        "template": "decision_algorithm",
        "title": "Sepsis Shock Management Pathway",
        "start_node_id": 1,
        "nodes": [
            {
                "id": 1,
                "question_or_action": "Patient has suspected infection and qSOFA score >= 2. What is your initial step?",
                "options": ["Administer IV fluids", "Start Vasopressors"],
                "next_ids": {"Administer IV fluids": 2, "Start Vasopressors": 3},
                "feedback": {
                    "Administer IV fluids": "Correct. 30 mL/kg crystalloid fluid resuscitation is recommended first.",
                    "Start Vasopressors": "Incorrect. Fluids should be attempted before starting vasopressors."
                },
                "is_terminal": False
            },
            {
                "id": 2,
                "question_or_action": "Fluid resuscitation complete. MAP remains < 65 mmHg. What next?",
                "options": ["Initiate Norepinephrine", "Double IV fluid volume"],
                "next_ids": {"Initiate Norepinephrine": 4, "Double IV fluid volume": 5},
                "feedback": {
                    "Initiate Norepinephrine": "Correct. Norepinephrine is the first-line vasopressor.",
                    "Double IV fluid volume": "Incorrect. Overloading can lead to pulmonary congestion."
                },
                "is_terminal": False
            },
            {
                "id": 4,
                "question_or_action": "Norepinephrine started. MAP target of 65 mmHg achieved. Monitor patient in ICU.",
                "options": [],
                "next_ids": {},
                "feedback": {},
                "is_terminal": True
            }
        ]
    },
    "lab_value_panel": {
        "template": "lab_value_panel",
        "title": "Basic Metabolic Panel Interpretation",
        "labs": [
            {
                "name": "Potassium",
                "value": 5.8,
                "unit": "mEq/L",
                "normal_min": 3.5,
                "normal_max": 5.0,
                "critical_min": 3.0,
                "critical_max": 6.0,
                "clinical_significance": "Hyperkalemia can cause severe cardiac arrhythmias and peaked T-waves on ECG."
            }
        ]
    },
    "cloze_passage": {
        "template": "cloze_passage",
        "title": "Renin-Angiotensin System",
        "passage": "In response to low blood pressure, the kidneys secrete [[1]] which cleaves angiotensinogen into [[2]]. This is then converted by ACE in the lungs into [[3]].",
        "blanks": {
            "1": "renin",
            "2": "angiotensin I",
            "3": "angiotensin II"
        },
        "word_bank": ["renin", "angiotensin I", "angiotensin II", "aldosterone", "erythropoietin"]
    },
    "mastery_heatmap": {
        "template": "mastery_heatmap",
        "title": "Cardiology Revision Consistency",
        "subject": "Cardiology",
        "data_points": [
            {"date": "2026-06-10", "value": 4},
            {"date": "2026-06-11", "value": 12},
            {"date": "2026-06-12", "value": 8}
        ]
    },
    "audio_id_quiz": {
        "template": "audio_id_quiz",
        "title": "Cardiac Auscultation Murmur Quiz",
        "questions": [
            {
                "id": 1,
                "audio_filename": "systolic_murmur.mp3",
                "question": "Identify the cardiac sound presented in the audio clip.",
                "options": ["Aortic Stenosis", "Mitral Regurgitation", "Aortic Regurgitation", "Mitral Stenosis"],
                "answer": "Aortic Stenosis",
                "explanation": "Aortic stenosis typically presents as a crescendo-decrescendo systolic ejection murmur loudest at the right upper sternal border."
            }
        ]
    }
}

# ─── LLM Prompt Builder ──────────────────────────────────────────────────────

STRICT_INSTRUCTIONS = {
    "mind_map": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 5 branches from the central concept.
- Each branch MUST have at least 3 children nodes.
- Use ALL 5 available colors: purple, teal, coral, blue, amber — distribute them across branches.
- Children should be specific, detailed terms — not vague summaries.
- The center node should be a concise 2-4 word core concept.""",

    "flashcard": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 10 flashcards.
- Mix difficulty levels: at least 3 easy, 4 medium, and 3 hard cards.
- Front side: specific clinical/scientific questions (not vague).
- Back side: detailed, comprehensive answers with key facts.
- Tags should categorize cards into sub-topics.
- Cover ALL major aspects of the topic from the context.""",

    "flowchart": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 8 steps.
- Include at least 1 'decision' type node and at least 1 'outcome' type node.
- Steps must have both a clear label AND a detailed sublabel explanation.
- Chain steps logically using the 'next' field — do not leave orphan steps.
- The flow must represent a complete clinical/scientific pathway.""",

    "timeline": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 6 timeline events.
- Each event MUST have a specific time marker (e.g., '0-6 hours', 'Day 1', 'Week 2').
- Use at least 3 different colors from: purple, teal, coral, blue, amber.
- Details should be comprehensive clinical/scientific descriptions, not brief labels.
- Events must be in chronological order.""",

    "comparison_table": """STRICT REQUIREMENTS:
- Include a MINIMUM of 4 items to compare.
- Include a MINIMUM of 5 comparison criteria.
- EVERY cell in the data matrix must be filled — no empty strings.
- Each cell should contain meaningful, specific clinical/scientific data.
- Criteria should cover: definition, mechanism, clinical features, treatment, and prognosis.""",

    "ddx_matrix": """STRICT REQUIREMENTS:
- Include a MINIMUM of 5 diseases in the differential.
- Include a MINIMUM of 6 symptoms/signs.
- Use ALL three states: 'present', 'absent', and 'variable' — each must appear at least once.
- Every cell in the matrix must be filled.
- Diseases and symptoms must be clinically accurate and relevant to the topic.""",

    "cycle_diagram": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 5 cycle steps.
- Each step MUST have both a concise label AND a detailed description.
- The cycle must be biologically/chemically accurate.
- Steps should form a logical closed loop.
- Include specific enzymes, substrates, or mediators where relevant.""",

    "drag_drop": """STRICT REQUIREMENTS:
- Include a MINIMUM of 3 categories.
- Include a MINIMUM of 9 items total (at least 3 per category).
- Each item must have clear, specific text.
- Categories must be distinct and non-overlapping.
- Include a description explaining the classification task.""",

    "sequence_builder": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 8 sequential steps.
- Steps must have a clear, unambiguous correct order.
- Each step text should be specific and detailed enough to distinguish from similar steps.
- The sequence must represent a complete process from start to finish.""",

    "wordle_game": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 6 words.
- All words MUST be in UPPERCASE.
- Word length must be between 4 and 8 characters.
- Each word must be a real medical/scientific term.
- Hints must be clear, educational definitions that don't contain the word itself.
- Include category classification for each word.""",

    "boss_battle": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 6 battle questions.
- Each question MUST have exactly 4 options.
- The 'answer' field MUST exactly match one of the options.
- Include a creative, thematic boss_name related to the topic (e.g., 'Dr. Nephron', 'The Glomerular Beast').
- Explanations must be detailed, ruling out each incorrect distractor.""",

    "clinical_vignette": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 4 clinical stages (e.g., Initial Assessment, Diagnosis, Treatment, Follow-up).
- Patient profile MUST include ALL fields: demographics, presentation, vitals, and exam findings.
- Each question must have exactly 4 options with the answer matching one exactly.
- Rationales must explain why the correct answer is right AND why each distractor is wrong.
- The case must be clinically realistic and internally consistent.""",

    "summary_sheet": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 5 sections.
- Each section MUST have a heading, a summary paragraph, AND at least 4 bullet points.
- Sections should cover: Definition, Etiology/Causes, Pathophysiology, Clinical Features, Management.
- Bullets should be specific, high-yield facts — not vague generalizations.
- Cover ALL major aspects of the topic comprehensively.""",

    "mnemonic_card": """STRICT REQUIREMENTS:
- The mnemonic MUST be a valid uppercase acronym word (e.g., 'MUDPILES', 'SOCRATES').
- Each letter MUST map to a real, clinically relevant concept.
- The 'detail' field for each item must contain a detailed clinical explanation.
- Include a description of what the mnemonic represents overall.
- The acronym must be medically recognized or cleverly constructed from the topic.""",

    "concept_tree": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 12 nodes total.
- Tree must be at least 3 levels deep (root → children → grandchildren).
- Exactly ONE root node (parent_id = null).
- Use at least 3 different colors from: purple, teal, coral, blue, amber.
- Each non-root node must have a valid parent_id referencing another node's id.
- Include detail text for leaf nodes explaining clinical significance.""",

    "pathophysiology_flow": """STRICT REQUIREMENTS:
- MUST include ALL 4 stages: 'Trigger', 'Mechanism', 'Pathology', 'Clinical'.
- Generate a MINIMUM of 2 entries per stage (8 total minimum).
- Each entry must have a detailed description (not just a label).
- Include key_mediators (cytokines, hormones, enzymes) where applicable.
- The flow must represent the complete disease cascade from cause to clinical manifestation.""",

    "anatomy_cross_section": """STRICT REQUIREMENTS:
- Include a MINIMUM of 3 anatomical layers.
- Each layer MUST have ALL fields filled: name, description, function, clinical_notes, components.
- Components list must have at least 2 items per layer.
- Clinical notes should mention specific pathologies associated with each layer.
- The organ_or_structure field must be specific (e.g., 'Renal Cortex', not just 'Kidney').""",

    "mcq_single_best": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 8 questions.
- Each question MUST have exactly 4 options.
- The 'answer' field MUST exactly match one of the options word-for-word.
- Explanations must detail why the correct answer is right AND why each distractor is wrong.
- Questions should test different cognitive levels: recall, comprehension, and application.""",

    "true_false_streak": """STRICT REQUIREMENTS:
- Generate a MINIMUM of 10 statements.
- Mix approximately 50/50 true and false statements.
- Statements must be specific, testable medical/scientific facts.
- Explanations must be detailed for BOTH true and false statements.
- Avoid ambiguous or opinion-based statements.""",

    "hotspot_image": """STRICT REQUIREMENTS:
- Provide a valid image_path filename from the vault.
- Define a MINIMUM of 3 distinct hotspots.
- Coordinates x and y must be percentages between 5.0 and 95.0.
- Description must explain the clinical/anatomical relevance of that specific hotspot coordinate.""",

    "drug_dose_calculator": """STRICT REQUIREMENTS:
- Clearly define drug_name, indication, and recommended_dose text.
- min_dose_mg_kg and max_dose_mg_kg must be valid floats.
- worked_example must detail the exact math calculation steps clearly.""",

    "decision_algorithm": """STRICT REQUIREMENTS:
- Provide a coherent branching decision tree.
- start_node_id must match the id of the first node.
- Each node's options must match the keys in next_ids and feedback.
- MUST contain at least one terminal node (is_terminal = true) with empty options.""",

    "lab_value_panel": """STRICT REQUIREMENTS:
- Include a MINIMUM of 5 lab items.
- Ensure normal_min and normal_max are correct for each lab.
- value should represent a realistic clinical scenario (normal, high, or low).""",

    "cloze_passage": """STRICT REQUIREMENTS:
- The passage text MUST contain blank markers formatted exactly as [[1]], [[2]], etc.
- The blanks keys must correspond exactly to the passage marker numbers.
- word_bank must contain all correct answers plus at least 2 distractors.""",

    "mastery_heatmap": """STRICT REQUIREMENTS:
- Provide data points for the past 14 days.
- Date must be in YYYY-MM-DD format.
- value must be an integer indicating revision activity count.""",

    "audio_id_quiz": """STRICT REQUIREMENTS:
- Provide a valid audio_filename (e.g., 'systolic_murmur.mp3').
- Generate a MINIMUM of 3 questions.
- Each question must have exactly 4 options with the correct answer matching one of them exactly."""
}

def build_prompt(context: str, visual_type: str) -> str:
    mock_json = MOCK_SCHEMAS[visual_type]
    schema_hint = json.dumps(mock_json, indent=2)
    strict = STRICT_INSTRUCTIONS.get(visual_type, "")
    
    return f"""You are a scientific education assistant.
Convert the provided medical/scientific study context into a structured JSON dataset for a {visual_type} template.

CONTEXT:
\"\"\"
{context}
\"\"\"

{strict}

OUTPUT RULES:
- Output ONLY valid JSON matching the exact structure template schema outlined below:
{schema_hint}
- CRITICAL REQUIREMENT FOR COMPREHENSIVENESS: Do not summarize briefly or select only a single sub-topic. Your output dataset MUST comprehensively cover ALL major aspects, concepts, symptoms, pathways, mechanisms, stages, or comparisons present in the provided context, acting as a complete visual summary of the entire lecture/content. Expand the arrays, branches, sections, or rows as much as needed to capture all important details from the context.
- All keys in the template structure are mandatory.
- Match properties exactly (e.g. integer IDs where required, correct color strings).
- Be medically/scientifically accurate based on the context. Do not invent facts.
- Do NOT wrap in markdown code blocks. Start directly with the open curly bracket {{.

JSON:"""

def _call_llm(context: str, visual_type: str, prev_error: str = None) -> str:
    base_prompt = build_prompt(context, visual_type)

    if prev_error:
        prompt = f"""{base_prompt}

PREVIOUS ERROR: {prev_error}
Return corrected JSON only. Start with {{."""
    else:
        prompt = base_prompt

    # Call Gemini client with schema validation
    schema_cls = SCHEMAS.get(visual_type, MindMapSchema)
    return gemini_client.generate_json(
        prompt=prompt,
        response_schema=schema_cls
    )

# ─── Validator & Retry Orchestration ────────────────────────────────────────

def generate_and_validate(context: str, visual_type: str, max_retries: int = None) -> dict:
    if max_retries is None:
        max_retries = getattr(config, "MAX_RETRIES", 2)
    """Generates structured visual JSON with corrective retry loops."""
    schema_cls = SCHEMAS.get(visual_type, MindMapSchema)
    
    last_error = None
    raw_response = ""

    for attempt in range(max_retries):
        try:
            raw_response = _call_llm(context, visual_type, last_error)
            
            # Clean up response
            start = raw_response.find("{")
            end = raw_response.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("Response does not contain a JSON object.")
                
            clean_json = raw_response[start:end+1]
            data = json.loads(clean_json)
            
            # Validate via Pydantic
            validated = schema_cls(**data)
            return validated.model_dump()
            
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            last_error = str(e)
            print(f"[Validator] Validation failed on attempt {attempt+1}/{max_retries}: {last_error}")
            
    raise RuntimeError(f"Failed to generate valid JSON for '{visual_type}' after {max_retries} attempts. Last error: {last_error}")
