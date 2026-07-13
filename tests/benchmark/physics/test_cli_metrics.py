import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from benchmark.physics.cli import main
from benchmark.physics.schema import QUESTION_IDS


class CliMetricsTests(unittest.TestCase):
    def test_metrics_compares_output_json_runs_and_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "benchmark"
            baseline_run = root / "runs" / "baseline"
            candidate_run = root / "runs" / "candidate"
            (root / "gold").mkdir(parents=True)
            (baseline_run / "outputs").mkdir(parents=True)
            (candidate_run / "outputs").mkdir(parents=True)
            self._write_gold(root / "gold" / "primary_scores.csv")
            self._write_output(baseline_run / "outputs" / "S001.json", "S001", {})
            self._write_output(baseline_run / "outputs" / "S002.json", "S002", {})
            self._write_output(candidate_run / "outputs" / "S001.json", "S001", {})
            self._write_output(
                candidate_run / "outputs" / "S002.json",
                "S002",
                {"Q1a": 1.0},
            )
            output_json = root / "metrics.json"
            output_md = root / "metrics.md"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "metrics",
                        "--root",
                        str(root),
                        "--baseline-run",
                        str(baseline_run),
                        "--candidate-run",
                        str(candidate_run),
                        "--output-json",
                        str(output_json),
                        "--output-md",
                        str(output_md),
                        "--bootstrap-samples",
                        "200",
                    ]
                )

            self.assertEqual(code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["record_type"], "physics_run_metrics_comparison")
            self.assertEqual(result["student_count"], 2)
            self.assertEqual(result["score_count"], 24)
            self.assertGreater(
                result["candidate"]["exact_agreement"],
                result["baseline"]["exact_agreement"],
            )
            self.assertAlmostEqual(
                result["candidate_minus_baseline"]["exact_agreement"],
                1 / 24,
            )
            self.assertTrue(output_json.exists())
            self.assertIn(
                "Physics Metrics Comparison",
                output_md.read_text(encoding="utf-8"),
            )

    def _write_gold(self, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("student_id", "question_id", "score"),
            )
            writer.writeheader()
            for student_id in ("S001", "S002"):
                for question_id in QUESTION_IDS:
                    writer.writerow(
                        {
                            "student_id": student_id,
                            "question_id": question_id,
                            "score": 1.0
                            if student_id == "S002" and question_id == "Q1a"
                            else 0.0,
                        }
                    )

    def _write_output(
        self, path: Path, student_id: str, score_overrides: dict[str, float]
    ) -> None:
        scores = [
            {
                "question_id": question_id,
                "extracted_evidence": "synthetic fixture",
                "score": score_overrides.get(question_id, 0.0),
                "evidence": "synthetic fixture",
                "confidence": "high",
                "flags": [],
            }
            for question_id in QUESTION_IDS
        ]
        path.write_text(
            json.dumps(
                {
                    "student_id": student_id,
                    "scores": scores,
                    "total": sum(row["score"] for row in scores),
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
