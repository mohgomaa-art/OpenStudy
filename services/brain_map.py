"""
Visual Brain Map builder.
Builds a knowledge graph from user performance data.
"""
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
import sqlite3
import json

try:
    from PySide6.QtCore import QThread, Signal
    HAS_PYSIDE = True
except ImportError:
    HAS_PYSIDE = False

@dataclass
class MapNode:
    topic: str
    strength: float
    last_reviewed: date
    accuracy: float
    connections: list[str]
    debt_score: float = 0.0

@dataclass  
class BrainMapData:
    nodes: list[MapNode]
    edges: list[tuple[str, str]]
    generated_at: datetime

def get_color(strength: float) -> str:
    if strength < 0:
        return "#64748B"  # not reviewed / invalid
    if strength <= 0.4:
         return "#EF4444"
    if strength <= 0.7:
         return "#F59E0B"
    return "#10B981"

async def extract_prerequisites(text: str, source_file: str):
    """
    Extracts conceptual dependencies from text using the LLM.
    Identifies 'Prerequisites' (e.g. topic A requires understanding topic B).
    """
    from services.llm import generate_json
    from services.memory import memory_service
    
    # Take a representative snippet if the text is too long
    # Usually the first 2000 chars often contain the core definitions/prereqs
    snippet = text[:3000]
    
    prompt = f"""
    Analyze the following medical/professional study text and extract conceptual prerequisites.
    A prerequisite means topic A is necessary to understand topic B.
    
    Example:
    Text: "To understand the mechanism of heart failure, one must first master Cardiac Output and Preload."
    Result: [{{ "source": "Cardiac Output", "target": "Heart Failure" }}]
    
    Text:
    {snippet}
    
    Return a JSON list of edges:
    {{
        "edges": [
            {{ "source": "Concept A", "target": "Concept B" }}
        ]
    }}
    
    Keep concept names concise (1-3 words).
    """
    
    try:
        result = await generate_json(prompt, fast=True)
        edges = result.get("edges", [])
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
                memory_service.save_concept_edge(source, target, source_file)
    except Exception as e:
        print(f"Extraction Error: {e}")


def export_json(map_data: BrainMapData) -> dict:
    return {
        "nodes": [
            {
                "id": node.topic,
                "label": node.topic,
                "topic": node.topic,
                "type": "topic",
                "strength": node.strength,
                "accuracy": round(node.accuracy * 100, 1),
                "debt_score": round(node.debt_score, 1),
                "last_reviewed": node.last_reviewed.isoformat(),
                "connections": list(node.connections),
            }
            for node in map_data.nodes
        ],
        "edges": [
            {"source": source, "target": target}
            for source, target in map_data.edges
        ],
        "generated_at": map_data.generated_at.isoformat()
    }

def build_map(memory_db_path: Path, sr_db_path: Path) -> BrainMapData:
    """Read sqlite databases and output MapData graph."""
    nodes = {}
    edges = set()

    if memory_db_path.exists():
        conn = None
        try:
            conn = sqlite3.connect(memory_db_path)
            cur = conn.cursor()

            # Fetch topic stats
            cur.execute("SELECT topic, correct, wrong, last_seen, seconds_spent FROM topic_stats")
            for row in cur.fetchall():
                topic, correct, wrong, last_seen, seconds_spent = row
                total = correct + wrong
                accuracy = (correct / total) if total > 0 else 1.0
                strength = accuracy

                dt = date.today()
                if last_seen:
                    try:
                        dt = datetime.fromisoformat(last_seen).date()
                    except ValueError:
                        pass

                nodes[topic] = MapNode(
                    topic=topic,
                    strength=strength,
                    last_reviewed=dt,
                    accuracy=accuracy,
                    connections=[]
                )

            # ── BUG-01 FIX: query edges BEFORE closing connection ──────────
            try:
                cur.execute("SELECT source_concept, target_concept FROM concept_edges")
                for row in cur.fetchall():
                    source, target = row
                    if source in nodes and target in nodes:
                        edges.add((source, target))
                        nodes[source].connections.append(target)
                        nodes[target].connections.append(source)
            except Exception as e:
                print(f"BrainMap Edge Error: {e}")

        except Exception as e:
            print(f"BrainMap DB Error: {e}")
        finally:
            if conn:
                conn.close()

    return BrainMapData(
        nodes=list(nodes.values()),
        edges=list(edges),
        generated_at=datetime.now()
    )



def build_map_with_debt(memory_db_path: Path, sr_db_path: Path) -> BrainMapData:
    """Build map and overlay debt scores from the memory engine."""
    from services.memory import memory_service
    
    map_data = build_map(memory_db_path, sr_db_path)
    
    # Get debt data and overlay onto nodes
    try:
        debts = memory_service.get_knowledge_debt()
        debt_map = {d["topic"]: d["debt_score"] for d in debts}
        for node in map_data.nodes:
            node.debt_score = debt_map.get(node.topic, 0.0)
    except Exception as e:
        print(f"BrainMap Debt Overlay Error: {e}")
    
    return map_data


if HAS_PYSIDE:
    class BrainMapThread(QThread):
        ready = Signal(dict)
        error = Signal(str)
        
        def __init__(self, memory_db: Path, sr_db: Path, parent=None):
            super().__init__(parent)
            self.memory_db = memory_db
            self.sr_db = sr_db
            
        def run(self):
            try:
                map_data = build_map(self.memory_db, self.sr_db)
                json_data = export_json(map_data)
                self.ready.emit(json_data)
            except Exception as e:
                self.error.emit(str(e))
