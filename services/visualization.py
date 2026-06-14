import sqlite3
from fastapi.responses import HTMLResponse
from services.lean_memory import memory_layer
from magic_engine.mindmap.generator import MindMapGenerator, MindMapNode

def get_db_nodes():
    with sqlite3.connect(memory_layer.db_file) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute('SELECT * FROM study_nodes').fetchall()]

def build_mindmap_svg() -> str:
    db_nodes = get_db_nodes()
    
    nodes_by_id = {}
    for r in db_nodes:
        # Give some colors based on whether it has content
        color = "#818cf8"
        if r.get("fact"):
            color = "#10b981" # Green if generated
        
        nodes_by_id[r["node_id"]] = MindMapNode(
            id=r["node_id"], 
            label=r["title"] or "Unnamed", 
            level=1, 
            color=color, 
            icon="📚"
        )
        
    root = MindMapNode("root_graph", "Study Universe", 0, "#ef4444", "🧠")
    
    # Wire parents and children
    for r in db_nodes:
        n_id = r["node_id"]
        p_id = r["parent_id"]
        
        current_node = nodes_by_id[n_id]
        
        if p_id and p_id in nodes_by_id:
            nodes_by_id[p_id].add_child(current_node)
            current_node.level = nodes_by_id[p_id].level + 1
        else:
            root.add_child(current_node)

    gen = MindMapGenerator()
    return gen.to_interactive_svg(root)

# To be added to main.py
