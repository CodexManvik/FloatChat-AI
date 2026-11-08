"""
Thin client for an OpenAI-compatible chat completions endpoint.
Returns None whenever no LLM is configured or the call fails, so callers can
fall back to data-only answers.
"""

import json
import logging
import time
from collections.abc import Iterator

import requests

from floatchat import config

logger = logging.getLogger(__name__)
MAX_RETRY_WAIT = 10.0
_sleep = time.sleep  # replaced in tests


def is_configured() -> bool:
    if not (config.LLM_BASE_URL and config.LLM_MODEL):
        return False
    # Hosted APIs (Groq, OpenAI, ...) need a key; until one is added, run without an LLM
    if config.LLM_BASE_URL.startswith("https://") and not config.LLM_API_KEY:
        return False
    return True


def _payload(prompt: str, system: str | None, temperature: float, max_tokens: int, json_mode: bool,
             stream: bool = False) -> dict:
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    payload = {"model": config.LLM_MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if stream:
        payload["stream"] = True
    return payload


def _post(payload: dict, stream: bool = False):
    """POST to the chat endpoint, retrying once on a rate limit (HTTP 429) after Retry-After (max 10 s)."""
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    for attempt in (1, 2):
        resp = requests.post(f"{config.LLM_BASE_URL}/chat/completions", json=payload, headers=headers,
                             timeout=config.LLM_TIMEOUT, stream=stream)
        if resp.status_code != 429 or attempt == 2:
            resp.raise_for_status()
            return resp
        try:
            wait = float(resp.headers.get("retry-after", 2))
        except ValueError:
            wait = 2.0
        logger.info("LLM rate-limited; retrying in %.1f s", min(wait, MAX_RETRY_WAIT))
        _sleep(min(wait, MAX_RETRY_WAIT))


def chat(prompt: str, system: str | None = None, temperature: float = 0.2, max_tokens: int = 600,
         json_mode: bool = False) -> str | None:
    if not is_configured():
        return None
    try:
        resp = _post(_payload(prompt, system, temperature, max_tokens, json_mode))
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return None


def chat_stream(prompt: str, system: str | None = None, temperature: float = 0.2,
                max_tokens: int = 600) -> Iterator[str]:
    """Yield the answer text as the LLM writes it; yields nothing if no LLM is available or the call fails."""
    if not is_configured():
        return
    try:
        resp = _post(_payload(prompt, system, temperature, max_tokens, json_mode=False, stream=True), stream=True)
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data = line[len("data: "):]
            if data.strip() == "[DONE]":
                break
            text = (json.loads(data)["choices"][0].get("delta") or {}).get("content")
            if text:
                yield text
        resp.close()
    except Exception as e:
        logger.warning(f"LLM stream failed: {e}")


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
