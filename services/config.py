import os
import sys
from pathlib import Path

class ConfigService:
    def __init__(self):
        # Resolve project root path dynamically.
        # If running in frozen mode (compiled with PyInstaller), we store user data in
        # %LOCALAPPDATA%\OpenStudy to ensure it's writeable on any target system.
        if getattr(sys, 'frozen', False):
            local_appdata = os.environ.get("LOCALAPPDATA")
            if not local_appdata:
                # Fallback to home directory if LOCALAPPDATA isn't defined
                local_appdata = os.path.expanduser("~")
            self.root_path = Path(local_appdata).resolve() / "OpenStudy"
            self.root_path.mkdir(parents=True, exist_ok=True)
            self.data_path = self.root_path / "data"
            self.data_path.mkdir(parents=True, exist_ok=True)
            
            # Copy default documents from PyInstaller package resources to writeable path
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                bundled_docs = Path(meipass) / "docs"
                if bundled_docs.exists():
                    import shutil
                    target_docs = self.root_path / "docs"
                    target_docs.mkdir(parents=True, exist_ok=True)
                    for src_file in bundled_docs.rglob("*"):
                        if src_file.is_file():
                            rel_path = src_file.relative_to(bundled_docs)
                            dest_file = target_docs / rel_path
                            if not dest_file.exists():
                                dest_file.parent.mkdir(parents=True, exist_ok=True)
                                try:
                                    shutil.copy2(src_file, dest_file)
                                except Exception as e:
                                    print(f"[Config] Failed to copy bundled doc {rel_path}: {e}")
        else:
            # Development mode: resolve dynamically relative to services/config.py
            self.root_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).resolve()
            self.data_path = self.root_path / "data"
            self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Try loading .env manually to avoid python-dotenv dependency
        try:
            env_path = self.root_path / ".env"
            # In frozen mode, also fallback to the bundled .env in _MEIPASS
            if getattr(sys, 'frozen', False):
                meipass = getattr(sys, '_MEIPASS', None)
                if meipass:
                    bundled_env = Path(meipass) / ".env"
                    if bundled_env.exists() and not env_path.exists():
                        env_path = bundled_env
            
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            os.environ[key.strip()] = val.strip()
        except Exception as e:
            print(f"[Config] Failed to load .env: {e}")
        
        # Default configuration for 4GB VRAM target
        self._config = {
            "WHISPER_MODEL": "base",
            "WHISPER_DEVICE": "cpu", # Force CPU to save VRAM
            "WHISPER_COMPUTE": "int8",
            "WHISPER_ENGINE": "local",
            "TTS_ENGINE": "edge",        # edge-tts: cloud, zero VRAM, works out of the box. Change to 'kokoro' if model downloaded.
            "MODELS_DIR": str(self.data_path / "models"),
            "OLLAMA_URL": "http://127.0.0.1:11434",
            "OLLAMA_MODEL": "llama3.2:1b-instruct-q4_K_M",  # q4_K_M: ~800 MB VRAM vs ~2.2 GB for float16
        }
        
    def get(self, key, default=None):
        return os.environ.get(key, self._config.get(key, default))

    def ensure_vault_path(self):
        vault_path = self.data_path / "vault"
        vault_path.mkdir(parents=True, exist_ok=True)
        return str(vault_path)

config_service = ConfigService()
