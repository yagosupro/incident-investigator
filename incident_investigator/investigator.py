"""Deterministic report construction: observations are never replaced by guesses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .tools import Evidence, ReadOnlyTools


@dataclass(frozen=True)
class Finding:
    claim: str
    confidence: str
    evidence_ids: list[str]


@dataclass(frozen=True)
class InvestigationReport:
    scenario: str
    outcome: str
    summary: str
    findings: list[Finding]
    limitations: list[str]
    evidence: list[Evidence]
    tool_calls: list[str]
    mode: str = "deterministic-offline"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = [item.to_dict() for item in self.evidence]
        return result


class Investigator:
    """A transparent policy, deliberately not an LLM or a root-cause engine."""

    def __init__(self, tools: ReadOnlyTools) -> None:
        self.tools = tools

    def investigate(self, scenario: str) -> InvestigationReport:
        # Fixed plan makes the access boundary auditable and naturally bounded.
        health = self.tools.collect("health", scenario)
        metrics = self.tools.collect("metrics", scenario)
        logs = self.tools.collect("logs", scenario)
        releases = self.tools.collect("releases", scenario)
        evidence = [health, metrics, logs, releases]
        ids = [item.id for item in evidence]

        diagnosis = self._release_diagnosis(logs, releases)
        if diagnosis:
            finding = Finding(diagnosis, "probable", [logs.id, releases.id])
            return self._report(
                scenario,
                "probable_diagnosis",
                "Evidence supports a probable release-related schema validation regression.",
                [finding],
                evidence,
            )

        if health.http_status >= 500:
            finding = Finding(
                "The service health endpoint returned a server error.", "observed", [health.id]
            )
            return self._report(
                scenario, "evidence_found", "Observed server-error responses; root cause is not established.",
                [finding], evidence,
            )
        if health.elapsed_ms >= 75 or (metrics.data.get("p95_latency_ms") or 0) >= 100:
            finding = Finding(
                "Elevated latency was observed in the simulated service.", "observed", ids
            )
            return self._report(
                scenario, "evidence_found", "Observed elevated latency; root cause is not established.",
                [finding], evidence,
            )
        if (metrics.data.get("error_rate") or 0) > 0.01:
            finding = Finding("An elevated error rate was reported.", "observed", [metrics.id])
            return self._report(
                scenario, "evidence_found", "Observed elevated errors; root cause is not established.",
                [finding], evidence,
            )
        return self._report(
            scenario,
            "insufficient_evidence",
            "Insufficient evidence to identify an incident or its cause.",
            [],
            evidence,
        )

    def _report(
        self, scenario: str, outcome: str, summary: str, findings: list[Finding], evidence: list[Evidence]
    ) -> InvestigationReport:
        return InvestigationReport(
            scenario=scenario,
            outcome=outcome,
            summary=summary,
            findings=findings,
            limitations=[
                "Only read-only /health, /metrics, /logs, and /releases checks were used.",
                "A probable diagnosis requires matching structured log and release evidence; HTTP status alone is not treated as a cause.",
            ],
            evidence=evidence,
            tool_calls=list(self.tools.calls),
        )

    @staticmethod
    def _release_diagnosis(logs: Evidence, releases: Evidence) -> str | None:
        """Return a bounded correlation claim only when both sources agree."""
        current_release = releases.data.get("current")
        changes = releases.data.get("changes")
        events = logs.data.get("events")
        if not isinstance(current_release, str) or not isinstance(changes, list) or not isinstance(events, list):
            return None
        for event in events:
            if not isinstance(event, dict):
                continue
            if (
                event.get("level") == "ERROR"
                and event.get("release") == current_release
                and event.get("error_code") == "SCHEMA_VALIDATION_ERROR"
                and "checkout schema validation" in changes
            ):
                return (
                    "A release-related checkout schema validation regression is probable: "
                    "the current release is named in a matching structured error event."
                )
        return None
