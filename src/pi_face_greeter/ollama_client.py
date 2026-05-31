from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("pi_face_greeter.ollama_client")


def _request(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama request failed: {exc.reason}") from exc

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama returned invalid JSON") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Ollama returned unexpected response type")
    return parsed


def health_check(base_url: str, timeout: float = 3.0) -> bool:
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        _request(url, timeout=timeout)
        return True
    except Exception:
        logger.debug("Ollama health check failed for %s", base_url, exc_info=True)
        return False


def generate(
    prompt: str,
    *,
    base_url: str,
    model: str,
    timeout: float = 8.0,
    max_tokens: int = 60,
    temperature: float = 0.7,
) -> str:
    url = f"{base_url.rstrip('/')}/api/generate"
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
        },
    }
    result = _request(url, method="POST", body=body, timeout=timeout)
    response = result.get("response")
    if not isinstance(response, str) or not response.strip():
        raise RuntimeError("Ollama returned empty response")
    return response.strip()
