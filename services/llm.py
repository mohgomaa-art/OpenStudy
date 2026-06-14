import os
import json
import logging
from typing import Iterator

logger = logging.getLogger("llm_service")

from services import gemini_client


class LLMService:
    def generate(self, prompt, system_instruction=None, model=None, fast=True, max_tokens=None):
        """Generate a non-streaming Gemini response (used for mind-map JSON and visual HTML)."""
        try:
            return gemini_client.generate_text(prompt, system_instruction=system_instruction, max_tokens=max_tokens)
        except Exception as e:
            logger.error("[LLMService] generate() failed: %s", e)
            return ""

    def _visual_max_tokens(self) -> int:
        return gemini_client.MAX_VISUAL_TOKENS

    def generate_json(self, prompt, model=None):
        """Generate a structured JSON response via Gemini."""
        try:
            res_text = gemini_client.generate_json(prompt)
            start = res_text.find("{")
            end = res_text.rfind("}")
            if start == -1 or end == -1:
                return {}
            return json.loads(res_text[start:end+1])
        except Exception as e:
            logger.error("[LLMService] generate_json() failed: %s", e)
            return {}

    async def generate_stream_async(
        self,
        prompt,
        system_instruction=None,
        provider="gemini",
        cached_content=None,
        pinned_api_key=None,
        pinned_model=None,
        # per-provider keys/model passed from settings
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        """
        Stream tokens from the configured provider.

        Supported providers:
          gemini     — Google Gemini (with key rotation + context cache)
          openai     — OpenAI Chat Completions
          anthropic  — Anthropic Claude
          groq       — Groq (OpenAI-compatible)
          openrouter — OpenRouter (OpenAI-compatible, different base_url)
          ollama     — Local Ollama (REST API)
        """
        import asyncio
        from queue import Queue, Empty
        import threading

        if provider == "ollama":
            async for token in self._generate_ollama_stream_async(prompt, system_instruction):
                yield token
            return

        if provider in ("openai", "groq", "openrouter"):
            async for token in self._generate_openai_compat_stream_async(
                prompt, provider, api_key, model, system_instruction, base_url
            ):
                yield token
            return

        if provider == "anthropic":
            async for token in self._generate_anthropic_stream_async(
                prompt, api_key, model, system_instruction
            ):
                yield token
            return

        # Default: Gemini with key rotation + optional context cache
        q = Queue()

        def run_stream():
            try:
                if cached_content:
                    if not pinned_api_key or not pinned_model:
                        q.put(("error", "cached_content requires pinned_api_key and pinned_model"))
                        return
                    iterator = gemini_client.generate_text_stream_pinned(
                        prompt,
                        api_key=pinned_api_key,
                        model=pinned_model,
                        cached_content=cached_content,
                        system_instruction=None,
                    )
                else:
                    iterator = gemini_client.generate_text_stream(
                        prompt, system_instruction=system_instruction,
                    )
                for chunk in iterator:
                    q.put(("token", chunk))
                q.put(("done", None))
            except gemini_client.CacheNotFoundError as cnf:
                q.put(("cache_not_found", str(cnf)))
            except Exception as e:
                q.put(("error", str(e)))

        threading.Thread(target=run_stream, daemon=True).start()

        loop = asyncio.get_running_loop()
        while True:
            try:
                msg_type, val = await loop.run_in_executor(None, lambda: q.get(timeout=0.1))
            except Empty:
                await asyncio.sleep(0.01)
                continue

            if msg_type == "token":
                yield val
            elif msg_type == "done":
                return
            elif msg_type == "cache_not_found":
                raise gemini_client.CacheNotFoundError(val)
            elif msg_type == "error":
                logger.error(f"[LLMStream] Streaming failed: {val}")
                raise RuntimeError(val)

    async def _generate_openai_compat_stream_async(
        self, prompt, provider, api_key, model, system_instruction, base_url
    ):
        import asyncio
        from queue import Queue, Empty
        import threading
        from services import openai_client

        if not api_key:
            raise RuntimeError(f"No API key configured for provider: {provider}")
        if not model:
            raise RuntimeError(f"No model configured for provider: {provider}")

        # Resolve base_url for known providers
        if not base_url:
            if provider == "groq":
                base_url = "https://api.groq.com/openai/v1"
            elif provider == "openrouter":
                base_url = "https://openrouter.ai/api/v1"
            else:
                base_url = None  # OpenAI default

        q = Queue()

        def run_stream():
            try:
                for chunk in openai_client.generate_text_stream(
                    prompt, api_key, model, system_instruction, base_url=base_url
                ):
                    q.put(("token", chunk))
                q.put(("done", None))
            except Exception as e:
                q.put(("error", str(e)))

        threading.Thread(target=run_stream, daemon=True).start()
        loop = asyncio.get_running_loop()
        while True:
            try:
                msg_type, val = await loop.run_in_executor(None, lambda: q.get(timeout=0.1))
            except Empty:
                await asyncio.sleep(0.01)
                continue
            if msg_type == "token":
                yield val
            elif msg_type == "done":
                return
            elif msg_type == "error":
                raise RuntimeError(val)

    async def _generate_anthropic_stream_async(
        self, prompt, api_key, model, system_instruction
    ):
        import asyncio
        from queue import Queue, Empty
        import threading
        from services import anthropic_client

        if not api_key:
            raise RuntimeError("No API key configured for Anthropic")
        if not model:
            raise RuntimeError("No model configured for Anthropic")

        q = Queue()

        def run_stream():
            try:
                for chunk in anthropic_client.generate_text_stream(
                    prompt, api_key, model, system_instruction
                ):
                    q.put(("token", chunk))
                q.put(("done", None))
            except Exception as e:
                q.put(("error", str(e)))

        threading.Thread(target=run_stream, daemon=True).start()
        loop = asyncio.get_running_loop()
        while True:
            try:
                msg_type, val = await loop.run_in_executor(None, lambda: q.get(timeout=0.1))
            except Empty:
                await asyncio.sleep(0.01)
                continue
            if msg_type == "token":
                yield val
            elif msg_type == "done":
                return
            elif msg_type == "error":
                raise RuntimeError(val)

    async def _generate_ollama_stream_async(self, prompt, system_instruction=None):
        import httpx
        import json

        ollama_model = os.environ.get("OLLAMA_MODEL", "llama3")
        ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

        payload = {
            "model": ollama_model,
            "prompt": prompt,
            "stream": True
        }
        if system_instruction:
            payload["system"] = system_instruction

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    f"{ollama_host}/api/generate",
                    json=payload
                ) as response:
                    if response.status_code != 200:
                        yield f"Ollama error: HTTP {response.status_code}"
                        return
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                yield token
                            if data.get("done", False):
                                break
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"[Ollama] Connection failed: {e}")
            yield (
                f"\n[Error: Could not connect to local Ollama on {ollama_host}. "
                f"Please ensure Ollama is running and has the model '{ollama_model}' pulled.]"
            )


llm_service = LLMService()


async def generate_json(prompt, fast=True):
    return llm_service.generate_json(prompt)
