import json
from typing import List, Dict, Any, Optional
from ..mindmap.templates.interactive_svg import MIND_MAP_HTML_TEMPLATE

class MindMapNode:
    def __init__(self, id: str, label: str, level: int = 0, color: str = "#818cf8", icon: str = ""):
        self.id = id
        self.label = label
        self.level = level
        self.color = color
        self.icon = icon
        self.children: List['MindMapNode'] = []

    def add_child(self, node: 'MindMapNode'):
        self.children.append(node)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "level": self.level,
            "color": self.color,
            "icon": self.icon,
            "children": [c.to_dict() for c in self.children]
        }

class MindMapGenerator:
    LEVEL_COLORS = ["#6366f1", "#8b5cf6", "#a855f7", "#c084fc", "#e879f9"]
    
    

    def _block_to_node(self, block: Any, index: int) -> Optional[MindMapNode]:
        label = ""
        icon = ""
        
        if block.type == "definition":
            label = block.metadata.get("term", "Definition")
            icon = "📖"
        elif block.type == "exam_tip":
            label = "Exam Tip"
            icon = "💡"
        elif block.type == "mnemonic":
            label = f"Mnemonic: {block.content.get('phrase', '')}"
            icon = "🧠"
        elif block.type == "comparison":
            label = "Comparison"
            icon = "📊"
        elif block.type == "timeline":
            label = "Timeline"
            icon = "⏳"
        elif block.type == "drug_card":
            label = block.content.get("name", "Drug Info")
            icon = "💊"
        elif block.type == "mind_map_node":
            label = block.content.get("center", "Topic")
            icon = "🕸️"
            node = MindMapNode(f"b{index}", label, 1, self.LEVEL_COLORS[1], icon)
            branches = block.content.get("branches", {})
            for b_name, b_items in branches.items():
                b_node = MindMapNode(f"b{index}_{b_name}", b_name, 2, self.LEVEL_COLORS[2])
                for item in b_items:
                    b_node.add_child(MindMapNode(f"b{index}_{b_name}_{item}", item, 3, self.LEVEL_COLORS[3]))
                node.add_child(b_node)
            return node
        else:
            return None

        return MindMapNode(f"b{index}", label, 1, self.LEVEL_COLORS[1], icon)

    def to_mermaid(self, root: MindMapNode) -> str:
        lines = ["mindmap", f"  root(({root.label}))"]
        self._render_mermaid_node(root, lines, depth=2)
        return "\n".join(lines)

    def to_interactive_svg(self, root: MindMapNode, theme: str = "clinical") -> str:
        nodes = []
        links = []
        self._flatten_tree(root, nodes, links)
        data = json.dumps({"nodes": nodes, "links": links})

        # Map legacy theme names to new cohesive theme variables
        theme_map = {
            "dark": "nightshift",
            "midnight-pro": "arcane",
            "medical-pro": "clinical",
            "light": "clinical",
            "apple-minimal": "clinical",
            "auto": "clinical"
        }
        theme = (theme or "clinical").lower().strip()
        theme = theme_map.get(theme, theme)
        if theme not in ("clinical", "nightshift", "botanica", "bloom", "solstice", "arcane"):
            theme = "clinical"

        return MIND_MAP_HTML_TEMPLATE.format(
            data=data,
            theme=theme
        )

    def _flatten_tree(self, node: MindMapNode, nodes: List[Dict], links: List[Dict]):
        nodes.append({"id": node.id, "label": node.label, "level": node.level})
        for child in node.children:
            links.append({"source": node.id, "target": child.id})
            self._flatten_tree(child, nodes, links)

    def _render_mermaid_node(self, node: MindMapNode, lines: List[str], depth: int):
        for child in node.children:
            indent = "  " * depth
            icon_str = f"\n{indent}::icon({child.icon})" if child.icon else ""
            lines.append(f"{indent}{child.label}{icon_str}")
            self._render_mermaid_node(child, lines, depth + 1)

    def to_obsidian_canvas(self, root: MindMapNode) -> Dict[str, Any]:
        # Minimal skeleton for .canvas JSON
        return {
            "nodes": [
                {"id": root.id, "type": "text", "text": root.label, "x": 0, "y": 0, "width": 200, "height": 60}
            ],
            "edges": []
        }
