"""Pluggable language-model backends for the assistant.

Pick one with environment variables (see .env.example):

  LLM_PROVIDER=gemini     LLM_API_KEY=...           (default model: GEMINI_MODEL)
  LLM_PROVIDER=anthropic  LLM_API_KEY=...           (default model: claude-haiku-5-5)
  LLM_PROVIDER=ollama     (local, free; LLM_MODEL=llama3.2, base http://localhost:11434/v1)
  LLM_PROVIDER=openai     LLM_API_KEY=...           (any OpenAI-compatible server via LLM_BASE_URL)

With no provider configured the assistant falls back to built-in rules, so the
app always works offline.

Privacy: the provider is only ever chosen explicitly. The app deliberately does
NOT pick up generic keys such as ANTHROPIC_API_KEY from your shell environment,
because your scan data would then be sent to that service without you asking.
(The one exception is the old GEMINI_API_KEY setting, kept for compatibility.)
"""

from __future__ import annotations

import httpx

from app.core.config import settings

ANTHROPIC_VERSION = "2023-06-01"
TIMEOUT_S = 30.0


class LLMError(RuntimeError):
    pass


def provider() -> str | None:
    p = (settings.LLM_PROVIDER or "").strip().lower()
    if p in {"gemini", "anthropic", "openai"}:
        return p
    if p == "ollama":
        return "openai"
    if p:
        return None
    return "gemini" if settings.GEMINI_API_KEY else None  # legacy setting only


def _openai_base() -> str:
    if settings.LLM_BASE_URL:
        return settings.LLM_BASE_URL.rstrip("/")
    return "http://localhost:11434/v1" if (settings.LLM_PROVIDER or "").lower() == "ollama" else "https://api.openai.com/v1"


def complete(system: str, prompt: str, client: httpx.Client | None = None) -> str:
    """Return the model's text answer. Raises LLMError on any failure."""
    which = provider()
    if which is None:
        raise LLMError("no language model configured")
    try:
        if which == "gemini":
            return _gemini(system, prompt)
        own = client or httpx.Client(timeout=TIMEOUT_S)
        try:
            return _anthropic(system, prompt, own) if which == "anthropic" else _openai(system, prompt, own)
        finally:
            if client is None:
                own.close()
    except LLMError:
        raise
    except Exception as exc:  # noqa: BLE001 - network, auth, quota, malformed reply...
        raise LLMError(f"{which} request failed: {exc.__class__.__name__}") from exc


def _gemini(system: str, prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.LLM_API_KEY or settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=settings.LLM_MODEL or settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, temperature=0.2),
    )
    return (response.text or "").strip()


def _anthropic(system: str, prompt: str, client: httpx.Client) -> str:
    r = client.post(
        f"{(settings.LLM_BASE_URL or 'https://api.anthropic.com').rstrip('/')}/v1/messages",
        headers={"x-api-key": settings.LLM_API_KEY, "anthropic-version": ANTHROPIC_VERSION},
        json={
            "model": settings.LLM_MODEL or "claude-haiku-5-5",
            "max_tokens": 500,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip()


def _openai(system: str, prompt: str, client: httpx.Client) -> str:
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"} if settings.LLM_API_KEY else {}
    r = client.post(
        f"{_openai_base()}/chat/completions",
        headers=headers,
        json={
            "model": settings.LLM_MODEL or "llama3.2",
            "temperature": 0.2,
            "max_tokens": 500,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        },
    )
    r.raise_for_status()
    return (r.json()["choices"][0]["message"]["content"] or "").strip()
