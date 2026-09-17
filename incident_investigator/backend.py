"""Small local HTTP service used by the demo and its integration tests."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


SCENARIOS = frozenset({"normal", "slow", "error", "unknown"})


def scenario_payload(path: str, scenario: str) -> tuple[int, dict[str, Any]]:
    """Return deterministic structured data for a simulated system condition."""
    if scenario not in SCENARIOS:
        return 400, {"error": "unknown scenario", "allowed": sorted(SCENARIOS)}

    health = {
        "normal": (200, {"service": "orders", "status": "ok"}),
        "slow": (200, {"service": "orders", "status": "ok"}),
        "error": (500, {"service": "orders", "status": "error", "code": "UPSTREAM_TIMEOUT"}),
        "unknown": (200, {"service": "orders", "status": "unknown"}),
    }
    metrics = {
        "normal": {"service": "orders", "requests": 1000, "error_rate": 0.0, "p95_latency_ms": 18},
        "slow": {"service": "orders", "requests": 1000, "error_rate": 0.0, "p95_latency_ms": 240},
        "error": {"service": "orders", "requests": 1000, "error_rate": 0.16, "p95_latency_ms": 35},
        "unknown": {"service": "orders", "requests": None, "error_rate": None, "p95_latency_ms": None},
    }
    if path == "/health":
        return health[scenario]
    if path == "/metrics":
        return 200, metrics[scenario]
    return 404, {"error": "not found"}


class _Handler(BaseHTTPRequestHandler):
    server_version = "IncidentInvestigatorDemo/1.0"

    def do_GET(self) -> None:  # noqa: N802 - HTTP protocol name
        parsed = urlparse(self.path)
        scenario = parse_qs(parsed.query).get("scenario", ["normal"])[0]
        # This delay is intentionally local and deterministic, not a fabricated observation.
        if parsed.path == "/health" and scenario == "slow":
            time.sleep(0.12)
        status, body = scenario_payload(parsed.path, scenario)
        encoded = json.dumps(body, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        """Keep the demo output focused on the report."""


class SimulatedBackend:
    """Context-managed localhost backend; no external service is contacted."""

    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> "SimulatedBackend":
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)
