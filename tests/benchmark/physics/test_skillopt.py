import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from benchmark.physics.cli import main
from benchmark.physics.skillopt import build_skillopt_pilot_summary


class SkillOptPilotTests(unittest.TestCase):
    def test_summary_splits_dev_feedback_and_applies_acceptance_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, baseline_run, candidate_run = self._fixture(Path(tmp))

            summary = build_skillopt_pilot_summary(
                root,
                baseline_run,
                candidate_run,
                train_fraction=0.5,
            )

            self.assertEqual(summary["record_type"], "physics_skillopt_pilot_summary")
            self.assertFalse(summary["privacy_scope"]["contains_raw_student_answers"])
            self.assertFalse(summary["privacy_scope"]["contains_model_transcripts"])
            self.assertEqual(summary["split"]["train_student_ids"], ["S001", "S002"])
            self.assertEqual(
                summary["split"]["validation_student_ids"], ["S003", "S004"]
            )
            self.assertGreater(
                summary["validation"]["candidate_minus_baseline"]["exact_agreement"],
                0,
            )
            self.assertTrue(summary["acceptance_gate"]["candidate_passes_gate"])
            self.assertEqual(
                summary["validation"]["weak_questions"][0]["question_id"],
                "Q2",
            )
            self.assertNotIn("evidence", json.dumps(summary))
            self.assertNotIn("student answer", json.dumps(summary).lower())

    def test_cli_writes_skillopt_pilot_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, baseline_run, candidate_run = self._fixture(Path(tmp))
            output_json = root / "runs" / "skillopt" / "anchor.json"
            output_md = root / "runs" / "skillopt" / "anchor.md"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "skillopt-pilot",
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
                    ]
                )

            self.assertEqual(code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["record_type"], "physics_skillopt_pilot_summary")
            self.assertTrue(output_json.exists())
            self.assertTrue(output_md.exists())
            self.assertIn(
                "Physics SkillOpt Pilot Anchor",
                output_md.read_text(encoding="utf-8"),
            )

    def _fixture(self, root_parent: Path) -> tuple[Path, Path, Path]:
        root = root_parent / "benchmark"
        baseline_run = root / "runs" / "baseline"
        candidate_run = root / "runs" / "candidate"
        (root / "gold").mkdir(parents=True)
        baseline_run.mkdir(parents=True)
        candidate_run.mkdir(parents=True)
        self._write_scores(root / "gold" / "primary_scores.csv", self._gold_rows())
        self._write_scores(baseline_run / "predictions.csv", self._baseline_rows())
        self._write_scores(candidate_run / "predictions.csv", self._candidate_rows())
        return root, baseline_run, candidate_run

    def _write_scores(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("student_id", "question_id", "score", "confidence"),
            )
            writer.writeheader()
            writer.writerows(rows)

    def _gold_rows(self) -> list[dict[str, object]]:
        return [
            {
                "student_id": student_id,
                "question_id": question_id,
                "score": 1.0,
                "confidence": "high",
            }
            for student_id in ("S001", "S002", "S003", "S004")
            for question_id in ("Q1", "Q2")
        ]

    def _baseline_rows(self) -> list[dict[str, object]]:
        return [
            {
                "student_id": row["student_id"],
                "question_id": row["question_id"],
                "score": 0.0,
                "confidence": "high",
            }
            for row in self._gold_rows()
        ]

    def _candidate_rows(self) -> list[dict[str, object]]:
        rows = []
        for row in self._gold_rows():
            question_id = row["question_id"]
            rows.append(
                {
                    "student_id": row["student_id"],
                    "question_id": question_id,
                    "score": 1.0 if question_id == "Q1" else 0.0,
                    "confidence": "high",
                }
            )
        return rows


if __name__ == "__main__":
    unittest.main()
