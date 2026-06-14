# ADHD Study Companion — Project Audit
**Date:** 2026-06-11  
**Codebase:** `F:\NotebookMG_COMPANION`  
**Stack:** FastAPI · SQLite · Ollama · Faster-Whisper · Kokoro TTS · Electron · React 19 · Three.js · Vite

---

## Project Purpose

Zero-VRAM gaming overlay that passively teaches study material while you play. Runs local LLM offline to pre-generate facts, then plays them via TTS during gaming with no GPU cost at runtime. Voice interaction supported via Whisper STT.

---

## Architecture Overview

```
run.bat
├── python main.py              ← FastAPI backend :8000
│   ├── /api/prep               extract docs → LLM → SQLite
│   ├── /api/mode               GAMING / WORK / BROWSE
│   ├── /ws/interact            voice I/O (STT → LLM → TTS)
│   ├── /mindmap                SVG knowledge graph
│   └── background_player       timed fact playback loop
│
├── npm run dev                 ← Vite dev server :5173
│
└── npx electron .             ← Frameless transparent overlay
    └── loads localhost:5173
        └── App.jsx             Three.js Neural Sphere (audio vis)
        └── FloatingCompanion   Study UI (NOT currently rendered)
```

---

## What Is Working

| Component | Status | Notes |
|---|---|---|
| FastAPI backend | **Working** | Health, mode switch, prep, mindmap all return 200 |
| SQLite lean_memory | **Working** | Upsert, spaced repetition query, play tracking |
| Ollama LLM | **Working** | `llama3.2:1b-instruct-q4_K_M`, `keep_alive=0` ejects model after each call |
| Content generator | **Working** | Key normalisation + `str()` cast prevents binding errors; no-op on bad JSON |
| Document extractor | **Working** | PPTX, PDF, DOCX, TXT → Node objects |
| `/api/prep` async task | **Working** | Fires background asyncio task, 5/5 nodes generated in test run |
| Ollama JSON fix | **Working** | Lowercase key normalisation catches `"Mnemonic"` vs `"mnemonic"` |
| `lean_memory` retry | **Working** | Failed nodes left empty so next prep run retries them |
| Electron window | **Configured** | Frameless, transparent, always-on-top, no taskbar |
| Three.js renderer | **Configured** | `alpha: true`, `setClearColor(0,0)`, no scene fog → transparent bg |
| `WebkitAppRegion: drag` | **Configured** | Glass panel drags window; buttons have `no-drag` override |
| `run.bat` | **Working** | Kills stale ports, boots all three processes, cleans up on exit |
| Mindmap endpoint | **Working** | Returns D3 SVG from study_nodes DB |

---

## Critical Bugs

### BUG-01 · Two frontends — study logic is disconnected
**Severity: CRITICAL**

`main.jsx` renders `App.jsx` (Three.js audio visualiser). `FloatingCompanion.jsx` contains ALL study functionality — WebSocket, voice recording, mode buttons, PREP trigger, fact display, TTS playback. It is not rendered anywhere.

The floating companion the user sees is a pretty sphere with no backend connection. Nothing is being taught.

**Fix:** Merge FloatingCompanion's study UI into App.jsx, or embed App.jsx's sphere as the visualiser inside FloatingCompanion and point `main.jsx` back to `FloatingCompanion`.

---

### BUG-02 · Click-through broken under Electron
**Severity: CRITICAL**

`useClickThrough.ts` calls `invoke('set_click_through')` — a Tauri command. The guard `"__TAURI_INTERNALS__" in window` silently no-ops under Electron. So:
- Mouse clicks on transparent sphere areas **do not pass through** to the game.
- No hover-based enable/disable of click-through happens at all.

**Fix:** Add Electron IPC for click-through. In `electron-main.cjs`:
```js
const { ipcMain } = require('electron');
ipcMain.on('set-click-through', (_, enabled) => {
  mainWindow.setIgnoreMouseEvents(enabled, { forward: true });
});
```
In a new `useClickThroughElectron.ts`, use `window.require('electron').ipcRenderer.send(...)`.

---

### BUG-03 · Hardware acceleration disabled but Three.js bloom runs on it
**Severity: HIGH**

`electron-main.cjs` calls `app.disableHardwareAcceleration()` to save VRAM. But `App.jsx` uses `UnrealBloomPass` via `EffectComposer`, which is heavily GPU-dependent. With CPU-only WebGL rendering, the bloom pass will render at 1–5 FPS on most machines.

**Fix:** Either:
- Re-enable hardware acceleration (bloom works, game VRAM risk is minimal for a frameless overlay), or
- Remove bloom (`composer` → plain `renderer.render()`) and keep HW accel disabled.

The VRAM-saving goal is served by `keep_alive=0` in Ollama, not by disabling Electron's GPU. Recommendation: **remove `app.disableHardwareAcceleration()`**.

---

### BUG-04 · EffectComposer may clear transparency
**Severity: HIGH**

`renderer.setClearColor(0x000000, 0)` sets alpha=0 on the raw renderer, but `EffectComposer` uses internal render targets that default to opaque black. The final composite blit may write black pixels over the transparent canvas, showing a black square behind the sphere.

**Fix:** After creating the composer:
```js
composer.renderToScreen = true;
renderer.autoClear = false;
```
And set the composer's render target to use alpha:
```js
const renderTarget = new THREE.WebGLRenderTarget(w, h, {
  format: THREE.RGBAFormat,
  type: THREE.HalfFloatType,
});
const composer = new EffectComposer(renderer, renderTarget);
```

---

### BUG-05 · OrbitControls conflict with drag region
**Severity: HIGH**

The glass panel has `WebkitAppRegion: drag`. But `OrbitControls` is attached to `renderer.domElement` (the canvas, which fills the whole window). When the user tries to drag the window by clicking the glass panel, OrbitControls intercepts the pointerdown event on the canvas underneath and rotates the sphere instead of moving the window.

**Fix:** Add `controls.enabled = false` when pointer is over the glass panel, or restrict OrbitControls to only activate on the canvas outside UI panels via pointer events CSS (`pointer-events: none` on canvas, `pointer-events: auto` on sphere area only).

---

## High-Priority Issues

### ISSUE-01 · Kokoro TTS not verified installed
**Severity: HIGH**

`background_player.py` calls `audio_service.synthesize()` on startup (lifespan → `bg_player.start()`). If Kokoro ONNX models are not at `data/models/kokoro/`, TTS fails silently and the background player loop runs but produces no audio. No error is surfaced to the user.

The companion is mute and gives no indication why.

**Required:** Download Kokoro ONNX model files to `data/models/kokoro/` before first run. Should be documented in README or auto-downloaded in lifespan startup.

---

### ISSUE-02 · Whisper first-run download during WS connection
**Severity: HIGH**

Whisper base model (~74 MB) downloads from HuggingFace on the first WebSocket audio packet. During download, the WS handler blocks for 30–60 seconds. Client receives no audio back, appears frozen.

**Fix:** Pre-download Whisper in the lifespan startup (non-blocking `asyncio.to_thread`):
```python
async with lifespan:
    asyncio.create_task(asyncio.to_thread(audio_service._ensure_whisper_loaded))
```

---

### ISSUE-03 · `background_player.py` imports Kokoro directly — no fallback
**Severity: HIGH**

If `kokoro` pip package is missing, `background_player.py` raises `ImportError` at import time, which crashes the FastAPI startup (lifespan fails). The entire backend goes down.

**Fix:** Wrap Kokoro import in try/except; fall back to Edge-TTS or silence with a logged warning.

---

### ISSUE-04 · `doc_sample` node fact starts with `{`
**Severity: MEDIUM**

The 1B model occasionally wraps its response in an outer JSON object:
```
{"The shortest war in history was between..."}
```
This renders as a broken fact string in TTS (it speaks the curly brace).

**Fix:** In `content_generator.py`, strip leading `{"` / trailing `"}` if the fact string starts with `{`:
```python
fact = result_lower.get("fact", "")
if isinstance(fact, str) and fact.startswith('{"'):
    fact = fact.strip('{"} ')
```

---

### ISSUE-05 · `session_stats` table is created but never used
**Severity: LOW**

`lean_memory.py` creates `session_stats` in `_init_db()` but no code reads or writes to it. Intended for per-session tracking (total questions answered, streak, etc.) but not implemented.

---

### ISSUE-06 · `SQLAlchemy` in requirements.txt but code uses raw `sqlite3`
**Severity: LOW**

`requirements.txt` lists `sqlalchemy` but `lean_memory.py` uses the stdlib `sqlite3` module directly. SQLAlchemy is never imported. Adds ~5 MB to install for no reason.

---

## Missing Features (Spec vs Reality)

| Spec Feature | File | Status |
|---|---|---|
| RAG vector search | `services/rag.py` | **Implemented, never called** — ChromaDB is fully built but no API endpoint calls it. `/api/prep` does not index into ChromaDB, only SQLite. |
| Vault indexer | `services/vault.py` | **Implemented, never called** — Multi-format extractor with manifest tracking exists but has no API endpoint or integration with main.py. |
| Provider router | `services/provider_router.py` | **Implemented, never called** — Hardware-aware cloud/local routing exists but `llm.py`, `audio.py` each hardcode their own providers. |
| Brain map / knowledge graph | `services/brain_map.py` | **Implemented, never called** — PySide6 graph visualiser exists but no UI trigger. |
| Hardware detection | `services/hardware_detector.py` | **Stub** — always returns `{tier: "cpu", vram_mb: 0}`. CUDA detection never runs. |
| `/api/prep/status` | `main.py` comment | **Missing** — comment in code says "not yet implemented". No way for frontend to know when prep finishes. |
| BROWSE mode behaviour | `background_player.py` | **Partial** — BROWSE sets 10-min interval but there is no browser extension or tab detection to trigger it automatically. |
| Correct/incorrect answer tracking | `lean_memory.py` | **Implemented** — `mark_question_answered()` exists. But nothing in `ws/interact` calls it when user responds to a question. |
| Spaced repetition scheduling | `lean_memory.py` | **Partial** — `ORDER BY times_played, (questions_asked - correct_answers), last_played` prioritises review but no SM-2 or proper SRS algorithm. |
| Floating companion visual | `FloatingCompanion.jsx` | **Disconnected** — Canvas orbital animation and full study UI exist but not rendered (main.jsx points to App.jsx). |

---

## Disconnected Services Map

```
services/
├── config.py           ← used by everything
├── lean_memory.py      ← used by main.py, background_player, content_generator ✓
├── content_generator.py← used by main.py /api/prep ✓
├── llm.py              ← used by content_generator, background_player ✓
├── audio.py            ← used by main.py ws/interact ✓
├── background_player.py← used by main.py lifespan ✓
├── extractor.py        ← used by main.py /api/prep ✓
├── visualization.py    ← used by main.py /mindmap ✓
├── hardware_detector.py← stub, unused by anything meaningful
├── rag.py              ← ORPHANED (ChromaDB vector search)
├── vault.py            ← ORPHANED (multi-format vault indexer)
├── provider_router.py  ← ORPHANED (hardware-aware routing)
└── brain_map.py        ← ORPHANED (PySide6 knowledge graph)
```

---

## File State Reference

| File | Lines | Last Modified Action |
|---|---|---|
| `main.py` | 179 | Rewritten — lifespan, ModeRequest, async prep, ws/interact |
| `services/lean_memory.py` | 111 | Fixed — retry filter includes `'Failed to parse content.'` |
| `services/content_generator.py` | 59 | Fixed — key normalisation, `str()` cast, no placeholder on failure |
| `services/llm.py` | 55 | Fixed — `keep_alive: 0`, model name `llama3.2:1b-instruct-q4_K_M` |
| `services/config.py` | 25 | Fixed — correct Ollama model name |
| `services/hardware_detector.py` | 15 | Created — stub only |
| `services/audio.py` | 434 | From spec — Whisper + Kokoro + Edge-TTS multi-engine |
| `services/background_player.py` | 90 | From spec — timed loop with mode-aware intervals |
| `services/extractor.py` | 154 | From spec — PPTX/PDF/DOCX/TXT Node extraction |
| `services/visualization.py` | 48 | From spec — mindmap SVG via D3 |
| `frontend/electron-main.cjs` | 55 | Updated — `backgroundColor: '#00000000'` |
| `frontend/src/App.jsx` | 476 | Replaced by user — Three.js Neural Sphere; patched for transparency |
| `frontend/src/FloatingCompanion.jsx` | 380 | From session — full study UI, **currently not rendered** |
| `frontend/src/main.jsx` | 11 | Changed — points to App.jsx (should be FloatingCompanion or merged) |
| `frontend/src/useWebSocket.ts` | 54 | Created — auto-reconnect WS hook |
| `frontend/src/useClickThrough.ts` | 27 | Created — Tauri only, **no-ops under Electron** |
| `run.bat` | 37 | Created — full launch sequence |

---

## Recommended Fix Order

1. **[CRITICAL]** Fix `main.jsx` — render `FloatingCompanion` with the Neural Sphere embedded as the background canvas, not standalone `App.jsx`. Study companion needs to show facts.
2. **[CRITICAL]** Fix Electron click-through — add `ipcMain`/`ipcRenderer` bridge for `setIgnoreMouseEvents`.
3. **[HIGH]** Remove `app.disableHardwareAcceleration()` — Three.js bloom is unrenderable on CPU.
4. **[HIGH]** Fix EffectComposer transparency — add RGBA render target to preserve alpha compositing.
5. **[HIGH]** Fix OrbitControls vs drag region conflict — disable controls on hover over UI panels.
6. **[HIGH]** Pre-warm Whisper in lifespan startup — prevents first-call 60s freeze.
7. **[HIGH]** Verify Kokoro install path and add fallback in `background_player.py`.
8. **[MEDIUM]** Strip `{` artifact from LLM facts in `content_generator.py`.
9. **[MEDIUM]** Add `/api/prep/status` endpoint so frontend knows when prep is done.
10. **[MEDIUM]** Wire `mark_question_answered()` into the WS interact loop.
11. **[LOW]** Remove `SQLAlchemy` from `requirements.txt`.
12. **[FUTURE]** Wire `rag.py` into `/api/prep` for semantic search on large vaults.
13. **[FUTURE]** Expose `vault.py` as `POST /api/vault/index` endpoint.
14. **[FUTURE]** Replace `hardware_detector.py` stub with real CUDA detection.

---

## Quick Test Commands

```bash
# Backend health
curl http://localhost:8000/

# Mode switch
curl -X POST http://localhost:8000/api/mode -H "Content-Type: application/json" -d "{\"mode\":\"GAMING\"}"

# Trigger prep (absolute path)
curl -X POST "http://localhost:8000/api/prep?folder=f:/NotebookMG_COMPANION/docs"

# DB state
python -c "import sqlite3; c=sqlite3.connect('f:/NotebookMG_COMPANION/data/companion.db'); [print(r) for r in c.execute('SELECT node_id, fact[:60] FROM study_nodes')]"

# Mindmap
curl http://localhost:8000/mindmap
```

---

## Environment Requirements

| Requirement | Status |
|---|---|
| Python 3.11+ | Required |
| `pip install -r requirements.txt` | Required |
| Ollama installed + running | Required (`ollama serve`) |
| `ollama pull llama3.2:1b-instruct-q4_K_M` | Required |
| Node.js 20+ | Required for Vite + Electron |
| `cd frontend && npm install` | Required |
| Kokoro ONNX model files in `data/models/kokoro/` | Required for TTS |
| Visual Studio Build Tools (C++ workload) | Required only for Tauri native build |
| Whisper base model (~74 MB) | Auto-downloads on first WS call |
