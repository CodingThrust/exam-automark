import csv
import tempfile
import unittest
from pathlib import Path

from benchmark.core.gold import validate_gold_table
from benchmark.core.schema import CourseSpec


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class GoldTableTests(unittest.TestCase):
    def test_complete_gold_table_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")
            gold_path = Path(tmp) / "primary_scores.csv"
            _write_gold(
                gold_path,
                [
                    ("S001", "Q1", "9.5"),
                    ("S001", "Q2a", "2.75"),
                    ("S001", "Q2b", "1.5"),
                    ("S002", "Q1", "8"),
                    ("S002", "Q2a", "3"),
                    ("S002", "Q2b", "2"),
                ],
            )

            report = validate_gold_table(course, gold_path, ["S001", "S002"])

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["expected_rows"], 6)
        self.assertEqual(report["filled_score_rows"], 6)
        self.assertEqual(report["failed_checks"], [])

    def test_blank_missing_and_invalid_scores_block_gold_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")
            gold_path = Path(tmp) / "primary_scores.csv"
            _write_gold(
                gold_path,
                [
                    ("S001", "Q1", "9.5"),
                    ("S001", "Q2a", ""),
                    ("S001", "Q2b", "1.5"),
                    ("S002", "Q1", "11"),
                    ("S002", "Q2a", "2.6"),
                ],
            )

            report = validate_gold_table(course, gold_path, ["S001", "S002"])

        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(report["blank_score_rows"], 1)
        self.assertIn("all_expected_pairs_present_once", report["failed_checks"])
        self.assertIn("scores_complete", report["failed_checks"])
        self.assertIn("scores_within_course_steps", report["failed_checks"])


def _write_gold(path: Path, rows: list[tuple[str, str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("student_id", "question_id", "score", "reviewer", "reviewed_at", "notes"),
        )
        writer.writeheader()
        for student_id, question_id, score in rows:
            writer.writerow(
                {
                    "student_id": student_id,
                    "question_id": question_id,
                    "score": score,
                    "reviewer": "primary",
                    "reviewed_at": "2026-07-18",
                    "notes": "",
                }
            )


if __name__ == "__main__":
    unittest.main()
