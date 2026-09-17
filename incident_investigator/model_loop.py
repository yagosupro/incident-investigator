"""A bounded, local-model-directed evidence investigation loop.

This module intentionally does not alter :class:`Investigator`: that class is
the deterministic offline policy.  A model may select the next read-only tool
or submit a final report, but it never receives a capability beyond
``ReadOnlyTools.collect``.
"""

from __future__ import annotations

import json
import socket
from dataclasses import asdict, dataclass, replace
from typing import Any, Protocol
from urllib.error import URLError

from .tools import Evidence, ReadOnlyTools, ToolBudgetExceeded


class ModelAdapter(Protocol):
    """Minimal interface used by the loop; useful for offline scripted tests."""

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Return one JSON action as text."""


@dataclass(frozen=True)
class ModelFinding:
    """A claim authored by the local model, not independently established."""

    claim: str
    confidence: str
    evidence_ids: list[str]
    claim_origin: str = "model-generated"


@dataclass(frozen=True)
class TraceStep:
    step: int
    action: str
    tool: str | None = None
    evidence_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ModelInvestigationReport:
    scenario: str
    outcome: str
    summary: str
    citations: list[str]
    findings: list[ModelFinding]
    evidence: list[Evidence]
    tool_calls: list[str]
    trace: list[TraceStep]
    limitations: list[str]
    mode: str = "model-directed-local"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = [item.to_dict() for item in self.evidence]
        return result


class ModelInvestigationLoop:
    """Fail-closed state machine for a local model's investigation choices."""

    def __init__(self, tools: ReadOnlyTools, model: ModelAdapter, max_steps: int = 8) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least one")
        self.tools = tools
        self.model = model
        self.max_steps = max_steps

    def investigate(self, scenario: str) -> ModelInvestigationReport:
        evidence: list[Evidence] = []
        trace: list[TraceStep] = []
        messages = [
            {
                "role": "system",
                "content": (
                    "You direct a read-only incident investigation. Reply with exactly one JSON object. "
                    "For a tool action use {\"action\":\"tool\",\"tool\":\"health|metrics|logs|releases\"}. "
                    "For a final answer use {\"action\":\"final\",\"summary\":string,"
                    "\"citations\":[evidence id],\"findings\":[{\"claim\":string,\"confidence\":string,"
                    "\"evidence_ids\":[evidence id]}]}. Cite only evidence ids supplied to you."
                ),
            },
            {"role": "user", "content": f"Investigate scenario: {scenario}"},
        ]
        for step in range(1, self.max_steps + 1):
            try:
                raw = self.model.chat(messages)
            except Exception as error:  # Adapters are untrusted protocol boundaries.
                if self._is_timeout(error):
                    trace.append(TraceStep(step, "model_error", error="model_timeout"))
                    return self._error(scenario, "model_timeout", "The local model timed out.", evidence, trace)
                trace.append(TraceStep(step, "model_error", error=type(error).__name__))
                return self._error(scenario, "model_error", "The local model request failed.", evidence, trace)

            action, error = self._parse_action(raw)
            if error:
                trace.append(TraceStep(step, "invalid_action", error=error))
                return self._error(scenario, "invalid_model_action", "The local model returned an invalid action.", evidence, trace)
            assert action is not None
            messages.append({"role": "assistant", "content": raw})
            if action["action"] == "tool":
                tool = action["tool"]
                try:
                    item = self.tools.collect(tool, scenario)
                except ToolBudgetExceeded:
                    trace.append(TraceStep(step, "tool", tool=tool, error="tool_budget_exhausted"))
                    return self._error(scenario, "tool_budget_exhausted", "The read-only tool budget was exhausted.", evidence, trace)
                except Exception as tool_error:
                    if self._is_timeout(tool_error):
                        trace.append(TraceStep(step, "tool", tool=tool, error="tool_timeout"))
                        return self._error(scenario, "tool_timeout", "A read-only evidence request timed out.", evidence, trace)
                    trace.append(TraceStep(step, "tool", tool=tool, error=type(tool_error).__name__))
                    return self._error(scenario, "tool_error", "A read-only evidence request failed.", evidence, trace)
                evidence.append(item)
                trace.append(TraceStep(step, "tool", tool=tool, evidence_id=item.id))
                messages.append({"role": "user", "content": "Evidence " + item.id + ": " + json.dumps(item.to_dict(), sort_keys=True)})
                continue

            report, error = self._validated_final(scenario, action, evidence, trace)
            if error:
                trace.append(TraceStep(step, "invalid_final", error=error))
                return self._error(scenario, "invalid_model_final", "The local model returned an invalid final report.", evidence, trace)
            trace.append(TraceStep(step, "final"))
            assert report is not None
            return replace(report, trace=list(trace))

        trace.append(TraceStep(self.max_steps, "step_budget_exhausted", error="step_budget_exhausted"))
        return self._error(scenario, "step_budget_exhausted", "The model did not finish within the step budget.", evidence, trace)

    @staticmethod
    def _parse_action(raw: object) -> tuple[dict[str, Any] | None, str | None]:
        if not isinstance(raw, str):
            return None, "response_not_text"
        try:
            action = json.loads(raw)
        except json.JSONDecodeError:
            return None, "malformed_json"
        if not isinstance(action, dict) or set(action).isdisjoint({"action"}):
            return None, "action_not_object"
        kind = action.get("action")
        if kind == "tool":
            if set(action) != {"action", "tool"} or not isinstance(action.get("tool"), str) or action["tool"] not in ReadOnlyTools.ALLOWED:
                return None, "unknown_or_malformed_tool"
        elif kind != "final":
            return None, "unknown_action"
        return action, None

    def _validated_final(
        self, scenario: str, action: dict[str, Any], evidence: list[Evidence], trace: list[TraceStep]
    ) -> tuple[ModelInvestigationReport | None, str | None]:
        allowed = {"action", "summary", "citations", "findings"}
        if set(action) != allowed or not isinstance(action.get("summary"), str) or not action["summary"].strip():
            return None, "malformed_final"
        ids = {item.id for item in evidence}
        citations = action["citations"]
        findings = action["findings"]
        if not self._valid_citations(citations, ids) or not isinstance(findings, list):
            return None, "invalid_citations"
        parsed_findings: list[ModelFinding] = []
        for finding in findings:
            if not isinstance(finding, dict) or set(finding) != {"claim", "confidence", "evidence_ids"}:
                return None, "malformed_finding"
            if not isinstance(finding["claim"], str) or not finding["claim"].strip() or not isinstance(finding["confidence"], str):
                return None, "malformed_finding"
            if not self._valid_citations(finding["evidence_ids"], ids):
                return None, "invalid_citations"
            parsed_findings.append(ModelFinding(finding["claim"], finding["confidence"], list(finding["evidence_ids"])))
        return ModelInvestigationReport(
            scenario=scenario, outcome="model_final", summary=action["summary"], citations=list(citations),
            findings=parsed_findings, evidence=evidence, tool_calls=list(self.tools.calls), trace=list(trace),
            limitations=[
                "Claims are model-generated; citation validation confirms only that cited evidence ids were collected.",
                "Citation validation does not establish semantic grounding, accuracy, causation, or completeness.",
                "Only allowlisted read-only health, metrics, logs, and releases tools were available.",
            ],
        ), None

    @staticmethod
    def _valid_citations(values: object, valid_ids: set[str]) -> bool:
        return isinstance(values, list) and bool(values) and all(isinstance(value, str) and value in valid_ids for value in values)

    @staticmethod
    def _is_timeout(error: BaseException) -> bool:
        return isinstance(error, (TimeoutError, socket.timeout)) or (
            isinstance(error, URLError) and isinstance(error.reason, (TimeoutError, socket.timeout))
        )

    def _error(self, scenario: str, outcome: str, summary: str, evidence: list[Evidence], trace: list[TraceStep]) -> ModelInvestigationReport:
        return ModelInvestigationReport(
            scenario=scenario, outcome=outcome, summary=summary, citations=[], findings=[], evidence=evidence,
            tool_calls=list(self.tools.calls), trace=list(trace),
            limitations=["No model-generated finding was accepted after the failure."],
        )


class ScriptedOfflineAdapter:
    """Offline test/demo adapter that returns pre-supplied JSON actions in order."""

    def __init__(self, actions: list[str]) -> None:
        self._actions = iter(actions)

    def chat(self, messages: list[dict[str, str]]) -> str:
        try:
            return next(self._actions)
        except StopIteration as error:
            raise RuntimeError("scripted offline actions exhausted") from error
