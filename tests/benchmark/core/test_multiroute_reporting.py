import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from benchmark.core.multiroute_reporting import (
    MultiRouteReportError,
    build_multi_route_report,
    build_t1_readiness_summary,
    canonicalize_public_multi_route_report,
    render_multi_route_typst,
    write_multi_route_report,
)


def _digest(letter: str) -> str:
    return letter * 64


PRIVACY = {
    "aggregate_only": True,
    "student_ids_included": False,
    "per_student_scores_included": False,
    "raw_answers_included": False,
    "model_evidence_included": False,
    "private_paths_included": False,
}

SNAPSHOT = _digest("a")
M1_PACKET = _digest("b")
T1_PACKET = _digest("c")
CODEX_PACKET = _digest("d")
DEEPSEEK_PACKET = _digest("e")
TEXT_SOURCE = _digest("f")
ROSTER = _digest("1")
RUBRIC = _digest("2")
M1_PROMPT = _digest("3")
CODEX_PROMPT = _digest("4")
DEEPSEEK_PROMPT = _digest("5")


class MultiRouteReportingTests(unittest.TestCase):
    def test_builds_strict_aggregate_dashboard_and_typst(self):
        report = self._report()
        encoded = json.dumps(report, sort_keys=True)
        typst = render_multi_route_typst(report)

        self.assertEqual([item["route"] for item in report["routes"]], ["M1", "G1-Codex", "G1-DeepSeek"])
        self.assertTrue(report["t1_readiness"]["ready_for_g1"])
        self.assertIn("Exact-agreement comparison", typst)
        self.assertIn("supplementary", typst)
        self.assertIn("[1.20]", typst)
        self.assertNotIn("S001", encoded + typst)
        self.assertNotIn("Data/", encoded + typst)
        self.assertEqual(report["lineage"]["g1_codex_packet_hash"], CODEX_PACKET)
        self.assertEqual(report["lineage"]["g1_deepseek_packet_hash"], DEEPSEEK_PACKET)

    def test_canonicalizer_rejects_unknown_and_rebuilds_static_values(self):
        report = self._report()
        for mutation in (
            lambda item: item.__setitem__("comment", "cannot leak"),
            lambda item: item["routes"][0]["run"].__setitem__("comment", "cannot leak"),
            lambda item: item["routes"][0]["comparison_provenance"].__setitem__("comment", "cannot leak"),
            lambda item: item["routes"][0]["metrics"].__setitem__("comment", 1),
        ):
            changed = copy.deepcopy(report)
            mutation(changed)
            with self.assertRaises(MultiRouteReportError):
                canonicalize_public_multi_route_report(changed)

        changed = copy.deepcopy(report)
        changed["routes"][0]["label"] = "free text"
        with self.assertRaises(MultiRouteReportError):
            render_multi_route_typst(changed)

    def test_rejects_bad_route_role_provider_and_provenance(self):
        m1 = self._comparison("M1")
        m1["baseline_run"]["input_mode"] = "text-only"
        with self.assertRaisesRegex(MultiRouteReportError, "input_mode"):
            self._build(m1_metrics=m1)

        deepseek = self._comparison("G1-DeepSeek")
        deepseek["candidate_run"]["provider"] = "codex-cli"
        with self.assertRaisesRegex(MultiRouteReportError, "provider"):
            self._build(g1_deepseek_metrics=deepseek)

        codex = self._comparison("G1-Codex")
        codex["comparison_provenance"]["data_snapshot"] = "different"
        with self.assertRaisesRegex(MultiRouteReportError, "provenance"):
            self._build(g1_codex_metrics=codex)

        contract = self._contract()
        contract["routes"]["M1"]["condition"] = "G1"
        with self.assertRaisesRegex(MultiRouteReportError, "condition M1"):
            self._build(route_contract=contract)

    def test_rejects_unmatched_t1_lineage_and_snapshot(self):
        bad_lineage = self._lineage("G1-DeepSeek")
        bad_lineage["g1"]["text_source_hash"] = _digest("9")
        with self.assertRaisesRegex(MultiRouteReportError, "same T1 source"):
            self._build(g1_deepseek_lineage=bad_lineage)

        g1 = self._comparison("G1-Codex")
        g1["candidate_run"]["data_snapshot_hash"] = _digest("8")
        with self.assertRaisesRegex(MultiRouteReportError, "snapshot"):
            self._build(g1_codex_metrics=g1)

        bad_source = self._lineage("G1-DeepSeek")
        bad_source["g1"]["source_run_id"] = "other-t1-run"
        with self.assertRaisesRegex(MultiRouteReportError, "source_run_id"):
            self._build(g1_deepseek_lineage=bad_source)

    def test_rejects_failed_t1_after_validating_safe_metadata(self):
        readiness = build_t1_readiness_summary(
            {
                "status": "failed",
                "students_expected": 3,
                "students_passed": 2,
                "students_failed": 1,
                "rows": [{"student_id": "S001", "detail": "private"}],
            },
            run_metadata=self._t1_metadata(validation_status="failed"),
        )
        with self.assertRaisesRegex(MultiRouteReportError, "T1 readiness is not complete"):
            self._build(t1_readiness=readiness)

    def test_custom_title_writes_no_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_json = root / "aggregate.json"
            output_typst = root / "dashboard.typ"
            with self.assertRaisesRegex(MultiRouteReportError, "custom Typst titles"):
                write_multi_route_report(
                    self._report(),
                    output_json=output_json,
                    output_typst=output_typst,
                    title="Alice Smith feedback",
                )
            self.assertFalse(output_json.exists())
            self.assertFalse(output_typst.exists())

    def test_writes_canonical_json_and_typst(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_json, output_typst = write_multi_route_report(
                self._report(),
                output_json=root / "aggregate.json",
                output_typst=root / "dashboard.typ",
            )
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["routes"][1]["label"], "Transcript grading - Codex")
            self.assertIn("synthetic-course quiz-1", output_typst.read_text(encoding="utf-8"))

    def test_publish_failure_leaves_no_mixed_output_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_json = root / "aggregate.json"
            output_typst = root / "dashboard.typ"
            actual_replace = os.replace
            calls = 0

            def fail_second_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("synthetic publish failure")
                return actual_replace(source, destination)

            with mock.patch(
                "benchmark.core.multiroute_reporting.os.replace",
                side_effect=fail_second_replace,
            ):
                with self.assertRaisesRegex(OSError, "synthetic publish failure"):
                    write_multi_route_report(
                        self._report(),
                        output_json=output_json,
                        output_typst=output_typst,
                    )
            self.assertFalse(output_json.exists())
            self.assertFalse(output_typst.exists())

    def test_rejects_same_or_existing_output_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shared = root / "shared.out"
            with self.assertRaisesRegex(MultiRouteReportError, "different paths"):
                write_multi_route_report(
                    self._report(), output_json=shared, output_typst=shared
                )
            existing = root / "existing.json"
            existing.write_text("old", encoding="utf-8")
            with self.assertRaisesRegex(MultiRouteReportError, "refusing to overwrite"):
                write_multi_route_report(
                    self._report(),
                    output_json=existing,
                    output_typst=root / "new.typ",
                )

    def test_rejects_packet_change_after_build(self):
        report = self._report()
        report["routes"][1]["run"]["packet_hash"] = _digest("9")
        with self.assertRaisesRegex(MultiRouteReportError, "packet_hash does not match"):
            canonicalize_public_multi_route_report(report)

    def _report(self):
        return self._build()

    def _build(self, **overrides):
        values = {
            "m1_metrics": self._comparison("M1"),
            "g1_codex_metrics": self._comparison("G1-Codex"),
            "g1_deepseek_metrics": self._comparison("G1-DeepSeek"),
            "t1_readiness": self._readiness(),
            "route_contract": self._contract(),
            "g1_codex_lineage": self._lineage("G1-Codex"),
            "g1_deepseek_lineage": self._lineage("G1-DeepSeek"),
        }
        values.update(overrides)
        return build_multi_route_report(**values)

    def _readiness(self):
        return build_t1_readiness_summary(
            {
                "status": "passed",
                "students_expected": 3,
                "students_passed": 3,
                "students_failed": 0,
                "rows": [{"student_id": "S001", "detail": "private"}],
            },
            run_metadata=self._t1_metadata(),
        )

    def _t1_metadata(self, validation_status="passed"):
        return {
            "record_type": "model_packet_run",
            "dry_run": False,
            "run_id": "T1-development-run",
            "packet_hash": T1_PACKET,
            "data_snapshot_hash": SNAPSHOT,
            "task": "transcribe",
            "input_mode": "multimodal",
            "condition": "T1",
            "validation_status": validation_status,
        }

    def _contract(self):
        return {
            "schema_version": 1,
            "record_type": "public_multi_route_contract",
            "privacy": PRIVACY,
            "course": {"course_id": "synthetic-course", "assessment_id": "quiz-1"},
            "scope": {"split": "development", "data_snapshot_hash": SNAPSHOT},
            "routes": {
                "M1": {
                    "declared_route": "M1", "provider": "codex-cli", "model": "vision-test",
                    "condition": "M1", "task": "grade", "input_mode": "multimodal",
                },
                "G1-Codex": {
                    "declared_route": "G1-Codex", "provider": "codex-cli", "model": "text-test",
                    "condition": "G1", "task": "grade", "input_mode": "text-only",
                },
                "G1-DeepSeek": {
                    "declared_route": "G1-DeepSeek", "provider": "deepseek", "model": "deepseek-test",
                    "condition": "G1", "task": "grade", "input_mode": "text-only",
                },
            },
        }

    def _lineage(self, route):
        packet = CODEX_PACKET if route == "G1-Codex" else DEEPSEEK_PACKET
        return {
            "schema_version": 1,
            "record_type": "public_full_route_lineage_binding",
            "status": "ready",
            "privacy": PRIVACY,
            "course": {"course_id": "synthetic-course", "assessment_id": "quiz-1"},
            "scope": {"data_snapshot_hash": SNAPSHOT, "roster_hash": ROSTER},
            "m1": {"packet_hash": M1_PACKET, "data_snapshot_hash": SNAPSHOT, "rubric_hash": RUBRIC},
            "t1": {
                "packet_hash": T1_PACKET, "run_id": "T1-development-run", "data_snapshot_hash": SNAPSHOT,
                "task": "transcribe", "input_mode": "multimodal", "condition": "T1", "validation_status": "passed",
            },
            "g1": {
                "packet_hash": packet, "data_snapshot_hash": SNAPSHOT, "rubric_hash": RUBRIC, "text_source_hash": TEXT_SOURCE,
                "source_run_id": "T1-development-run", "source_transcription_packet_hash": T1_PACKET,
            },
        }

    def _comparison(self, route):
        if route == "M1":
            baseline = self._run("M1")
            candidate = self._run("G1-Codex")
            baseline_metrics, candidate_metrics = self._metrics(0.70), self._metrics(0.80)
        elif route == "G1-Codex":
            baseline = self._run("M1")
            candidate = self._run("G1-Codex")
            baseline_metrics, candidate_metrics = self._metrics(0.70), self._metrics(0.82)
        else:
            baseline = self._run("M1")
            candidate = self._run("G1-DeepSeek")
            baseline_metrics, candidate_metrics = self._metrics(0.70), self._metrics(0.78)
        return {
            "schema_version": 1,
            "record_type": "course_generic_run_metrics_comparison",
            "course": {
                "course_id": "synthetic-course", "assessment_id": "quiz-1", "score_unit": "points",
                "question_count": 4, "max_total": 100,
            },
            "population": {"student_count": 3, "score_row_count": 12},
            "comparison_provenance": {
                "run_validation": "passed", "course_metadata": "matched",
                "population": "matched_by_exact_question_coverage", "data_snapshot": "matched",
            },
            "baseline_run": baseline,
            "candidate_run": candidate,
            "baseline": baseline_metrics,
            "candidate": candidate_metrics,
            "privacy": PRIVACY,
        }

    def _run(self, route):
        values = {
            "source_kind": "run_directory_outputs", "validation_status": "passed", "course_metadata": "matched",
            "engine": "codex" if route != "G1-DeepSeek" else "deepseek",
            "experiment_condition": route, "split": "development", "rubric_hash": RUBRIC,
        }
        if route == "M1":
            values.update({
                "provider": "codex-cli", "model": "vision-test", "condition": "M1", "task": "grade",
                "input_mode": "multimodal", "run_id": "M1-development-run", "packet_hash": M1_PACKET,
                "prompt_hash": M1_PROMPT, "data_snapshot_hash": SNAPSHOT,
            })
        elif route == "G1-Codex":
            values.update({
                "provider": "codex-cli", "model": "text-test", "condition": "G1", "task": "grade",
                "input_mode": "text-only", "run_id": "G1-codex-development-run", "packet_hash": CODEX_PACKET,
                "prompt_hash": CODEX_PROMPT, "data_snapshot_hash": SNAPSHOT, "text_source_hash": TEXT_SOURCE,
                "source_run_id": "T1-development-run", "source_transcription_packet_hash": T1_PACKET,
            })
        else:
            values.update({
                "provider": "deepseek", "model": "deepseek-test", "condition": "G1", "task": "grade",
                "input_mode": "text-only", "run_id": "G1-deepseek-development-run", "packet_hash": DEEPSEEK_PACKET,
                "prompt_hash": DEEPSEEK_PROMPT, "data_snapshot_hash": SNAPSHOT, "text_source_hash": TEXT_SOURCE,
                "source_run_id": "T1-development-run", "source_transcription_packet_hash": T1_PACKET,
            })
        return values

    def _metrics(self, exact):
        return {
            "exact_agreement": exact,
            "macro_accuracy": exact - 0.02,
            "subquestion_mae": 0.6,
            "total_score_mae": 1.2,
            "within_1_point_rate": 0.80,
            "severe_error_rate": 0.05,
            "mean_signed_error": -0.1,
        }


if __name__ == "__main__":
    unittest.main()
