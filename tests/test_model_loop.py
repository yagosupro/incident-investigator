import json
import socket
import unittest
from unittest.mock import patch
from urllib.error import URLError

from incident_investigator.backend import SimulatedBackend
from incident_investigator.model_loop import ModelInvestigationLoop, ScriptedOfflineAdapter
from incident_investigator.ollama import ModelProtocolError, OllamaLocalAdapter, _RejectRedirects
from incident_investigator.tools import ReadOnlyTools


def action(value):
    return json.dumps(value)


class ModelLoopTests(unittest.TestCase):
    def run_loop(self, actions, *, max_calls=4, max_steps=8):
        with SimulatedBackend() as backend:
            return ModelInvestigationLoop(
                ReadOnlyTools(backend.base_url, max_calls=max_calls),
                ScriptedOfflineAdapter(actions), max_steps=max_steps,
            ).investigate("slow")

    def test_scripted_offline_success_records_trace_and_labels_claims(self):
        report = self.run_loop([
            action({"action": "tool", "tool": "metrics"}),
            action({"action": "final", "summary": "Latency is elevated.", "citations": ["evidence-1"],
                    "findings": [{"claim": "The p95 is high.", "confidence": "observed", "evidence_ids": ["evidence-1"]}]}),
        ])
        self.assertEqual(report.outcome, "model_final")
        self.assertEqual(report.tool_calls, ["metrics"])
        self.assertEqual([step.action for step in report.trace], ["tool", "final"])
        self.assertEqual(report.findings[0].claim_origin, "model-generated")
        self.assertIn("not establish semantic grounding", " ".join(report.limitations))

    def test_malformed_model_json_fails_closed(self):
        report = self.run_loop(["not json"])
        self.assertEqual(report.outcome, "invalid_model_action")
        self.assertEqual(report.findings, [])
        self.assertEqual(report.trace[-1].error, "malformed_json")

    def test_unknown_tool_fails_closed_without_a_request(self):
        report = self.run_loop([action({"action": "tool", "tool": "delete_everything"})])
        self.assertEqual(report.outcome, "invalid_model_action")
        self.assertEqual(report.tool_calls, [])
        self.assertEqual(report.trace[-1].error, "unknown_or_malformed_tool")

    def test_non_string_tools_are_rejected_without_crashing(self):
        for tool in ([], {}, None, 7):
            with self.subTest(tool=tool):
                report = self.run_loop([action({"action": "tool", "tool": tool})])
                self.assertEqual(report.outcome, "invalid_model_action")
                self.assertEqual(report.tool_calls, [])

    def test_fabricated_evidence_id_in_final_is_rejected(self):
        report = self.run_loop([
            action({"action": "tool", "tool": "health"}),
            action({"action": "final", "summary": "Claim", "citations": ["evidence-999"], "findings": []}),
        ])
        self.assertEqual(report.outcome, "invalid_model_final")
        self.assertEqual(report.findings, [])
        self.assertEqual(report.trace[-1].error, "invalid_citations")

    def test_tool_budget_exhaustion_is_explicit(self):
        report = self.run_loop([
            action({"action": "tool", "tool": "health"}),
            action({"action": "tool", "tool": "metrics"}),
        ], max_calls=1)
        self.assertEqual(report.outcome, "tool_budget_exhausted")
        self.assertEqual(report.tool_calls, ["health"])

    def test_step_budget_exhaustion_is_explicit(self):
        report = self.run_loop([action({"action": "tool", "tool": "health"})], max_steps=1)
        self.assertEqual(report.outcome, "step_budget_exhausted")

    def test_model_timeout_is_explicit(self):
        class TimeoutAdapter:
            def chat(self, messages):
                raise socket.timeout()
        with SimulatedBackend() as backend:
            report = ModelInvestigationLoop(ReadOnlyTools(backend.base_url), TimeoutAdapter()).investigate("slow")
        self.assertEqual(report.outcome, "model_timeout")

    def test_urlerror_wrapped_timeout_is_explicit(self):
        class TimeoutAdapter:
            def chat(self, messages):
                raise URLError(socket.timeout())
        with SimulatedBackend() as backend:
            report = ModelInvestigationLoop(ReadOnlyTools(backend.base_url), TimeoutAdapter()).investigate("slow")
        self.assertEqual(report.outcome, "model_timeout")


class OllamaAdapterTests(unittest.TestCase):
    def test_request_uses_official_json_chat_shape(self):
        captured = {}

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'{"message":{"content":"{\\\"action\\\":\\\"tool\\\",\\\"tool\\\":\\\"health\\\"}"}}'

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data)
            captured["timeout"] = timeout
            return Response()

        with patch("incident_investigator.ollama.urlopen", side_effect=fake_urlopen):
            result = OllamaLocalAdapter("qwen", timeout_seconds=3).chat([{"role": "user", "content": "hi"}])
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/chat")
        self.assertEqual(captured["body"]["stream"], False)
        self.assertEqual(captured["body"]["format"], "json")
        self.assertEqual(captured["body"]["model"], "qwen")
        self.assertEqual(captured["timeout"], 3)
        self.assertIn('"action"', result)

    def test_protocol_errors_and_no_server_are_not_silently_accepted(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b"not-json"
        with patch("incident_investigator.ollama.urlopen", return_value=Response()):
            with self.assertRaises(ModelProtocolError):
                OllamaLocalAdapter("qwen").chat([])
        with patch("incident_investigator.ollama.urlopen", side_effect=URLError("connection refused")):
            with self.assertRaises(URLError):
                OllamaLocalAdapter("qwen").chat([])

    def test_redirects_are_rejected(self):
        with self.assertRaises(ModelProtocolError):
            _RejectRedirects().redirect_request(None, None, 302, "Found", {}, "https://example.com")

    def test_rejects_non_loopback_and_credentialed_urls(self):
        for url in ("https://example.com", "http://10.0.0.8:11434", "http://token@127.0.0.1:11434"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    OllamaLocalAdapter("qwen", base_url=url)


if __name__ == "__main__":
    unittest.main()
