"""
Anthropic Claude streaming client.
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
) -> Iterator[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_instruction:
        kwargs["system"] = system_instruction

    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            if text:
                yield text


def generate_text(
    prompt: str,
    api_key: str,
    model: str,
    system_instruction: str | None = None,
    max_tokens: int = MAX_VISUAL_TOKENS,
) -> str:
    return "".join(generate_text_stream(
        prompt, api_key, model, system_instruction, max_tokens
    ))
