import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

import sys
import io

# ── Headless / pythonw compatibility ─────────────────────────────────────────
# When launched by pythonw (no console), sys.stdout and sys.stderr are None.
# Uvicorn's logging formatter calls sys.stdout.isatty() and crashes.
# Redirect to devnull to keep everything silent and stable.
_headless = sys.stdout is None or sys.stderr is None
if _headless:
    _devnull = open(os.devnull, 'w', encoding='utf-8')
    if sys.stdout is None:
        sys.stdout = _devnull
    if sys.stderr is None:
        sys.stderr = _devnull

from services.config import config_service
from services.llm import llm_service
from services.lean_memory import memory_layer
from services.export.png_export import export_to_png
from services.export.pdf_export import export_to_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SETTINGS_FILE = str(config_service.data_path / "settings.json")

def _provider_defaults():
    return {
        "gemini":     {"api_keys": [], "model": "gemini-2.5-flash"},
        "openai":     {"api_keys": [], "model": "gpt-4o"},
        "anthropic":  {"api_keys": [], "model": "claude-sonnet-4-6"},
        "groq":       {"api_keys": [], "model": "llama-3.3-70b-versatile"},
        "openrouter": {"api_keys": [], "model": "openai/gpt-4o"},
        "ollama":     {"base_url": "http://localhost:11434", "model": "llama3"},
    }

def load_custom_settings():
    defaults = {
        "active_provider": "gemini",
        "providers": _provider_defaults(),
        "system_prompt": "",
        "prep_prompt": "",
        "visual_theme": "auto",
        # legacy fields kept for backward-compat with Gemini cache code
        "gemini_api_keys": [],
        "gemini_model": "gemini-2.5-flash",
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Fill any missing top-level keys
            for k, v in defaults.items():
                data.setdefault(k, v)
            # Fill any missing providers
            providers = data.setdefault("providers", {})
            for pname, pdef in _provider_defaults().items():
                if pname not in providers:
                    providers[pname] = dict(pdef)
                else:
                    for pk, pv in pdef.items():
                        providers[pname].setdefault(pk, pv)
            # Migrate .env GEMINI_API_KEYS → providers.gemini.api_keys if not yet in settings
            if not providers["gemini"]["api_keys"]:
                env_keys = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]
                if env_keys:
                    providers["gemini"]["api_keys"] = env_keys
                    data["gemini_api_keys"] = env_keys
                    save_custom_settings(data)
            # Sync legacy gemini_api_keys → providers.gemini.api_keys (one-way migration)
            if data.get("gemini_api_keys") and not providers["gemini"]["api_keys"]:
                providers["gemini"]["api_keys"] = data["gemini_api_keys"]
            if data.get("gemini_model") and providers["gemini"]["model"] == "gemini-2.5-flash":
                providers["gemini"]["model"] = data["gemini_model"]
            # Keep legacy fields in sync for existing caching code
            data["gemini_api_keys"] = providers["gemini"]["api_keys"]
            data["gemini_model"]    = providers["gemini"]["model"]
            return data
        except Exception:
            pass
    return defaults

def save_custom_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

# Load settings at startup and initialize environment/config variables
try:
    _start_settings = load_custom_settings()
    _keys = _start_settings.get("gemini_api_keys", [])
    if _keys:
        os.environ["GEMINI_API_KEYS"] = ",".join(_keys)
    _model = _start_settings.get("gemini_model", "")
    if _model:
        os.environ["GEMINI_MODEL"] = _model
    _ollama = _start_settings.get("providers", {}).get("ollama", {})
    if _ollama.get("base_url"):
        os.environ.setdefault("OLLAMA_HOST", _ollama["base_url"])
    if _ollama.get("model"):
        os.environ.setdefault("OLLAMA_MODEL", _ollama["model"])
except Exception as _e:
    print(f"[Startup Settings] Failed to apply: {_e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OpenStudy starting...")
    yield
    logger.info("OpenStudy stopped.")


app = FastAPI(title="OpenStudy", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "http://localhost:1420",
        "http://localhost:5173",
        "http://127.0.0.1:1420",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def _safe_join(root: str, user_path: str) -> str:
    from pathlib import Path
    root_path = Path(root).resolve()
    candidate = (root_path / user_path).resolve()
    if root_path not in candidate.parents and candidate != root_path:
        raise HTTPException(status_code=403, detail="Access denied: Path traversal blocked")
    return str(candidate)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok"}


# Prep/RAG ingestion was removed — uploads now save to docs/ and feed
# Gemini context caching directly via /api/chat/query. See plan:
# C:\Users\mnile\.claude\plans\refactored-stargazing-diffie.md
#
# /api/rag/download served files from visual-rag/output and rag_uploads.
# Both directories are gone; chat-history exports use /api/chat/export.


class OpenDocumentRequest(BaseModel):
    filepath: str

@app.post("/api/documents/open")
async def open_document(req: OpenDocumentRequest):
    from pathlib import Path
    import subprocess
    import sys
    
    target_path = Path(req.filepath)
    if not target_path.is_absolute():
        filename = target_path.name
        docs_dir = Path(config_service.root_path) / "docs"
        uploads_dir = Path(config_service.data_path) / "rag_uploads"
        
        found_path = None
        for root, _, files in os.walk(docs_dir):
            if filename in files:
                found_path = Path(root) / filename
                break
        if not found_path:
            if uploads_dir.exists():
                for root, _, files in os.walk(uploads_dir):
                    if filename in files:
                        found_path = Path(root) / filename
                        break
        if found_path:
            target_path = found_path
        else:
            raise HTTPException(status_code=404, detail="File not found in docs or rag_uploads")
            
    abs_path = target_path.resolve()

    allowed_dirs = [
        Path(config_service.root_path) / "docs",
        Path(config_service.data_path) / "exports",
    ]

    is_allowed = False
    for parent in allowed_dirs:
        if parent.exists():
            parent_resolved = parent.resolve()
            if (parent_resolved == abs_path or parent_resolved in abs_path.parents) and abs_path.exists():
                is_allowed = True
                break

    if not is_allowed:
        raise HTTPException(status_code=403, detail="Access denied: File access not permitted")

    try:
        if sys.platform == "win32":
            os.startfile(str(abs_path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(abs_path)], check=True)
        else:
            subprocess.run(["xdg-open", str(abs_path)], check=True)
        return {"status": "success", "message": f"Opened {abs_path.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open file: {e}")


class OpenUrlRequest(BaseModel):
    url: str

@app.post("/api/utils/open-url")
def open_url_in_browser(req: OpenUrlRequest):
    """Open a URL in the user's default web browser."""
    import webbrowser
    if not (req.url.startswith("http://") or req.url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Invalid URL protocol")
    try:
        webbrowser.open(req.url)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RevealDocumentRequest(BaseModel):
    filepath: str

@app.post("/api/documents/reveal")
async def reveal_document(req: RevealDocumentRequest):
    from pathlib import Path
    import subprocess
    import sys

    target_path = Path(req.filepath)
    if not target_path.is_absolute():
        filename = target_path.name
        docs_dir = Path(config_service.root_path) / "docs"
        exports_dir = Path(config_service.data_path) / "exports"
        found_path = None
        for root, _, files in os.walk(docs_dir):
            if filename in files:
                found_path = Path(root) / filename
                break
        if not found_path and exports_dir.exists() and (exports_dir / filename).exists():
            found_path = exports_dir / filename

        if found_path:
            target_path = found_path
        else:
            raise HTTPException(status_code=404, detail="File not found")

    abs_path = target_path.resolve()

    allowed_dirs = [
        Path(config_service.root_path) / "docs",
        Path(config_service.data_path) / "exports",
    ]
    
    is_allowed = False
    for parent in allowed_dirs:
        if parent.exists():
            parent_resolved = parent.resolve()
            if (parent_resolved == abs_path or parent_resolved in abs_path.parents) and abs_path.exists():
                is_allowed = True
                break
            
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Access denied: File reveal not permitted")
        
    try:
        if sys.platform == "win32":
            subprocess.run(["explorer.exe", "/select,", str(abs_path)], check=True)
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", str(abs_path)], check=True)
        else:
            subprocess.run(["xdg-open", str(abs_path.parent)], check=True)
        return {"status": "success", "message": f"Revealed {abs_path.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reveal file: {e}")



# ── Document Management ───────────────────────────────────────────────────────

@app.get("/api/visual/view/{filename}")
def view_visual(filename: str):
    """Serve a generated visual HTML from data/visuals/."""
    from pathlib import Path
    visuals_dir = Path(config_service.data_path) / "visuals"
    # _safe_join enforces path traversal protection.
    abs_path = Path(_safe_join(str(visuals_dir), filename))
    if not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Visual not found")
    if abs_path.suffix.lower() != ".html":
        raise HTTPException(status_code=400, detail="Not an HTML file")
    return FileResponse(str(abs_path), media_type="text/html")


@app.head("/api/visual/view/{filename}")
def check_visual(filename: str):
    """Check if a generated visual HTML exists in data/visuals/."""
    from pathlib import Path
    from fastapi.responses import Response
    visuals_dir = Path(config_service.data_path) / "visuals"
    abs_path = Path(_safe_join(str(visuals_dir), filename))
    if not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Visual not found")
    if abs_path.suffix.lower() != ".html":
        raise HTTPException(status_code=400, detail="Not an HTML file")
    return Response(status_code=200, media_type="text/html")


@app.get("/api/documents/download")
def download_document(path: str):
    """Serve a file from docs/ or data/exports/. Used by chat-export download links."""
    from pathlib import Path
    abs_path = Path(path).resolve()
    allowed_dirs = [
        Path(config_service.root_path) / "docs",
        Path(config_service.data_path) / "exports",
    ]
    is_allowed = False
    for parent in allowed_dirs:
        if parent.exists():
            parent_resolved = parent.resolve()
            if (parent_resolved == abs_path or parent_resolved in abs_path.parents) and abs_path.exists():
                is_allowed = True
                break
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Access denied: File download not permitted")
    return FileResponse(str(abs_path), filename=abs_path.name)


@app.get("/api/documents/structure")
def get_docs_structure():
    docs_dir = os.path.abspath(os.path.join(str(config_service.root_path), "docs"))
    os.makedirs(docs_dir, exist_ok=True)

    structure = {}
    for item in os.listdir(docs_dir):
        item_path = os.path.join(docs_dir, item)
        if os.path.isdir(item_path):
            structure[item] = {}
            for subitem in os.listdir(item_path):
                subitem_path = os.path.join(item_path, subitem)
                if os.path.isdir(subitem_path):
                    files = [f for f in os.listdir(subitem_path) if os.path.isfile(os.path.join(subitem_path, f))]
                    structure[item][subitem] = files
                else:
                    structure[item].setdefault("", []).append(subitem)
        else:
            structure.setdefault("", {}).setdefault("", []).append(item)
    return {"status": "success", "structure": structure}


@app.get("/api/study/library")
def get_study_library():
    """Retrieve all nodes from the study_nodes library."""
    try:
        from services.visualization import get_db_nodes
        nodes = get_db_nodes()
        return {"status": "success", "nodes": nodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/upload")
async def upload_document(
    files: list[UploadFile] = File(...),
    subject: str = "",
    lecture: str = "",
    session_id: str = ""
):
    """
    Save uploaded files to docs/. If `session_id` is provided, the first
    file's extracted text is attached to that chat session (server-side —
    no huge body in the response). Without `session_id`, this is just a
    save-to-vault operation.

    Per-file response shape: {filename, text_length, warning?}.
    """
    from services.text_extract import extract_text, SUPPORTED_EXTS

    subject = "".join(c for c in subject if c.isalnum() or c in " _-").strip()
    lecture = "".join(c for c in lecture if c.isalnum() or c in " _-").strip()

    target_dir = os.path.abspath(os.path.join(str(config_service.root_path), "docs"))
    if subject:
        target_dir = os.path.join(target_dir, subject)
        if lecture:
            target_dir = os.path.join(target_dir, lecture)
    os.makedirs(target_dir, exist_ok=True)

    results = []
    attached = False
    for f in files:
        file_path = os.path.join(target_dir, f.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await f.read())

        entry = {"filename": os.path.basename(file_path), "text_length": 0}
        ext = os.path.splitext(file_path)[1].lower()
        text = ""
        if ext not in SUPPORTED_EXTS:
            entry["warning"] = f"unsupported_type:{ext}"
        else:
            try:
                text = await asyncio.to_thread(extract_text, file_path)
                entry["text_length"] = len(text)
                if len(text) == 0:
                    entry["warning"] = "no_text_extracted"
            except Exception as e:
                logger.error(f"[upload] extract_text failed for {f.filename}: {e}")
                entry["warning"] = f"extraction_error:{type(e).__name__}"

        if session_id and text and not attached:
            try:
                memory_layer.attach_document(session_id, entry["filename"], text)
                entry["attached_to_session"] = session_id
                attached = True
            except Exception as e:
                logger.error(f"[upload] attach_document failed: {e}")
                entry["warning"] = f"attach_error:{type(e).__name__}"

        results.append(entry)

    return {"status": "success", "files": results,
            "saved_files": [r["filename"] for r in results]}


# ── Chat & Session Management ─────────────────────────────────────────────────

class SaveChatSessionRequest(BaseModel):
    session_id: str
    title: str
    messages: list[dict]


class ChatQueryRequest(BaseModel):
    session_id: str
    message: str
    visual_type: str | None = None
    visual_types: list[str] | None = None
    strict: bool = True
    provider: str | None = None  # None = use active_provider from settings
    theme: str | None = None



class ChatExportRequest(BaseModel):
    session_id: str
    format: str  # 'pdf' or 'png'


@app.get("/api/chat/sessions")
def get_chat_sessions():
    try:
        return {"status": "success", "sessions": memory_layer.get_chat_sessions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/sessions/{session_id}")
def get_chat_session(session_id: str):
    try:
        session = memory_layer.get_chat_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "success", "session": session}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/sessions")
def save_chat_session(req: SaveChatSessionRequest):
    try:
        memory_layer.save_chat_session(req.session_id, req.title, req.messages)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/chat/sessions/{session_id}")
def delete_chat_session(session_id: str):
    try:
        # Best-effort: drop the Gemini context cache too. Failure here must not
        # block the SQLite delete (cache will expire on its own via TTL anyway).
        try:
            from services import gemini_cache
            doc = memory_layer.get_session_doc(session_id) or {}
            cache_name = doc.get("cache_name")
            if cache_name:
                owning_key = gemini_cache.find_key_by_id(doc.get("cache_api_key_id"))
                gemini_cache.delete(cache_name, owning_key)
        except Exception as cache_err:
            logger.debug(f"[delete_session] cache cleanup failed (ignored): {cache_err}")
        try:
            from services import visual_engine
            visual_engine.delete_session_visuals(session_id)
        except Exception as vis_err:
            logger.debug(f"[delete_session] visual cleanup failed (ignored): {vis_err}")
        memory_layer.delete_chat_session(session_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def markdown_to_html(text: str) -> str:
    import html
    import re
    
    text = html.escape(text)
    
    def parse_html_table(rows):
        if len(rows) < 2:
            return "\n".join(rows)
            
        def split_row(r):
            cells = r.split('|')[1:-1]
            return [c.strip() for c in cells]
            
        headers = split_row(rows[0])
        separator = split_row(rows[1])
        
        is_sep = all(all(char in '-: ' for char in cell) for cell in separator) if separator else False
        if not is_sep:
            return "\n".join(rows)
            
        thead_cells = []
        for h in headers:
            thead_cells.append(f'<th style="border: 1px solid #cbd5e1; padding: 10px; font-weight: bold; background-color: #f1f5f9; text-align: left; font-size: 13px; color: #0f172a;">{h}</th>')
        thead_html = f'<tr>{"".join(thead_cells)}</tr>'
        
        tbody_rows = []
        for row in rows[2:]:
            cells = split_row(row)
            tbody_cells = []
            for c in cells:
                tbody_cells.append(f'<td style="border: 1px solid #cbd5e1; padding: 10px; font-size: 13px; color: #334155; line-height: 1.5;">{c}</td>')
            while len(tbody_cells) < len(headers):
                tbody_cells.append('<td style="border: 1px solid #cbd5e1; padding: 10px; font-size: 13px; color: #334155;"></td>')
            tbody_rows.append(f'<tr>{"".join(tbody_cells[:len(headers)])}</tr>')
            
        table_style = 'width: 100%; border-collapse: collapse; margin: 16px 0; font-family: sans-serif;'
        return f'<table style="{table_style}"><thead>{thead_html}</thead><tbody>{"".join(tbody_rows)}</tbody></table>'

    # Table parsing
    lines = text.split('\n')
    in_table = False
    table_rows = []
    new_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
            table_rows.append(stripped)
        else:
            if in_table:
                table_html = parse_html_table(table_rows)
                new_lines.append(table_html)
                table_rows = []
                in_table = False
            new_lines.append(line)
            
    if in_table:
        table_html = parse_html_table(table_rows)
        new_lines.append(table_html)
        
    text = "\n".join(new_lines)

    # Custom blocks like ```disease, ```drug, etc.
    custom_types = ['disease', 'drug', 'osce', 'mnemonic', 'clinical', 'differential']
    for t_type in custom_types:
        pattern = r'```' + t_type + r'\n(.*?)```'
        def replace_custom(match):
            content = match.group(1)
            lines = content.strip().split('\n')
            html_fields = []
            for l in lines:
                if ':' in l:
                    k, v = l.split(':', 1)
                    html_fields.append(f'<div style="margin-bottom: 6px;"><strong style="text-transform: capitalize; color:#475569; font-size:12px;">{k.strip()}:</strong> <span style="font-size:13px; color:#1e293b;">{v.strip()}</span></div>')
                else:
                    html_fields.append(f'<div style="margin-bottom: 6px; font-size:13px; color:#334155;">{l.strip()}</div>')
            fields_html = "\n".join(html_fields)
            
            accent_color = "#3b82f6"
            if t_type == 'disease': accent_color = "#ef4444"
            elif t_type == 'drug': accent_color = "#10b981"
            elif t_type == 'osce': accent_color = "#f59e0b"
            elif t_type == 'mnemonic': accent_color = "#6366f1"
            elif t_type == 'clinical': accent_color = "#ec4899"
            
            return f'<div style="background:#f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid {accent_color}; border-radius:12px; padding:14px; margin: 14px 0; font-family: sans-serif;"><strong style="color:{accent_color}; text-transform: uppercase; font-size:10px; display:block; margin-bottom:8px; tracking-wide: 0.05em;">{t_type} Card</strong>{fields_html}</div>'
        
        text = re.sub(pattern, replace_custom, text, flags=re.DOTALL | re.IGNORECASE)

    # Obsidian-style callouts: > [!NOTE]
    def replace_callout(match):
        c_type = match.group(1).upper()
        content = match.group(2)
        content = re.sub(r'^&gt;\s*', '', content, flags=re.MULTILINE)
        bg = "#f0f9ff" if "NOTE" in c_type or "INFO" in c_type else "#f0fdf4" if "TIP" in c_type else "#faf5ff" if "IMPORTANT" in c_type else "#fef2f2"
        border = "#0284c7" if "NOTE" in c_type or "INFO" in c_type else "#22c55e" if "TIP" in c_type else "#a855f7" if "IMPORTANT" in c_type else "#ef4444"
        return f'<div style="background:{bg}; border-left: 4px solid {border}; padding: 12px; border-radius: 8px; margin: 12px 0;"><strong style="color:{border}; display:block; margin-bottom: 4px; font-size:10px; text-transform:uppercase; font-family:sans-serif;">{c_type}</strong><div style="font-size:14px; line-height:1.5; color: #1e293b;">{content.strip()}</div></div>'
    
    text = re.sub(r'&gt;\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](.*?)(?=\n\n|\n&gt;|$)', replace_callout, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Standard blockquotes
    text = re.sub(r'^&gt;\s*(.*?)$', r'<blockquote style="border-left: 3px solid #3b82f6; padding-left: 12px; color: #475569; margin: 12px 0;">\1</blockquote>', text, flags=re.MULTILINE)

    # Code blocks
    text = re.sub(r'```(.*?)\n(.*?)```', r'<pre style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px; overflow-x:auto; font-family:monospace; font-size:13px; color:#0f172a; margin: 12px 0;"><code class="language-\1">\2</code></pre>', text, flags=re.DOTALL)
    
    # Inline code
    text = re.sub(r'`(.*?)`', r'<code style="background:#f1f5f9; border:1px solid #e2e8f0; border-radius:4px; padding:2px 6px; font-family:monospace; font-size:13px; color:#0f172a;">\1</code>', text)
    
    # Bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # Headers
    text = re.sub(r'^### (.*?)$', r'<h3 style="color:#0f172a; font-size:15px; margin:18px 0 8px 0; font-weight:700;">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*?)$', r'<h2 style="color:#0f172a; font-size:17px; margin:22px 0 10px 0; font-weight:700;">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*?)$', r'<h1 style="color:#0f172a; font-size:20px; margin:26px 0 12px 0; font-weight:700; border-bottom: 1px solid #e2e8f0; padding-bottom:6px;">\1</h1>', text, flags=re.MULTILINE)
    
    # Bullet lists
    text = re.sub(r'^\s*-\s+(.*?)$', r'<li style="margin-bottom:4px; margin-left:20px; font-size:14px; line-height:1.5; color:#334155;">\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+(.*?)$', r'<li style="margin-bottom:4px; margin-left:20px; font-size:14px; line-height:1.5; color:#334155;">\1</li>', text, flags=re.MULTILINE)

    # Paragraphs / Newlines
    lines = text.split('\n')
    formatted_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted_lines.append('<div style="height:8px;"></div>')
        elif (stripped.startswith('<h') or stripped.startswith('<pre') or stripped.startswith('</pre') or 
              stripped.startswith('<li') or stripped.startswith('<div') or stripped.startswith('</div') or 
              stripped.startswith('<blockquote') or stripped.startswith('</blockquote') or 
              stripped.startswith('<table') or stripped.startswith('</table') or 
              stripped.startswith('<thead') or stripped.startswith('</thead') or 
              stripped.startswith('<tbody') or stripped.startswith('</tbody') or 
              stripped.startswith('<tr') or stripped.startswith('</tr') or 
              stripped.startswith('<th') or stripped.startswith('<td')):
            formatted_lines.append(line)
        else:
            formatted_lines.append(f'<p style="margin: 0 0 6px 0; line-height: 1.5; font-size:14px; color:#334155;">{line}</p>')
            
    return "\n".join(formatted_lines)


def _mask_key(k: str) -> str:
    """Render a Gemini API key as a masked preview (last 4 chars only)."""
    if not k:
        return ""
    if len(k) <= 4:
        return "..." + k
    return "..." + k[-4:]


def _is_masked_key(k: str) -> bool:
    """Detect the mask format produced by _mask_key — used to mean 'keep existing'."""
    if not isinstance(k, str) or not k.startswith("..."):
        return False
    tail = k[3:]
    return 0 < len(tail) <= 8 and all(c.isalnum() or c in "-_" for c in tail)


@app.get("/api/llm/status")
def get_llm_status():
    """Snapshot of provider health for UI status pills and rate-limit toasts."""
    settings = load_custom_settings()
    active = settings.get("active_provider", "gemini")
    try:
        if active == "gemini":
            from services.gemini_client import rotator_status, get_rotator
            rot = get_rotator()
            rot.reload_keys()
            snapshot = rotator_status()
            snapshot["provider"] = "gemini"
            return {"status": "success", **snapshot}
        else:
            provider_cfg = settings.get("providers", {}).get(active, {})
            keys = provider_cfg.get("api_keys", [])
            return {
                "status": "success",
                "provider": active,
                "total_keys": len(keys),
                "available_keys": len(keys),
                "keys": [{"masked": _mask_key(k), "cooldown_remaining": 0} for k in keys],
                "earliest_available_in": 0.0,
            }
    except Exception as e:
        return {
            "status": "success",
            "provider": active,
            "total_keys": 0,
            "available_keys": 0,
            "keys": [],
            "earliest_available_in": 0.0,
            "error": str(e),
        }


@app.get("/api/settings")
def get_settings():
    settings = load_custom_settings()
    # Mask all API keys for each provider before sending to frontend
    providers = settings.get("providers", {})
    masked_providers = {}
    for pname, pcfg in providers.items():
        masked_pcfg = dict(pcfg)
        if "api_keys" in masked_pcfg:
            masked_pcfg["api_keys"] = [_mask_key(k) for k in masked_pcfg["api_keys"]]
        masked_providers[pname] = masked_pcfg
    # Also mask legacy field
    settings["gemini_api_keys"] = [_mask_key(k) for k in settings.get("gemini_api_keys", [])]
    settings["providers"] = masked_providers
    return settings


class ProviderConfig(BaseModel):
    api_keys: list[str] = []
    model: str = ""
    base_url: str = ""


class SaveSettingsRequest(BaseModel):
    active_provider: str = "gemini"
    providers: dict = {}
    system_prompt: str = ""
    prep_prompt: str = ""
    visual_theme: str = "auto"
    # legacy fields still accepted so old frontend code still works
    gemini_api_keys: list[str] = []
    gemini_model: str = ""


@app.post("/api/settings")
def save_settings(req: SaveSettingsRequest):
    existing = load_custom_settings()
    existing_providers = existing.get("providers", {})

    # Resolve provider configs, un-masking preserved keys
    new_providers = {}
    incoming = req.providers or {}

    for pname, pdefault in _provider_defaults().items():
        inc = incoming.get(pname, {})
        ex = existing_providers.get(pname, {})

        # Un-mask api_keys
        incoming_keys = inc.get("api_keys", []) if isinstance(inc, dict) else []
        existing_real_keys = ex.get("api_keys", []) or []
        resolved_keys = []
        for submitted in incoming_keys:
            submitted = (submitted or "").strip()
            if not submitted:
                continue
            if not _is_masked_key(submitted):
                resolved_keys.append(submitted)
                continue
            suffix = submitted[3:]
            matches = [k for k in existing_real_keys if k and k.endswith(suffix)]
            if matches:
                resolved_keys.append(matches[0])

        new_providers[pname] = {
            "api_keys": resolved_keys[:10],
            "model": (inc.get("model") or ex.get("model") or pdefault.get("model", "")).strip(),
        }
        if "base_url" in pdefault:
            new_providers[pname]["base_url"] = (
                inc.get("base_url") or ex.get("base_url") or pdefault["base_url"]
            ).strip()

    # Handle legacy gemini_api_keys field (old frontends that haven't updated yet)
    if req.gemini_api_keys:
        leg_resolved = []
        ex_gem_keys = existing_providers.get("gemini", {}).get("api_keys", [])
        for submitted in req.gemini_api_keys:
            submitted = (submitted or "").strip()
            if not submitted:
                continue
            if not _is_masked_key(submitted):
                leg_resolved.append(submitted)
            else:
                suffix = submitted[3:]
                matches = [k for k in ex_gem_keys if k and k.endswith(suffix)]
                if matches:
                    leg_resolved.append(matches[0])
        if leg_resolved:
            new_providers["gemini"]["api_keys"] = leg_resolved[:10]
    if req.gemini_model:
        new_providers["gemini"]["model"] = req.gemini_model.strip()

    gemini_keys = new_providers["gemini"]["api_keys"]
    gemini_model = new_providers["gemini"]["model"] or "gemini-2.5-flash"

    settings = {
        "active_provider": req.active_provider,
        "providers": new_providers,
        "system_prompt": req.system_prompt,
        "prep_prompt": req.prep_prompt,
        "visual_theme": req.visual_theme,
        "gemini_api_keys": gemini_keys,
        "gemini_model": gemini_model,
    }
    save_custom_settings(settings)

    # Hot-reload Gemini rotator
    try:
        os.environ["GEMINI_API_KEYS"] = ",".join(gemini_keys)
        os.environ["GEMINI_MODEL"] = gemini_model
        from services import gemini_client
        rotator = gemini_client.get_rotator()
        rotator.keys = gemini_keys
        rotator.cool_downs.clear()
    except Exception as e:
        logger.error(f"Failed to reload Gemini rotator: {e}")

    # Apply Ollama env vars
    try:
        ollama_cfg = new_providers.get("ollama", {})
        if ollama_cfg.get("base_url"):
            os.environ["OLLAMA_HOST"] = ollama_cfg["base_url"]
        if ollama_cfg.get("model"):
            os.environ["OLLAMA_MODEL"] = ollama_cfg["model"]
    except Exception:
        pass

    return {"status": "success"}


@app.post("/api/chat/export")
async def export_chat(req: ChatExportRequest):
    try:
        from datetime import datetime
        import html

        session = memory_layer.get_chat_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        title = session.get("title", "Workspace Chat")
        messages = session.get("messages", [])

        messages_html_list = []
        for m in messages:
            role = m.get("role", "user")
            components = m.get("components", [])
            content_html_list = []
            for c in components:
                if c.get("type") == "text":
                    content_html_list.append(markdown_to_html(c.get("content", "")))
                elif c.get("type") == "code":
                    content_html_list.append(
                        f'<pre style="background:#0d0d0d; border:1px solid #2a2f45; border-radius:8px; padding:12px; overflow-x:auto; font-family:monospace; font-size:13px; color:#e2e8f0; margin: 12px 0;"><code class="language-{c.get("language", "")}">{html.escape(c.get("content", ""))}</code></pre>'
                    )
            
            content_html = "\n".join(content_html_list)

            if role == "user":
                messages_html_list.append(f"""
                <div class="message-row">
                    <span class="sender-label sender-user">You</span>
                    <div class="message-user">
                        {content_html}
                    </div>
                </div>
                """)
            else:
                messages_html_list.append(f"""
                <div class="message-row">
                    <span class="sender-label sender-assistant">OpenStudy Assistant</span>
                    <div class="message-assistant">
                        {content_html}
                    </div>
                </div>
                """)

        messages_html = "\n".join(messages_html_list)
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html_template = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<!-- KaTeX CSS & JS for LaTeX Math Rendering -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js" onload="renderMath();"></script>
<script>
    function renderMath() {{
        if (typeof renderMathInElement === 'function') {{
            renderMathInElement(document.body, {{
                delimiters: [
                    {{left: '$$', right: '$$', display: true}},
                    {{left: '$', right: '$', display: false}},
                    {{left: '\\(', right: '\\)', display: false}},
                    {{left: '\\[', right: '\\]', display: true}}
                ],
                throwOnError : false
            }});
        }}
    }}
    window.addEventListener('load', renderMath);
    document.addEventListener('DOMContentLoaded', renderMath);
</script>
<style>
body {{
    background: #ffffff;
    color: #1e293b;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    margin: 0;
    padding: 40px 20px;
    display: block;
}}
.container {{
    max-width: 760px;
    margin: 0 auto;
    width: 100%;
}}
.header {{
    border-bottom: 2px solid #f1f5f9;
    padding-bottom: 20px;
    margin-bottom: 30px;
}}
.title {{
    font-size: 26px;
    font-weight: 800;
    color: #0f172a;
    margin: 0;
}}
.meta {{
    font-size: 13px;
    color: #64748b;
    margin-top: 6px;
}}
.message-row {{
    margin-bottom: 24px;
    display: block;
    page-break-inside: avoid;
}}
.sender-label {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
    display: block;
}}
.sender-user {{
    color: #2563eb;
    text-align: right;
}}
.sender-assistant {{
    color: #059669;
    text-align: left;
}}
.message-user {{
    margin-left: auto;
    max-width: 85%;
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 12px 12px 0 12px;
    padding: 12px 18px;
    color: #0f172a;
}}
.message-assistant {{
    margin-right: auto;
    max-width: 85%;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px 12px 12px 0;
    padding: 12px 18px;
    color: #334155;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1 class="title">{html.escape(title)}</h1>
        <div class="meta">OpenStudy Chat Session Export • Generated on {date_str}</div>
    </div>
    {messages_html}
</div>
</body>
</html>"""

        export_dir = os.path.join(str(config_service.data_path), "exports")
        os.makedirs(export_dir, exist_ok=True)

        html_filename = f"chat_{req.session_id}.html"
        html_path = os.path.join(export_dir, html_filename)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_template)

        if req.format == "pdf":
            pdf_path = await asyncio.to_thread(export_to_pdf, html_path)
            return {
                "status": "success",
                "format": "pdf",
                "filename": os.path.basename(pdf_path),
                "download_path": pdf_path
            }
        elif req.format == "png":
            png_path = await asyncio.to_thread(export_to_png, html_path)
            return {
                "status": "success",
                "format": "png",
                "filename": os.path.basename(png_path),
                "download_path": png_path
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use 'pdf' or 'png'.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Visual generation scaffolding removed with the rest of the RAG pipeline.


def _build_system_instruction(custom_prompt: str, strict: bool) -> str:
    """Compose the system prompt sent to Gemini (or baked into a context cache)."""
    base = custom_prompt.strip() if custom_prompt else "You are a helpful and detailed scientific/medical study companion."
    if strict:
        rules = """1. You are a strict study companion that ONLY answers using the attached DOCUMENT.
2. If the answer is not in the document, respond exactly with: "I'm sorry, but I cannot find the answer to this question in your uploaded document. I am configured to strictly chat with your files only."
3. Under no circumstances use general knowledge, external information, or assumptions not directly supported by the document.
4. You MUST ALWAYS use rich, highly colorful Markdown to format your response. NEVER output plain text paragraphs.
5. DO NOT use any emojis in headings or text."""
    else:
        rules = """1. You are a helpful study companion. Prioritize answering using the attached DOCUMENT.
2. If the answer is not in the document, you may use your general scientific/medical knowledge.
3. Be transparent: if you use general knowledge rather than the document, state that clearly.
4. You MUST ALWAYS use rich, highly colorful Markdown to format your response. NEVER output plain text paragraphs.
5. DO NOT use any emojis in headings or text."""
    formatting = """

Use the following custom fenced code blocks whenever applicable:
- ```disease (disease:, presentation:, diagnosis:, treatment:, mnemonic:)
- ```drug (drug:, class:, moa:, side effects:, contraindications:)
- ```osce (station:, scenario:, history:, exam:, marks:)
- ```mnemonic (title:, letters:, meanings:)
- ```flashcard (front:, back:)
- ```clinical (case:, vignette:, question:, answer:)
- ```differential (title:, list of bullet points)

Use standard Markdown features extensively:
- Obsidian-style callouts: `> [!NOTE]`, `> [!WARNING]`, `> [!TIP]`, `> [!IMPORTANT]`
- KaTeX for math: `$inline$` or `$$block$$`
- Tables, bolding, lists."""
    return f"{base}\n\nGROUNDING RULES:\n{rules}{formatting}"


MIN_CACHE_CHARS = 4000  # Floor for Gemini 2.5 Flash context cache (~1024 input tokens)


@app.post("/api/chat/query")
async def chat_query(req: ChatQueryRequest):
    import hashlib
    import time as _time
    from services import gemini_cache
    from services.gemini_client import (
        get_rotator, rotator_status, RateLimitError, CacheNotFoundError,
    )

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    settings = load_custom_settings()
    active_provider = req.provider or settings.get("active_provider", "gemini")
    providers_cfg = settings.get("providers", {})

    # ── Per-provider key/model resolution ────────────────────────────────────
    provider_api_key  = None
    provider_model    = None
    provider_base_url = None

    if active_provider != "gemini":
        pcfg = providers_cfg.get(active_provider, {})
        keys = [k for k in pcfg.get("api_keys", []) if k]
        provider_api_key  = keys[0] if keys else None
        provider_model    = pcfg.get("model", "")
        provider_base_url = pcfg.get("base_url", "")

        if active_provider not in ("ollama",) and not provider_api_key:
            async def key_err_stream():
                yield sse("no_api_key", {"status": "no_api_key", "provider": active_provider})
            return StreamingResponse(
                key_err_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    # 1. Zero-state: no Gemini keys configured
    if active_provider == "gemini":
        try:
            rot = get_rotator()
            rot.reload_keys()
            if not rot.keys:
                raise ValueError("No Gemini keys")
        except Exception:
            async def key_err_stream():
                yield sse("no_api_key", {"status": "no_api_key"})
            return StreamingResponse(
                key_err_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    # 2. Session + doc lookup
    session = memory_layer.get_chat_session(req.session_id)
    doc_state = memory_layer.get_session_doc(req.session_id) or {}
    past_messages = session.get("messages", []) if session else []
    doc_text = doc_state.get("extracted_text")
    cache_name = doc_state.get("cache_name")
    cache_exp = doc_state.get("cache_expires_at") or 0
    cache_model_used = doc_state.get("cache_model")
    cache_sys_hash = doc_state.get("cache_system_prompt_hash")
    cache_key_id = doc_state.get("cache_api_key_id")

    # 3. Compose current system instruction
    current_model = (os.environ.get("GEMINI_MODEL")
                     or settings.get("gemini_model")
                     or "gemini-2.0-flash").strip()
    if current_model.startswith("models/"):
        current_model = current_model[7:]
    system_instruction = _build_system_instruction(settings.get("system_prompt", ""), req.strict)
    current_sys_hash = hashlib.sha256(system_instruction.encode("utf-8")).hexdigest()

    # 4. Invalidate stale cache (near-expiry, model swap, system-prompt swap)
    if cache_name and (
        _time.time() > cache_exp - 60
        or cache_model_used != current_model
        or cache_sys_hash != current_sys_hash
    ):
        try:
            owning_key = gemini_cache.find_key_by_id(cache_key_id) if cache_key_id else None
            await asyncio.to_thread(gemini_cache.delete, cache_name, owning_key)
        except Exception as e:
            logger.debug(f"[Chat] stale cache delete failed (ignored): {e}")
        memory_layer.clear_cache(req.session_id)
        cache_name = None
        cache_key_id = None

    # 5. Create cache when we have a big-enough doc and don't have one yet
    if (active_provider == "gemini" and doc_text and not cache_name
            and len(doc_text) >= MIN_CACHE_CHARS):
        try:
            cache_name, cache_exp, owning_key = await asyncio.to_thread(
                gemini_cache.create,
                current_model, doc_text, system_instruction, req.session_id, 1800,
            )
            cache_key_id = gemini_cache.key_id_for(owning_key)
            memory_layer.update_cache(
                req.session_id, cache_name, cache_exp, current_model,
                current_sys_hash, cache_key_id,
            )
            cache_model_used = current_model
        except Exception as e:
            logger.warning(f"[Chat] cache create failed, falling back to inline: {e}")
            cache_name = None
            cache_key_id = None

    # 6. Build the prompt + extra kwargs for the stream
    if active_provider != "gemini":
        # Non-Gemini providers: no context cache, just inline doc if present
        if doc_text:
            prompt = (f"DOCUMENT:\n\"\"\"\n{doc_text}\n\"\"\"\n\nQUESTION:\n{req.message}")
        else:
            prompt = req.message
        stream_kwargs = {
            "system_instruction": system_instruction,
            "api_key": provider_api_key,
            "model": provider_model,
            "base_url": provider_base_url or None,
        }
    elif cache_name and cache_key_id:
        prompt = req.message
        owning_key = gemini_cache.find_key_by_id(cache_key_id)
        if not owning_key:
            memory_layer.clear_cache(req.session_id)
            cache_name = None
            stream_kwargs = {"system_instruction": system_instruction}
        else:
            stream_kwargs = {
                "cached_content": cache_name,
                "pinned_api_key": owning_key,
                "pinned_model": cache_model_used,
            }
    elif doc_text:
        prompt = (f"DOCUMENT:\n\"\"\"\n{doc_text}\n\"\"\"\n\n"
                  f"QUESTION:\n{req.message}")
        stream_kwargs = {"system_instruction": system_instruction}
    else:
        prompt = req.message
        stream_kwargs = {"system_instruction": system_instruction}

    async def response_stream():
        full_reply = []
        cache_retried = False
        try:
            async for token in llm_service.generate_stream_async(
                prompt, provider=active_provider, **stream_kwargs,
            ):
                full_reply.append(token)
                yield sse("token", {"token": token})
        except CacheNotFoundError as cnf:
            # Cache vanished mid-stream (expired between our check and the call,
            # or was wiped externally). Clear it and retry once with the inline-doc path.
            logger.warning(f"[Chat] Cache 404 mid-stream — retrying inline: {cnf}")
            memory_layer.clear_cache(req.session_id)
            cache_retried = True
            inline_prompt = (f"DOCUMENT:\n\"\"\"\n{doc_text}\n\"\"\"\n\nQUESTION:\n{req.message}"
                             if doc_text else req.message)
            try:
                async for token in llm_service.generate_stream_async(
                    inline_prompt, provider=active_provider,
                    system_instruction=system_instruction,
                ):
                    full_reply.append(token)
                    yield sse("token", {"token": token})
            except Exception as retry_ex:
                yield sse("error", {"detail": f"retry after cache miss failed: {retry_ex}"})
                return
        except Exception as stream_ex:
            logger.error(f"[Chat] Streaming failed: {stream_ex}")
            rl = stream_ex if isinstance(stream_ex, RateLimitError) else None
            if rl is None:
                msg = str(stream_ex).lower()
                if any(s in msg for s in ("429", "rate limit", "resource_exhausted", "quota")):
                    snap = rotator_status()
                    rl = RateLimitError(
                        retry_in_seconds=snap.get("earliest_available_in", 30.0),
                        total_keys=snap.get("total_keys", 0),
                        available_keys=snap.get("available_keys", 0),
                        reason="quota_inferred_from_message",
                    )
            if rl is not None:
                try:
                    snap = rotator_status()
                except Exception:
                    snap = {"total_keys": rl.total_keys, "available_keys": rl.available_keys, "keys": [], "earliest_available_in": rl.retry_in_seconds}
                yield sse("rate_limit", {
                    "retry_in_seconds": rl.retry_in_seconds,
                    "total_keys": rl.total_keys,
                    "available_keys": rl.available_keys,
                    "reason": rl.reason,
                    "rotator": snap,
                    "provider": active_provider,
                })
            else:
                yield sse("error", {"detail": str(stream_ex)})
            return

        reply = "".join(full_reply)
        # Merge visual_types and legacy visual_type into one list (deduped)
        _types = list(req.visual_types or [])
        if req.visual_type and req.visual_type not in _types:
            _types.append(req.visual_type)

        visuals_list = []
        if reply and _types:
            try:
                from services import visual_engine
                _theme = req.theme or settings.get("visual_theme", "auto")
                async def _gen(vt):
                    try:
                        return await asyncio.to_thread(
                            visual_engine.generate_visual,
                            vt, req.message, req.session_id, reply, _theme,
                        )
                    except Exception as ve:
                        logger.warning(f"[Chat] visual '{vt}' failed (ignored): {ve}")
                        return None
                results = await asyncio.gather(*[_gen(vt) for vt in _types])
                visuals_list = [r for r in results if r is not None]
            except Exception as ve:
                logger.warning(f"[Chat] visual generation failed (ignored): {ve}")

        # Back-compat: single visual field = first item
        visual_meta = visuals_list[0] if visuals_list else None
        if reply:
            assistant_components = [{"type": "text", "content": reply}]
            assistant_msg = {"role": "assistant", "components": assistant_components}
            if visuals_list:
                assistant_msg["visuals"] = visuals_list
                assistant_msg["visual"] = visual_meta  # back-compat
            new_messages = past_messages + [
                {"role": "user", "components": [{"type": "text", "content": req.message}]},
                assistant_msg,
            ]
            title = session.get("title") if session else (req.message[:50] or "Untitled")
            try:
                memory_layer.save_chat_session(req.session_id, title, new_messages)
            except Exception as e:
                logger.error(f"[Chat] save_chat_session failed: {e}")
        yield sse("done", {"reply": reply, "visual": visual_meta, "visuals": visuals_list, "cache_retried": cache_retried})

    return StreamingResponse(
        response_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



if __name__ == "__main__":
    # Pass the app object directly (not "main:app" string) so uvicorn never
    # tries to re-import the module via sys.path — avoids failures when
    # launched as a subprocess from Tauri where the project root may not be
    # on sys.path. reload is disabled because object-form doesn't support it.
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_config=None if _headless else uvicorn.config.LOGGING_CONFIG,
        access_log=not _headless,
    )
