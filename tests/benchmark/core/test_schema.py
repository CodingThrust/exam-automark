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

    def test_supports_leaf_subparts_discrete_scores_and_capped_bonus_total(self):
        course = CourseSpec(
            course_id="linearalgebra",
            assessment_id="quiz",
            questions=(
                QuestionSpec(
                    "Q1a",
                    5,
                    score_step=1,
                    parent_question_id="Q1",
                    allowed_scores=(0, 5),
                ),
                QuestionSpec("Q2", 95, score_step=1),
                QuestionSpec(
                    "Q2bonus",
                    10,
                    score_step=1,
                    parent_question_id="Q2",
                    allowed_scores=(0, 10),
                    is_bonus=True,
                ),
            ),
            base_total_points=100,
            final_score_cap=100,
        )
        records = [
            ScoreRecord("S001", "Q1a", 5, "high", "selected true"),
            ScoreRecord("S001", "Q2", 95, "high", "valid work"),
            ScoreRecord("S001", "Q2bonus", 10, "high", "two distinct methods"),
        ]

        self.assertEqual(course.question_map["Q1a"].parent_question_id, "Q1")
        self.assertEqual(course.raw_max_total, 110)
        self.assertEqual(course.max_total, 100)
        self.assertEqual(validate_score_records(records, course), 100)
        self.assertFalse(course.question_map["Q1a"].allows_score(4))

    def test_rejects_self_parent_and_invalid_discrete_score(self):
        with self.assertRaisesRegex(ValueError, "differ"):
            QuestionSpec("Q1", 5, parent_question_id="Q1")
        with self.assertRaisesRegex(ValueError, "allowed_scores"):
            QuestionSpec("Q1a", 5, allowed_scores=(1, 6))

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
