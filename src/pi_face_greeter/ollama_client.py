from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from pi_face_greeter.events import log_event, truncate_session_text

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
        reason = str(exc.reason)
        if "timed out" in reason.lower():
            raise RuntimeError(f"Ollama request timed out after {timeout}s") from exc
        raise RuntimeError(f"Ollama request failed: {reason}") from exc

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
    keep_alive: str | None = None,
) -> str:
    url = f"{base_url.rstrip('/')}/api/generate"
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
        },
    }
    if keep_alive is not None:
        body["keep_alive"] = keep_alive
    result = _request(url, method="POST", body=body, timeout=timeout)
    response = result.get("response")
    if not isinstance(response, str) or not response.strip():
        raise RuntimeError("Ollama returned empty response")
    return response.strip()


def warmup(
    *,
    base_url: str,
    model: str,
    timeout: float = 60.0,
    keep_alive: str | None = "10m",
) -> None:
    """Load the model into memory with a minimal generation."""
    logger.info("Warming up Ollama model %s", model)
    generate(
        "Hi",
        base_url=base_url,
        model=model,
        timeout=timeout,
        max_tokens=1,
        temperature=0.0,
        keep_alive=keep_alive,
    )
    logger.info("Ollama model %s ready", model)


def chat_stream(
    messages: list[dict[str, str]],
    *,
    base_url: str,
    model: str,
    timeout: float = 8.0,
    max_tokens: int = 120,
    temperature: float = 0.7,
    keep_alive: str | None = None,
):
    url = f"{base_url.rstrip('/')}/api/chat"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
        },
    }
    if keep_alive is not None:
        body["keep_alive"] = keep_alive

    log_event(f"llm start model={model}")

    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw_chunk in response:
                for line in raw_chunk.decode("utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    message = chunk.get("message")
                    if isinstance(message, dict):
                        token = message.get("content")
                        if isinstance(token, str) and token:
                            yield token
                    if chunk.get("done") is True:
                        break
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        err = RuntimeError(f"Ollama HTTP {exc.code}: {detail}")
        log_event(f"llm failed: {truncate_session_text(str(err))}")
        raise err from exc
    except urllib.error.URLError as exc:
        reason = str(exc.reason)
        if "timed out" in reason.lower():
            err = RuntimeError(f"Ollama request timed out after {timeout}s")
        else:
            err = RuntimeError(f"Ollama request failed: {reason}")
        log_event(f"llm failed: {truncate_session_text(str(err))}")
        raise err from exc


def chat(
    messages: list[dict[str, str]],
    *,
    base_url: str,
    model: str,
    timeout: float = 8.0,
    max_tokens: int = 120,
    temperature: float = 0.7,
    keep_alive: str | None = None,
) -> str:
    started = time.monotonic()
    try:
        parts = list(
            chat_stream(
                messages,
                base_url=base_url,
                model=model,
                timeout=timeout,
                max_tokens=max_tokens,
                temperature=temperature,
                keep_alive=keep_alive,
            )
        )
    except RuntimeError:
        raise
    elapsed = time.monotonic() - started
    text = "".join(parts).strip()
    if not text:
        err = RuntimeError("Ollama chat returned empty response")
        log_event(f"llm failed: {truncate_session_text(str(err))}")
        raise err
    log_event(f"llm reply {elapsed:.1f}s: {truncate_session_text(text)}")
    return text
