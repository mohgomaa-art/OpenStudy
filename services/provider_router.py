"""
Tier-Aware Provider Router
Decision = hardware_capability AND user_preference — not hardware alone.

A student with 4GB RAM + excellent internet should get cloud AI.
A student with RTX 4060 + bad internet should get local AI.
Hardware tier determines defaults; user config overrides them.
"""
import logging
from services.config import config_service
from providers.registry import provider_registry

log = logging.getLogger("provider_router")


def _tier() -> str:
    """Return 'low' | 'mid' | 'high' from the cached hardware profile."""
    try:
        from services.hardware_detector import hardware_detector
        profile = hardware_detector.detect()
        return profile.compute_tier  # "low" | "mid" | "high"
    except Exception:
        return "low"


def _cfg(key: str, default=None):
    return config_service.get(key, default)


# ── LLM ──────────────────────────────────────────────────────────────────────
def _select_llm():
    from providers.llm import (
        OpenAIProvider, AnthropicProvider, GeminiProvider,
        OpenRouterProvider, OllamaProvider, LlamaCppProvider,
    )

    tier = _tier()
    # User-explicit override beats everything
    user_provider = str(_cfg("LLM_PROVIDER", "auto")).lower().strip()
    # Treat legacy "ai-to-api" value as "auto" — that provider no longer exists
    if user_provider == "ai-to-api":
        user_provider = "auto"

    openai_key   = str(_cfg("OPENAI_API_KEY",   "") or "")
    anthropic_key= str(_cfg("ANTHROPIC_API_KEY","") or "")
    gemini_key   = str(_cfg("GEMINI_API_KEY",   "") or "")
    openrouter_key=str(_cfg("OPENROUTER_API_KEY","") or "")
    ollama_base  = str(_cfg("OLLAMA_API_BASE",  "http://localhost:11434") or "http://localhost:11434")
    active_model = str(_cfg("ACTIVE_MODEL",     "") or "")
    local_model  = str(_cfg("LOCAL_MODEL_PATH", "") or "")

    def _cloud_provider():
        """Return first available cloud provider or None."""
        if openai_key:
            model = active_model if "gpt" in active_model.lower() else "gpt-4o-mini"
            return OpenAIProvider(openai_key, model)
        if anthropic_key:
            model = active_model if "claude" in active_model.lower() else "claude-haiku-4-5-20251001"
            return AnthropicProvider(anthropic_key, model)
        if gemini_key:
            model = active_model if "gemini" in active_model.lower() else "gemini-2.0-flash"
            return GeminiProvider(gemini_key, model)
        if openrouter_key:
            return OpenRouterProvider(openrouter_key, active_model or "google/gemma-3-4b-it:free")
        return None

    def _local_provider():
        """Return Ollama or llama.cpp if available."""
        p = OllamaProvider(ollama_base, active_model or "qwen3:8b")
        if p.is_available():
            return p
        if local_model:
            p2 = LlamaCppProvider(local_model)
            if p2.is_available():
                return p2
        return None

    # Explicit user choice
    if user_provider == "openai" and openai_key:
        model = active_model if "gpt" in active_model.lower() else "gpt-4o-mini"
        return OpenAIProvider(openai_key, model)
    if user_provider == "anthropic" and anthropic_key:
        model = active_model if "claude" in active_model.lower() else "claude-haiku-4-5-20251001"
        return AnthropicProvider(anthropic_key, model)
    if user_provider == "gemini" and gemini_key:
        model = active_model if "gemini" in active_model.lower() else "gemini-2.0-flash"
        return GeminiProvider(gemini_key, model)
    if user_provider == "openrouter" and openrouter_key:
        return OpenRouterProvider(openrouter_key, active_model or "google/gemma-3-4b-it:free")
    if user_provider == "ollama":
        return OllamaProvider(ollama_base, active_model or "qwen3:8b")
    if user_provider in ("local", "llamacpp") and local_model:
        return LlamaCppProvider(local_model)
    if user_provider == "cloud":
        return _cloud_provider()
    if user_provider == "local_auto":
        return _local_provider()

    # Auto-select: tier default but prefer whatever the user already has configured
    if tier == "low":
        # Low hardware → prefer cloud; local only if explicitly set
        return _cloud_provider() or _local_provider()
    elif tier == "mid":
        # Mid → prefer local (Ollama/Qwen3-8B); fall back to cloud
        local = _local_provider()
        return local or _cloud_provider()
    else:
        # High → prefer local; cloud as backup
        local = _local_provider()
        return local or _cloud_provider()


# ── TTS ──────────────────────────────────────────────────────────────────────
def _select_tts():
    from providers.tts import EdgeTTSProvider, PiperTTSProvider, KokoroProvider

    tier = _tier()
    user_tts = str(_cfg("TTS_PROVIDER", "auto")).lower().strip()
    piper_model = str(_cfg("PIPER_MODEL_PATH", "") or "")

    if user_tts == "edge_tts":
        return EdgeTTSProvider()
    if user_tts == "piper":
        return PiperTTSProvider(piper_model)
    if user_tts == "kokoro":
        return KokoroProvider()

    # Auto
    if tier == "low":
        return EdgeTTSProvider()
    elif tier == "mid":
        p = PiperTTSProvider(piper_model)
        if p.is_available():
            return p
        return EdgeTTSProvider()
    else:
        k = KokoroProvider()
        if k.is_available():
            return k
        p = PiperTTSProvider(piper_model)
        if p.is_available():
            return p
        return EdgeTTSProvider()


# ── STT ──────────────────────────────────────────────────────────────────────
def _select_stt():
    from providers.stt import WhisperAPIProvider, FasterWhisperProvider, WhisperLargeProvider

    tier = _tier()
    user_stt = str(_cfg("STT_PROVIDER", "auto")).lower().strip()
    openai_key = str(_cfg("OPENAI_API_KEY", "") or "")
    whisper_model = str(_cfg("WHISPER_MODEL_SIZE", "") or "")

    if user_stt == "whisper_api" and openai_key:
        return WhisperAPIProvider(openai_key)
    if user_stt == "faster_whisper":
        size = whisper_model or ("medium" if tier != "high" else "large-v3")
        return FasterWhisperProvider(size)
    if user_stt == "whisper_large":
        return WhisperLargeProvider()

    # Auto
    if tier == "low":
        if openai_key:
            return WhisperAPIProvider(openai_key)
        return FasterWhisperProvider("base")
    elif tier == "mid":
        return FasterWhisperProvider(whisper_model or "medium")
    else:
        return WhisperLargeProvider()


# ── OCR ──────────────────────────────────────────────────────────────────────
def _select_ocr():
    from providers.ocr import TesseractProvider, PaddleOCRProvider

    tier = _tier()
    user_ocr = str(_cfg("OCR_PROVIDER", "auto")).lower().strip()

    if user_ocr == "tesseract":
        return TesseractProvider()
    if user_ocr in ("paddleocr", "paddle"):
        use_gpu = tier in ("mid", "high")
        use_layout = tier == "high"
        p = PaddleOCRProvider(use_gpu=use_gpu, use_doc_layout=use_layout)
        if p.is_available():
            return p
        return TesseractProvider()

    # Auto — PaddleOCR on all tiers, Tesseract as fallback
    use_gpu = tier in ("mid", "high")
    use_layout = tier == "high"
    p = PaddleOCRProvider(use_gpu=use_gpu, use_doc_layout=use_layout)
    if p.is_available():
        return p
    return TesseractProvider()


# ── Init — called once at startup ────────────────────────────────────────────
def init_providers():
    """
    Detect hardware + read user config → populate provider_registry.
    Safe to call multiple times (idempotent after first call).
    """
    try:
        provider_registry.set_llm(_select_llm())
    except Exception as e:
        log.error("LLM provider init failed: %s", e)

    try:
        provider_registry.set_tts(_select_tts())
    except Exception as e:
        log.error("TTS provider init failed: %s", e)

    try:
        provider_registry.set_stt(_select_stt())
    except Exception as e:
        log.error("STT provider init failed: %s", e)

    try:
        provider_registry.set_ocr(_select_ocr())
    except Exception as e:
        log.error("OCR provider init failed: %s", e)

    log.info("[provider_router] initialized: %s", provider_registry.summary())
    return provider_registry.summary()


# ── Runtime fallback helpers ─────────────────────────────────────────────────
async def tts_with_fallback(text: str, voice: str = "") -> bytes:
    """Try active TTS provider; fall back down the chain on failure."""
    from providers.tts import EdgeTTSProvider, PiperTTSProvider, KokoroProvider

    primary = provider_registry.get_tts()
    fallback_chain = [EdgeTTSProvider()]  # always available (cloud, no install)

    for provider in ([primary] if primary else []) + fallback_chain:
        if provider is None:
            continue
        try:
            result = await provider.synthesize(text, voice)
            if result:
                return result
        except Exception as e:
            log.warning("[tts_fallback] %s failed: %s", getattr(provider, "name", "?"), e)
    raise RuntimeError("All TTS providers failed")


async def stt_with_fallback(audio_path: str, language: str = "") -> str:
    """Try active STT provider; fall back to smaller Whisper on failure."""
    from providers.stt import FasterWhisperProvider

    primary = provider_registry.get_stt()
    fallback = FasterWhisperProvider("base")

    for provider in ([primary] if primary else []) + [fallback]:
        if provider is None:
            continue
        try:
            result = await provider.transcribe(audio_path, language)
            if result:
                return result
        except Exception as e:
            log.warning("[stt_fallback] %s failed: %s", getattr(provider, "name", "?"), e)
    raise RuntimeError("All STT providers failed")


async def ocr_with_fallback(image_path: str, language: str = "en") -> str:
    """Try PaddleOCR; fall back to Tesseract."""
    from providers.ocr import TesseractProvider

    primary = provider_registry.get_ocr()
    fallback = TesseractProvider()

    for provider in ([primary] if primary else []) + [fallback]:
        if provider is None:
            continue
        if not provider.is_available():
            continue
        try:
            result = await provider.extract_text(image_path, language)
            if result:
                return result
        except Exception as e:
            log.warning("[ocr_fallback] %s failed: %s", getattr(provider, "name", "?"), e)
    raise RuntimeError("All OCR providers failed")
