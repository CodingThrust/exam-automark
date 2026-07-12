import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


AGENT_SKILL = Path(".agents/skills/grade-homework")
CLAUDE_SKILL = Path(".claude/skills/grade-homework")


class GradeHomeworkCandidateSkillTests(unittest.TestCase):
    def test_skill_bundled_resources_are_synchronized(self):
        relative_files = [
            Path("SKILL.md"),
            Path("references/grading-prompt.md"),
            Path("scripts/discover.py"),
            Path("scripts/to_images.py"),
            Path("scripts/write_outputs.py"),
        ]

        for relative in relative_files:
            with self.subTest(relative=relative):
                self.assertEqual(
                    (AGENT_SKILL / relative).read_text(encoding="utf-8"),
                    (CLAUDE_SKILL / relative).read_text(encoding="utf-8"),
                )

    def test_skill_uses_teacher_partial_credit_policy(self):
        text = (AGENT_SKILL / "SKILL.md").read_text(encoding="utf-8").lower()
        prompt = (AGENT_SKILL / "references" / "grading-prompt.md").read_text(
            encoding="utf-8"
        ).lower()
        combined = text + "\n" + prompt

        self.assertIn("do not use 0.25-point", combined)
        self.assertIn("final answer is correct and the process", combined)
        self.assertIn("roughly correct", combined)
        self.assertIn("award full credit", combined)
        self.assertIn("when the final answer is wrong", combined)
        self.assertIn("process credit", combined)
        self.assertNotIn("if the rubric allows quarter points", combined)
        self.assertNotIn("quarter-point increment", combined)

    def test_discover_script_reports_solution_submissions_and_late_students(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "solutions.pdf").write_bytes(b"%PDF synthetic")
            (root / "S001_page1.jpg").write_bytes(b"image")
            (root / "S002_LATE_page1.png").write_bytes(b"image")

            result = subprocess.run(
                [
                    sys.executable,
                    str(AGENT_SKILL / "scripts" / "discover.py"),
                    str(root),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0)
        self.assertIsNone(payload["solutions_error"])
        self.assertEqual(payload["solutions_candidates"], ["solutions.pdf"])
        self.assertEqual(len(payload["submissions"]), 2)
        self.assertEqual(payload["late_students"], ["S002"])

    def test_to_images_script_converts_image_to_page_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "S001_page1.png"
            output = root / "pages"
            Image.new("RGB", (12, 10), color=(255, 255, 255)).save(source)

            result = subprocess.run(
                [
                    sys.executable,
                    str(AGENT_SKILL / "scripts" / "to_images.py"),
                    str(source),
                    str(output),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            payload = json.loads(result.stdout)
            page_exists = (output / "page-001.png").is_file()

        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(page_exists)

    def test_write_outputs_script_writes_csv_and_feedback(self):
        record = {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "Q1",
                    "score": 1.5,
                    "max_score": 2,
                    "evidence": "Shows correct setup with one arithmetic slip.",
                    "feedback": "Good setup; check the final arithmetic.",
                    "confidence": "medium",
                    "flags": ["high_impact_deduction"],
                }
            ],
            "total": 1.5,
            "flags": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            grades = Path(tmp) / "grades"
            result = subprocess.run(
                [
                    sys.executable,
                    str(AGENT_SKILL / "scripts" / "write_outputs.py"),
                    str(grades),
                ],
                input=json.dumps(record),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            with (grades / "grades.csv").open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                rows = list(csv.DictReader(handle))
            feedback = (grades / "feedback" / "S001.md").read_text(
                encoding="utf-8"
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(rows[0]["Q1"], "1.5")
        self.assertIn("Q1:high_impact_deduction", rows[0]["flags"])
        self.assertIn("Shows correct setup", feedback)


if __name__ == "__main__":
    unittest.main()
