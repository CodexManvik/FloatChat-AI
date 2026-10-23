"""
Thin client for an OpenAI-compatible chat completions endpoint.
Returns None whenever no LLM is configured or the call fails, so callers can
fall back to data-only answers.
"""

import logging

import requests

import config

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    if not (config.LLM_BASE_URL and config.LLM_MODEL):
        return False
    # Hosted APIs (Groq, OpenAI, ...) need a key; until one is added, run without an LLM
    if config.LLM_BASE_URL.startswith("https://") and not config.LLM_API_KEY:
        return False
    return True


def chat(prompt: str, system: str | None = None, temperature: float = 0.2, max_tokens: int = 600) -> str | None:
    if not is_configured():
        return None

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"

    try:
        resp = requests.post(
            f"{config.LLM_BASE_URL}/chat/completions",
            json={
                "model": config.LLM_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            headers=headers,
            timeout=config.LLM_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return None


def status() -> dict:
    """Report whether the configured LLM endpoint is reachable."""
    if not is_configured():
        return {"configured": False, "reachable": False, "model": None, "error": None}
    error = None
    try:
        headers = {"Authorization": f"Bearer {config.LLM_API_KEY}"} if config.LLM_API_KEY else {}
        resp = requests.get(f"{config.LLM_BASE_URL}/models", headers=headers, timeout=5)
        reachable = resp.ok
        if resp.status_code in (401, 403):
            error = "missing or invalid LLM_API_KEY"
        elif not resp.ok:
            error = f"HTTP {resp.status_code}"
    except Exception as e:
        reachable, error = False, f"cannot connect ({e.__class__.__name__})"
    return {"configured": True, "reachable": reachable, "model": config.LLM_MODEL, "error": error}
