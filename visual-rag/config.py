import os
import json

# Load env variables and settings
def _load_env():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(base_dir)
    env_path = os.path.join(root_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

    # Load settings.json as fallback
    settings_path = os.path.join(root_dir, "data", "settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                keys = data.get("gemini_api_keys", [])
                if keys and not os.environ.get("GEMINI_API_KEYS"):
                    os.environ["GEMINI_API_KEYS"] = ",".join(keys)
                model = data.get("gemini_model", "")
                if model and not os.environ.get("GEMINI_MODEL"):
                    os.environ["GEMINI_MODEL"] = model
        except Exception:
            pass

_load_env()

# ── Models ───────────────────────────────────────────────────────────────────
LLM_MODEL          = "gemma-4-q4:latest"
FALLBACK_LLM_MODEL = "llama3.2:1b-instruct-q4_K_M"
EMBED_MODEL        = "nomic-embed-text"

GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEYS    = os.environ.get("GEMINI_API_KEYS", "")
GEMINI_MODEL       = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")  # default: fast + generous quota
TEXT_EMBED_MODEL   = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-2")  # separate quota pool — 1 500 RPD free

# ── Chunking ─────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 512
CHUNK_OVERLAP = 50
MIN_CHUNK_LEN = 40   # chars — skip shorter

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(BASE_DIR, "study_db")
OUTPUT_DIR   = os.path.join(BASE_DIR, "output")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

# ── Search ────────────────────────────────────────────────────────────────────
# 8 chunks is a good balance for enough context without timing out the LLM
DEFAULT_N_RESULTS = 8

# ── Generation Speed Tuning ──────────────────────────────────────────────────
# Max chars of context to pass to the LLM.  Trim beyond this to keep prompts short.
MAX_CONTEXT_CHARS  = 1200
# Max tokens the LLM should output for structured JSON visuals.
MAX_JSON_TOKENS    = 3072
# Max tokens the LLM should output for conversational text.
MAX_CHAT_TOKENS    = 4000
# Number of retry attempts on schema validation failure (1 = try once, retry once)
MAX_RETRIES        = 2

# ── Rate-limit safety margins (per rotating key) ──────────────────────────────
# text-embedding-004: 1500 RPD free → sleep 0.2s between embeds (3 keys = 9 RPM headroom)
# gemini-2.0-flash:   1500 RPD free → key rotator handles cooldowns automatically
EMBED_SLEEP_SECS   = 0.2
