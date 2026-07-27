import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.cli import main
from benchmark.core.error_book import audit_public_error_summary
from benchmark.core.error_book_iteration import validate_error_book_registry
from benchmark.core.error_regressions import (
    build_regression_suite,
    evaluate_regression_suite,
)


REPO_ROOT = Path(__file__).parents[3]
RECORD_ROOT = (
    REPO_ROOT
    / "experiments"
    / "records"
    / "DSAA3071-week5-error-regression-suite"
)
REGISTRY_PATH = (
    REPO_ROOT / "experiments" / "records" / "grading-skill-error-book-registry.json"
)


class ErrorRegressionTests(unittest.TestCase):
    def _fixture(
        self, root: Path
    ) -> tuple[Path, Path, Path, dict, dict]:
        provenance = {
            "course_id": "COURSE",
            "assessment_id": "A1",
            "provider": "provider",
            "model": "model",
            "input_mode": "reviewed-transcript",
            "data_snapshot_sha256": "data-hash",
            "gold_sha256": "gold-hash",
            "text_source_sha256": "text-hash",
            "skill_version_id": "skill-v1",
            "run_id": "run-v1",
            "output_set_sha256": "output-v1",
        }
        cases = [
            {
                "case_id": "ERR-1",
                "anonymous_student_id": "S001",
                "question_id": "Q6",
                "gold_score": 0.0,
                "predicted_score": 6.0,
                "absolute_error": 6.0,
                "severe_error": True,
            },
            {
                "case_id": "ERR-2",
                "anonymous_student_id": "S002",
                "question_id": "Q9",
                "gold_score": 25.0,
                "predicted_score": 17.0,
                "absolute_error": 8.0,
                "severe_error": True,
            },
            {
                "case_id": "ERR-3",
                "anonymous_student_id": "S003",
                "question_id": "Q7",
                "gold_score": 10.0,
                "predicted_score": 9.0,
                "absolute_error": 1.0,
                "severe_error": False,
            },
        ]
        private_book = {
            "record_type": "grading_error_book_private",
            "schema_version": 1,
            "scope": {"split": "development"},
            "provenance": provenance,
            "population": {
                "students": 3,
                "student_question_pairs": 3,
                "error_pairs": 3,
                "exact_pairs": 0,
                "severe_error_pairs": 2,
            },
            "cases": cases,
        }
        annotations = [
            {
                "case_id": "ERR-1",
                "mechanism_code": "unsupported_evidence_credit",
                "review_confidence": "high",
                "recommended_action": "require explicit evidence",
            },
            {
                "case_id": "ERR-2",
                "mechanism_code": "rule_precedence_or_gate_error",
                "review_confidence": "high",
                "recommended_action": "apply holistic override",
            },
            {
                "case_id": "ERR-3",
                "mechanism_code": "score_band_boundary_disagreement",
                "review_confidence": "medium",
                "recommended_action": "retain anchor",
            },
        ]
        diagnoses = {"annotations": annotations}
        policy = {
            "schema_version": 1,
            "suite_id": "fixture-regressions-v1",
            "split": "development",
            "selectors": [
                {
                    "selector_id": "q6-negative",
                    "question_id": "Q6",
                    "mechanism_code": "unsupported_evidence_credit",
                    "severe_only": True,
                    "expected_case_count": 1,
                    "regression_class": "negative_credit",
                    "gate": {"kind": "nonsevere_and_improved"},
                },
                {
                    "selector_id": "q9-positive",
                    "question_id": "Q9",
                    "mechanism_code": "rule_precedence_or_gate_error",
                    "severe_only": False,
                    "expected_case_count": 1,
                    "regression_class": "positive_credit",
                    "gate": {"kind": "nonsevere_and_improved"},
                },
            ],
        }
        book_path = root / "source.private.json"
        diagnoses_path = root / "diagnoses.private.json"
        policy_path = root / "policy.json"
        book_path.write_text(json.dumps(private_book), encoding="utf-8")
        diagnoses_path.write_text(json.dumps(diagnoses), encoding="utf-8")
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        return (
            book_path,
            diagnoses_path,
            policy_path,
            private_book,
            policy,
        )

    def test_builds_positive_and_negative_targets_without_public_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book, diagnoses, policy, _, _ = self._fixture(root)
            result = build_regression_suite(
                private_book_path=book,
                diagnoses_path=diagnoses,
                policy_path=policy,
            )

        self.assertEqual(result.public_summary["target_case_count"], 2)
        self.assertEqual(
            {
                row["regression_class"]: row["target_cases"]
                for row in result.public_summary["by_regression_class"]
            },
            {"negative_credit": 1, "positive_credit": 1},
        )
        self.assertEqual(audit_public_error_summary(result.public_summary), [])
        serialized = json.dumps(result.public_summary)
        self.assertNotIn("S001", serialized)
        self.assertNotIn("S002", serialized)
        self.assertNotIn("gold_score", serialized)
        self.assertNotIn("predicted_score", serialized)

    def test_selector_count_is_a_drift_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book, diagnoses, policy_path, _, policy = self._fixture(root)
            policy["selectors"][0]["expected_case_count"] = 2
            policy_path.write_text(json.dumps(policy), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "expected 2 cases"):
                build_regression_suite(
                    private_book_path=book,
                    diagnoses_path=diagnoses,
                    policy_path=policy_path,
                )

    def test_rejects_held_out_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book, diagnoses, policy, payload, _ = self._fixture(root)
            payload["scope"]["split"] = "test"
            book.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "development"):
                build_regression_suite(
                    private_book_path=book,
                    diagnoses_path=diagnoses,
                    policy_path=policy,
                )

    def test_baseline_is_a_failing_negative_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book, diagnoses, policy, _, _ = self._fixture(root)
            suite_result = build_regression_suite(
                private_book_path=book,
                diagnoses_path=diagnoses,
                policy_path=policy,
            )
            suite_path = root / "suite.private.json"
            suite_path.write_text(
                json.dumps(suite_result.private_suite), encoding="utf-8"
            )
            evaluation = evaluate_regression_suite(
                private_suite_path=suite_path,
                current_private_book_path=book,
            )

        self.assertEqual(evaluation.public_summary["status"], "failed")
        self.assertEqual(
            evaluation.public_summary["counts"],
            {"target_cases": 2, "passed": 0, "failed": 2},
        )

    def test_nonsevere_improvement_can_pass_without_exact_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book, diagnoses, policy, source, _ = self._fixture(root)
            suite_result = build_regression_suite(
                private_book_path=book,
                diagnoses_path=diagnoses,
                policy_path=policy,
            )
            suite_path = root / "suite.private.json"
            suite_path.write_text(
                json.dumps(suite_result.private_suite), encoding="utf-8"
            )
            current = copy.deepcopy(source)
            current["provenance"]["skill_version_id"] = "skill-v2"
            current["provenance"]["run_id"] = "run-v2"
            current["cases"] = [
                {
                    "case_id": "CURRENT-1",
                    "anonymous_student_id": "S001",
                    "question_id": "Q6",
                    "gold_score": 0.0,
                    "predicted_score": 4.0,
                    "absolute_error": 4.0,
                    "severe_error": False,
                },
                {
                    "case_id": "CURRENT-2",
                    "anonymous_student_id": "S002",
                    "question_id": "Q9",
                    "gold_score": 25.0,
                    "predicted_score": 24.0,
                    "absolute_error": 1.0,
                    "severe_error": False,
                }
            ]
            current["population"].update(
                {
                    "error_pairs": 2,
                    "exact_pairs": 1,
                    "severe_error_pairs": 0,
                }
            )
            current_path = root / "current.private.json"
            current_path.write_text(json.dumps(current), encoding="utf-8")

            evaluation = evaluate_regression_suite(
                private_suite_path=suite_path,
                current_private_book_path=current_path,
            )

        self.assertEqual(evaluation.public_summary["status"], "passed")
        self.assertEqual(evaluation.public_summary["counts"]["passed"], 2)
        self.assertEqual(
            evaluation.public_summary["observations"]["exact_gold"][
                "exact_cases"
            ],
            0,
        )
        self.assertFalse(
            evaluation.public_summary["observations"]["exact_gold"][
                "hard_gate"
            ]
        )
        self.assertEqual(audit_public_error_summary(evaluation.public_summary), [])

    def test_exact_gold_gate_remains_available_for_adjudicated_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book, diagnoses, policy_path, _, policy = self._fixture(root)
            policy["selectors"][1]["gate"] = {"kind": "exact_gold"}
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            suite_result = build_regression_suite(
                private_book_path=book,
                diagnoses_path=diagnoses,
                policy_path=policy_path,
            )
            suite_path = root / "suite.private.json"
            suite_path.write_text(
                json.dumps(suite_result.private_suite), encoding="utf-8"
            )
            evaluation = evaluate_regression_suite(
                private_suite_path=suite_path,
                current_private_book_path=book,
            )

        q9 = next(
            row
            for row in evaluation.private_evaluation["cases"]
            if row["question_id"] == "Q9"
        )
        self.assertFalse(q9["passed"])
        self.assertEqual(q9["reason"], "still_disagrees_with_gold")

    def test_rejects_incomplete_current_error_book(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book, diagnoses, policy, source, _ = self._fixture(root)
            suite_result = build_regression_suite(
                private_book_path=book,
                diagnoses_path=diagnoses,
                policy_path=policy,
            )
            suite_path = root / "suite.private.json"
            suite_path.write_text(
                json.dumps(suite_result.private_suite), encoding="utf-8"
            )
            source["cases"].pop()
            current_path = root / "incomplete.private.json"
            current_path.write_text(json.dumps(source), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "case count"):
                evaluate_regression_suite(
                    private_suite_path=suite_path,
                    current_private_book_path=current_path,
                )

    def test_comparability_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book, diagnoses, policy, source, _ = self._fixture(root)
            suite_result = build_regression_suite(
                private_book_path=book,
                diagnoses_path=diagnoses,
                policy_path=policy,
            )
            suite_path = root / "suite.private.json"
            suite_path.write_text(
                json.dumps(suite_result.private_suite), encoding="utf-8"
            )
            source["provenance"]["input_mode"] = "direct-multimodal"
            current_path = root / "current.private.json"
            current_path.write_text(json.dumps(source), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "input_mode"):
                evaluate_regression_suite(
                    private_suite_path=suite_path,
                    current_private_book_path=current_path,
                )

    def test_cli_builds_suite_and_returns_failure_for_negative_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book, diagnoses, policy, _, _ = self._fixture(root)
            suite_path = root / "suite.private.json"
            suite_public = root / "suite-public.json"
            with contextlib.redirect_stdout(io.StringIO()):
                build_code = main(
                    [
                        "build-error-regression-suite",
                        "--private-book",
                        str(book),
                        "--diagnoses",
                        str(diagnoses),
                        "--policy",
                        str(policy),
                        "--private-output",
                        str(suite_path),
                        "--public-output",
                        str(suite_public),
                    ]
                )
            evaluation_private = root / "evaluation.private.json"
            evaluation_public = root / "evaluation-public.json"
            with contextlib.redirect_stdout(io.StringIO()):
                evaluation_code = main(
                    [
                        "evaluate-error-regressions",
                        "--suite",
                        str(suite_path),
                        "--current-private-book",
                        str(book),
                        "--private-output",
                        str(evaluation_private),
                        "--public-output",
                        str(evaluation_public),
                    ]
                )
            self.assertEqual(build_code, 0)
            self.assertEqual(evaluation_code, 1)
            self.assertTrue(suite_public.exists())
            self.assertTrue(evaluation_public.exists())


class CommittedRegressionRecordTests(unittest.TestCase):
    def test_public_record_is_privacy_safe_and_detects_known_errors(self):
        suite = json.loads(
            (RECORD_ROOT / "public-suite-summary.json").read_text(
                encoding="utf-8"
            )
        )
        negative_control = json.loads(
            (RECORD_ROOT / "baseline-negative-control.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(audit_public_error_summary(suite), [])
        self.assertEqual(audit_public_error_summary(negative_control), [])
        self.assertEqual(suite["target_case_count"], 6)
        self.assertEqual(
            {
                row["question_id"]: row["target_cases"]
                for row in suite["by_question"]
            },
            {"Q6": 2, "Q9": 4},
        )
        self.assertEqual(negative_control["status"], "failed")
        self.assertEqual(negative_control["counts"]["passed"], 0)
        self.assertEqual(negative_control["counts"]["failed"], 6)
        self.assertEqual(
            {
                row["gate_kind"]
                for row in suite["by_selector"]
            },
            {"nonsevere_and_improved"},
        )
        self.assertEqual(
            negative_control["observations"]["exact_gold"]["exact_cases"],
            0,
        )

    def test_readme_is_bilingual_and_states_necessary_not_sufficient(self):
        text = (RECORD_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## 中文", text)
        self.assertIn("## English", text)
        self.assertIn("必要条件", text)
        self.assertIn("necessary", text)

    def test_registry_requires_and_validates_the_regression_suite(self):
        self.assertEqual(
            validate_error_book_registry(
                repo_root=REPO_ROOT,
                registry_path=REGISTRY_PATH,
            ),
            [],
        )
        with tempfile.TemporaryDirectory() as tmp:
            registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            registry.pop("regression_suites")
            path = Path(tmp) / "missing-regressions.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            findings = validate_error_book_registry(
                repo_root=REPO_ROOT,
                registry_path=path,
            )
        self.assertTrue(
            any("regression suite" in finding for finding in findings)
        )

    def test_future_registry_entry_cannot_skip_regression_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            future = copy.deepcopy(registry["entries"][-1])
            future.update(
                {
                    "skill_version_id": "skill_future_fixture",
                    "predecessor_skill_version_id": registry[
                        "active_skill_version_id"
                    ],
                    "iteration_delta_status": "compared",
                    "public_iteration_delta": None,
                }
            )
            future.pop("public_regression_evaluations", None)
            registry["entries"].append(future)
            registry["active_skill_version_id"] = "skill_future_fixture"
            path = Path(tmp) / "future-without-regression.json"
            path.write_text(json.dumps(registry), encoding="utf-8")

            findings = validate_error_book_registry(
                repo_root=REPO_ROOT,
                registry_path=path,
            )

        self.assertTrue(
            any(
                "missing regression evaluation" in finding
                for finding in findings
            )
        )


if __name__ == "__main__":
    unittest.main()
