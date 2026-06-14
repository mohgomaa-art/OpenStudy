<div align="center">

<img src="docs/openstudy-logo-concept2-horizontal.svg" alt="OpenStudy" width="340" />

<br/>

**An AI-powered local study companion — built for medical students, designed for everyone.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tauri](https://img.shields.io/badge/Tauri-v2-24C8D8?logo=tauri)](https://tauri.app)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)

[**Download**](#installation) · [**Quick Start**](#quick-start) · [**Providers**](#ai-providers) · [**Screenshots**](#screenshots)

</div>

---

OpenStudy transforms your study notes into interactive visual learning experiences. It runs entirely on your machine, keeps your data private, and supports every major AI provider — from cloud APIs to local Ollama models.

---

## Features

- **19 Visual Templates** — Mind maps, flashcards, clinical vignettes, timelines, decision trees, concept webs, and more — generated as fully interactive HTML pages
- **Multi-Provider AI** — OpenAI, Anthropic, Google Gemini, Groq, OpenRouter, and local Ollama — switch providers in one click
- **Up to 10 API Keys per Provider** — Automatic round-robin rotation with rate-limit detection
- **Document Vault** — Upload PDFs, DOCX, PPTX, and images; ask questions grounded in your own files
- **Gemini Context Caching** — Large documents are cached at the API level, slashing token costs on repeated queries
- **6 Visual Themes** — Clinical, Nightshift, Botanica, Bloom, Solstice, Arcane — visuals auto-follow the app theme
- **Study Library** — Curated concept cards across subjects (Medicine, CS, History, Science, and more)
- **Export Chat** — Save your chat sessions as PDF or PNG
- **Native Desktop App** — Tauri v2 (Rust + React), custom title bar, system tray, transparent window
- **Privacy-first** — All your notes and documents stay on your machine

---

## AI Providers

| Provider | Models | Get API Key |
|---|---|---|
| **Google Gemini** | gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash, gemini-1.5-pro | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **OpenAI** | gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o1-mini | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **Anthropic** | claude-sonnet-4-6, claude-opus-4-8, claude-haiku-4-5 | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) |
| **Groq** | llama-3.3-70b, llama-3.1-8b, mixtral-8x7b, gemma2-9b | [console.groq.com/keys](https://console.groq.com/keys) |
| **OpenRouter** | 200+ models (GPT-4o, Claude, Llama, Mistral…) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Ollama** | Any locally running model | [ollama.com](https://ollama.com) — free, runs locally |

Configure providers in **Settings → Providers**. You can add up to 10 API keys per provider and the app rotates them automatically when one hits a rate limit.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, Tailwind CSS v4 |
| Desktop Shell | Tauri v2 (Rust) |
| Backend | FastAPI + Uvicorn (Python 3.11+) |
| LLM Routing | google-genai, openai, anthropic, groq, httpx |
| Document Parsing | PyMuPDF, python-docx, python-pptx |
| Persistence | SQLite (via `sqlite3`) |
| Export | Playwright (PDF / PNG) |
| Visuals | 19 standalone HTML templates, CSS variable theming, postMessage height/theme sync |

---

## Quick Start

### Prerequisites

- Python 3.11 or later
- Node.js 20 or later
- Rust + Cargo — [rustup.rs](https://rustup.rs)
- Windows: Visual Studio 2022 with **"Desktop development with C++"** workload

### 1. Clone the repo

```bash
git clone https://github.com/mohgomaa-art/NotebookMG.git
cd NotebookMG
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
```

### 4. Run

```bash
# Windows — from project root:
run.bat            # Launches Tauri desktop app (full native experience)
# OR
run-browser.bat    # Browser-only mode, no Rust build required
```

On first launch, open **Settings → Providers**, pick your provider, paste your API key, and click **Set as Active**.

---

## Installation (Pre-built)

Download the latest installer from [Releases](https://github.com/mohgomaa-art/NotebookMG/releases).

Run `OpenStudy_x.x.x_x64-setup.exe` — the bundled Python backend is included, no separate Python install needed.

---

## Build Your Own Installer

```bash
# 1. Bundle the Python backend
build_installer.bat          # produces dist/OpenStudyBackend.exe

# 2. Copy the exe into the Tauri project
copy dist\OpenStudyBackend.exe frontend\src-tauri\

# 3. Build the Tauri installer
cd frontend
npm run tauri build          # produces src-tauri/target/release/bundle/
```

---

## Project Structure

```
NotebookMG/
├── main.py                  # FastAPI backend entry point
├── requirements.txt
├── run.bat                  # Dev launcher (Tauri)
├── run-browser.bat          # Dev launcher (browser)
├── build_installer.bat      # PyInstaller bundler
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main React application
│   │   └── MarkdownViewer.jsx
│   ├── src-tauri/
│   │   ├── src/lib.rs       # Rust Tauri commands + backend spawner
│   │   └── tauri.conf.json
│   └── package.json
├── services/
│   ├── llm.py               # Multi-provider LLM router
│   ├── visual_engine.py     # Visual template generator
│   ├── lean_memory.py       # SQLite chat persistence
│   ├── config.py            # Settings read/write
│   ├── text_extract.py      # PDF/DOCX/PPTX extraction
│   ├── openai_client.py     # OpenAI / Groq / OpenRouter streaming
│   ├── anthropic_client.py  # Anthropic streaming
│   └── gemini_client.py     # Gemini streaming + context caching
└── data/                    # Local user data (gitignored)
    ├── visuals/             # Generated visual HTML files
    ├── uploads/             # Uploaded documents
    └── settings.json        # User configuration
```

---

## Screenshots

<table>
  <tr>
    <td width="50%"><img src="images/document-grounded-answer.png" width="100%" alt="Document-grounded chat answer"/><p align="center"><sub><b>Document-grounded chat</b><br/>Answers cite your uploaded files</sub></p></td>
    <td width="50%"><img src="images/mind-map-template.png" width="100%" alt="Mind map visual template"/><p align="center"><sub><b>Interactive mind maps</b><br/>Generated from your notes</sub></p></td>
  </tr>
  <tr>
    <td width="50%"><img src="images/flashcards-clinical-vignette.png" width="100%" alt="Flashcards and OSCE clinical vignette"/><p align="center"><sub><b>Flashcards & OSCE vignettes</b><br/>Memory aids and clinical practice cases</sub></p></td>
    <td width="50%"><img src="images/pathophysiology-flow-template.png" width="100%" alt="Pathophysiology flow template"/><p align="center"><sub><b>Pathophysiology flow</b><br/>Expandable step-by-step disease process</sub></p></td>
  </tr>
  <tr>
    <td width="50%"><img src="images/mnemonic-cards-template.png" width="100%" alt="Mnemonic cards template"/><p align="center"><sub><b>Mnemonic cards</b><br/>Visual recall aids for any topic</sub></p></td>
    <td width="50%"><img src="images/disease-profile-tables.png" width="100%" alt="Disease profile comparison tables"/><p align="center"><sub><b>Disease comparison tables</b><br/>Structured etiology and pathophysiology breakdowns</sub></p></td>
  </tr>
  <tr>
    <td width="50%"><img src="images/study-aids-mnemonics.png" width="100%" alt="Mnemonic study aids"/><p align="center"><sub><b>Categorized study aids</b><br/>Memory tools organized by topic</sub></p></td>
    <td width="50%"><img src="images/onboarding-decision-flow.png" width="100%" alt="Onboarding decision flow"/><p align="center"><sub><b>Guided onboarding</b><br/>Walks new users through the study cycle</sub></p></td>
  </tr>
</table>

---

## Contributing

Pull requests are welcome. For significant changes, please open an issue first to discuss the approach.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes
4. Open a pull request

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.

---

<div align="center">

Built by [Mohamed Gomaa](https://github.com/mohgomaa-art)

[GitHub](https://github.com/mohgomaa-art) · [Email](mailto:mohamelgomaa@gmail.com) · [Instagram](https://instagram.com/moh.gomaa.art) · [Facebook](https://facebook.com/moh.gomaa.art) · [X / Twitter](https://x.com/moh.gomaa.art)

</div>
