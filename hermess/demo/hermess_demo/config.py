"""ChatModel construction — OpenAI-compatible (DeepSeek / Qwen)."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

_DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = "deepseek-chat"


def build_chat_model(
    *,
    temperature: float = 0.0,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> ChatOpenAI:
    """Return a configured ChatOpenAI instance.

    Precedence for each setting: explicit arg → env var → built-in default.

    Env vars:
        DEEPSEEK_API_KEY / OPENAI_API_KEY
        DEEPSEEK_BASE_URL / OPENAI_BASE_URL
        DEEPSEEK_MODEL   / OPENAI_MODEL
    """
    api_key = (
        api_key
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "No API key found. Set DEEPSEEK_API_KEY or OPENAI_API_KEY in your "
            ".env file."
        )

    base_url = (
        base_url
        or os.getenv("DEEPSEEK_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or _DEFAULT_BASE_URL
    )
    model = (
        model
        or os.getenv("DEEPSEEK_MODEL")
        or os.getenv("OPENAI_MODEL")
        or _DEFAULT_MODEL
    )

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )
