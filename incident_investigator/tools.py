"""Bounded read-only HTTP evidence collection."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Evidence:
    id: str
    tool: str
    endpoint: str
    observed_at_unix_ms: int
    http_status: int
    elapsed_ms: int
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolBudgetExceeded(RuntimeError):
    pass


class ReadOnlyTools:
    """Permit only two fixed GET checks and enforce an investigation call budget."""

    ALLOWED = {"health": "/health", "metrics": "/metrics"}

    def __init__(self, base_url: str, max_calls: int = 2, timeout_seconds: float = 1.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_calls = max_calls
        self.timeout_seconds = timeout_seconds
        self.calls: list[str] = []

    def collect(self, tool: str, scenario: str) -> Evidence:
        if tool not in self.ALLOWED:
            raise ValueError(f"tool {tool!r} is not allowlisted")
        if len(self.calls) >= self.max_calls:
            raise ToolBudgetExceeded(f"read-only tool budget of {self.max_calls} calls exhausted")
        endpoint = f"{self.ALLOWED[tool]}?scenario={scenario}"
        started = time.monotonic()
        request = Request(f"{self.base_url}{endpoint}", method="GET")
        # Failed attempts consume budget too; callers cannot retry indefinitely.
        self.calls.append(tool)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                http_status = response.status
                raw = response.read()
        except HTTPError as error:
            http_status = error.code
            try:
                raw = error.read()
            finally:
                error.close()
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return Evidence(
            id=f"evidence-{len(self.calls)}",
            tool=tool,
            endpoint=endpoint,
            observed_at_unix_ms=round(time.time() * 1000),
            http_status=http_status,
            elapsed_ms=elapsed_ms,
            data=json.loads(raw),
        )
