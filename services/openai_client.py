"""
OpenAI-compatible streaming client.
Handles OpenAI, Groq, and OpenRouter (all share the same SDK interface).
"""
import logging
from typing import Iterator

logger = logging.getLogger(__name__)

MAX_CHAT_TOKENS = 8192
MAX_VISUAL_TOKENS = 16384


def generate_text_stream(
    prompt: str,
    api_key: str,
    model: str,
    system_instruction: str | None = None,
    max_tokens: int = MAX_CHAT_TOKENS,
    base_url: str | None = None,
) -> Iterator[str]:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=base_url or "https://api.openai.com/v1",
    )
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    with client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta


def generate_text(
    prompt: str,
    api_key: str,
    model: str,
    system_instruction: str | None = None,
    max_tokens: int = MAX_VISUAL_TOKENS,
    base_url: str | None = None,
) -> str:
    return "".join(generate_text_stream(
        prompt, api_key, model, system_instruction, max_tokens, base_url
    ))
