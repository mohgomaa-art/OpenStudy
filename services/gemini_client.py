"""
Gemini API client with key rotation, model fallback, and context-caching support.

Moved from visual-rag/gemini_client.py during the RAG removal. The rotator and
retry logic are unchanged — only the config plumbing was switched from
visual-rag/config.py to direct env reads via services.config, and two surfaces
were added for context caching:

  * `_call_gemini_stream_with_retry(..., cached_content=...)` — pass through to
    the SDK's `GenerateContentConfig.cached_content` so the rotator can stream
    against an existing cache.
  * `generate_text_stream_pinned(prompt, api_key, model, cached_content, ...)`
    — bypass the rotator entirely and use a specific key/model pair. The cache
    is bound to the key that created it, so reuse must run on that key.
"""

import os
import re
import time
import logging
from google import genai
from google.genai import types

from services.config import config_service

logger = logging.getLogger("gemini_client")
logger.setLevel(logging.INFO)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "") or config_service.get(name, default) or default


def _default_model() -> str:
    return _env("GEMINI_MODEL", "gemini-2.0-flash")


MAX_CHAT_TOKENS = int(os.environ.get("MAX_CHAT_TOKENS", "8192"))
MAX_VISUAL_TOKENS = int(os.environ.get("MAX_VISUAL_TOKENS", "16384"))
MAX_JSON_TOKENS = int(os.environ.get("MAX_JSON_TOKENS", "800"))


class APIKeyRotator:
    def __init__(self):
        self.keys = []
        self.cool_downs = {}
        self.current_idx = 0
        self.reload_keys()

    def reload_keys(self):
        keys_str = _env("GEMINI_API_KEYS", "")
        if keys_str:
            self.keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        else:
            single_key = _env("GEMINI_API_KEY", "")
            self.keys = [single_key] if single_key else []
        logger.info(f"[Rotator] Loaded {len(self.keys)} Gemini API keys.")

    def get_next_key(self) -> str:
        if not self.keys:
            raise ValueError(
                "No Gemini API keys are configured. "
                "Add GEMINI_API_KEYS (comma-separated) or GEMINI_API_KEY to the environment."
            )
        now = time.time()
        available = [k for k in self.keys if now >= self.cool_downs.get(k, 0)]
        if not available:
            logger.warning("[Rotator] All Gemini keys in cooldown — resetting.")
            self.cool_downs.clear()
            available = self.keys
        self.current_idx = (self.current_idx + 1) % len(available)
        return available[self.current_idx]


class RateLimitError(Exception):
    def __init__(self, retry_in_seconds: float, total_keys: int, available_keys: int, reason: str = "all_keys_cooling_down"):
        super().__init__(f"All {total_keys} Gemini keys are rate-limited. Retry in {retry_in_seconds:.0f}s.")
        self.retry_in_seconds = max(0.0, float(retry_in_seconds))
        self.total_keys = int(total_keys)
        self.available_keys = int(available_keys)
        self.reason = reason


class CacheNotFoundError(Exception):
    """The cached_content name passed to generate is no longer valid (404)."""


def rotator_status() -> dict:
    r = get_rotator()
    now = time.time()
    keys = list(r.keys)
    cooldowns = []
    available = 0
    soonest = None
    for k in keys:
        cool_until = r.cool_downs.get(k, 0)
        remaining = max(0.0, cool_until - now)
        if remaining <= 0:
            available += 1
        else:
            if soonest is None or remaining < soonest:
                soonest = remaining
        cooldowns.append({
            "masked": (f"...{k[-4:]}" if len(k) > 4 else "..."),
            "cooldown_remaining": round(remaining, 1),
        })
    return {
        "total_keys": len(keys),
        "available_keys": available,
        "keys": cooldowns,
        "earliest_available_in": round(soonest, 1) if soonest is not None else 0.0,
    }


_rotator = None
_clients = {}
_key_models_cache = {}


def get_rotator() -> APIKeyRotator:
    global _rotator
    if _rotator is None:
        _rotator = APIKeyRotator()
    return _rotator


def get_gemini_client(api_key: str) -> genai.Client:
    if api_key not in _clients:
        _clients[api_key] = genai.Client(api_key=api_key)
    return _clients[api_key]


def _get_working_models(key: str, client: genai.Client) -> list[str]:
    if key in _key_models_cache:
        return _key_models_cache[key]
    try:
        models = list(client.models.list())
        names = []
        for m in models:
            n = m.name[7:] if m.name.startswith("models/") else m.name
            names.append(n)
        preferred = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-2.5-flash",
            "gemini-1.5-pro",
            "gemini-2.5-pro",
        ]
        config_model = _default_model()
        if config_model.startswith("models/"):
            config_model = config_model[7:]
        if config_model and config_model not in preferred:
            preferred.insert(0, config_model)
        elif config_model in preferred:
            preferred.remove(config_model)
            preferred.insert(0, config_model)

        ranked = list(preferred)
        for n in names:
            if n not in ranked and ("gemini" in n or "gemma" in n) and not any(x in n for x in ["embed", "tts", "image", "audio", "vision-preview"]):
                ranked.append(n)
        if not ranked:
            ranked = ["gemini-2.0-flash", "gemini-2.5-flash"]
        _key_models_cache[key] = ranked
        logger.info(f"[Rotator] Auto-detected models for key ...{key[-6:]}: {ranked}")
        return ranked
    except Exception as e:
        logger.error(f"[Rotator] Failed to list models for key ...{key[-6:]}: {e}")
        return ["gemini-2.0-flash", "gemini-2.5-flash"]


def _parse_retry_seconds(message: str) -> float:
    match = re.search(r"Please retry in (\d+\.?\d*)(s|ms)", message, re.IGNORECASE)
    if match:
        val = float(match.group(1))
        unit = match.group(2).lower()
        return (val / 1000.0 + 0.1) if unit == "ms" else val + 0.1
    return 1.5


def _call_gemini_with_retry(
    contents: str,
    temperature: float,
    max_tokens: int,
    response_mime_type: str = None,
    response_schema=None,
    system_instruction=None,
) -> str:
    from google.genai import errors
    rotator = get_rotator()
    rotator.reload_keys()

    last_error = None
    for outer_attempt in range(3):
        now = time.time()
        start_idx = rotator.current_idx
        ordered = rotator.keys[start_idx:] + rotator.keys[:start_idx] if start_idx < len(rotator.keys) else rotator.keys
        available = [k for k in ordered if now >= rotator.cool_downs.get(k, 0)]

        if not available:
            min_cool_time = min((rotator.cool_downs.get(k, 0) for k in rotator.keys), default=now)
            sleep_for = max(0.1, min(10.0, min_cool_time - now))
            logger.warning(f"[Rotator] All keys on cooldown — sleeping {sleep_for:.2f}s.")
            time.sleep(sleep_for)
            now = time.time()
            available = [k for k in ordered if now >= rotator.cool_downs.get(k, 0)]

        if not available:
            now2 = time.time()
            soonest = min((rotator.cool_downs.get(k, 0) - now2 for k in rotator.keys), default=0.0)
            raise RateLimitError(max(0.0, soonest), len(rotator.keys), 0, "all_keys_cooling_down")

        for key in available:
            masked = f"...{key[-6:]}" if len(key) > 6 else "InvalidKey"
            try:
                client = get_gemini_client(key)
                models = _get_working_models(key, client)
            except Exception as e:
                rotator.cool_downs[key] = time.time() + 10
                last_error = e
                continue

            tried_any = False
            for model_name in models:
                model_cd_key = f"{key}:{model_name}"
                if time.time() < rotator.cool_downs.get(model_cd_key, 0):
                    continue
                tried_any = True
                try:
                    gen_config = types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    )
                    if response_mime_type:
                        gen_config.response_mime_type = response_mime_type
                    if response_schema:
                        gen_config.response_schema = response_schema
                    if system_instruction:
                        gen_config.system_instruction = system_instruction

                    logger.info(f"[Rotator] Generating with key {masked}, model {model_name} (attempt {outer_attempt+1}/3)")
                    response = client.models.generate_content(model=model_name, contents=contents, config=gen_config)
                    if key in rotator.keys:
                        rotator.current_idx = (rotator.keys.index(key) + 1) % len(rotator.keys)
                    return response.text or ""
                except errors.APIError as api_err:
                    last_error = api_err
                    code = api_err.code
                    msg = api_err.message if hasattr(api_err, "message") else str(api_err)
                    if code == 429:
                        rotator.cool_downs[model_cd_key] = time.time() + _parse_retry_seconds(msg)
                        continue
                    elif code in (500, 503, 504):
                        rotator.cool_downs[model_cd_key] = time.time() + 10
                        continue
                    elif code == 404:
                        rotator.cool_downs[model_cd_key] = time.time() + 86400
                        continue
                    elif code in (400, 401, 403):
                        rotator.cool_downs[key] = time.time() + 600
                        break
                    else:
                        rotator.cool_downs[key] = time.time() + 5
                        break
                except Exception as other_err:
                    last_error = other_err
                    rotator.cool_downs[key] = time.time() + 2
                    break
            if tried_any:
                rotator.cool_downs[key] = time.time() + 5

    raise RuntimeError(f"All Gemini keys/models failed. Last error: {last_error}")


def generate_json(prompt: str, response_schema=None, system_instruction=None) -> str:
    return _call_gemini_with_retry(
        contents=prompt,
        temperature=0.1,
        max_tokens=MAX_JSON_TOKENS,
        response_mime_type="application/json",
        response_schema=response_schema,
        system_instruction=system_instruction,
    )


def generate_text(prompt: str, system_instruction=None, max_tokens: int = None) -> str:
    return _call_gemini_with_retry(
        contents=prompt,
        temperature=0.7,
        max_tokens=max_tokens if max_tokens is not None else MAX_CHAT_TOKENS,
        system_instruction=system_instruction,
    )


def _build_gen_config(temperature: float, max_tokens: int, system_instruction=None, cached_content=None):
    """
    Build a GenerateContentConfig. system_instruction and cached_content are
    mutually exclusive — when a cache is in use, its system instruction was
    bound at create-time and re-setting it here will be ignored (or rejected
    by the API depending on SDK version).
    """
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if cached_content:
        cfg.cached_content = cached_content
    elif system_instruction:
        cfg.system_instruction = system_instruction
    return cfg


def _is_cache_not_found(err) -> bool:
    """Heuristic: SDK raises APIError(404) with 'CachedContent' in the message."""
    msg = str(err).lower()
    return "cachedcontent" in msg or "cached_content" in msg or ("cache" in msg and "not found" in msg)


def _call_gemini_stream_with_retry(
    contents: str,
    temperature: float,
    max_tokens: int,
    system_instruction=None,
    cached_content=None,
):
    from google.genai import errors
    rotator = get_rotator()
    rotator.reload_keys()

    last_error = None
    for outer_attempt in range(3):
        now = time.time()
        start_idx = rotator.current_idx
        ordered = rotator.keys[start_idx:] + rotator.keys[:start_idx] if start_idx < len(rotator.keys) else rotator.keys
        available = [k for k in ordered if now >= rotator.cool_downs.get(k, 0)]

        if not available:
            min_cool_time = min((rotator.cool_downs.get(k, 0) for k in rotator.keys), default=now)
            sleep_for = max(0.1, min(10.0, min_cool_time - now))
            time.sleep(sleep_for)
            now = time.time()
            available = [k for k in ordered if now >= rotator.cool_downs.get(k, 0)]

        if not available:
            now2 = time.time()
            soonest = min((rotator.cool_downs.get(k, 0) - now2 for k in rotator.keys), default=0.0)
            raise RateLimitError(max(0.0, soonest), len(rotator.keys), 0, "all_keys_cooling_down")

        for key in available:
            masked = f"...{key[-6:]}" if len(key) > 6 else "InvalidKey"
            try:
                client = get_gemini_client(key)
                models = _get_working_models(key, client)
            except Exception as e:
                rotator.cool_downs[key] = time.time() + 10
                last_error = e
                continue

            tried_any = False
            for model_name in models:
                model_cd_key = f"{key}:{model_name}"
                if time.time() < rotator.cool_downs.get(model_cd_key, 0):
                    continue
                tried_any = True
                try:
                    cfg = _build_gen_config(temperature, max_tokens, system_instruction, cached_content)
                    logger.info(f"[Rotator] Streaming with key {masked}, model {model_name} (attempt {outer_attempt+1}/3)")
                    response = client.models.generate_content_stream(model=model_name, contents=contents, config=cfg)
                    it = iter(response)
                    try:
                        first = next(it)
                    except StopIteration:
                        if key in rotator.keys:
                            rotator.current_idx = (rotator.keys.index(key) + 1) % len(rotator.keys)
                        return
                    yield first.text or ""
                    for chunk in it:
                        yield chunk.text or ""
                    if key in rotator.keys:
                        rotator.current_idx = (rotator.keys.index(key) + 1) % len(rotator.keys)
                    return
                except errors.APIError as api_err:
                    last_error = api_err
                    code = api_err.code
                    if code == 404 and cached_content and _is_cache_not_found(api_err):
                        raise CacheNotFoundError(str(api_err))
                    if code == 429:
                        rotator.cool_downs[model_cd_key] = time.time() + _parse_retry_seconds(api_err.message if hasattr(api_err, "message") else str(api_err))
                        continue
                    elif code in (500, 503, 504):
                        rotator.cool_downs[model_cd_key] = time.time() + 10
                        continue
                    elif code == 404:
                        rotator.cool_downs[model_cd_key] = time.time() + 86400
                        continue
                    elif code in (400, 401, 403):
                        rotator.cool_downs[key] = time.time() + 600
                        break
                    else:
                        rotator.cool_downs[key] = time.time() + 5
                        break
                except Exception as other_err:
                    last_error = other_err
                    rotator.cool_downs[key] = time.time() + 2
                    break
            if tried_any:
                rotator.cool_downs[key] = time.time() + 5

    raise RuntimeError(f"All Gemini keys/models failed. Last error: {last_error}")


def generate_text_stream(prompt: str, system_instruction=None, cached_content=None):
    return _call_gemini_stream_with_retry(
        contents=prompt,
        temperature=0.7,
        max_tokens=MAX_CHAT_TOKENS,
        system_instruction=system_instruction,
        cached_content=cached_content,
    )


# ── Pinned-key streaming (cache reuse) ────────────────────────────────────────
#
# Gemini context caches are bound to the API key + model that created them.
# When a chat session has a live cache, generate calls MUST hit that exact
# (key, model). The rotator can't help — it'd pick a different key and the
# cached_content reference would 404.

def generate_text_stream_pinned(prompt: str, api_key: str, model: str, cached_content: str | None = None, system_instruction: str | None = None):
    """
    Single-shot streaming generate using a specific key + model. No rotation,
    no model fallback. Raises CacheNotFoundError on a 404 that names the cache
    so the caller can clear it and retry on the rotator.
    """
    from google.genai import errors
    if not api_key:
        raise ValueError("api_key is required for pinned generate")
    client = get_gemini_client(api_key)
    cfg = _build_gen_config(0.7, MAX_CHAT_TOKENS, system_instruction, cached_content)
    try:
        response = client.models.generate_content_stream(model=model, contents=prompt, config=cfg)
        for chunk in response:
            yield chunk.text or ""
    except errors.APIError as api_err:
        if api_err.code == 404 and cached_content and _is_cache_not_found(api_err):
            raise CacheNotFoundError(str(api_err))
        raise
