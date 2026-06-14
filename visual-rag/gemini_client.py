import os
import time
import logging
from google import genai
from google.genai import types
import config

# Setup logging
logger = logging.getLogger("gemini_client")
logger.setLevel(logging.INFO)

class APIKeyRotator:
    def __init__(self):
        self.keys = []
        self.cool_downs = {}  # key -> timestamp_until_cool
        self.current_idx = 0
        self.reload_keys()

    def reload_keys(self):
        # Read comma-separated keys first, fall back to single key
        keys_str = getattr(config, "GEMINI_API_KEYS", "") or os.environ.get("GEMINI_API_KEYS", "")
        if keys_str:
            self.keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        else:
            single_key = getattr(config, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
            self.keys = [single_key] if single_key else []
            
        logger.info(f"[Rotator] Loaded {len(self.keys)} Gemini API keys.")

    def get_next_key(self) -> str:
        if not self.keys:
            raise ValueError(
                "No Gemini API keys are configured. "
                "Please add GEMINI_API_KEYS (comma-separated list) or GEMINI_API_KEY to your .env file."
            )
            
        now = time.time()
        # Filter available keys (not in cool down)
        available_keys = [k for k in self.keys if now >= self.cool_downs.get(k, 0)]
        
        if not available_keys:
            logger.warning("[Rotator] All Gemini API keys are in cooldown! Resetting cooldowns to prevent complete outage.")
            self.cool_downs.clear()
            available_keys = self.keys
            
        # Round-robin selection
        self.current_idx = (self.current_idx + 1) % len(available_keys)
        return available_keys[self.current_idx]

    def report_failure(self, key: str, is_rate_limit: bool = True):
        now = time.time()
        # 60s cooldown for rate limits, 5 mins for key errors/other failures
        cooldown_duration = 60 if is_rate_limit else 300
        self.cool_downs[key] = now + cooldown_duration
        
        masked_key = f"...{key[-6:]}" if len(key) > 6 else "InvalidKey"
        reason = "Rate Limit (429)" if is_rate_limit else "General Failure"
        logger.warning(f"[Rotator] Key {masked_key} placed on cooldown for {cooldown_duration}s due to: {reason}")


class RateLimitError(Exception):
    """Raised when every configured Gemini key is in cooldown.

    Carries structured info the UI can use to render a countdown:
    - retry_in_seconds: earliest moment a key becomes available again
    - total_keys / available_keys: rotator snapshot at giveup time
    - reason: short human-readable label
    """
    def __init__(self, retry_in_seconds: float, total_keys: int, available_keys: int, reason: str = "all_keys_cooling_down"):
        super().__init__(f"All {total_keys} Gemini keys are rate-limited. Retry in {retry_in_seconds:.0f}s.")
        self.retry_in_seconds = max(0.0, float(retry_in_seconds))
        self.total_keys = int(total_keys)
        self.available_keys = int(available_keys)
        self.reason = reason


def rotator_status() -> dict:
    """Snapshot of rotator health for /api/llm/status and SSE rate_limit events."""
    import time as _t
    r = get_rotator()
    now = _t.time()
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

def get_rotator() -> APIKeyRotator:
    global _rotator
    if _rotator is None:
        _rotator = APIKeyRotator()
    return _rotator

_key_models_cache = {}

def get_gemini_client(api_key: str) -> genai.Client:
    global _clients
    if api_key not in _clients:
        _clients[api_key] = genai.Client(api_key=api_key)
    return _clients[api_key]

def _get_working_models(key: str, client: genai.Client) -> list[str]:
    global _key_models_cache
    if key in _key_models_cache:
        return _key_models_cache[key]

    try:
        models = list(client.models.list())
        names = [m.name for m in models]
        # Clean prefix "models/" if present
        clean_names = []
        for name in names:
            if name.startswith("models/"):
                clean_names.append(name[7:])
            else:
                clean_names.append(name)
        
        # Rank according to PREFERRED_MODELS
        # gemini-2.0-flash: 1500 RPD free — always try first
        # gemini-2.5-flash: only 20 RPM free — use as fallback
        preferred = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-2.5-flash",
            "gemini-1.5-pro",
            "gemini-2.5-pro",
            "gemma-4-31b-it"
        ]
        
        # If a specific model is set in config, try that first
        config_model = getattr(config, "GEMINI_MODEL", "gemini-2.0-flash")
        if config_model.startswith("models/"):
            config_model = config_model[7:]
            
        if config_model and config_model not in preferred:
            preferred.insert(0, config_model)
        elif config_model in preferred:
            preferred.remove(config_model)
            preferred.insert(0, config_model)
            
        ranked = []
        for pref in preferred:
            ranked.append(pref)
                
        # Append other models that support generation
        for name in clean_names:
            if name not in ranked:
                # Basic check for generation models
                if ("gemini" in name or "gemma" in name) and not any(x in name for x in ["embed", "tts", "image", "audio", "vision-preview"]):
                    ranked.append(name)
                    
        if not ranked:
            ranked = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash"]  # Fallback defaults
            
        _key_models_cache[key] = ranked
        logger.info(f"[Rotator] Auto-detected models for key ...{key[-6:]}: {ranked}")
        return ranked
    except Exception as e:
        logger.error(f"[Rotator] Failed to list/detect models for key ...{key[-6:]}: {e}")
        return ["gemini-2.5-flash", "gemini-2.0-flash"]

import re

def _call_gemini_with_retry(
    contents: str,
    temperature: float,
    max_tokens: int,
    response_mime_type: str = None,
    response_schema=None,
    system_instruction=None
) -> str:
    """
    Sends a prompt to the Gemini API with key rotation, backoff, and robust error recovery.
    """
    from google.genai import errors
    rotator = get_rotator()
    rotator.reload_keys()

    def parse_retry_seconds(message: str) -> float:
        match = re.search(r"Please retry in (\d+\.?\d*)(s|ms)", message, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            unit = match.group(2).lower()
            if unit == "ms":
                return (val / 1000.0) + 0.1
            else:
                return val + 0.1
        return 1.5

    last_error = None
    # 3 retry loops globally across keys
    for outer_attempt in range(3):
        now = time.time()
        # Order keys starting from current_idx to support true round-robin distribution
        start_idx = rotator.current_idx
        if start_idx < len(rotator.keys):
            ordered_keys = rotator.keys[start_idx:] + rotator.keys[:start_idx]
        else:
            ordered_keys = rotator.keys
            
        available_keys = [k for k in ordered_keys if now >= rotator.cool_downs.get(k, 0)]
        
        # If all keys are in cooldown, find the one that expires first
        if not available_keys:
            min_cool_key = None
            min_cool_time = float('inf')
            for k in rotator.keys:
                cool_until = rotator.cool_downs.get(k, 0)
                if cool_until < min_cool_time:
                    min_cool_time = cool_until
                    min_cool_key = k
            
            if min_cool_key:
                sleep_duration = max(0.1, min_cool_time - now)
                # Cap sleep duration at 10 seconds to avoid long hangs
                if sleep_duration > 10.0:
                    logger.warning(f"[Rotator] Earliest key cooldown is too long ({sleep_duration:.2f}s). Capping sleep at 10s.")
                    sleep_duration = 10.0
                
                logger.warning(f"[Rotator] All keys are on cooldown. Sleeping {sleep_duration:.2f}s...")
                time.sleep(sleep_duration)
                now = time.time()
                
                start_idx = rotator.current_idx
                if start_idx < len(rotator.keys):
                    ordered_keys = rotator.keys[start_idx:] + rotator.keys[:start_idx]
                else:
                    ordered_keys = rotator.keys
                available_keys = [k for k in ordered_keys if now >= rotator.cool_downs.get(k, 0)]
                
        # If still no keys are available (e.g. sleep duration was capped),
        # surface a structured RateLimitError so the UI can show a countdown.
        if not available_keys:
            now2 = time.time()
            soonest = min(
                (rotator.cool_downs.get(k, 0) - now2 for k in rotator.keys),
                default=0.0,
            )
            raise RateLimitError(
                retry_in_seconds=max(0.0, soonest),
                total_keys=len(rotator.keys),
                available_keys=0,
                reason="all_keys_cooling_down",
            )

        # Try active keys in round-robin fashion
        for key in available_keys:
            masked_key = f"...{key[-6:]}" if len(key) > 6 else "InvalidKey"
            try:
                client = get_gemini_client(key)
                models = _get_working_models(key, client)
            except Exception as e:
                logger.error(f"[Rotator] Failed to list models for key {masked_key}: {e}")
                rotator.cool_downs[key] = time.time() + 10
                last_error = e
                continue

            # Try models in ranked order
            tried_any_model = False
            for model_name in models:
                # Check model-specific cooldown
                model_cooldown_key = f"{key}:{model_name}"
                if time.time() < rotator.cool_downs.get(model_cooldown_key, 0):
                    continue
                
                tried_any_model = True
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

                    logger.info(f"[Rotator] Attempting generation using key {masked_key} and model {model_name} (global attempt {outer_attempt+1}/3)")
                    
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=gen_config
                    )
                    if key in rotator.keys:
                        rotator.current_idx = (rotator.keys.index(key) + 1) % len(rotator.keys)
                    return response.text or ""
                except errors.APIError as api_err:
                    last_error = api_err
                    err_code = api_err.code
                    err_msg = api_err.message if hasattr(api_err, "message") else str(api_err)
                    
                    if err_code == 429:
                        retry_after = parse_retry_seconds(err_msg)
                        logger.warning(f"[Rotator] Key {masked_key} rate limited on model {model_name}. Setting model cooldown for {retry_after:.2f}s.")
                        rotator.cool_downs[model_cooldown_key] = time.time() + retry_after
                        continue  # Try next model on same key
                    elif err_code in (500, 503, 504):
                        logger.warning(f"[Rotator] Model {model_name} got transient error {err_code} for key {masked_key}. Trying next model...")
                        # 10s cooldown for transient error on this model-key
                        rotator.cool_downs[model_cooldown_key] = time.time() + 10
                        continue
                    elif err_code == 404:
                        logger.warning(f"[Rotator] Model {model_name} not found (404) for key {masked_key}. Skipping model...")
                        # 24 hours cooldown for this model-key to avoid trying it again
                        rotator.cool_downs[model_cooldown_key] = time.time() + 86400
                        continue
                    elif err_code in (400, 401, 403):
                        logger.error(f"[Rotator] Key {masked_key} invalid/unauthorized (code {err_code}): {err_msg}. Cooldown 10 mins.")
                        rotator.cool_downs[key] = time.time() + 600
                        break  # Rotate to next key
                    else:
                        logger.warning(f"[Rotator] API error {err_code} on key {masked_key}, model {model_name}: {err_msg}")
                        rotator.cool_downs[key] = time.time() + 5
                        break  # Rotate to next key
                except Exception as other_err:
                    last_error = other_err
                    logger.warning(f"[Rotator] Network/unexpected error for key {masked_key}, model {model_name}: {other_err}")
                    rotator.cool_downs[key] = time.time() + 2
                    break  # Rotate to next key

            # If all tried models on this key failed, place the key itself on a brief cooldown
            # so we rotate to the next key before retrying this one.
            if tried_any_model:
                rotator.cool_downs[key] = time.time() + 5

    raise RuntimeError(f"All available Gemini API keys and models failed. Last error: {last_error}")


def generate_json(prompt: str, response_schema=None, system_instruction=None) -> str:
    """
    Sends a prompt to the configured Gemini model, requesting a JSON response.
    Features API key rotation, model auto-detection, and automatic failover retries.
    """
    max_tokens = getattr(config, "MAX_JSON_TOKENS", 800)
    return _call_gemini_with_retry(
        contents=prompt,
        temperature=0.1,
        max_tokens=max_tokens,
        response_mime_type="application/json",
        response_schema=response_schema,
        system_instruction=system_instruction
    )


def generate_text(prompt: str, system_instruction=None) -> str:
    """
    Sends a prompt to the configured Gemini model, requesting plain text response.
    Features API key rotation, model auto-detection, and automatic failover retries.
    """
    max_tokens = getattr(config, "MAX_CHAT_TOKENS", 4000)
    return _call_gemini_with_retry(
        contents=prompt,
        temperature=0.7,
        max_tokens=max_tokens,
        system_instruction=system_instruction
    )


def _call_gemini_stream_with_retry(
    contents: str,
    temperature: float,
    max_tokens: int,
    system_instruction=None
):
    """
    Streams content from Gemini API with key rotation and failover retries.
    """
    from google.genai import errors
    rotator = get_rotator()
    rotator.reload_keys()

    def parse_retry_seconds(message: str) -> float:
        match = re.search(r"Please retry in (\d+\.?\d*)(s|ms)", message, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            unit = match.group(2).lower()
            if unit == "ms":
                return (val / 1000.0) + 0.1
            else:
                return val + 0.1
        return 1.5

    last_error = None
    for outer_attempt in range(3):
        now = time.time()
        start_idx = rotator.current_idx
        if start_idx < len(rotator.keys):
            ordered_keys = rotator.keys[start_idx:] + rotator.keys[:start_idx]
        else:
            ordered_keys = rotator.keys
            
        available_keys = [k for k in ordered_keys if now >= rotator.cool_downs.get(k, 0)]
        
        if not available_keys:
            min_cool_key = None
            min_cool_time = float('inf')
            for k in rotator.keys:
                cool_until = rotator.cool_downs.get(k, 0)
                if cool_until < min_cool_time:
                    min_cool_time = cool_until
                    min_cool_key = k
            
            if min_cool_key:
                sleep_duration = max(0.1, min_cool_time - now)
                if sleep_duration > 10.0:
                    sleep_duration = 10.0
                time.sleep(sleep_duration)
                now = time.time()
                
                start_idx = rotator.current_idx
                if start_idx < len(rotator.keys):
                    ordered_keys = rotator.keys[start_idx:] + rotator.keys[:start_idx]
                else:
                    ordered_keys = rotator.keys
                available_keys = [k for k in ordered_keys if now >= rotator.cool_downs.get(k, 0)]
                
        if not available_keys:
            now2 = time.time()
            soonest = min(
                (rotator.cool_downs.get(k, 0) - now2 for k in rotator.keys),
                default=0.0,
            )
            raise RateLimitError(
                retry_in_seconds=max(0.0, soonest),
                total_keys=len(rotator.keys),
                available_keys=0,
                reason="all_keys_cooling_down",
            )

        for key in available_keys:
            masked_key = f"...{key[-6:]}" if len(key) > 6 else "InvalidKey"
            try:
                client = get_gemini_client(key)
                models = _get_working_models(key, client)
            except Exception as e:
                rotator.cool_downs[key] = time.time() + 10
                last_error = e
                continue

            tried_any_model = False
            for model_name in models:
                model_cooldown_key = f"{key}:{model_name}"
                if time.time() < rotator.cool_downs.get(model_cooldown_key, 0):
                    continue
                
                tried_any_model = True
                try:
                    gen_config = types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    )
                    if system_instruction:
                        gen_config.system_instruction = system_instruction

                    logger.info(f"[Rotator] Attempting streaming generation using key {masked_key} and model {model_name} (global attempt {outer_attempt+1}/3)")
                    
                    response = client.models.generate_content_stream(
                        model=model_name,
                        contents=contents,
                        config=gen_config
                    )
                    
                    # Check first chunk before committing
                    iterator = iter(response)
                    try:
                        first_chunk = next(iterator)
                    except StopIteration:
                        if key in rotator.keys:
                            rotator.current_idx = (rotator.keys.index(key) + 1) % len(rotator.keys)
                        return
                        
                    yield first_chunk.text or ""
                    
                    for chunk in iterator:
                        yield chunk.text or ""
                        
                    if key in rotator.keys:
                        rotator.current_idx = (rotator.keys.index(key) + 1) % len(rotator.keys)
                    return
                except errors.APIError as api_err:
                    last_error = api_err
                    err_code = api_err.code
                    err_msg = api_err.message if hasattr(api_err, "message") else str(api_err)
                    
                    if err_code == 429:
                        retry_after = parse_retry_seconds(err_msg)
                        rotator.cool_downs[model_cooldown_key] = time.time() + retry_after
                        continue
                    elif err_code in (500, 503, 504):
                        rotator.cool_downs[model_cooldown_key] = time.time() + 10
                        continue
                    elif err_code == 404:
                        rotator.cool_downs[model_cooldown_key] = time.time() + 86400
                        continue
                    elif err_code in (400, 401, 403):
                        rotator.cool_downs[key] = time.time() + 600
                        break
                    else:
                        rotator.cool_downs[key] = time.time() + 5
                        break
                except Exception as other_err:
                    last_error = other_err
                    rotator.cool_downs[key] = time.time() + 2
                    break

            if tried_any_model:
                rotator.cool_downs[key] = time.time() + 5

    is_quota = False
    last_msg = str(last_error) if last_error else ""
    try:
        from google.genai import errors as _genai_errors
        if isinstance(last_error, _genai_errors.APIError) and getattr(last_error, "code", None) == 429:
            is_quota = True
    except Exception:
        pass
    if not is_quota and any(s in last_msg.lower() for s in ("429", "rate limit", "resource_exhausted", "quota")):
        is_quota = True
    if is_quota:
        now2 = time.time()
        soonest = min(
            (rotator.cool_downs.get(k, 0) - now2 for k in rotator.keys),
            default=0.0,
        )
        raise RateLimitError(
            retry_in_seconds=max(0.0, soonest if soonest > 0 else parse_retry_seconds(last_msg)),
            total_keys=len(rotator.keys),
            available_keys=sum(1 for k in rotator.keys if rotator.cool_downs.get(k, 0) <= now2),
            reason="quota_exhausted_after_retries",
        )
    raise RuntimeError(f"All available Gemini API keys and models failed. Last error: {last_error}")


def generate_text_stream(prompt: str, system_instruction=None):
    """
    Sends a prompt to the configured Gemini model, requesting plain text response streamed back.
    Features API key rotation, model auto-detection, and automatic failover retries.
    """
    max_tokens = getattr(config, "MAX_CHAT_TOKENS", 4000)
    return _call_gemini_stream_with_retry(
        contents=prompt,
        temperature=0.7,
        max_tokens=max_tokens,
        system_instruction=system_instruction
    )


