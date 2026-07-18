import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.schema import CourseSpec
from benchmark.core.transcripts import validate_transcript_source


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class TranscriptSourceTests(unittest.TestCase):
    def test_complete_transcript_source_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")
            _write_transcript(root / "S001.json", course, "S001")
            _write_transcript(root / "S002" / "transcript.json", course, "S002")

            report = validate_transcript_source(course, root, ["S001", "S002"])

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["expected_student_count"], 2)
        self.assertEqual(report["valid_transcript_count"], 2)
        self.assertEqual(report["failed_checks"], [])

    def test_missing_and_malformed_transcripts_block_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")
            _write_transcript(
                root / "S001.json",
                course,
                "S001",
                answers=[
                    {"question_id": "Q1", "text": "visible", "unclear": False},
                ],
            )

            report = validate_transcript_source(course, root, ["S001", "S002"])

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("all_expected_transcripts_present", report["failed_checks"])
        self.assertIn("transcripts_match_course_schema", report["failed_checks"])
        self.assertEqual(len(report["missing_students"]), 1)
        self.assertEqual(len(report["invalid_transcripts"]), 1)


def _write_transcript(
    path: Path,
    course: CourseSpec,
    student_id: str,
    *,
    answers: list[dict[str, object]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "student_id": student_id,
        "answers": answers
        if answers is not None
        else [
            {"question_id": question_id, "text": "visible answer", "unclear": False}
            for question_id in course.question_ids
        ],
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    unittest.main()
