import json
import unittest
from pathlib import Path

from benchmark.core.schema import CourseSpec


REPO_ROOT = Path(__file__).resolve().parents[3]
COURSE_PATH = REPO_ROOT / "experiments" / "course_specs" / "linearalgebra_quiz1.json"
RECORD_ROOT = REPO_ROOT / "experiments" / "records" / "linearalgebra-quiz1-plan"


class LinearAlgebraCourseAssetTests(unittest.TestCase):
    def test_q2_subparts_are_independently_scored_and_aligned(self):
        course_payload = json.loads(COURSE_PATH.read_text(encoding="utf-8"))
        course = CourseSpec.from_dict(course_payload)
        rubric = json.loads((RECORD_ROOT / "rubric_v1.json").read_text(encoding="utf-8"))
        reference = json.loads(
            (RECORD_ROOT / "reference_solution_v1.json").read_text(encoding="utf-8")
        )

        expected_ids = ["Q1", "Q2a", "Q2b", "Q3", "Q4"]
        self.assertEqual(list(course.question_ids), expected_ids)
        self.assertEqual(course.question_map["Q2a"].max_score, 15)
        self.assertEqual(course.question_map["Q2b"].max_score, 15)
        self.assertEqual(sum(question.max_score for question in course.questions), 100)
        self.assertEqual([question["id"] for question in rubric["questions"]], expected_ids)
        self.assertEqual([question["id"] for question in reference["questions"]], expected_ids)


if __name__ == "__main__":
    unittest.main()
