import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from benchmark.core.readiness_scaffolding import (
    GOLD_TEMPLATE_COLUMNS,
    ReadinessScaffoldError,
    collect_anonymous_student_ids,
    freeze_split,
    initialize_blank_gold,
)
from benchmark.core.schema import CourseSpec


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"
REPO_ROOT = Path(__file__).parents[3]


class ReadinessScaffoldingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")

    def test_blank_gold_is_question_level_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            students_file = root / "students.txt"
            students_file.write_text("# cohort\nS002\n\nS001\n", encoding="utf-8")
            gold_path = root / "gold.csv"

            student_ids = collect_anonymous_student_ids(
                self.course, students_file=students_file
            )
            created = initialize_blank_gold(self.course, student_ids, gold_path)
            repeated = initialize_blank_gold(self.course, student_ids, gold_path)
            with gold_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(student_ids, ("S001", "S002"))
        self.assertEqual(created["status"], "created")
        self.assertEqual(repeated["status"], "already_matches_template")
        self.assertEqual(tuple(rows[0]), GOLD_TEMPLATE_COLUMNS)
        self.assertEqual(len(rows), 6)
        self.assertEqual(
            [(row["student_id"], row["question_id"], row["score"]) for row in rows],
            [
                ("S001", "Q1", ""),
                ("S001", "Q2a", ""),
                ("S001", "Q2b", ""),
                ("S002", "Q1", ""),
                ("S002", "Q2a", ""),
                ("S002", "Q2b", ""),
            ],
        )

    def test_blank_gold_never_replaces_divergent_nonempty_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            gold_path = Path(tmp) / "gold.csv"
            gold_path.write_text("do not replace\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ReadinessScaffoldError, "refusing to overwrite non-empty gold template"
            ):
                initialize_blank_gold(self.course, ("S001",), gold_path)

            current = gold_path.read_text(encoding="utf-8")

        self.assertEqual(current, "do not replace\n")

    def test_students_dir_is_nonrecursive_and_uses_matching_child_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "S002").mkdir()
            (root / "S001").mkdir()
            (root / "metadata.json").write_text("{}", encoding="utf-8")
            nested = root / "other" / "S003"
            nested.mkdir(parents=True)

            student_ids = collect_anonymous_student_ids(
                self.course, students_dir=root
            )

        self.assertEqual(student_ids, ("S001", "S002"))

    def test_freeze_split_is_repeatable_and_refuses_divergent_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_path = root / "split.json"
            development_path = root / "development.txt"
            heldout_path = root / "heldout.txt"
            students = ("S004", "S001", "S003", "S002")

            created = freeze_split(
                self.course,
                students,
                seed="week4-r1",
                heldout_count=1,
                output_json=split_path,
                development_students_file=development_path,
                heldout_students_file=heldout_path,
            )
            repeated = freeze_split(
                self.course,
                tuple(reversed(students)),
                seed="week4-r1",
                heldout_count=1,
                output_json=split_path,
                development_students_file=development_path,
                heldout_students_file=heldout_path,
            )
            before = {
                path: path.read_bytes()
                for path in (split_path, development_path, heldout_path)
            }
            with self.assertRaisesRegex(
                ReadinessScaffoldError, "divergent frozen split outputs"
            ):
                freeze_split(
                    self.course,
                    students,
                    seed="different-seed",
                    heldout_count=1,
                    output_json=split_path,
                    development_students_file=development_path,
                    heldout_students_file=heldout_path,
                )
            after = {
                path: path.read_bytes()
                for path in (split_path, development_path, heldout_path)
            }
            payload = json.loads(split_path.read_text(encoding="utf-8"))

        self.assertEqual(created["status"], "frozen")
        self.assertEqual(repeated["status"], "already_frozen")
        self.assertEqual(before, after)
        self.assertEqual(payload["student_count"], 4)
        self.assertEqual(payload["heldout_count"], 1)
        self.assertEqual(len(payload["development_student_ids"]), 3)

    def test_standalone_clis_create_only_synthetic_temp_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course_path = FIXTURES / "course_dsaa3073_hw1.json"
            gold_path = root / "gold.csv"
            split_path = root / "split.json"
            development_path = root / "development.txt"
            heldout_path = root / "heldout.txt"

            gold = _run_script(
                "init_blank_gold.py",
                "--course",
                str(course_path),
                "--output",
                str(gold_path),
                "--student-id",
                "S001",
                "--student-id",
                "S002",
            )
            split = _run_script(
                "freeze_anonymous_split.py",
                "--course",
                str(course_path),
                "--seed",
                "synthetic-seed",
                "--heldout-count",
                "1",
                "--output",
                str(split_path),
                "--development-students-file",
                str(development_path),
                "--heldout-students-file",
                str(heldout_path),
                "--student-id",
                "S001",
                "--student-id",
                "S002",
            )

        self.assertEqual(gold["status"], "created")
        self.assertEqual(gold["columns"], list(GOLD_TEMPLATE_COLUMNS))
        self.assertEqual(split["status"], "frozen")
        self.assertEqual(split["student_count"], 2)


def _run_script(script_name: str, *args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-B", str(REPO_ROOT / "scripts" / script_name), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"{script_name} failed with {result.returncode}: {result.stderr}"
        )
    return json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()
