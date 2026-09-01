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
            Path("references/course-package-template.json"),
            Path("scripts/roster.py"),
            Path("scripts/discover.py"),
            Path("scripts/to_images.py"),
            Path("scripts/render_submission.py"),
            Path("scripts/write_outputs.py"),
            Path("scripts/annotate_submission.py"),
        ]

        for relative in relative_files:
            with self.subTest(relative=relative):
                self.assertEqual(
                    (AGENT_SKILL / relative).read_text(encoding="utf-8"),
                    (CLAUDE_SKILL / relative).read_text(encoding="utf-8"),
                )

    def test_skill_keeps_course_specific_policy_outside_the_generic_core(self):
        text = (AGENT_SKILL / "SKILL.md").read_text(encoding="utf-8").lower()
        prompt = (AGENT_SKILL / "references" / "grading-prompt.md").read_text(
            encoding="utf-8"
        ).lower()
        combined = " ".join((text + "\n" + prompt).split())

        self.assertIn("course package", combined)
        self.assertIn("does not supply subject knowledge", combined)
        self.assertIn("do not invent a universal point rule", combined)
        self.assertIn("frozen for the batch", combined)
        for historical_overlay in ("physics week", "dsaa", "q7", "q8", "q9"):
            with self.subTest(historical_overlay=historical_overlay):
                self.assertNotIn(historical_overlay, combined)

    def test_skill_declares_cross_course_leaf_subpart_scoring(self):
        combined = "\n".join(
            (
                (AGENT_SKILL / "SKILL.md").read_text(encoding="utf-8"),
                (AGENT_SKILL / "references" / "grading-prompt.md").read_text(
                    encoding="utf-8"
                ),
            )
        ).lower()
        for phrase in (
            "smallest independently scoreable leaf",
            "do not invent subparts",
            "do not merge",
            "aggregate parent score",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, combined)

    def test_skill_declares_generic_evidence_trace_and_annotation_contract(self):
        combined = "\n".join(
            (
                (AGENT_SKILL / "SKILL.md").read_text(encoding="utf-8"),
                (AGENT_SKILL / "references" / "grading-prompt.md").read_text(
                    encoding="utf-8"
                ),
            )
        ).lower()
        for phrase in (
            "complete anonymous submission",
            "deduction_trace",
            "points_deducted",
            "attention_note",
            "marked-page annotations",
            "student_name,student_number",
            "private roster",
            "a teacher owns",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, combined)

    def test_skill_treats_page_positions_as_locators_not_question_ids(self):
        combined = "\n".join(
            (
                (AGENT_SKILL / "SKILL.md").read_text(encoding="utf-8"),
                (AGENT_SKILL / "references" / "grading-prompt.md").read_text(
                    encoding="utf-8"
                ),
            )
        ).lower()
        for phrase in (
            "page position",
            "never question numbers",
            "do not assume that p01",
            "page_order_uncertain",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, combined)

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
        self.assertEqual(payload["root"], ".")
        self.assertEqual(payload["solutions_candidates"], ["solutions.pdf"])
        self.assertEqual(len(payload["submissions"]), 2)
        self.assertEqual(payload["late_students"], ["S002"])
        self.assertNotIn("S001_page1.jpg", result.stdout)
        self.assertNotIn(str(root), result.stdout)

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
        self.assertEqual(payload["pages"], ["page-001.png"])
        self.assertNotIn(str(source), result.stdout)
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
                    "deduction_trace": [
                        {
                            "rubric_criterion": "final arithmetic",
                            "observed_evidence_or_missing_or_incorrect_part": "The final arithmetic result is incorrect.",
                            "deduction_type": "local_arithmetic_or_notation_error",
                            "points_deducted": 0.5,
                        }
                    ],
                    "attention_note": "Review the final arithmetic step.",
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
        self.assertIn("Deduction trace", feedback)

    def test_grouped_batch_writes_roster_columns_and_renders_marked_pages(self):
        record = {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "leaf-a",
                    "score": 1,
                    "max_score": 2,
                    "evidence": "A visible required component is absent.",
                    "feedback": "Please include the required component.",
                    "confidence": "medium",
                    "flags": ["needs_manual_review"],
                    "deduction_trace": [
                        {
                            "rubric_criterion": "visible requirement",
                            "observed_evidence_or_missing_or_incorrect_part": "The required component is absent.",
                            "deduction_type": "missing_required_evidence",
                            "points_deducted": 1,
                        }
                    ],
                    "attention_note": "Please verify the marked region.",
                }
            ],
            "annotations": [
                {
                    "question_id": "leaf-a",
                    "page_id": "source-001-page-001",
                    "box": [0.1, 0.65, 0.4, 0.15],
                    "kind": "praise",
                    "label": "A valid component is clearly shown.",
                },
                {
                    "question_id": "leaf-a",
                    "page_id": "source-001-page-001",
                    "box": [0.1, 0.1, 0.4, 0.2],
                    "kind": "deduction",
                    "label": "Required component is missing.",
                },
                {
                    "question_id": "leaf-a",
                    "page_id": "source-001-page-001",
                    "box": [0.1, 0.4, 0.4, 0.2],
                    "kind": "review",
                    "label": "Please verify this region.",
                },
            ],
            "total": 1,
            "flags": [],
        }
        course_package = {
            "schema_version": 1,
            "course_id": "synthetic-course",
            "assessment_id": "synthetic-assessment",
            "score_leaves": [
                {"question_id": "leaf-a", "max_score": 2, "allowed_increment": 1}
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roster = root / "roster.csv"
            roster.write_text(
                "submission_id,student_name,student_number\nS001,Test Person,900001\n",
                encoding="utf-8",
            )
            package_path = root / "course-package.json"
            package_path.write_text(json.dumps(course_package), encoding="utf-8")
            submission = root / "submissions" / "S001"
            submission.mkdir(parents=True)
            Image.new("RGB", (80, 60), color=(255, 255, 255)).save(
                submission / "scan.png"
            )
            rendered = root / "rendered" / "S001"
            render = subprocess.run(
                [
                    sys.executable,
                    str(AGENT_SKILL / "scripts" / "render_submission.py"),
                    str(submission),
                    str(rendered),
                    "--submission-id",
                    "S001",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            grades = root / "grades"
            missing_praise_record = dict(record)
            missing_praise_record["annotations"] = [
                annotation
                for annotation in record["annotations"]
                if annotation["kind"] != "praise"
            ]
            missing_praise = subprocess.run(
                [
                    sys.executable,
                    str(AGENT_SKILL / "scripts" / "write_outputs.py"),
                    str(root / "missing-praise"),
                    "--roster",
                    str(roster),
                    "--course-package",
                    str(package_path),
                    "--require-annotations",
                ],
                input=json.dumps(missing_praise_record),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            write = subprocess.run(
                [
                    sys.executable,
                    str(AGENT_SKILL / "scripts" / "write_outputs.py"),
                    str(grades),
                    "--roster",
                    str(roster),
                    "--course-package",
                    str(package_path),
                    "--require-annotations",
                ],
                input=json.dumps(record),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            annotate = subprocess.run(
                [
                    sys.executable,
                    str(AGENT_SKILL / "scripts" / "annotate_submission.py"),
                    str(rendered / "pages.json"),
                    str(grades / "annotations" / "S001.json"),
                    str(grades / "marked" / "S001"),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            with (grades / "grades.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            review = (grades / "review.csv").read_text(encoding="utf-8")
            manifest = (rendered / "pages.json").read_text(encoding="utf-8")

            self.assertEqual(render.returncode, 0, render.stderr)
            self.assertEqual(missing_praise.returncode, 2)
            self.assertIn("requires a praise annotation", missing_praise.stderr)
            self.assertEqual(write.returncode, 0, write.stderr)
            self.assertEqual(annotate.returncode, 0, annotate.stderr)
            self.assertEqual(rows[0]["student_name"], "Test Person")
            self.assertEqual(rows[0]["student_number"], "900001")
            self.assertIn("needs_manual_review", review)
            self.assertTrue((grades / "marked" / "S001" / "marked.pdf").is_file())
            self.assertNotIn("scan.png", manifest)
            self.assertNotIn(str(root), write.stdout)
            self.assertNotIn("Test Person", write.stdout)

    def test_write_outputs_refuses_an_unignored_git_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(
                ["git", "init", "--quiet", str(root)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(AGENT_SKILL / "scripts" / "write_outputs.py"),
                    str(root / "grades"),
                ],
                input="{}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("private and ignored", result.stderr)


if __name__ == "__main__":
    unittest.main()
