import unittest
from dataclasses import replace
from unittest.mock import patch

from incident_investigator.backend import SimulatedBackend
from incident_investigator.investigator import Investigator
from incident_investigator.tools import ReadOnlyTools, ToolBudgetExceeded


class InvestigatorTests(unittest.TestCase):
    def test_failed_attempt_consumes_budget(self):
        tools = ReadOnlyTools("http://127.0.0.1:1", max_calls=1)
        with patch("incident_investigator.tools.urlopen", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                tools.collect("health", "normal")
        with self.assertRaises(ToolBudgetExceeded):
            tools.collect("health", "normal")

    def investigate(self, scenario: str):
        with SimulatedBackend() as backend:
            return Investigator(ReadOnlyTools(backend.base_url)).investigate(scenario)

    def test_findings_are_grounded_in_collected_evidence(self):
        report = self.investigate("slow")
        evidence_ids = {item.id for item in report.evidence}
        self.assertEqual(report.mode, "deterministic-offline")
        self.assertEqual(report.outcome, "evidence_found")
        self.assertTrue(report.findings)
        for finding in report.findings:
            self.assertTrue(finding.evidence_ids)
            self.assertTrue(set(finding.evidence_ids).issubset(evidence_ids))

    def test_unknown_says_insufficient_evidence_without_causal_finding(self):
        report = self.investigate("unknown")
        self.assertEqual(report.outcome, "insufficient_evidence")
        self.assertIn("Insufficient evidence", report.summary)
        self.assertEqual(report.findings, [])
        self.assertEqual(report.tool_calls, ["health", "metrics", "logs", "releases"])

    def test_normal_has_no_incident_finding(self):
        report = self.investigate("normal")
        self.assertEqual(report.outcome, "insufficient_evidence")
        self.assertEqual(report.findings, [])
        self.assertEqual(report.evidence[0].data["status"], "ok")

    def test_tool_budget_and_allowlist_are_enforced(self):
        with SimulatedBackend() as backend:
            tools = ReadOnlyTools(backend.base_url, max_calls=1)
            tools.collect("health", "normal")
            with self.assertRaises(ToolBudgetExceeded):
                tools.collect("metrics", "normal")
            with self.assertRaises(ValueError):
                tools.collect("write_database", "normal")

    def test_error_evidence_preserves_http_500_body(self):
        report = self.investigate("error")
        self.assertEqual(report.evidence[0].http_status, 500)
        self.assertEqual(report.evidence[0].data["code"], "UPSTREAM_TIMEOUT")
        self.assertEqual(report.findings[0].evidence_ids, ["evidence-1"])
        self.assertEqual(report.outcome, "evidence_found")
        self.assertNotIn("probable", report.findings[0].claim.lower())

    def test_matching_log_and_release_evidence_produces_probable_diagnosis(self):
        report = self.investigate("release_regression")
        self.assertEqual(report.outcome, "probable_diagnosis")
        self.assertEqual(report.findings[0].confidence, "probable")
        self.assertEqual(report.findings[0].evidence_ids, ["evidence-3", "evidence-4"])
        self.assertIn("schema validation regression", report.findings[0].claim)

    def test_http_500_without_matching_log_and_release_is_not_given_a_cause(self):
        report = self.investigate("error")
        self.assertEqual(report.outcome, "evidence_found")
        self.assertEqual(report.findings[0].confidence, "observed")
        self.assertEqual(report.findings[0].claim, "The service health endpoint returned a server error.")
        self.assertFalse(any(finding.confidence == "probable" for finding in report.findings))

    def test_release_hypothesis_requires_both_matching_sources(self):
        report = self.investigate("release_regression")
        evidence = {item.tool: item for item in report.evidence}
        for release_patch in (
            {"current": "unrelated-release"},
            {"changes": ["routine dependency update"]},
            {"changes": []},
        ):
            with self.subTest(release_patch=release_patch):
                releases = replace(
                    evidence["releases"],
                    data={**evidence["releases"].data, **release_patch},
                )
                with patch.object(ReadOnlyTools, "collect", side_effect=[
                    evidence["health"], evidence["metrics"], evidence["logs"], releases
                ]):
                    result = Investigator(ReadOnlyTools("http://127.0.0.1:1")).investigate("release_regression")
                self.assertEqual(result.outcome, "evidence_found")
                self.assertFalse(any(f.confidence == "probable" for f in result.findings))

    def test_full_evidence_plan_requires_four_call_budget(self):
        with SimulatedBackend() as backend:
            report = Investigator(ReadOnlyTools(backend.base_url, max_calls=4)).investigate("normal")
            self.assertEqual(report.tool_calls, ["health", "metrics", "logs", "releases"])
            with self.assertRaises(ToolBudgetExceeded):
                Investigator(ReadOnlyTools(backend.base_url, max_calls=3)).investigate("normal")


if __name__ == "__main__":
    unittest.main()
