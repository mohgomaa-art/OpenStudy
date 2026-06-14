"""
Per-chat visual generator.

`mind_map` uses the existing `MindMapGenerator` + a JSON spec produced by
Gemini. Every other catalog type goes through `_generate_generic_html`,
which asks Gemini for a single self-contained HTML document.

`/api/chat/query` calls `generate_visual` after the chat reply completes
and attaches the returned metadata to the SSE `done` event so the
frontend renders the iframe and persists it onto the assistant message.
"""

import json
import logging
import re
import uuid
from pathlib import Path

from services.config import config_service
from services.llm import llm_service
from magic_engine.mindmap.generator import MindMapGenerator, MindMapNode

logger = logging.getLogger(__name__)

VISUAL_TYPES = {
    "mind_map", "flashcard", "summary_sheet", "mnemonic_card", "concept_tree",
    "flowchart", "cycle_diagram", "timeline", "pathophysiology_flow",
    "sequence_builder", "comparison_table", "ddx_matrix",
    "anatomy_cross_section", "mcq_single_best", "true_false_streak",
    "boss_battle", "clinical_vignette", "wordle_game", "drag_drop",
}

_FENCE_RE = re.compile(r"^```(?:html)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


def _visuals_dir() -> Path:
    d = config_service.data_path / "visuals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _label_for(visual_type: str) -> str:
    return visual_type.replace("_", " ").title()


def generate_visual(visual_type: str, topic: str, session_id: str,
                    reply_md: str = "", theme: str = "auto") -> dict:
    """
    Build a single-file HTML visual for `topic` and persist it under
    `data/visuals/`. Returns `{filename, title, template, html_path}`
    matching the shape the frontend already expects on `msg.visual`.

    Caller is responsible for try/except — a visual failure must not
    bubble up and tank the chat reply.
    """
    if visual_type not in VISUAL_TYPES:
        raise ValueError(f"unknown visual_type: {visual_type}")
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("empty topic")

    if visual_type == "mind_map":
        return _generate_mind_map(topic, session_id, theme)
    return _generate_generic_html(visual_type, topic, session_id, reply_md, theme)


# ── Mind map ──────────────────────────────────────────────────────────────────

_MIND_MAP_PROMPT = """You are a study-companion visual generator.

Return ONLY a JSON object with this exact shape (no prose, no fences):

{{
  "center": "<short center label, 1-5 words>",
  "branches": {{
    "<branch name>": ["<leaf>", "<leaf>", ...],
    ...
  }}
}}

Rules:
- 4-7 branches.
- 3-6 leaves per branch.
- Labels concise (max ~6 words). No emojis. No markdown.
- Center must reflect the topic.

TOPIC: {topic}
"""


def _resolve_theme(topic: str, theme: str) -> str:
    theme_lower = (theme or "auto").lower().strip()
    # Support legacy theme name mappings
    theme_map = {
        "dark": "nightshift",
        "midnight-pro": "arcane",
        "exec-command": "nightshift",
        "medical-pro": "clinical",
        "light": "clinical",
        "apple-minimal": "clinical",
    }
    resolved_theme = theme_map.get(theme_lower, theme_lower)
    
    if resolved_theme == "auto":
        resolved_theme = "clinical"  # default
        topic_lower = topic.lower()
        subject_theme_hints = {
            "pharmacology": "botanica",
            "cardiology":   "clinical",
            "physiology":   "clinical",
            "obgyn":        "bloom",
            "emergency":    "solstice",
            "pediatric":    "bloom",
            "anatomy":      "nightshift",
            "neuro":        "arcane",
            "game":         "solstice",
            "toxicology":   "botanica",
            "surgery":      "solstice"
        }
        for keyword, hint in subject_theme_hints.items():
            if keyword in topic_lower:
                resolved_theme = hint
                break
    
    if resolved_theme not in ("clinical", "nightshift", "botanica", "bloom", "solstice", "arcane"):
        resolved_theme = "clinical"
    return resolved_theme


def _generate_mind_map(topic: str, session_id: str, theme: str) -> dict:
    spec = llm_service.generate_json(_MIND_MAP_PROMPT.format(topic=topic)) or {}
    center = (spec.get("center") or topic).strip()[:80]
    branches = spec.get("branches") or {}
    if not isinstance(branches, dict) or not branches:
        # Fall back to a one-branch map so we still render something useful.
        branches = {"Overview": [topic]}

    gen = MindMapGenerator()
    root = MindMapNode("root", center, level=0,
                       color=gen.LEVEL_COLORS[0], icon="")
    for i, (b_name, items) in enumerate(branches.items()):
        b_id = f"b{i}"
        b_color = gen.LEVEL_COLORS[min(1, len(gen.LEVEL_COLORS) - 1)]
        b_node = MindMapNode(b_id, str(b_name)[:60], level=1, color=b_color)
        if isinstance(items, list):
            leaf_color = gen.LEVEL_COLORS[min(2, len(gen.LEVEL_COLORS) - 1)]
            for j, leaf in enumerate(items):
                b_node.add_child(MindMapNode(
                    f"{b_id}_{j}", str(leaf)[:80], level=2, color=leaf_color,
                ))
        root.add_child(b_node)

    resolved_theme = _resolve_theme(topic, theme)
    html = gen.to_interactive_svg(root, theme=resolved_theme)
    filename = f"{session_id}_mind_map_{_short_id()}.html"
    html_path = _visuals_dir() / filename
    html_path.write_text(html, encoding="utf-8")

    return {
        "filename": filename,
        "title": center,
        "template": "mind_map",
        "html_path": str(html_path),
    }


# ── Generic LLM-rendered HTML ─────────────────────────────────────────────────

_GENERIC_SYSTEM = """You are a study-companion visual generator.

You produce a SINGLE self-contained HTML document for a study visual.

Theme & Styling Rules:
- The document MUST define and support all 6 cohesive CSS themes using CSS variables in the <style> block:
  1. clinical: Light clinical (blue + teal). --bg: #f8fafc; --surface: #ffffff; --border: #e2e8f0; --text: #0f172a; --text-secondary: #64748b; --accent: #2563eb; --accent-soft: #dbeafe; --accent-2: #0d9488; --accent-2-soft: #ccfbf1; --success: #16a34a; --warning: #d97706; --danger: #dc2626;
  2. nightshift: Dark tech (sky-cyan + violet). --bg: #0a0e17; --surface: #131a26; --border: rgba(255,255,255,0.08); --text: #e2e8f0; --text-secondary: #94a3b8; --accent: #38bdf8; --accent-soft: rgba(56,189,248,0.15); --accent-2: #a78bfa; --accent-2-soft: rgba(167,139,250,0.15); --success: #4ade80; --warning: #fbbf24; --danger: #f87171;
  3. botanica: Green/nature (sage + terracotta). --bg: #f6f8f1; --surface: #ffffff; --border: #dde6d5; --text: #2b3a26; --text-secondary: #6b7d63; --accent: #4d7c4a; --accent-soft: #e3ecdf; --accent-2: #c9852f; --accent-2-soft: #f6e6cf; --success: #4d7c4a; --warning: #c9852f; --danger: #b3473a;
  4. bloom: Warm/playful (pink + teal). --bg: #fff5f7; --surface: #ffffff; --border: #fbd5e0; --text: #4a2540; --text-secondary: #9c7a8f; --accent: #ec4899; --accent-soft: #fce7f3; --accent-2: #14b8a6; --accent-2-soft: #ccfbf1; --success: #22c55e; --warning: #f59e0b; --danger: #e11d48;
  5. solstice: Warm/energetic (orange + sky-blue). --bg: #fff8f0; --surface: #ffffff; --border: #fde4cf; --text: #3a2418; --text-secondary: #8a6a55; --accent: #f97316; --accent-soft: #ffedd5; --accent-2: #0ea5e9; --accent-2-soft: #e0f2fe; --success: #65a30d; --warning: #eab308; --danger: #dc2626;
  6. arcane: Dark fantasy/neon (violet/magenta + teal). --bg: #0d0a1a; --surface: #1a1430; --border: rgba(167, 139, 250, 0.15); --text: #f1eaff; --text-secondary: #a89bc4; --accent: #c084fc; --accent-soft: rgba(192, 132, 252, 0.15); --accent-2: #2dd4bf; --accent-2-soft: rgba(45, 212, 191, 0.15); --success: #34d399; --warning: #fbbf24; --danger: #fb7185;
- Declare the variables in :root (defaulting to clinical) and define them for each [data-theme="..."] selector.
- Use only these variables (e.g. var(--bg), var(--surface), var(--text), var(--text-secondary), var(--border), var(--accent), var(--accent-soft), var(--accent-2), var(--accent-2-soft)) to style all HTML elements. Never use hardcoded colors.
- Use var(--text) and var(--text-secondary) for small body/paragraph text for readability compliance. Do not use --accent for small body text.
- Set the data-theme attribute on the <html> tag of the output to match the requested theme.

Hard rules:
- Return ONLY the raw HTML. No markdown fences. No prose before or after.
- One file. Inline all CSS in <style> and all JS in <script> tags.
- External assets allowed ONLY via https CDN script tags (e.g. d3, chart.js). No external CSS, fonts, images.
- Must work standalone in an <iframe> with no parent stylesheet.
- Responsive: fill the viewport, sensible padding, clean typography.
- No emoji in headings.
- No external network calls beyond the CDN scripts you load.
"""

_GENERIC_USER = """Produce an interactive HTML visual.

VISUAL TYPE: {visual_type_human}
TOPIC: {topic}
THEME: {theme}
{reply_section}
Render it as a polished, useful study aid. Include interactivity that fits
the type (flip for flashcards, drag for sequence, click-to-reveal for mcq,
etc.). Keep it focused — one screen, one job.
"""


def _generate_generic_html(visual_type: str, topic: str, session_id: str,
                           reply_md: str, theme: str) -> dict:
    resolved_theme = _resolve_theme(topic, theme)
    reply_section = (
        f"\nSOURCE NOTES (use as ground truth, do not invent facts beyond it):\n\"\"\"\n{reply_md[:6000]}\n\"\"\"\n"
        if reply_md.strip() else ""
    )
    prompt = _GENERIC_USER.format(
        visual_type_human=_label_for(visual_type),
        topic=topic,
        theme=resolved_theme,
        reply_section=reply_section,
    )

    raw = llm_service.generate(prompt, system_instruction=_GENERIC_SYSTEM, max_tokens=llm_service._visual_max_tokens()) or ""
    html = _strip_fences(raw).strip()
    if not html.lower().startswith("<!doctype") and "<html" not in html.lower():
        # Model returned something unusable; wrap it so the iframe still has content.
        html = _wrap_fallback(visual_type, topic, html or "(empty model response)")

    # Force injection of resolved_theme into <html data-theme="..."> if not present or incorrect
    import re
    if "<html" in html.lower():
        html = re.sub(
            r'<html([^>]*?)(?:\s+data-theme="[^"]*")?([^>]*?)>',
            f'<html\\1 data-theme="{resolved_theme}"\\2>',
            html,
            flags=re.IGNORECASE,
            count=1
        )
    else:
        # Wrap or prefix with resolved_theme
        html = f"<!DOCTYPE html><html data-theme='{resolved_theme}'><head><meta charset='utf-8'></head><body>{html}</body></html>"

    filename = f"{session_id}_{visual_type}_{_short_id()}.html"
    html_path = _visuals_dir() / filename
    html_path.write_text(_inject_height_reporter(html), encoding="utf-8")

    return {
        "filename": filename,
        "title": topic[:80],
        "template": visual_type,
        "html_path": str(html_path),
    }


def _strip_fences(text: str) -> str:
    if "```" not in text:
        return text
    return _FENCE_RE.sub("", text)


_HEIGHT_REPORTER = (
    '<script>'
    '(function(){'
    # Track last reported height to avoid redundant messages.
    # Only send when content height *exceeds* what we already told the parent —
    # this breaks the resize feedback loop where parent grows iframe → body
    # fills new height → ResizeObserver fires again → infinite grow.
    'var _last=0;'
    'function rh(){'
    # Measure the natural scroll height of content children, not document/body
    # which stretches to match the iframe viewport.
    'var h=0;'
    'var children=document.body?document.body.children:[];'
    'for(var i=0;i<children.length;i++){var r=children[i].getBoundingClientRect();var b=r.bottom+(window.scrollY||0);if(b>h)h=b;}'
    'if(h<100)h=document.documentElement.scrollHeight;'
    'h=Math.round(h);'
    # Only report strictly larger values — never allow shrinking to re-trigger grow
    'if(h>_last){_last=h;window.parent.postMessage({__visualHeight:h},"*");}}'
    'window.reportHeight=rh;'
    # Initial fires: staggered to catch async renders (charts, mermaid, etc.)
    'setTimeout(rh,120);setTimeout(rh,600);setTimeout(rh,1800);'
    # DOM mutations (accordion open, tab switch, etc.) — use MutationObserver only,
    # NOT ResizeObserver on body (that's what caused the feedback loop).
    'if(window.MutationObserver){'
    'new MutationObserver(function(){setTimeout(rh,60);}).observe(document.body,'
    '{childList:true,subtree:true,attributes:true,'
    'attributeFilter:["class","style","hidden","open"],characterData:false});}'
    # Theme switching
    'window.addEventListener("message",function(e){'
    'if(e.data&&e.data.__setTheme){'
    'document.documentElement.setAttribute("data-theme",e.data.__setTheme);'
    'setTimeout(rh,80);}'
    '});'
    '})()'
    '</script>'
)


def _inject_height_reporter(html: str) -> str:
    """Insert the height-reporter snippet before </body> so the parent iframe can auto-size."""
    tag = '</body>'
    idx = html.lower().rfind(tag)
    if idx != -1:
        return html[:idx] + _HEIGHT_REPORTER + html[idx:]
    return html + _HEIGHT_REPORTER


def _wrap_fallback(visual_type: str, topic: str, body: str) -> str:
    import html as _html
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>body{background:#0f0f1a;color:#e2e8f0;font-family:sans-serif;"
        "padding:32px;line-height:1.5}h1{color:#a78bfa;font-size:18px;margin:0 0 16px}"
        "pre{white-space:pre-wrap;background:#1a1a2e;padding:16px;border-radius:8px;"
        "border:1px solid #2a2a4a}</style></head><body>"
        f"<h1>{_html.escape(_label_for(visual_type))} — {_html.escape(topic)}</h1>"
        f"<pre>{_html.escape(body)}</pre></body></html>"
    )


# ── Cleanup ───────────────────────────────────────────────────────────────────

def delete_session_visuals(session_id: str) -> int:
    """Best-effort: remove all visual HTML files belonging to a session."""
    if not session_id:
        return 0
    try:
        d = _visuals_dir()
    except Exception:
        return 0
    count = 0
    for p in d.glob(f"{session_id}_*.html"):
        try:
            p.unlink()
            count += 1
        except Exception as e:
            logger.debug(f"[visuals] failed to delete {p}: {e}")
    return count
