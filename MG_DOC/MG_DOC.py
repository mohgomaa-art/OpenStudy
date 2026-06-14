#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI Architect v20 - FIXED CTK EDITION
- GUI like v18.5 (CustomTkinter sidebar + pages)
- Fix: Load configs relative to script (no empty modes)
- Fix: Groq call with browser-like headers, no br encoding, show error body on 403
- Features: Smart Inputs (OCR/PDF/YT), Visual Engine (Mermaid->img), Exam Radar tags,
            Theme + Color scheme, Remix, HTML preview, Export PDF (WeasyPrint first).
"""

import os
import re
import json
import base64
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import requests
from PIL import Image

# Optional deps
try:
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

try:
    import PyPDF2
    PDF_READER_AVAILABLE = True
except Exception:
    PDF_READER_AVAILABLE = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_AVAILABLE = True
except Exception:
    YOUTUBE_AVAILABLE = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False

try:
    from weasyprint import HTML as WeasyHTML
    WEASYPRINT_AVAILABLE = True
except Exception:
    WEASYPRINT_AVAILABLE = False


APP_VERSION = "20.0-fixed-ctk"
FENCE = "`" * 3
BASE_DIR = Path(__file__).resolve().parent


# =========================
# JSON helpers
# =========================
def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        try:
            return path.read_text(encoding="utf-8-sig")
        except Exception:
            return path.read_text(errors="ignore")


def load_json_config(path: Path, default_data):
    try:
        if path.exists():
            return json.loads(safe_read_text(path))
    except Exception:
        pass
    return default_data


def save_json_config(path: Path, data) -> bool:
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def hex_to_rgb_str(hex_color: str) -> str:
    try:
        h = hex_color.lstrip("#")
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return f"{r}, {g}, {b}"
    except Exception:
        return "0, 0, 0"


def ensure_scheme_rgb(s: dict) -> dict:
    s = dict(s or {})
    if "primary" in s and "primary_rgb" not in s:
        s["primary_rgb"] = hex_to_rgb_str(s.get("primary", "#000000"))
    if "secondary" in s and "secondary_rgb" not in s:
        s["secondary_rgb"] = hex_to_rgb_str(s.get("secondary", "#000000"))
    if "accent" in s and "accent_rgb" not in s:
        s["accent_rgb"] = hex_to_rgb_str(s.get("accent", "#000000"))
    return s


# =========================
# Config defaults
# =========================
DEFAULT_MODELS = {
    "providers": {
        "groq": {
            "name": "Groq",
            "icon": "🔥",
            "api_url": "https://api.groq.com/openai/v1/chat/completions",
            "models": [
                {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "context": 128000},
                {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B (Instant)", "context": 128000},
            ],
        }
    }
}

DEFAULT_THEMES = {
    "themes": [
        {
            "id": "neon_glass",
            "name": "🔮 Neon Glassmorphism",
            "gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)",
            "card": "rgba(255, 255, 255, 0.08)",
            "border": "rgba(255, 255, 255, 0.18)",
            "text": "#e0e7ff",
            "heading": "#c7d2fe",
            "accent": "#818cf8",
            "glow": "0 0 40px rgba(129, 140, 248, 0.6), 0 0 80px rgba(129, 140, 248, 0.3)",
            "highlight": "linear-gradient(120deg, rgba(129, 140, 248, 0.3), rgba(165, 180, 252, 0.6))"
        },
        {
            "id": "cyber_matrix",
            "name": "⚡ Cyber Matrix",
            "gradient": "linear-gradient(135deg, #0a0e27 0%, #1a0f2e 50%, #0f0a20 100%)",
            "card": "rgba(0, 255, 159, 0.05)",
            "border": "rgba(0, 255, 159, 0.3)",
            "text": "#00ff9f",
            "heading": "#00ffff",
            "accent": "#ff00ff",
            "glow": "0 0 30px rgba(0, 255, 159, 0.8), 0 0 60px rgba(0, 255, 255, 0.4)",
            "highlight": "linear-gradient(120deg, rgba(0, 255, 159, 0.2), rgba(255, 0, 255, 0.3))"
        },
        {
            "id": "aurora_dream",
            "name": "🌈 Aurora Dream",
            "gradient": "linear-gradient(135deg, #a8edea 0%, #fed6e3 33%, #f5efef 66%, #c2e9fb 100%)",
            "card": "rgba(255, 255, 255, 0.7)",
            "border": "rgba(168, 237, 234, 0.5)",
            "text": "#1e3a8a",
            "heading": "#6366f1",
            "accent": "#ec4899",
            "glow": "0 0 50px rgba(236, 72, 153, 0.4)",
            "highlight": "linear-gradient(120deg, rgba(168, 237, 234, 0.5), rgba(236, 72, 153, 0.5))"
        },
        {
            "id": "dark_premium",
            "name": "💎 Dark Premium",
            "gradient": "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f1e 100%)",
            "card": "rgba(255, 255, 255, 0.03)",
            "border": "rgba(212, 175, 55, 0.3)",
            "text": "#e5e7eb",
            "heading": "#fbbf24",
            "accent": "#d4af37",
            "glow": "0 0 40px rgba(212, 175, 55, 0.5)",
            "highlight": "linear-gradient(120deg, rgba(212, 175, 55, 0.2), rgba(251, 191, 36, 0.3))"
        },
        {
            "id": "ocean_depth",
            "name": "🌊 Ocean Depth",
            "gradient": "linear-gradient(135deg, #0c4a6e 0%, #075985 33%, #0e7490 66%, #06b6d4 100%)",
            "card": "rgba(6, 182, 212, 0.08)",
            "border": "rgba(103, 232, 249, 0.3)",
            "text": "#cffafe",
            "heading": "#67e8f9",
            "accent": "#22d3ee",
            "glow": "0 0 50px rgba(34, 211, 238, 0.6)",
            "highlight": "linear-gradient(120deg, rgba(34, 211, 238, 0.3), rgba(103, 232, 249, 0.5))"
        },
        {
            "id": "sunset_paradise",
            "name": "🌅 Sunset Paradise",
            "gradient": "linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 25%, #c44569 50%, #6c5ce7 75%, #a29bfe 100%)",
            "card": "rgba(255, 255, 255, 0.1)",
            "border": "rgba(255, 107, 107, 0.4)",
            "text": "#fff1f2",
            "heading": "#fecaca",
            "accent": "#fb7185",
            "glow": "0 0 60px rgba(251, 113, 133, 0.7)",
            "highlight": "linear-gradient(120deg, rgba(255, 107, 107, 0.4), rgba(162, 155, 254, 0.4))"
        },
        {
            "id": "forest_mystic",
            "name": "🌲 Forest Mystic",
            "gradient": "linear-gradient(135deg, #0f2027 0%, #203a43 33%, #2c5364 66%, #134e4a 100%)",
            "card": "rgba(16, 185, 129, 0.08)",
            "border": "rgba(52, 211, 153, 0.3)",
            "text": "#d1fae5",
            "heading": "#6ee7b7",
            "accent": "#34d399",
            "glow": "0 0 45px rgba(52, 211, 153, 0.6)",
            "highlight": "linear-gradient(120deg, rgba(16, 185, 129, 0.3), rgba(110, 231, 183, 0.4))"
        },
        {
            "id": "royal_purple",
            "name": "👑 Royal Purple",
            "gradient": "linear-gradient(135deg, #2e1065 0%, #4c1d95 33%, #6b21a8 66%, #7c3aed 100%)",
            "card": "rgba(196, 181, 253, 0.08)",
            "border": "rgba(196, 181, 253, 0.3)",
            "text": "#ede9fe",
            "heading": "#c4b5fd",
            "accent": "#a78bfa",
            "glow": "0 0 50px rgba(167, 139, 250, 0.7)",
            "highlight": "linear-gradient(120deg, rgba(124, 58, 237, 0.3), rgba(196, 181, 253, 0.4))"
        },
        {
            "id": "sakura_zen",
            "name": "🌸 Sakura Zen",
            "gradient": "linear-gradient(135deg, #fce7f3 0%, #fbcfe8 33%, #f9a8d4 66%, #f472b6 100%)",
            "card": "rgba(255, 255, 255, 0.6)",
            "border": "rgba(249, 168, 212, 0.4)",
            "text": "#831843",
            "heading": "#be185d",
            "accent": "#ec4899",
            "glow": "0 0 40px rgba(236, 72, 153, 0.5)",
            "highlight": "linear-gradient(120deg, rgba(249, 168, 212, 0.4), rgba(244, 114, 182, 0.5))"
        },
        {
            "id": "v20_midnight_ink",
            "name": "🖋️ Midnight Ink (v20)",
            "gradient": "linear-gradient(135deg, #0b1220 0%, #111827 50%, #0b1220 100%)",
            "card": "rgba(255, 255, 255, 0.04)",
            "border": "rgba(148, 163, 184, 0.18)",
            "text": "#e5e7eb",
            "heading": "#ffffff",
            "accent": "#22d3ee",
            "glow": "0 0 45px rgba(34, 211, 238, 0.35)",
            "highlight": "linear-gradient(120deg, rgba(34, 211, 238, 0.18), rgba(167, 139, 250, 0.14))"
        },
        {
            "id": "v20_desert_gold",
            "name": "🏜️ Desert Gold (v20)",
            "gradient": "linear-gradient(135deg, #7c2d12 0%, #b45309 50%, #f59e0b 100%)",
            "card": "rgba(255, 255, 255, 0.10)",
            "border": "rgba(254, 215, 170, 0.35)",
            "text": "#fff7ed",
            "heading": "#ffedd5",
            "accent": "#fde68a",
            "glow": "0 0 55px rgba(245, 158, 11, 0.45)",
            "highlight": "linear-gradient(120deg, rgba(245, 158, 11, 0.25), rgba(251, 113, 133, 0.18))"
        },
        {
            "id": "v20_clinic_clean",
            "name": "🏥 Clinic Clean (v20)",
            "gradient": "linear-gradient(135deg, #e0f2fe 0%, #ffffff 50%, #ecfeff 100%)",
            "card": "rgba(255, 255, 255, 0.85)",
            "border": "rgba(14, 165, 233, 0.18)",
            "text": "#0f172a",
            "heading": "#111827",
            "accent": "#0284c7",
            "glow": "0 0 40px rgba(2, 132, 199, 0.22)",
            "highlight": "linear-gradient(120deg, rgba(2, 132, 199, 0.16), rgba(34, 197, 94, 0.12))"
        },
        {
            "id": "v20_rose_quartz",
            "name": "🪷 Rose Quartz (v20)",
            "gradient": "linear-gradient(135deg, #fff1f2 0%, #ffe4e6 50%, #fdf2f8 100%)",
            "card": "rgba(255, 255, 255, 0.75)",
            "border": "rgba(219, 39, 119, 0.22)",
            "text": "#500724",
            "heading": "#831843",
            "accent": "#db2777",
            "glow": "0 0 45px rgba(219, 39, 119, 0.22)",
            "highlight": "linear-gradient(120deg, rgba(219, 39, 119, 0.18), rgba(251, 191, 36, 0.12))"
        },
        {
            "id": "v20_arctic_signal",
            "name": "📡 Arctic Signal (v20)",
            "gradient": "linear-gradient(135deg, #082f49 0%, #0c4a6e 50%, #06b6d4 100%)",
            "card": "rgba(6, 182, 212, 0.10)",
            "border": "rgba(103, 232, 249, 0.35)",
            "text": "#cffafe",
            "heading": "#ecfeff",
            "accent": "#67e8f9",
            "glow": "0 0 55px rgba(103, 232, 249, 0.45)",
            "highlight": "linear-gradient(120deg, rgba(103, 232, 249, 0.22), rgba(167, 139, 250, 0.16))"
        },
        {
            "id": "v20_graphite_luxe",
            "name": "🩶 Graphite Luxe (v20)",
            "gradient": "linear-gradient(135deg, #111827 0%, #1f2937 50%, #0b1220 100%)",
            "card": "rgba(255, 255, 255, 0.035)",
            "border": "rgba(255, 255, 255, 0.10)",
            "text": "#e5e7eb",
            "heading": "#f9fafb",
            "accent": "#a78bfa",
            "glow": "0 0 45px rgba(167, 139, 250, 0.32)",
            "highlight": "linear-gradient(120deg, rgba(167, 139, 250, 0.18), rgba(34, 211, 238, 0.14))"
        },
        {
            "id": "v20_orchid_wave",
            "name": "🌺 Orchid Wave (v20)",
            "gradient": "linear-gradient(135deg, #2e1065 0%, #7c3aed 50%, #22d3ee 100%)",
            "card": "rgba(196, 181, 253, 0.10)",
            "border": "rgba(34, 211, 238, 0.26)",
            "text": "#ede9fe",
            "heading": "#ffffff",
            "accent": "#22d3ee",
            "glow": "0 0 60px rgba(34, 211, 238, 0.42)",
            "highlight": "linear-gradient(120deg, rgba(124, 58, 237, 0.22), rgba(34, 211, 238, 0.18))"
        },
        {
            "id": "v20_emerald_study",
            "name": "📚 Emerald Study (v20)",
            "gradient": "linear-gradient(135deg, #064e3b 0%, #059669 50%, #10b981 100%)",
            "card": "rgba(16, 185, 129, 0.10)",
            "border": "rgba(167, 243, 208, 0.28)",
            "text": "#d1fae5",
            "heading": "#ecfdf5",
            "accent": "#34d399",
            "glow": "0 0 55px rgba(52, 211, 153, 0.40)",
            "highlight": "linear-gradient(120deg, rgba(52, 211, 153, 0.22), rgba(251, 191, 36, 0.14))"
        },
        {
            "id": "v20_solar_focus",
            "name": "☀️ Solar Focus (v20)",
            "gradient": "linear-gradient(135deg, #0f172a 0%, #111827 50%, #f59e0b 100%)",
            "card": "rgba(245, 158, 11, 0.08)",
            "border": "rgba(251, 191, 36, 0.30)",
            "text": "#f8fafc",
            "heading": "#ffffff",
            "accent": "#fbbf24",
            "glow": "0 0 60px rgba(251, 191, 36, 0.38)",
            "highlight": "linear-gradient(120deg, rgba(251, 191, 36, 0.20), rgba(34, 211, 238, 0.12))"
        },
        {
            "id": "v20_blueprint",
            "name": "🧩 Blueprint Grid (v20)",
            "gradient": "linear-gradient(135deg, #0b1220 0%, #0c4a6e 50%, #111827 100%)",
            "card": "rgba(59, 130, 246, 0.08)",
            "border": "rgba(59, 130, 246, 0.22)",
            "text": "#e5e7eb",
            "heading": "#ffffff",
            "accent": "#60a5fa",
            "glow": "0 0 55px rgba(96, 165, 250, 0.36)",
            "highlight": "linear-gradient(120deg, rgba(96, 165, 250, 0.16), rgba(34, 211, 238, 0.12))"
        }
    ]
}

DEFAULT_COLORS = {
    "color_schemes": [
        {
            "id": "scheme_1",
            "name": "🎨 Vibrant Professional",
            "primary": "#3b82f6",
            "secondary": "#8b5cf6",
            "accent": "#ec4899",
            "background": "#ffffff",
            "text": "#1f2937",
            "heading": "#111827",
            "link": "#2563eb",
            "border": "#e5e7eb",
            "card_bg": "#f9fafb",
            "primary_rgb": "59, 130, 246",
            "secondary_rgb": "139, 92, 246",
            "accent_rgb": "236, 72, 153"
        },
        {
            "id": "scheme_2",
            "name": "🌙 Dark Elegance",
            "primary": "#60a5fa",
            "secondary": "#a78bfa",
            "accent": "#fbbf24",
            "background": "#0f172a",
            "text": "#e2e8f0",
            "heading": "#f1f5f9",
            "link": "#60a5fa",
            "border": "#334155",
            "card_bg": "#1e293b",
            "primary_rgb": "96, 165, 250",
            "secondary_rgb": "167, 139, 250",
            "accent_rgb": "251, 191, 36"
        },
        {
            "id": "scheme_3",
            "name": "🌿 Nature Fresh",
            "primary": "#10b981",
            "secondary": "#14b8a6",
            "accent": "#f59e0b",
            "background": "#f0fdf4",
            "text": "#064e3b",
            "heading": "#022c22",
            "link": "#059669",
            "border": "#bbf7d0",
            "card_bg": "#dcfce7",
            "primary_rgb": "16, 185, 129",
            "secondary_rgb": "20, 184, 166",
            "accent_rgb": "245, 158, 11"
        },
        {
            "id": "scheme_4",
            "name": "🔥 Warm Sunset",
            "primary": "#f97316",
            "secondary": "#ef4444",
            "accent": "#fbbf24",
            "background": "#fffbeb",
            "text": "#78350f",
            "heading": "#451a03",
            "link": "#ea580c",
            "border": "#fed7aa",
            "card_bg": "#fef3c7",
            "primary_rgb": "249, 115, 22",
            "secondary_rgb": "239, 68, 68",
            "accent_rgb": "251, 191, 36"
        },
        {
            "id": "scheme_5",
            "name": "💎 Royal Purple",
            "primary": "#7c3aed",
            "secondary": "#a855f7",
            "accent": "#ec4899",
            "background": "#faf5ff",
            "text": "#581c87",
            "heading": "#3b0764",
            "link": "#7c3aed",
            "border": "#e9d5ff",
            "card_bg": "#f3e8ff",
            "primary_rgb": "124, 58, 237",
            "secondary_rgb": "168, 85, 247",
            "accent_rgb": "236, 72, 153"
        },
        {
            "id": "scheme_6",
            "name": "🌊 Ocean Blue",
            "primary": "#0ea5e9",
            "secondary": "#06b6d4",
            "accent": "#6366f1",
            "background": "#f0f9ff",
            "text": "#0c4a6e",
            "heading": "#082f49",
            "link": "#0284c7",
            "border": "#bae6fd",
            "card_bg": "#e0f2fe",
            "primary_rgb": "14, 165, 233",
            "secondary_rgb": "6, 182, 212",
            "accent_rgb": "99, 102, 241"
        },
        {
            "id": "scheme_7",
            "name": "🌸 Soft Pink",
            "primary": "#ec4899",
            "secondary": "#f472b6",
            "accent": "#a855f7",
            "background": "#fdf2f8",
            "text": "#831843",
            "heading": "#500724",
            "link": "#db2777",
            "border": "#fbcfe8",
            "card_bg": "#fce7f3",
            "primary_rgb": "236, 72, 153",
            "secondary_rgb": "244, 114, 182",
            "accent_rgb": "168, 85, 247"
        },
        {
            "id": "scheme_8",
            "name": "⚡ Electric Neon",
            "primary": "#22d3ee",
            "secondary": "#a78bfa",
            "accent": "#fb923c",
            "background": "#0a0e27",
            "text": "#e0e7ff",
            "heading": "#f0f9ff",
            "link": "#22d3ee",
            "border": "#1e293b",
            "card_bg": "#1e1b4b",
            "primary_rgb": "34, 211, 238",
            "secondary_rgb": "167, 139, 250",
            "accent_rgb": "251, 146, 60"
        },
        {
            "id": "scheme_9",
            "name": "🍁 Autumn Warm",
            "primary": "#dc2626",
            "secondary": "#ea580c",
            "accent": "#ca8a04",
            "background": "#fffbeb",
            "text": "#78350f",
            "heading": "#431407",
            "link": "#dc2626",
            "border": "#fcd34d",
            "card_bg": "#fef3c7",
            "primary_rgb": "220, 38, 38",
            "secondary_rgb": "234, 88, 12",
            "accent_rgb": "202, 138, 4"
        },
        {
            "id": "scheme_10",
            "name": "🌌 Space Gray",
            "primary": "#6b7280",
            "secondary": "#9ca3af",
            "accent": "#60a5fa",
            "background": "#f9fafb",
            "text": "#374151",
            "heading": "#1f2937",
            "link": "#4b5563",
            "border": "#d1d5db",
            "card_bg": "#f3f4f6",
            "primary_rgb": "107, 114, 128",
            "secondary_rgb": "156, 163, 175",
            "accent_rgb": "96, 165, 250"
        },
        {
            "id": "scheme_11",
            "name": "🎭 Deep Indigo",
            "primary": "#4f46e5",
            "secondary": "#6366f1",
            "accent": "#fbbf24",
            "background": "#f0f9ff",
            "text": "#1e1b4b",
            "heading": "#3730a3",
            "link": "#4f46e5",
            "border": "#c7d2fe",
            "card_bg": "#eef2ff",
            "primary_rgb": "79, 70, 229",
            "secondary_rgb": "99, 102, 241",
            "accent_rgb": "251, 191, 36"
        },
        {
            "id": "scheme_12",
            "name": "🏔️ Mountain Stone",
            "primary": "#64748b",
            "secondary": "#475569",
            "accent": "#f59e0b",
            "background": "#f8fafc",
            "text": "#334155",
            "heading": "#0f172a",
            "link": "#64748b",
            "border": "#cbd5e1",
            "card_bg": "#f1f5f9",
            "primary_rgb": "100, 116, 139",
            "secondary_rgb": "71, 85, 105",
            "accent_rgb": "245, 158, 11"
        },
        {
            "id": "scheme_13",
            "name": "💚 Emerald Dream",
            "primary": "#059669",
            "secondary": "#10b981",
            "accent": "#f97316",
            "background": "#ecfdf5",
            "text": "#065f46",
            "heading": "#064e3b",
            "link": "#047857",
            "border": "#a7f3d0",
            "card_bg": "#d1fae5",
            "primary_rgb": "5, 150, 105",
            "secondary_rgb": "16, 185, 129",
            "accent_rgb": "249, 115, 22"
        },
        {
            "id": "scheme_14",
            "name": "🎨 Coral Reef",
            "primary": "#f43f5e",
            "secondary": "#fb7185",
            "accent": "#7c3aed",
            "background": "#fff5f7",
            "text": "#831843",
            "heading": "#500724",
            "link": "#e11d48",
            "border": "#fbcfe8",
            "card_bg": "#fce7f3",
            "primary_rgb": "244, 63, 94",
            "secondary_rgb": "251, 113, 133",
            "accent_rgb": "124, 58, 237"
        },
        {
            "id": "scheme_15",
            "name": "🌟 Golden Hour",
            "primary": "#d97706",
            "secondary": "#f59e0b",
            "accent": "#ec4899",
            "background": "#fffbeb",
            "text": "#78350f",
            "heading": "#451a03",
            "link": "#b45309",
            "border": "#fde68a",
            "card_bg": "#fef3c7",
            "primary_rgb": "217, 119, 6",
            "secondary_rgb": "245, 158, 11",
            "accent_rgb": "236, 72, 153"
        },
        {
            "id": "scheme_16",
            "name": "🚀 Cyber Blue",
            "primary": "#0284c7",
            "secondary": "#0ea5e9",
            "accent": "#14b8a6",
            "background": "#f0f9ff",
            "text": "#0c2d4a",
            "heading": "#082f49",
            "link": "#0369a1",
            "border": "#7dd3fc",
            "card_bg": "#cffafe",
            "primary_rgb": "2, 132, 199",
            "secondary_rgb": "14, 165, 233",
            "accent_rgb": "20, 184, 166"
        },
        {
            "id": "scheme_17",
            "name": "💜 Lavender Mist",
            "primary": "#9333ea",
            "secondary": "#a855f7",
            "accent": "#f472b6",
            "background": "#faf5ff",
            "text": "#581c87",
            "heading": "#3b0764",
            "link": "#7e22ce",
            "border": "#ddd6fe",
            "card_bg": "#f3e8ff",
            "primary_rgb": "147, 51, 234",
            "secondary_rgb": "168, 85, 247",
            "accent_rgb": "244, 114, 182"
        },
        {
            "id": "scheme_18",
            "name": "🌊 Teal Oasis",
            "primary": "#0d9488",
            "secondary": "#14b8a6",
            "accent": "#fbbf24",
            "background": "#f0fdfa",
            "text": "#134e4a",
            "heading": "#0f2f2d",
            "link": "#0f766e",
            "border": "#99f6e4",
            "card_bg": "#ccfbf1",
            "primary_rgb": "13, 148, 136",
            "secondary_rgb": "20, 184, 166",
            "accent_rgb": "251, 191, 36"
        },
        {
            "id": "scheme_19",
            "name": "🎯 Bold Red",
            "primary": "#dc2626",
            "secondary": "#ef4444",
            "accent": "#fbbf24",
            "background": "#fef2f2",
            "text": "#7f1d1d",
            "heading": "#450a0a",
            "link": "#b91c1c",
            "border": "#fecaca",
            "card_bg": "#fee2e2",
            "primary_rgb": "220, 38, 38",
            "secondary_rgb": "239, 68, 68",
            "accent_rgb": "251, 191, 36"
        },
        {
            "id": "scheme_20",
            "name": "🌈 Vibrant Fusion",
            "primary": "#7c3aed",
            "secondary": "#06b6d4",
            "accent": "#f97316",
            "background": "#ffffff",
            "text": "#1f2937",
            "heading": "#111827",
            "link": "#7c3aed",
            "border": "#e5e7eb",
            "card_bg": "#f9fafb",
            "primary_rgb": "124, 58, 237",
            "secondary_rgb": "6, 182, 212",
            "accent_rgb": "249, 115, 22"
        },
        {
            "id": "scheme_21",
            "name": "🧊 Glacier Mint",
            "primary": "#22c55e",
            "secondary": "#06b6d4",
            "accent": "#a3e635",
            "background": "#ecfeff",
            "text": "#064e3b",
            "heading": "#022c22",
            "link": "#16a34a",
            "border": "#a7f3d0",
            "card_bg": "#cffafe",
            "primary_rgb": "34, 197, 94",
            "secondary_rgb": "6, 182, 212",
            "accent_rgb": "163, 230, 53"
        },
        {
            "id": "scheme_22",
            "name": "🪐 Cosmic Violet",
            "primary": "#8b5cf6",
            "secondary": "#22d3ee",
            "accent": "#f472b6",
            "background": "#0b1220",
            "text": "#e5e7eb",
            "heading": "#ffffff",
            "link": "#a78bfa",
            "border": "#334155",
            "card_bg": "#111827",
            "primary_rgb": "139, 92, 246",
            "secondary_rgb": "34, 211, 238",
            "accent_rgb": "244, 114, 182"
        },
        {
            "id": "scheme_23",
            "name": "🧡 Amber Tech",
            "primary": "#f59e0b",
            "secondary": "#f97316",
            "accent": "#0ea5e9",
            "background": "#0f172a",
            "text": "#e2e8f0",
            "heading": "#f8fafc",
            "link": "#fb923c",
            "border": "#334155",
            "card_bg": "#111827",
            "primary_rgb": "245, 158, 11",
            "secondary_rgb": "249, 115, 22",
            "accent_rgb": "14, 165, 233"
        },
        {
            "id": "scheme_24",
            "name": "🫧 Pearl Blue",
            "primary": "#38bdf8",
            "secondary": "#6366f1",
            "accent": "#22c55e",
            "background": "#f8fafc",
            "text": "#0f172a",
            "heading": "#111827",
            "link": "#0ea5e9",
            "border": "#e2e8f0",
            "card_bg": "#ffffff",
            "primary_rgb": "56, 189, 248",
            "secondary_rgb": "99, 102, 241",
            "accent_rgb": "34, 197, 94"
        },
        {
            "id": "scheme_25",
            "name": "🩶 Graphite Pro",
            "primary": "#111827",
            "secondary": "#374151",
            "accent": "#22d3ee",
            "background": "#ffffff",
            "text": "#111827",
            "heading": "#0b1220",
            "link": "#111827",
            "border": "#e5e7eb",
            "card_bg": "#f9fafb",
            "primary_rgb": "17, 24, 39",
            "secondary_rgb": "55, 65, 81",
            "accent_rgb": "34, 211, 238"
        },
        {
            "id": "scheme_26",
            "name": "🪷 Lotus Rose",
            "primary": "#db2777",
            "secondary": "#fb7185",
            "accent": "#fbbf24",
            "background": "#fff1f2",
            "text": "#500724",
            "heading": "#831843",
            "link": "#be185d",
            "border": "#fecdd3",
            "card_bg": "#ffe4e6",
            "primary_rgb": "219, 39, 119",
            "secondary_rgb": "251, 113, 133",
            "accent_rgb": "251, 191, 36"
        },
        {
            "id": "scheme_27",
            "name": "🌵 Desert Lime",
            "primary": "#84cc16",
            "secondary": "#f59e0b",
            "accent": "#06b6d4",
            "background": "#fffbeb",
            "text": "#365314",
            "heading": "#1a2e05",
            "link": "#65a30d",
            "border": "#fde68a",
            "card_bg": "#fef3c7",
            "primary_rgb": "132, 204, 22",
            "secondary_rgb": "245, 158, 11",
            "accent_rgb": "6, 182, 212"
        },
        {
            "id": "scheme_28",
            "name": "🧪 Lab Cyan",
            "primary": "#06b6d4",
            "secondary": "#0ea5e9",
            "accent": "#f43f5e",
            "background": "#ecfeff",
            "text": "#0c4a6e",
            "heading": "#082f49",
            "link": "#0891b2",
            "border": "#bae6fd",
            "card_bg": "#cffafe",
            "primary_rgb": "6, 182, 212",
            "secondary_rgb": "14, 165, 233",
            "accent_rgb": "244, 63, 94"
        },
        {
            "id": "scheme_29",
            "name": "🧿 Sapphire Night",
            "primary": "#2563eb",
            "secondary": "#1d4ed8",
            "accent": "#fbbf24",
            "background": "#0b1220",
            "text": "#e5e7eb",
            "heading": "#ffffff",
            "link": "#60a5fa",
            "border": "#1f2937",
            "card_bg": "#111827",
            "primary_rgb": "37, 99, 235",
            "secondary_rgb": "29, 78, 216",
            "accent_rgb": "251, 191, 36"
        },
        {
            "id": "scheme_30",
            "name": "🧯 Rescue Orange",
            "primary": "#ea580c",
            "secondary": "#dc2626",
            "accent": "#22c55e",
            "background": "#fff7ed",
            "text": "#431407",
            "heading": "#7c2d12",
            "link": "#c2410c",
            "border": "#fed7aa",
            "card_bg": "#ffedd5",
            "primary_rgb": "234, 88, 12",
            "secondary_rgb": "220, 38, 38",
            "accent_rgb": "34, 197, 94"
        }
    ]
}

# Supports BOTH schemas:
# A) {"modes":[{id,name,description,prompt},...]}  (your big prompts_config.json) [file:5]
# B) {"strict":{"name":..,"prompt":..}, "summarizer":{...}} (v18.5 style) [file:13]
DEFAULT_PROMPTS_A = {
    "modes": [
        {
            "id": "strict",
            "name": "📋 Strict Preserve",
            "description": "تنسيق منظم بدون تغيير المعنى",
            "prompt": "You are an expert document formatter.\n\nRules:\n- Preserve meaning exactly.\n- Output clean HTML only.\n- Use headings, bullet lists, and tables when helpful.\n- Do not add extra facts.\n- If you create a diagram, use a ```mermaid\n"
        },
        {
            "id": "explainer",
            "name": "🎓 Deep Explainer",
            "description": "شرح مبسط وعميق",
            "prompt": "You are a senior educator.\n\nOutput requirements:\n- Output clean HTML.\n- Use short sections with clear headings.\n- Use examples briefly.\n- Use tables for comparisons.\n- Add a Mermaid flowchart if the process has steps.\n- Mark high-yield items with [🔥 EXAM_TIP].\n- Mark key definitions with [💡 KEY_POINT].\n"
        },
        {
            "id": "mcq",
            "name": "❓ MCQ Generator",
            "description": "أسئلة اختيار من متعدد",
            "prompt": "Create MCQs from the user's content.\n\nOutput as HTML.\n- Provide 10-20 questions.\n- Include answer key at the end.\n- Mark the most exam-relevant questions with [🔥 EXAM_TIP].\n"
        },
        {
            "id": "summarizer",
            "name": "📝 Smart Summary",
            "description": "تلخيص ذكي",
            "prompt": "Summarize the user's content.\n\nOutput as HTML.\n- Use headings and bullet lists.\n- Include a short 'Key Points' section.\n- Mark must-know definitions with [💡 KEY_POINT].\n"
        },
        {
            "id": "flashcards",
            "name": "🎴 Flashcards",
            "description": "بطاقات مراجعة",
            "prompt": "Turn the user's content into flashcards.\n\nOutput as HTML.\n- Use Q/A cards.\n- Mark the highest-yield cards with [🔥 EXAM_TIP].\n"
        },
        {
            "id": "mindmap",
            "name": "🧠 Mind Map Generator",
            "description": "Mindmap mermaid",
            "prompt": "Create a mind map from the user's content.\n\nOutput as HTML.\n- Include a ```mermaid\n"
        },
        {
            "id": "flowchart",
            "name": "📊 Flowchart Creator",
            "description": "Flowchart mermaid",
            "prompt": "Create a flowchart from the user's content.\n\nOutput as HTML.\n- Include a ```mermaid\n"
        },
        {
            "id": "visual_summary",
            "name": "✨ Visual Summary Pro",
            "description": "تلخيص بصري مع جداول/رسومات عند الحاجة",
            "prompt": "Produce a modern visual summary.\n\nOutput as HTML.\n- Use bento-style sections (divs) when useful.\n- Use tables for comparisons.\n- If a diagram helps, include a ```mermaid\n"
        },
        {
            "id": "comparison",
            "name": "⚖️ Comparison Table Pro",
            "description": "مقارنة احترافية",
            "prompt": "Compare key entities from the user's content.\n\nOutput as HTML.\n- Use an HTML table.\n- Highlight critical differences with [🔥 EXAM_TIP].\n- Mark definitions with [💡 KEY_POINT].\n"
        },
        {
            "id": "custom",
            "name": "✨ Custom Prompt",
            "description": "Prompt مخصص",
            "prompt": "Follow the user's instructions precisely.\nOutput clean HTML.\nIf you produce a diagram, use ```mermaid\n"
        },
        {
            "id": "plain_text",
            "name": "📄 Plain Study Text",
            "description": "نص منظم بدون أي عناصر بصرية",
            "prompt": "Format the content as clean study notes.\n- Output HTML only.\n- Use headings, paragraphs, and bullet lists.\n- No visual boxes, no tables unless necessary.\n- Font size suitable for A4 (10–12).\n- Preserve meaning exactly.\n"
        },
        {
            "id": "visual_study",
            "name": "🎨 Visual Study Notes",
            "description": "مذكرات بصرية بصناديق وجداول",
            "prompt": "Create A4-ready visual study notes.\n- Output clean HTML.\n- Use visual boxes for definitions, exam tips, and summaries.\n- Use tables where helpful.\n- Font size between 10–12.\n- Optimized for PDF study.\n"
        },
        {
            "id": "definition_focus",
            "name": "💡 Definitions Focus",
            "description": "تعريفات فقط بصناديق واضحة",
            "prompt": "Extract and format all definitions.\n- Output HTML only.\n- Each definition in a highlighted definition box.\n- Short, precise, exam-oriented.\n- A4 study format.\n"
        },
        {
            "id": "exam_high_yield",
            "name": "🔥 High-Yield Exam Mode",
            "description": "النقاط اللي بتيجي في الامتحان",
            "prompt": "Identify and format high-yield exam points.\n- Output HTML.\n- Use exam-tip boxes.\n- Bullet points only.\n- Very concise.\n- A4 PDF ready.\n"
        },
        {
            "id": "step_by_step",
            "name": "🪜 Step-by-Step Process",
            "description": "خطوات مرتبة مع فلو تشارت",
            "prompt": "Format the content as step-by-step processes.\n- Output HTML.\n- Use numbered steps.\n- Include a Mermaid flowchart if applicable.\n- A4-friendly layout.\n"
        },
        {
            "id": "comparison_table",
            "name": "⚖️ Comparison Tables",
            "description": "مقارنات منظمة في جداول",
            "prompt": "Create comparison tables.\n- Output HTML.\n- Use tables as the main structure.\n- Highlight key differences.\n- Suitable for A4 study PDFs.\n"
        },
        {
            "id": "mcq_standard",
            "name": "❓ MCQ Standard",
            "description": "MCQs للمذاكرة",
            "prompt": "Generate multiple choice questions.\n- Output HTML.\n- 10–15 MCQs.\n- Clear options.\n- Include answer key at the end.\n- A4 layout.\n"
        },
        {
            "id": "mcq_exam_style",
            "name": "📝 MCQ Exam Style",
            "description": "أسئلة قريبة من الامتحان",
            "prompt": "Generate exam-style MCQs.\n- Output HTML.\n- Focus on tricky concepts.\n- Mark high-yield questions.\n- Include answers separately.\n"
        },
        {
            "id": "flashcards_a4",
            "name": "🎴 Flashcards A4",
            "description": "فلاش كاردز للطباعة",
            "prompt": "Convert content into flashcards.\n- Output HTML.\n- Q/A format.\n- Group cards in printable A4 sections.\n- Font size 10–12.\n"
        },
        {
            "id": "mindmap_mode",
            "name": "🧠 Mind Map",
            "description": "Mind map للمحتوى",
            "prompt": "Create a mind map of the content.\n- Output HTML.\n- Include a Mermaid mindmap.\n- Minimal explanatory text.\n- A4 safe.\n"
        },
        {
            "id": "graphical_explain",
            "name": "📊 Graph-Based Explanation",
            "description": "شرح باستخدام جرافات بسيطة",
            "prompt": "Explain concepts using simple visual graphs.\n- Output HTML.\n- Use bar-style visual graphs (no JS).\n- Minimal text.\n- PDF compatible.\n"
        },
        {
            "id": "revision_sheet",
            "name": "🔁 Revision Sheet",
            "description": "ورقة مراجعة سريعة",
            "prompt": "Create a last-day revision sheet.\n- Output HTML.\n- Bullet points only.\n- High-yield focus.\n- One or two A4 pages max.\n"
        },
        {
            "id": "clinical_focus",
            "name": "🏥 Clinical Focus",
            "description": "ربط المحتوى بالكلينيكال",
            "prompt": "Rewrite the content with clinical focus.\n- Output HTML.\n- Symptoms, signs, investigations.\n- Use boxes for cases.\n- Study-PDF ready.\n"
        },
        {
            "id": "case_based",
            "name": "🧩 Case-Based Learning",
            "description": "تعلم بالحالات",
            "prompt": "Convert content into short clinical cases.\n- Output HTML.\n- Each case in a separate box.\n- Include key learning point.\n- A4 format.\n"
        },
        {
            "id": "faq_mode",
            "name": "❔ FAQ Mode",
            "description": "أسئلة وإجابات شائعة",
            "prompt": "Generate frequently asked questions.\n- Output HTML.\n- Q&A format.\n- Clear and concise.\n- Study friendly.\n"
        },
        {
            "id": "error_traps",
            "name": "⚠️ Common Mistakes",
            "description": "الأخطاء الشائعة",
            "prompt": "Identify common mistakes and misconceptions.\n- Output HTML.\n- Each mistake in a warning box.\n- Exam-oriented.\n"
        },
        {
            "id": "formula_sheet",
            "name": "📐 Formula & Values Sheet",
            "description": "قوانين وأرقام",
            "prompt": "Extract formulas, values, and thresholds.\n- Output HTML.\n- Use compact boxes.\n- A4 printable.\n"
        },
        {
            "id": "one_page_notes",
            "name": "🧾 One-Page Notes",
            "description": "ملخص صفحة واحدة",
            "prompt": "Condense the content into one A4 page.\n- Output HTML.\n- Very concise.\n- Visual boxes allowed.\n- Font 10–11.\n"
        },
        {
            "id": "custom_free",
            "name": "🛠️ Custom Free Mode",
            "description": "تنفيذ تعليمات المستخدم حرفيًا",
            "prompt": "Follow the user's instructions exactly.\n- Output clean HTML.\n- Ensure A4 PDF compatibility.\n- No extra content unless requested.\n"
        }
    ]
}


def normalize_prompts(modes_obj):
    """
    Return normalized schema: {"modes":[{id,name,description,prompt},...]}
    """
    if isinstance(modes_obj, dict) and isinstance(modes_obj.get("modes"), list):
        # Schema A
        fixed = {"modes": []}
        for m in modes_obj.get("modes", []):
            if not isinstance(m, dict):
                continue
            if not m.get("id"):
                continue
            fixed["modes"].append(
                {
                    "id": str(m.get("id", "")).strip(),
                    "name": str(m.get("name", m.get("id", ""))).strip(),
                    "description": str(m.get("description", "")).strip(),
                    "prompt": str(m.get("prompt", "")).strip(),
                }
            )
        return fixed if fixed["modes"] else DEFAULT_PROMPTS_A

    # Schema B (v18.5 dict)
    if isinstance(modes_obj, dict) and "modes" not in modes_obj:
        out = {"modes": []}
        for k, v in modes_obj.items():
            if not isinstance(v, dict):
                continue
            out["modes"].append(
                {
                    "id": str(k).strip(),
                    "name": str(v.get("name", k)).strip(),
                    "description": "",
                    "prompt": str(v.get("prompt", "")).strip(),
                }
            )
        return out if out["modes"] else DEFAULT_PROMPTS_A

    return DEFAULT_PROMPTS_A


# =========================
# HTTP / API
# =========================
def get_browser_headers():
    # IMPORTANT: No Accept-Encoding: br
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
    }


def call_openai_style_chat(api_url: str, api_key: str, model: str, system_prompt: str, user_text: str, timeout=90):
    headers = get_browser_headers()
    headers["Authorization"] = f"Bearer {api_key}"
    # Extra browser-ish headers
    headers["Origin"] = "[https://console.groq.com](https://console.groq.com)"
    headers["Referer"] = "[https://console.groq.com/](https://console.groq.com/)"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.4,
    }

    r = requests.post(api_url, headers=headers, json=payload, timeout=timeout)

    if r.status_code >= 400:
        # Show body for debugging (403 reasons, etc.)
        body = r.text[:1500]
        raise RuntimeError(f"HTTP {r.status_code}\n{body}")

    data = r.json()
    return data["choices"][0]["message"]["content"]


# =========================
# Smart inputs
# =========================
def extract_from_image(img_path: str) -> str:
    if not OCR_AVAILABLE:
        return "OCR not available. Install pytesseract + Tesseract."
    try:
        img = Image.open(img_path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        return f"OCR Error: {e}"


def extract_from_pdf(pdf_path: str, max_pages=40) -> str:
    if not PDF_READER_AVAILABLE:
        return "PDF reading not available. Install PyPDF2."
    try:
        out = []
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = min(len(reader.pages), max_pages)
            for i in range(pages):
                try:
                    out.append(reader.pages[i].extract_text() or "")
                except Exception:
                    pass
        return "\n".join([x for x in out if x.strip()]).strip()
    except Exception as e:
        return f"PDF Error: {e}"


def extract_youtube_transcript(url_or_id: str) -> str:
    if not YOUTUBE_AVAILABLE:
        return "YouTube transcript not available. Install youtube-transcript-api."
    try:
        vid = url_or_id.strip()
        m = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})(?:\\?|&|$)", vid)
        if m:
            vid = m.group(1)
        transcript = YouTubeTranscriptApi.get_transcript(vid)
        return "\n".join([x.get("text", "") for x in transcript if x.get("text")]).strip()
    except Exception as e:
        return f"YouTube Error: {e}"


# =========================
# Visual + Exam radar
# =========================
def process_visuals(html: str) -> str:
    # Mermaid -> mermaid.ink image
    pattern = r"```mermaid\s+(.*?)```"

    def repl(m):
        code = m.group(1).strip()
        b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{b64}?bgColor=white"
        return (
            '<div class="diagram-card">'
            '<div class="diagram-title">📌 Diagram</div>'
            f'<img class="diagram-img" src="{url}" alt="Diagram" />'
            "</div>"
        )

    html = re.sub(pattern, repl, html, flags=re.DOTALL)

    # Exam radar tags -> badges (keep HTML safe)
    html = html.replace("[🔥 EXAM_TIP]", '<span class="exam-badge">🔥 HIGH YIELD</span>')
    html = html.replace("[💡 KEY_POINT]", '<span class="key-badge">💡 MUST KNOW</span>')

    # Table wrapper for nicer styling
    html = re.sub(r"<table(.*?)>", r'<div class="table-wrap"><table\1>', html, flags=re.IGNORECASE)
    html = re.sub(r"</table>", r"</table></div>", html, flags=re.IGNORECASE)

    return html


def wrap_html_document(body_html: str, theme: dict, scheme: dict, title="AI Architect Document") -> str:
    scheme = ensure_scheme_rgb(scheme)
    gradient = theme.get("gradient", "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)")
    card = theme.get("card", "rgba(30, 41, 59, 0.72)")
    border = theme.get("border", "rgba(255,255,255,0.12)")
    text = theme.get("text", scheme.get("text", "#e5e7eb"))
    heading = theme.get("heading", scheme.get("heading", "#ffffff"))
    glow = theme.get("glow", "0 12px 40px rgba(0,0,0,0.35)")
    highlight = theme.get("highlight", "linear-gradient(120deg, rgba(56,189,248,0.25), rgba(129,140,248,0.18))")

    primary = scheme.get("primary", "#22d3ee")
    secondary = scheme.get("secondary", "#818cf8")
    accent = scheme.get("accent", "#f472b6")
    prgb = scheme.get("primary_rgb", hex_to_rgb_str(primary))
    argb = scheme.get("accent_rgb", hex_to_rgb_str(accent))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    css = f"""
<style>
  :root {{
    --primary: {primary};
    --secondary: {secondary};
    --accent: {accent};
    --primary-rgb: {prgb};
    --accent-rgb: {argb};
    --bg: {gradient};
    --card: {card};
    --border: {border};
    --text: {text};
    --heading: {heading};
    --glow: {glow};
    --highlight: {highlight};
  }}
  html, body {{
    margin: 0;
    padding: 0;
    font-family: Inter, Segoe UI, Arial, sans-serif;
    color: var(--text);
  }}
  .page {{
    min-height: 100vh;
    padding: 26px;
    background: var(--bg);
  }}
  .sheet {{
    border-radius: 18px;
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.04);
    box-shadow: var(--glow);
    padding: 22px;
  }}
  h1,h2,h3 {{ color: var(--heading); }}
  p,li {{ line-height: 1.65; }}

  .table-wrap {{
    width: 100%;
    overflow-x: auto;
    border-radius: 14px;
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.03);
    margin: 12px 0;
  }}
  table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    min-width: 560px;
  }}
  th {{
    text-align: left;
    padding: 10px 12px;
    background: rgba(var(--primary-rgb), 0.18);
    color: var(--heading);
    border-bottom: 1px solid var(--border);
  }}
  td {{
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }}

  .diagram-card {{
    background: rgba(255,255,255,0.05);
    border: 1px dashed rgba(var(--accent-rgb), 0.55);
    border-radius: 16px;
    padding: 12px;
    margin: 14px 0;
  }}
  .diagram-title {{
    font-weight: 800;
    margin-bottom: 10px;
    color: var(--heading);
  }}
  .diagram-img {{
    width: 100%;
    border-radius: 12px;
    background: #fff;
  }}

  .exam-badge {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 900;
    font-size: 0.85em;
    color: #111827;
    background: linear-gradient(135deg, #fb7185, #fbbf24);
    margin-right: 8px;
  }}
  .key-badge {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 900;
    font-size: 0.85em;
    color: #0b1220;
    background: linear-gradient(135deg, #67e8f9, #a78bfa);
    margin-right: 8px;
  }}

  @media print {{
    body {{
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }}

    .page {{
      background: var(--bg) !important;
    }}

    .sheet {{
      background: rgba(255,255,255,0.04) !important;
      box-shadow: none !important;
    }}
  }}
</style>
"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
{css}
</head>
<body>
  <div class="page">
    <div class="sheet">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;">
        <h1 style="margin:0;">{title}</h1>
        <div style="opacity:0.9;">Generated: {now} - v{APP_VERSION}</div>

      </div>
      <hr style="border:0;border-top:1px solid rgba(255,255,255,0.12);margin:14px 0 18px 0;" />
      {body_html}
    </div>
  </div>
</body>
</html>
"""


# =========================
# Export PDF
# =========================
def export_pdf_weasyprint(html_path: Path, pdf_path: Path):
    if not WEASYPRINT_AVAILABLE:
        raise RuntimeError("WeasyPrint not installed.")
    WeasyHTML(filename=str(html_path)).write_pdf(str(pdf_path))


async def export_pdf_playwright(html_path: Path, pdf_path: Path):
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright not installed.")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{html_path}", wait_until="networkidle")
        await page.pdf(path=str(pdf_path), print_background=True, format="A4")
        await browser.close()


# =========================
# App
# =========================
class AIArchitectApp:
    def __init__(self):
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title(f"🚀 AI Architect v{APP_VERSION}")
        self.root.geometry("1500x950")

        # Load configs relative to script (FIX for empty lists)
        self.models_path = BASE_DIR / "models_config.json"
        self.themes_path = BASE_DIR / "themes_config.json"
        self.colors_path = BASE_DIR / "color_schemes.json"
        self.prompts_path = BASE_DIR / "prompts_config.json"
        self.keys_path = BASE_DIR / "api_keys.json"

        self.MODELS_CONFIG = load_json_config(self.models_path, DEFAULT_MODELS)
        self.THEMES_CONFIG = load_json_config(self.themes_path, DEFAULT_THEMES)
        self.COLOR_SCHEMES = load_json_config(self.colors_path, DEFAULT_COLORS)
        self.MODES = normalize_prompts(load_json_config(self.prompts_path, DEFAULT_PROMPTS_A))

        # Normalize schemes rgb
        self.COLOR_SCHEMES["color_schemes"] = [ensure_scheme_rgb(s) for s in self.COLOR_SCHEMES.get("color_schemes", [])]

        # State
        self.selected_provider = tk.StringVar(value=self._first_provider_id())
        self.selected_model = tk.StringVar(value=self._first_model_id(self.selected_provider.get()))
        self.selected_mode = tk.StringVar(value=self._first_mode_id())
        self.selected_theme = tk.StringVar(value=self._first_theme_id())
        self.selected_scheme = tk.StringVar(value=self._first_scheme_id())

        self.processing = False
        self.last_html_path = BASE_DIR / "last_output.html"
        self.last_html = ""

        self.api_keys = load_json_config(self.keys_path, {"keys": {}})

        self._build_ui()
        self._load_settings_to_ui()

    # -------- config getters
    def _first_provider_id(self):
        providers = self.MODELS_CONFIG.get("providers", {})
        return next(iter(providers.keys()), "groq")

    def _first_model_id(self, provider_id):
        p = self.MODELS_CONFIG.get("providers", {}).get(provider_id, {})
        ms = p.get("models", [])
        return ms[0].get("id", "llama-3.3-70b-versatile") if ms else "llama-3.3-70b-versatile"

    def _first_mode_id(self):
        modes = self.MODES.get("modes", [])
        return modes[0]["id"] if modes else "strict"

    def _first_theme_id(self):
        ts = self.THEMES_CONFIG.get("themes", [])
        return ts[0]["id"] if ts else "bento_modern"

    def _first_scheme_id(self):
        cs = self.COLOR_SCHEMES.get("color_schemes", [])
        return cs[0]["id"] if cs else "cyber_neon"

    def _get_provider(self, provider_id):
        return self.MODELS_CONFIG.get("providers", {}).get(provider_id, {})

    def _get_mode(self, mode_id):
        for m in self.MODES.get("modes", []):
            if m.get("id") == mode_id:
                return m
        return None

    def _get_theme(self, theme_id):
        for t in self.THEMES_CONFIG.get("themes", []):
            if t.get("id") == theme_id:
                return t
        return self.THEMES_CONFIG.get("themes", [{}])[0] if self.THEMES_CONFIG.get("themes") else {}

    def _get_scheme(self, scheme_id):
        for s in self.COLOR_SCHEMES.get("color_schemes", []):
            if s.get("id") == scheme_id:
                return ensure_scheme_rgb(s)
        first = self.COLOR_SCHEMES.get("color_schemes", [{}])[0] if self.COLOR_SCHEMES.get("color_schemes") else {}
        return ensure_scheme_rgb(first)

    # -------- UI
    def _build_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self.root, width=280, corner_radius=0)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        ctk.CTkLabel(
            self.sidebar,
            text="AI ARCHITECT",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(pady=26)

        self.btn_generate = self._nav_btn("✨ Generate", self.show_generate)
        self.btn_tools = self._nav_btn("🛠️ Smart Tools", self.show_tools)
        self.btn_settings = self._nav_btn("⚙️ Settings", self.show_settings)

        # Main view
        self.main_view = ctk.CTkFrame(self.root, corner_radius=20, fg_color="transparent")
        self.main_view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.status = tk.StringVar(value="Ready")
        self.status_label = ctk.CTkLabel(self.sidebar, textvariable=self.status, wraplength=240, justify="left")
        self.status_label.pack(side=tk.BOTTOM, padx=20, pady=18)

        self.show_generate()

    def _nav_btn(self, text, command):
        btn = ctk.CTkButton(
            self.sidebar,
            text=text,
            command=command,
            height=45,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#1f2937",
            anchor="w",
        )
        btn.pack(fill=tk.X, padx=20, pady=6)
        return btn

    def _clear_view(self):
        for w in self.main_view.winfo_children():
            w.destroy()

    # -------- Pages
    def show_generate(self):
        self._clear_view()

        header = ctk.CTkFrame(self.main_view, corner_radius=20)
        header.pack(fill=tk.X, pady=(0, 14))
        ctk.CTkLabel(header, text="✨ Generate", font=ctk.CTkFont(size=22, weight="bold")).pack(side=tk.LEFT, padx=18, pady=16)

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side=tk.RIGHT, padx=18)

        self.provider_combo = ctk.CTkOptionMenu(controls, values=self._provider_options(), command=self._on_provider_change)
        self.provider_combo.set(self.selected_provider.get())
        self.provider_combo.pack(side=tk.LEFT, padx=6)

        self.model_combo = ctk.CTkOptionMenu(controls, values=self._model_options(self.selected_provider.get()))
        self.model_combo.set(self.selected_model.get())
        self.model_combo.pack(side=tk.LEFT, padx=6)

        self.mode_combo = ctk.CTkOptionMenu(controls, values=self._mode_options(), command=self._on_mode_change)
        self.mode_combo.set(self.selected_mode.get())
        self.mode_combo.pack(side=tk.LEFT, padx=6)

        self.theme_combo = ctk.CTkOptionMenu(controls, values=self._theme_options())
        self.theme_combo.set(self.selected_theme.get())
        self.theme_combo.pack(side=tk.LEFT, padx=6)

        self.scheme_combo = ctk.CTkOptionMenu(controls, values=self._scheme_options())
        self.scheme_combo.set(self.selected_scheme.get())
        self.scheme_combo.pack(side=tk.LEFT, padx=6)

        # Split input/output
        pane = ctk.CTkFrame(self.main_view, fg_color="transparent")
        pane.pack(fill=tk.BOTH, expand=True)

        left = ctk.CTkFrame(pane, corner_radius=20)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right = ctk.CTkFrame(pane, corner_radius=20)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        ctk.CTkLabel(left, text="📥 Input", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        self.input_text = ctk.CTkTextbox(left, font=("Inter", 13))
        self.input_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 12))

        tools_bar = ctk.CTkFrame(left, fg_color="transparent")
        tools_bar.pack(fill=tk.X, padx=15, pady=(0, 12))
        ctk.CTkButton(tools_bar, text="📷 OCR", command=self.tool_ocr).pack(side=tk.LEFT, padx=6)
        ctk.CTkButton(tools_bar, text="📄 PDF", command=self.tool_pdf).pack(side=tk.LEFT, padx=6)
        ctk.CTkButton(tools_bar, text="🎥 YouTube", command=self.tool_youtube).pack(side=tk.LEFT, padx=6)

        ctk.CTkLabel(right, text="🧾 Output HTML", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        self.output_text = ctk.CTkTextbox(right, font=("Consolas", 12), text_color="#cbd5e1")
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 12))

        # Action bar
        actions = ctk.CTkFrame(self.main_view, corner_radius=20)
        actions.pack(fill=tk.X, pady=(14, 0))

        self.gen_btn = ctk.CTkButton(actions, text="🚀 GENERATE", command=self.generate, height=50, font=ctk.CTkFont(weight="bold"))
        self.gen_btn.pack(side=tk.LEFT, padx=18, pady=18, expand=True, fill=tk.X)

        ctk.CTkButton(actions, text="👁️ Preview", command=self.preview_html, width=120).pack(side=tk.LEFT, padx=6)
        ctk.CTkButton(actions, text="📄 Export PDF", command=self.export_pdf, width=140, fg_color="#ef4444").pack(side=tk.LEFT, padx=6)
        ctk.CTkButton(actions, text="🎲 Remix", command=self.remix, width=110, fg_color="#7c3aed").pack(side=tk.LEFT, padx=6)

    def show_tools(self):
        self._clear_view()
        ctk.CTkLabel(self.main_view, text="🛠️ Smart Tools", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=16)

        items = [
            ("📄 PDF Remaster", "Extract text from PDF into the input box.", self.tool_pdf),
            ("📷 OCR Scanner", "Extract text from an image into the input box.", self.tool_ocr),
            ("🎥 YouTube to Text", "Fetch transcript into the input box.", self.tool_youtube),
            ("🧠 Reload Prompts", "Reload prompts_config.json from disk.", self.reload_prompts),
        ]
        for title, desc, cmd in items:
            card = ctk.CTkFrame(self.main_view, corner_radius=20)
            card.pack(fill=tk.X, pady=10, padx=20)
            left = ctk.CTkFrame(card, fg_color="transparent")
            left.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=18, pady=18)
            ctk.CTkLabel(left, text=title, font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(left, text=desc, text_color="#94a3b8").pack(anchor="w", pady=(6, 0))
            ctk.CTkButton(card, text="Launch", command=cmd, width=120).pack(side=tk.RIGHT, padx=18, pady=18)

    def show_settings(self):
        self._clear_view()
        ctk.CTkLabel(self.main_view, text="⚙️ Settings", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=16)

        card = ctk.CTkFrame(self.main_view, corner_radius=20)
        card.pack(fill=tk.X, padx=20, pady=10)

        ctk.CTkLabel(card, text="API Keys (saved in api_keys.json)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=18, pady=(16, 6))

        self.key_entries = {}
        providers = self.MODELS_CONFIG.get("providers", {})
        for pid in providers.keys():
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill=tk.X, padx=18, pady=8)
            ctk.CTkLabel(row, text=f"{pid.upper()}:", width=110).pack(side=tk.LEFT)
            ent = ctk.CTkEntry(row, show="*", width=520)
            ent.pack(side=tk.LEFT, padx=8)
            self.key_entries[pid] = ent

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill=tk.X, padx=18, pady=(10, 18))
        ctk.CTkButton(btns, text="Save Settings", command=self.save_settings).pack(side=tk.LEFT)
        ctk.CTkButton(btns, text="Reload All Configs", command=self.reload_all_configs).pack(side=tk.LEFT, padx=10)

        info = ctk.CTkFrame(self.main_view, corner_radius=20)
        info.pack(fill=tk.X, padx=20, pady=10)
        ctk.CTkLabel(info, text="Config files must be next to the .py file:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(info, text=str(self.models_path)).pack(anchor="w", padx=18)
        ctk.CTkLabel(info, text=str(self.prompts_path)).pack(anchor="w", padx=18)
        ctk.CTkLabel(info, text=str(self.themes_path)).pack(anchor="w", padx=18)
        ctk.CTkLabel(info, text=str(self.colors_path)).pack(anchor="w", padx=18, pady=(0, 16))

    # -------- Options lists
    def _provider_options(self):
        return list(self.MODELS_CONFIG.get("providers", {}).keys()) or ["groq"]

    def _model_options(self, provider_id):
        p = self._get_provider(provider_id)
        ms = p.get("models", [])
        return [m.get("id", "") for m in ms if m.get("id")] or ["llama-3.3-70b-versatile"]

    def _mode_options(self):
        return [m.get("id") for m in self.MODES.get("modes", [])] or ["strict"]

    def _theme_options(self):
        return [t.get("id") for t in self.THEMES_CONFIG.get("themes", [])] or ["bento_modern"]

    def _scheme_options(self):
        return [s.get("id") for s in self.COLOR_SCHEMES.get("color_schemes", [])] or ["cyber_neon"]

    # -------- Events
    def _on_provider_change(self, value):
        self.selected_provider.set(value)
        # refresh model options
        if hasattr(self, "model_combo"):
            models = self._model_options(value)
            self.model_combo.configure(values=models)
            self.selected_model.set(models[0])
            self.model_combo.set(models[0])
        self.status.set(f"Provider set: {value}")

    def _on_mode_change(self, value):
        self.selected_mode.set(value)

    # -------- Settings persistence
    def _load_settings_to_ui(self):
        # keys
        keys = self.api_keys.get("keys", {})
        if hasattr(self, "key_entries"):
            for pid, ent in self.key_entries.items():
                ent.delete(0, tk.END)
                ent.insert(0, keys.get(pid, ""))

    def save_settings(self):
        self.api_keys.setdefault("keys", {})
        for pid, ent in getattr(self, "key_entries", {}).items():
            self.api_keys["keys"][pid] = ent.get().strip()
        if save_json_config(self.keys_path, self.api_keys):
            self.status.set("Settings saved.")
            messagebox.showinfo("Saved", "✅ Settings saved.")
        else:
            messagebox.showerror("Error", "Failed to save settings.")

    def reload_all_configs(self):
        self.MODELS_CONFIG = load_json_config(self.models_path, DEFAULT_MODELS)
        self.THEMES_CONFIG = load_json_config(self.themes_path, DEFAULT_THEMES)
        self.COLOR_SCHEMES = load_json_config(self.colors_path, DEFAULT_COLORS)
        self.COLOR_SCHEMES["color_schemes"] = [ensure_scheme_rgb(s) for s in self.COLOR_SCHEMES.get("color_schemes", [])]
        self.reload_prompts()
        self.status.set("Configs reloaded. Open Generate page again.")
        messagebox.showinfo("Reloaded", "Configs reloaded. Re-open Generate page.")

    def reload_prompts(self):
        self.MODES = normalize_prompts(load_json_config(self.prompts_path, DEFAULT_PROMPTS_A))
        self.status.set(f"Prompts loaded: {len(self.MODES.get('modes', []))} modes")

        # If mode combo exists, refresh it
        if hasattr(self, "mode_combo"):
            mode_ids = self._mode_options()
            self.mode_combo.configure(values=mode_ids)
            if mode_ids:
                self.selected_mode.set(mode_ids[0])
                self.mode_combo.set(mode_ids[0])

    # -------- Core actions
    def generate(self):
        if self.processing:
            return

        content = self.input_text.get("1.0", "end").strip() if hasattr(self, "input_text") else ""
        if not content:
            messagebox.showwarning("Input", "Please enter input text.")
            return

        provider_id = self.provider_combo.get() if hasattr(self, "provider_combo") else self.selected_provider.get()
        model_id = self.model_combo.get() if hasattr(self, "model_combo") else self.selected_model.get()
        mode_id = self.mode_combo.get() if hasattr(self, "mode_combo") else self.selected_mode.get()

        # Get API key
        api_key = self.api_keys.get("keys", {}).get(provider_id, "")
        if not api_key and hasattr(self, "key_entries") and provider_id in self.key_entries:
            api_key = self.key_entries[provider_id].get().strip()

        if not api_key:
            messagebox.showwarning("API Key", f"Please add API key for {provider_id} in Settings.")
            return

        mode = self._get_mode(mode_id)
        system_prompt = (mode.get("prompt") if mode else "") or DEFAULT_PROMPTS_A["modes"][0]["prompt"]

        provider = self._get_provider(provider_id)
        api_url = provider.get("api_url", "")

        theme_id = self.theme_combo.get() if hasattr(self, "theme_combo") else self.selected_theme.get()
        scheme_id = self.scheme_combo.get() if hasattr(self, "scheme_combo") else self.selected_scheme.get()

        self.processing = True
        self.gen_btn.configure(state="disabled", text="⏳ Processing...")
        self.status.set("Processing...")

        def worker():
            try:
                raw = call_openai_style_chat(
                    api_url=api_url,
                    api_key=api_key,
                    model=model_id,
                    system_prompt=system_prompt,
                    user_text=content,
                )

                # If response is markdown-ish but not HTML, wrap it lightly
                body = self._to_html_if_needed(raw)

                # Visual + exam radar
                body = process_visuals(body)

                final = wrap_html_document(
                    body_html=body,
                    theme=self._get_theme(theme_id),
                    scheme=self._get_scheme(scheme_id),
                    title="AI Architect Export",
                )

                self.last_html = final
                self.last_html_path.write_text(final, encoding="utf-8")

                self.output_text.delete("1.0", "end")
                self.output_text.insert("1.0", final)

                self.status.set("✅ Done. Saved: last_output.html")
            except Exception as e:
                self.status.set("❌ Error (see popup)")
                messagebox.showerror("Generate Error", str(e))
            finally:
                self.processing = False
                try:
                    self.gen_btn.configure(state="normal", text="🚀 GENERATE")
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _to_html_if_needed(self, text: str) -> str:
        if re.search(r"</(p|h1|h2|h3|ul|ol|table|div)>", text, re.IGNORECASE):
            return text

        # Keep Mermaid fences intact (avoid the old syntax errors by NOT checking literal backticks)
        if (FENCE + "mermaid") in text:
            # Wrap as minimal HTML container (do not escape)
            return f"<div>{text}</div>"

        # Minimal line-to-HTML
        lines = text.splitlines()
        out = []
        in_ul = False
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("### "):
                if in_ul:
                    out.append("</ul>")
                    in_ul = False
                out.append(f"<h3>{self._escape_html(s[4:])}</h3>")
            elif s.startswith("## "):
                if in_ul:
                    out.append("</ul>")
                    in_ul = False
                out.append(f"<h2>{self._escape_html(s[3:])}</h2>")
            elif s.startswith("# "):
                if in_ul:
                    out.append("</ul>")
                    in_ul = False
                out.append(f"<h1>{self._escape_html(s[2:])}</h1>")
            elif s.startswith(("- ", "• ")):
                if not in_ul:
                    out.append("<ul>")
                    in_ul = True
                out.append(f"<li>{self._escape_html(s[2:])}</li>")
            else:
                if in_ul:
                    out.append("</ul>")
                    in_ul = False
                out.append(f"<p>{self._escape_html(s)}</p>")
        if in_ul:
            out.append("</ul>")
        return "\n".join(out)

    def _escape_html(self, s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def preview_html(self):
        if not self.last_html:
            html = self.output_text.get("1.0", "end").strip() if hasattr(self, "output_text") else ""
            if not html:
                messagebox.showwarning("Preview", "No HTML to preview.")
                return
            self.last_html = html
            self.last_html_path.write_text(html, encoding="utf-8")

        webbrowser.open(f"file://{self.last_html_path}")
        self.status.set("Preview opened in browser.")

    def remix(self):
        # random theme + scheme
        import random
        ts = self.THEMES_CONFIG.get("themes", [])
        cs = self.COLOR_SCHEMES.get("color_schemes", [])
        if ts:
            t = random.choice(ts)
            self.selected_theme.set(t.get("id", ""))
            if hasattr(self, "theme_combo"):
                self.theme_combo.set(self.selected_theme.get())
        if cs:
            c = random.choice(cs)
            self.selected_scheme.set(c.get("id", ""))
            if hasattr(self, "scheme_combo"):
                self.scheme_combo.set(self.selected_scheme.get())
        self.status.set("🎲 Remix applied (theme + scheme). Re-generate for full effect.")

    def export_pdf(self):
        html = self.output_text.get("1.0", "end").strip() if hasattr(self, "output_text") else ""
        if not html:
            messagebox.showwarning("PDF", "No HTML to export.")
            return

        pdf_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not pdf_path:
            return

        tmp_html = BASE_DIR / "export_tmp.html"
        tmp_html.write_text(html, encoding="utf-8")
        pdf_path = Path(pdf_path)

        self.status.set("Exporting PDF...")

        # WeasyPrint first
        if WEASYPRINT_AVAILABLE:
            try:
                export_pdf_weasyprint(tmp_html, pdf_path)
                self.status.set(f"✅ PDF saved: {pdf_path.name} (WeasyPrint)")
                messagebox.showinfo("PDF", f"Saved: {pdf_path}")
                return
            except Exception as e:
                messagebox.showwarning("WeasyPrint failed", str(e))

        # Playwright fallback
        if PLAYWRIGHT_AVAILABLE:
            try:
                import asyncio
                asyncio.run(export_pdf_playwright(tmp_html, pdf_path))
                self.status.set(f"✅ PDF saved: {pdf_path.name} (Playwright)")
                messagebox.showinfo("PDF", f"Saved: {pdf_path}")
                return
            except Exception as e:
                messagebox.showerror("Playwright PDF failed", str(e))
                return

        messagebox.showinfo("PDF", "WeasyPrint/Playwright not available. Open preview and print manually.")
        self.status.set("PDF fallback: use browser print.")

    # -------- Tools
    def tool_ocr(self):
        fp = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")])
        if not fp:
            return
        self.status.set("OCR extracting...")
        txt = extract_from_image(fp)
        if hasattr(self, "input_text"):
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", txt)
        self.status.set("OCR done.")

    def tool_pdf(self):
        fp = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf"), ("All files", "*.*")])
        if not fp:
            return
        self.status.set("PDF extracting...")
        txt = extract_from_pdf(fp)
        if hasattr(self, "input_text"):
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", txt)
        self.status.set("PDF extract done.")

    def tool_youtube(self):
        if not YOUTUBE_AVAILABLE:
            messagebox.showwarning("YouTube", "youtube-transcript-api not installed.")
            return
        url = ctk.CTkInputDialog(text="Paste YouTube URL or Video ID:", title="YouTube Transcript").get_input()
        if not url:
            return
        self.status.set("Fetching transcript...")
        txt = extract_youtube_transcript(url)
        if hasattr(self, "input_text"):
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", txt)
        self.status.set("Transcript ready.")

    # -------- Run
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = AIArchitectApp()
    app.run()