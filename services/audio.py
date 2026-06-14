import os
import io
import sys
import asyncio
import tempfile
import threading
import subprocess
import time
from typing import Optional, Type
from pathlib import Path

from services.config import config_service

# ── Dynamic Config Helpers ────────────────────────────────────────────────────
def _get_audio_config():
    return {
        "whisper_model":   config_service.get("WHISPER_MODEL", "base"),
        "whisper_device":  config_service.get("WHISPER_DEVICE", "auto"),
        "whisper_compute": config_service.get("WHISPER_COMPUTE", "int8"),
        "whisper_engine": config_service.get("WHISPER_ENGINE", "local"),
        "whispercpp_url": config_service.get("WHISPER_CPP_URL", ""),
        "tts_engine":      config_service.get("TTS_ENGINE", "edge"),
        "tts_voice":       config_service.get("TTS_VOICE", "ar-EG-ShakirNeural"),
        "piper_model":     config_service.get("PIPER_MODEL_PATH", ""),
        "piper_config":    config_service.get("PIPER_CONFIG_PATH", ""),
        "piper_bin":       config_service.get("PIPER_BIN", "piper"),
        "coqui_model":    config_service.get("COQUI_MODEL", ""),
        "coqui_bin":      config_service.get("COQUI_BIN", "tts"),
        "elevenlabs_model": config_service.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        "kokoro_model":    config_service.get("KOKORO_MODEL_PATH", ""),
        "models_dir":     config_service.get("MODELS_DIR", ""),
    }

# ── Whisper Singleton ─────────────────────────────────────────────────────────
_whisper_model  = None
_whisper_lock   = threading.Lock()
_whisper_last_used = 0.0
_whisper_timer = None

def _unload_whisper_task():
    global _whisper_model, _whisper_timer
    with _whisper_lock:
        now = time.time()
        # 5 minutes idle (300 seconds)
        if _whisper_model is not None and (now - _whisper_last_used) >= 300:
            print("[Whisper] Auto-unloading model due to inactivity (P-07)")
            _whisper_model = None
            import gc
            gc.collect()
            if os.name == 'nt':
                # Optional: collect CUDA memory if torch is used, 
                # but faster-whisper uses ctranslate2.
                pass
        _whisper_timer = None


def _load_whisper(force_cpu=False):
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None or force_cpu:
            from faster_whisper import WhisperModel
            cfg = _get_audio_config()
            whisper_model = cfg["whisper_model"]
            whisper_device = "cpu" if force_cpu else cfg["whisper_device"]
            whisper_compute = "int8" if force_cpu else cfg["whisper_compute"]
            models_dir = cfg.get("models_dir")
            if not models_dir:
                models_dir = str(config_service.data_path / "models")
            
            download_kwargs = {}
            whisper_dir = os.path.join(models_dir, "whisper")
            os.makedirs(whisper_dir, exist_ok=True)
            download_kwargs["download_root"] = whisper_dir

            try:
                _whisper_model = WhisperModel(
                    whisper_model,
                    device=whisper_device,
                    compute_type=whisper_compute,
                    cpu_threads=min(os.cpu_count() or 4, 8),
                    num_workers=2,
                    **download_kwargs
                )
                print(f"[Whisper] Loaded: {whisper_model} on {whisper_device}")
            except Exception:
                _whisper_model = WhisperModel(
                    whisper_model,
                    device="cpu",
                    compute_type="int8",
                    **download_kwargs
                )
                print("[Whisper] Fallback to CPU")
        
        global _whisper_last_used, _whisper_timer
        _whisper_last_used = time.time()
        if _whisper_timer is None:
            # Schedule unload in 5 mins
            _whisper_timer = threading.Timer(310, _unload_whisper_task)
            _whisper_timer.daemon = True
            _whisper_timer.start()

    return _whisper_model


def prewarm_whisper():
    """يُشغَّل في background thread عند startup."""
    if os.getenv("OPENSTUDY_ENABLE_WHISPER", "0") != "1":
        print("[Whisper] Prewarm skipped (OPENSTUDY_ENABLE_WHISPER is off).")
        return
        
    try:
        _load_whisper()
    except Exception as e:
        print(f"[Whisper prewarm failed] {e}")


# ── Transcription ─────────────────────────────────────────────────────────────

async def transcribe_audio(audio_bytes: bytes, language: Optional[str] = None) -> dict:
    """
    يحوّل audio bytes لنص.
    يرجع: {"text": str, "segments": list, "language": str}
    """
    if language == "auto" or language == "":
        language = None

    cfg = _get_audio_config()
    engine = str(cfg["whisper_engine"]).lower()
    if engine == "openai":
        return await _openai_whisper(audio_bytes, language)
    if engine == "whispercpp":
        return await _whispercpp(audio_bytes, language, cfg)

    model = await asyncio.get_event_loop().run_in_executor(None, _load_whisper)

    # احفظ الـ bytes في temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        def _run_transcribe(m):
            return m.transcribe(
                tmp_path,
                language=language,
                vad_filter=True,
                beam_size=3,
                temperature=0.0,
                condition_on_previous_text=False,
            )

        try:
            segments_result, info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _run_transcribe(model)
            )
        except RuntimeError as e:
            # GPU runtime error (e.g. cublas64_12.dll missing) — fallback to CPU
            print(f"[Whisper] GPU runtime error: {e}, retrying on CPU...")
            model = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _load_whisper(force_cpu=True)
            )
            segments_result, info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _run_transcribe(model)
            )

        segments = []
        full_text = ""

        for seg in segments_result:
            segments.append({
                "start": round(seg.start, 2),
                "end":   round(seg.end, 2),
                "text":  seg.text.strip(),
            })
            full_text += seg.text + " "

        filler = ["آ ", "إيه ", "يعني ", "عم ", "اممm", " uh ", " um "]
        for f in filler:
            full_text = full_text.replace(f, " ")

        return {
            "text":     full_text.strip(),
            "segments": segments,
            "language": info.language,
            "duration": round(info.duration, 2) if hasattr(info, "duration") else 0,
        }

    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def _openai_whisper(audio_bytes: bytes, language: Optional[str]) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=config_service.get("OPENAI_API_KEY"))
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as f:
            kwargs = {
                "model": "whisper-1",
                "file": f,
            }
            if language:
                kwargs["language"] = language
            result = await client.audio.transcriptions.create(**kwargs)
        return {
            "text": result.text or "",
            "segments": [],
            "language": language or "en",
            "duration": 0,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def _whispercpp(audio_bytes: bytes, language: Optional[str], cfg: dict) -> dict:
    import httpx
    url = cfg.get("whispercpp_url")
    if not url:
        raise RuntimeError("WHISPER_CPP_URL is required for whispercpp engine")
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    data = {}
    if language:
        data["language"] = language
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, files=files, data=data)
        resp.raise_for_status()
        data = resp.json()
    return {
        "text": data.get("text", ""),
        "segments": data.get("segments", []),
        "language": data.get("language", language or "en"),
        "duration": data.get("duration", 0),
    }


# ── TTS ───────────────────────────────────────────────────────────────────────

async def synthesize_speech(text: str, voice: str = None) -> bytes:
    cfg = _get_audio_config()
    voice = voice or cfg["tts_voice"]
    engine = cfg["tts_engine"]

    try:
        if engine == "edge":
            return await _edge_tts(text, voice)
        elif engine == "openai":
            return await _openai_tts(text, voice)
        elif engine == "piper":
            return await _piper_tts(text, cfg)
        elif engine == "coqui":
            return await _coqui_tts(text, cfg)
        elif engine == "elevenlabs":
            return await _elevenlabs_tts(text, cfg)
        elif engine == "kokoro":
            return await _kokoro_tts(text, cfg, voice)
        else:
            raise NotImplementedError(f"TTS engine '{engine}' not supported yet")
    except Exception as e:
        print(f"[TTS Error] Engine '{engine}' failed: {e}. Trying edge-tts fallback...")
        if engine != "edge":
            try:
                fallback_voice = "en-US-AvaNeural"
                return await _edge_tts(text, fallback_voice)
            except Exception as fallback_err:
                print(f"[TTS Fallback Error] Edge-TTS fallback failed: {fallback_err}")
        raise e


async def _edge_tts(text: str, voice: str) -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    audio_bytes = b""

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]

    return audio_bytes


async def _openai_tts(text: str, voice: str) -> bytes:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=config_service.get("OPENAI_API_KEY"))
    
    response = await client.audio.speech.create(
        model="tts-1",
        voice=voice, # e.g. alloy, echo, fable, onyx, nova, shimmer
        input=text,
    )
    return await response.aread()

async def _piper_tts(text: str, cfg: dict) -> bytes:
    model_path = cfg.get("piper_model", "")
    if not model_path:
        raise RuntimeError("PIPER_MODEL_PATH is required for piper TTS")
        
    models_dir = cfg.get("models_dir")
    if not models_dir:
        models_dir = str(config_service.data_path / "models")
    if not os.path.isabs(model_path):
        model_path = os.path.join(models_dir, "tts", model_path)
        
    bin_path = cfg.get("piper_bin", "piper")
    config_path = cfg.get("piper_config", "")
    if config_path and not os.path.isabs(config_path):
        config_path = os.path.join(models_dir, "tts", config_path)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out_path = tmp.name

    cmd = [bin_path, "--model", model_path, "--output_file", out_path]
    if config_path:
        cmd.extend(["--config", config_path])

    proc = await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: subprocess.run(cmd, input=text.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE),
    )

    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="ignore")[:500]
        Path(out_path).unlink(missing_ok=True)
        raise RuntimeError(f"Piper TTS failed: {err}")

    audio_bytes = Path(out_path).read_bytes()
    Path(out_path).unlink(missing_ok=True)
    return audio_bytes


async def _coqui_tts(text: str, cfg: dict) -> bytes:
    bin_path = cfg.get("coqui_bin", "tts")
    model_name = cfg.get("coqui_model", "")
    if not model_name:
        raise RuntimeError("COQUI_MODEL is required for coqui TTS")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out_path = tmp.name
    cmd = [bin_path, "--text", text, "--out_path", out_path, "--model_name", model_name]
    proc = await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE),
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="ignore")[:500]
        Path(out_path).unlink(missing_ok=True)
        raise RuntimeError(f"Coqui TTS failed: {err}")
    audio_bytes = Path(out_path).read_bytes()
    Path(out_path).unlink(missing_ok=True)
    return audio_bytes


async def _elevenlabs_tts(text: str, cfg: dict) -> bytes:
    import httpx
    api_key = config_service.get("ELEVENLABS_API_KEY", "")
    voice_id = cfg.get("tts_voice")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is required for elevenlabs")
    if not voice_id:
        raise RuntimeError("TTS_VOICE must be set to a valid ElevenLabs voice id")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {"text": text, "model_id": cfg.get("elevenlabs_model", "eleven_multilingual_v2")}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.content

async def _kokoro_tts(text: str, cfg: dict, voice: str) -> bytes:
    from kokoro_onnx import Kokoro
    
    model_path = cfg.get("kokoro_model")
    models_dir = cfg.get("models_dir")
    if not models_dir:
        models_dir = str(config_service.data_path / "models")
    
    if not model_path:
        model_path = os.path.join(models_dir, "tts", "kokoro-v0_19.onnx")
        voices_path = os.path.join(models_dir, "tts", "voices.json")
    else:
        voices_path = os.path.join(os.path.dirname(model_path), "voices.json")

    if not os.path.exists(model_path):
         raise RuntimeError(f"Kokoro model not found at {model_path}")
    
    # KOKORO-CONFIG-FIX: Handle frozen builds and missing config.json
    import kokoro_onnx
    pkg_dir = os.path.dirname(kokoro_onnx.__file__)
    pkg_config = os.path.join(pkg_dir, "config.json")
    
    if not os.path.exists(pkg_config):
        # In frozen builds, files might be in sys._MEIPASS
        if getattr(sys, 'frozen', False):
            meipass_config = os.path.join(sys._MEIPASS, "kokoro_onnx", "config.json")
            if os.path.exists(meipass_config):
                pkg_config = meipass_config
                print(f"[Kokoro] Using bundled config: {pkg_config}")

        # Fallback to models dir if still not found
        if not os.path.exists(pkg_config):
            alt_config = os.path.join(models_dir, "tts", "config.json")
            if os.path.exists(alt_config):
                pkg_config = alt_config
                print(f"[Kokoro] Using fallback config: {pkg_config}")
            else:
                raise FileNotFoundError(f"Kokoro config.json not found in package, bundle, or {alt_config}")

    # Patch kokoro_onnx to find its config if we found it elsewhere
    if pkg_config != os.path.join(pkg_dir, "config.json"):
        # We can't easily change where the library looks, so we try to copy it if possible
        # or we might need a more invasive patch if the library is already imported and has cached the missing path
        try:
            if not os.path.exists(os.path.join(pkg_dir, "config.json")):
                os.makedirs(pkg_dir, exist_ok=True)
                import shutil
                shutil.copy2(pkg_config, os.path.join(pkg_dir, "config.json"))
        except Exception:
            pass

    kokoro = Kokoro(model_path, voices_path)
    samples, sample_rate = kokoro.create(text, voice=voice or "af_bella", speed=1.0, lang="en-us")
    
    import soundfile as sf
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format='WAV')
    return buffer.getvalue()

async def get_available_voices(language: str = None) -> list[dict]:
    """MISSING-08 FIX: returns all voices, optionally filtered by locale prefix.
    e.g. language='ar' returns Arabic voices only, None returns all.
    """
    import edge_tts
    voices = await edge_tts.list_voices()
    result = [
        {"name": v["ShortName"], "gender": v["Gender"], "locale": v["Locale"]}
        for v in voices
        if (language is None or v["Locale"].lower().startswith(language.lower()))
    ]
    return result


# ── Smart Notes Generation ────────────────────────────────────────────────────

# ── Singleton ──────────────────────────────────────────────────────────────────
class AudioService:
    transcribe = staticmethod(transcribe_audio)
    synthesize = staticmethod(synthesize_speech)
    
    prewarm = staticmethod(prewarm_whisper)

audio_service = AudioService()
