import unittest
from pathlib import Path

from benchmark.core.schema import (
    CourseSpec,
    QuestionSpec,
    ScoreRecord,
    SplitPlan,
    validate_score_records,
)


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class CoreSchemaTests(unittest.TestCase):
    def test_loads_multi_course_spec_from_synthetic_fixture(self):
        course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")

        self.assertEqual(course.course_id, "dsaa3073")
        self.assertEqual(course.assessment_id, "hw1")
        self.assertEqual(course.question_ids, ("Q1", "Q2a", "Q2b"))
        self.assertEqual(course.max_total, 15.0)
        self.assertIn("transcript", course.input_modes)

    def test_rejects_duplicate_question_ids(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            CourseSpec(
                course_id="linearalgebra",
                assessment_id="midterm",
                questions=(
                    QuestionSpec("Q1", 5),
                    QuestionSpec("Q1", 5),
                ),
            )

    def test_validates_course_specific_score_ranges_and_steps(self):
        course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")
        records = [
            ScoreRecord("S001", "Q1", 9.5, "high", "visible derivation"),
            ScoreRecord("S001", "Q2a", 2.75, "medium", "minor gap"),
            ScoreRecord("S001", "Q2b", 1.5, "high", "correct conclusion"),
        ]

        self.assertEqual(validate_score_records(records, course), 13.75)

        bad = list(records)
        bad[1] = ScoreRecord("S001", "Q2a", 2.6, "medium", "off increment")
        with self.assertRaisesRegex(ValueError, "Q2a score"):
            validate_score_records(bad, course)

    def test_rejects_nonanonymous_student_ids(self):
        course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")
        records = [
            ScoreRecord("real_name", "Q1", 9.5, "high", "visible derivation"),
            ScoreRecord("real_name", "Q2a", 2.75, "medium", "minor gap"),
            ScoreRecord("real_name", "Q2b", 1.5, "high", "correct conclusion"),
        ]

        with self.assertRaisesRegex(ValueError, "anonymous student id"):
            validate_score_records(records, course)

    def test_split_plan_rejects_overlap_and_outside_transcript_subset(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            SplitPlan(
                development_student_ids=("S001", "S002"),
                heldout_student_ids=("S002", "S003"),
            )

        with self.assertRaisesRegex(ValueError, "outside split"):
            SplitPlan(
                development_student_ids=("S001",),
                heldout_student_ids=("S002",),
                transcript_development_student_ids=("S003",),
            )

    def test_split_plan_validates_anonymous_ids_against_course(self):
        course = CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")
        split = SplitPlan(
            development_student_ids=("S001",),
            heldout_student_ids=("student-real-name",),
        )

        with self.assertRaisesRegex(ValueError, "anonymous student id"):
            split.validate_against_course(course)


if __name__ == "__main__":
    unittest.main()
