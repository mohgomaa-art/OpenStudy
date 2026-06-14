"""
Thin wrapper around the google-genai context-cache API.

Lifecycle:
  * create(model, contents, system_instruction, display_name, ttl_s)
      -> (cache_name, expires_at_epoch, api_key_used)
  * delete(cache_name, api_key=None) — best-effort, swallows errors
  * key_id_for(api_key) / find_key_by_id(key_id) — stable 16-char hash so
    we can persist "which key owns this cache" in SQLite without storing
    the plaintext key itself.

Caches are bound to the (api_key, model) that created them. Reuse calls must
hit that exact pair — see services.gemini_client.generate_text_stream_pinned.
"""

import hashlib
import logging
import time

from google import genai
from google.genai import types

from services.gemini_client import get_rotator, get_gemini_client

logger = logging.getLogger(__name__)


def key_id_for(api_key: str) -> str:
    """Stable 16-char identifier so we don't persist plaintext keys in SQLite."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def find_key_by_id(key_id: str) -> str | None:
    """Reverse the stable hash against the rotator's currently-loaded keys."""
    if not key_id:
        return None
    rotator = get_rotator()
    for k in rotator.keys:
        if key_id_for(k) == key_id:
            return k
    return None


def _normalize_model(model: str) -> str:
    return model if model.startswith("models/") else f"models/{model}"


def create(
    model: str,
    contents: str,
    system_instruction: str | None,
    display_name: str,
    ttl_s: int = 1800,
):
    """
    Create a context cache for `contents` + `system_instruction`.

    Returns (cache_name, expires_at_epoch, api_key_used).
    Raises if no key is available or the SDK call fails — callers should
    catch and fall through to the inline-doc path.
    """
    rotator = get_rotator()
    rotator.reload_keys()

    now = time.time()
    available = [k for k in rotator.keys if now >= rotator.cool_downs.get(k, 0)]
    if not available:
        raise RuntimeError("No available Gemini keys to create cache")
    api_key = available[0]

    client = get_gemini_client(api_key)
    cfg = types.CreateCachedContentConfig(
        contents=[contents],
        ttl=f"{ttl_s}s",
        display_name=display_name,
    )
    if system_instruction:
        cfg.system_instruction = system_instruction

    cache = client.caches.create(model=_normalize_model(model), config=cfg)
    expires_at = int(time.time() + ttl_s)
    logger.info(f"[gemini_cache] Created {cache.name} (model={model}, ttl={ttl_s}s, key=...{api_key[-4:]})")
    return cache.name, expires_at, api_key


def delete(cache_name: str, api_key: str | None = None) -> None:
    """
    Best-effort cache delete. Tries the provided key first, then falls back
    to every loaded key — useful when the owning key has been removed from
    the rotator since the cache was created.
    """
    if not cache_name:
        return
    rotator = get_rotator()
    keys_to_try = []
    if api_key:
        keys_to_try.append(api_key)
    keys_to_try.extend(k for k in rotator.keys if k != api_key)

    for k in keys_to_try:
        if not k:
            continue
        try:
            client = get_gemini_client(k)
            client.caches.delete(name=cache_name)
            logger.info(f"[gemini_cache] Deleted {cache_name} via key ...{k[-4:]}")
            return
        except Exception as e:
            logger.debug(f"[gemini_cache] delete failed for key ...{k[-4:]}: {e}")
            continue
    logger.warning(f"[gemini_cache] Could not delete {cache_name} with any loaded key")
