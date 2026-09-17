"""Local-only adapter for Ollama's documented ``POST /api/chat`` endpoint."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener


class ModelProtocolError(ValueError):
    """The local model server did not return the expected chat response."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ModelProtocolError("Local model redirects are not allowed")


def urlopen(request, timeout):
    # Do not route localhost evidence through environment proxies or redirects.
    return build_opener(ProxyHandler({}), _RejectRedirects()).open(request, timeout=timeout)


class OllamaLocalAdapter:
    """Call a loopback Ollama server without credentials or external fallback."""

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434", timeout_seconds: float = 10.0) -> None:
        if not model.strip():
            raise ValueError("model name is required")
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
            raise ValueError("Ollama URL must be an unauthenticated http loopback URL")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Ollama base URL must not include a path, query, or fragment")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def chat(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False, "format": "json"}
        request = Request(
            self.base_url + "/api/chat", data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read()
        try:
            decoded = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise ModelProtocolError("Ollama returned malformed JSON") from error
        if not isinstance(decoded, dict) or not isinstance(decoded.get("message"), dict) or not isinstance(decoded["message"].get("content"), str):
            raise ModelProtocolError("Ollama response lacks message.content text")
        return decoded["message"]["content"]
