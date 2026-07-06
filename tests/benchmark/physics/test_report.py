import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.physics.gold import SCORE_FIELDS
from benchmark.physics.report import render_benchmark_report


class ReportTests(unittest.TestCase):
    def _workspace(self, root: Path, *, student_id: str = "S001") -> Path:
        benchmark_root = root / "benchmark"
        runs = benchmark_root / "runs" / "G2-test-r1"
        runs.mkdir(parents=True)
        with (runs / "predictions.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "student_id": student_id,
                    "question_id": "Q1a",
                    "score": "2",
                    "confidence": "high",
                    "evidence": "",
                    "ambiguity_code": "",
                }
            )

        for split, accuracy in (("test", 0.8), ("all", 0.82), ("dev", 0.85)):
            metrics = {
                "split": split,
                "reference_status": "single_primary_rater",
                "excluded_runs": ["G1-dev-r1"],
                "conditions": {
                    condition: self._condition(condition, accuracy)
                    for condition in ("G0", "G2", "D1", "G3", "D2")
                },
                "paired_vs_g0": {
                    "G2": {
                        "mean_difference": -0.02,
                        "lower": -0.08,
                        "upper": 0.04,
                    },
                    "D1": {
                        "mean_difference": -0.05,
                        "lower": -0.12,
                        "upper": 0.01,
                    },
                },
                "transcript_subset_comparisons": {
                    "GPT": {
                        "automatic_condition": "G2",
                        "human_condition": "G3",
                        "n_students": 6,
                        "automatic_exact_agreement": 0.78,
                        "human_exact_agreement": 0.80,
                        "human_minus_automatic": {
                            "mean_difference": 0.02,
                            "lower": -0.03,
                            "upper": 0.07,
                        },
                    }
                },
            }
            (benchmark_root / f"metrics-{split}.json").write_text(
                json.dumps(metrics), encoding="utf-8"
            )
        return benchmark_root

    @staticmethod
    def _condition(condition: str, accuracy: float) -> dict:
        subset = condition in {"G3", "D2"}
        return {
            "run_id": f"{condition}-test-r1",
            "n_students": 6 if subset else 18,
            "population": "transcript_subset" if subset else "full_split",
            "exact_agreement": accuracy,
            "macro_accuracy": accuracy - 0.01,
            "subquestion_mae": 0.2,
            "total_score_mae": 1.1,
            "within_1_point_rate": 0.7,
            "mean_signed_error": -0.1,
            "severe_error_rate": 0.1,
            "per_question_accuracy": {"Q1a": accuracy, "Q2a": accuracy - 0.2},
        }

    def test_renders_anonymous_heldout_first_report_with_limitations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._workspace(Path(tmp))

            report = render_benchmark_report(root)

            self.assertIn("# Physics Week 9 Internal Grading Benchmark", report)
            self.assertIn("Historical direct workflow", report)
            self.assertIn("Codex Plus interactive run", report)
            self.assertIn("single run", report.lower())
            self.assertIn("G0", report)
            self.assertIn("G2", report)
            self.assertIn("D1", report)
            self.assertNotIn("student_real_name_001", report.lower())
            self.assertNotIn("OPENAI_API_KEY", report)
            self.assertNotIn("G1-dev-r1", report.split("Accuracy Results")[1])
            self.assertLess(
                report.index("Held-Out Results"), report.index("Combined Results")
            )
            self.assertIn("single primary-rater standard", report)
            self.assertIn("model-run variance was not estimated", report)
            self.assertIn("Human minus automatic", report)

    def test_rejects_nonanonymous_student_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._workspace(Path(tmp), student_id="student_real_name_001")

            with self.assertRaisesRegex(ValueError, "non-anonymous student ID"):
                render_benchmark_report(root)


if __name__ == "__main__":
    unittest.main()
