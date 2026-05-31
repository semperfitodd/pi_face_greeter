from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from pi_face_greeter import ollama_client


def test_health_check_returns_true_on_success() -> None:
    with patch("pi_face_greeter.ollama_client._request", return_value={"models": []}):
        assert ollama_client.health_check("http://localhost:11434") is True


def test_health_check_returns_false_on_error() -> None:
    with patch(
        "pi_face_greeter.ollama_client._request",
        side_effect=RuntimeError("down"),
    ):
        assert ollama_client.health_check("http://localhost:11434") is False


def test_generate_returns_response_text() -> None:
    with patch(
        "pi_face_greeter.ollama_client._request",
        return_value={"response": "Hey Todd, good morning."},
    ):
        text = ollama_client.generate(
            "Say hello",
            base_url="http://localhost:11434",
            model="llama3.2:1b",
        )
    assert text == "Hey Todd, good morning."


def test_generate_raises_on_empty_response() -> None:
    with patch(
        "pi_face_greeter.ollama_client._request",
        return_value={"response": "   "},
    ):
        with pytest.raises(RuntimeError, match="empty response"):
            ollama_client.generate(
                "Say hello",
                base_url="http://localhost:11434",
                model="llama3.2:1b",
            )


def test_request_raises_on_http_error() -> None:
    import urllib.error

    error = urllib.error.HTTPError(
        url="http://localhost:11434/api/generate",
        code=500,
        msg="error",
        hdrs=None,
        fp=io.BytesIO(b"server error"),
    )
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            ollama_client._request("http://localhost:11434/api/generate")


def test_request_parses_json_body() -> None:
    payload = json.dumps({"response": "hello"}).encode("utf-8")
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__.return_value = response
    response.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=response) as mock_open:
        result = ollama_client._request(
            "http://localhost:11434/api/generate",
            method="POST",
            body={"model": "llama3.2:1b", "prompt": "hi", "stream": False},
        )

    assert result == {"response": "hello"}
    request = mock_open.call_args[0][0]
    assert request.get_method() == "POST"
