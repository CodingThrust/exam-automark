import copy
import tempfile
import unittest
from pathlib import Path

from benchmark.core.packets import PromptPacketSpec, build_prompt_packet
from benchmark.core.rubrics import require_valid_rubric, validate_concept_rubric
from benchmark.core.schema import CourseSpec, QuestionSpec


def _course() -> CourseSpec:
    return CourseSpec(
        course_id="DSAA3071",
        assessment_id="week5",
        questions=(
            QuestionSpec(id="Q1", max_score=5, score_step=1),
            QuestionSpec(id="Q2", max_score=10, score_step=1),
        ),
    )


def _bands(maximum: int) -> dict[str, dict[str, int]]:
    return {
        "full": {"minimum": maximum, "maximum": maximum},
        "substantially_correct": {"minimum": maximum - 2, "maximum": maximum - 1},
        "partially_correct": {"minimum": 2, "maximum": maximum - 3},
        "minimal_relevant": {"minimum": 1, "maximum": 1},
        "no_credit": {"minimum": 0, "maximum": 0},
    }


def _question(question_id: str, maximum: int, *, element_id: str) -> dict[str, object]:
    return {
        "id": question_id,
        "max_score": maximum,
        "scoring_elements": [
            {
                "element_id": element_id,
                "levels": {
                    "mentioned_only": 1,
                    "partial_understanding": 2,
                    "demonstrated": maximum,
                },
            }
        ],
        "score_bands": _bands(maximum),
        "material_errors": [{"id": "none", "cap": maximum}],
        "full_credit_rule": "Demonstrate the required element.",
    }


def _rubric() -> dict[str, object]:
    return {
        "rubric_format": "concept_keyterm_v1",
        "questions": [
            _question("Q1", 5, element_id="first"),
            _question("Q2", 10, element_id="second"),
        ],
    }


class ConceptKeytermRubricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.course = _course()
        self.valid_rubric = _rubric()

    def test_valid_concept_rubric_has_no_findings(self) -> None:
        self.assertEqual(validate_concept_rubric(self.valid_rubric, self.course), [])

    def test_legacy_rubric_is_unchanged(self) -> None:
        self.assertEqual(validate_concept_rubric({"questions": []}, self.course), [])

    def test_level_credit_must_use_question_score_step(self) -> None:
        invalid = copy.deepcopy(self.valid_rubric)
        invalid["questions"][1]["scoring_elements"][0]["levels"]["mentioned_only"] = 1.5
        errors = validate_concept_rubric(invalid, self.course)
        self.assertIn("Q2 mentioned_only credit must use the 1.0 score step", errors)

    def test_detects_question_ids_maxima_and_duplicate_element_ids(self) -> None:
        invalid = copy.deepcopy(self.valid_rubric)
        invalid["questions"] = [
            _question("Q1", 10, element_id="duplicate"),
            _question("Q1", 5, element_id="duplicate"),
            _question("Q3", 10, element_id="third"),
        ]
        errors = validate_concept_rubric(invalid, self.course)
        self.assertIn("missing rubric question IDs: Q2", errors)
        self.assertIn("extra rubric question IDs: Q3", errors)
        self.assertIn("Q1 max_score must match course maximum 5.0", errors)
        self.assertIn("duplicate rubric question ID: Q1", errors)
        self.assertIn("duplicate scoring element ID: duplicate", errors)

    def test_rejects_invalid_levels_and_excess_demonstrated_total(self) -> None:
        invalid = copy.deepcopy(self.valid_rubric)
        levels = invalid["questions"][0]["scoring_elements"][0]["levels"]
        levels["mentioned_only"] = 2
        levels["partial_understanding"] = 2
        levels["demonstrated"] = 2.5
        invalid["questions"][0]["scoring_elements"].append(
            {
                "element_id": "extra",
                "levels": {
                    "mentioned_only": 1,
                    "partial_understanding": 2,
                    "demonstrated": 5,
                },
            }
        )
        errors = validate_concept_rubric(invalid, self.course)
        self.assertIn("Q1 level credits must be strictly ascending integers", errors)
        self.assertIn("Q1 demonstrated credits total 7.5 exceeds maximum 5.0", errors)

    def test_rejects_missing_or_invalid_score_bands_and_caps(self) -> None:
        invalid = copy.deepcopy(self.valid_rubric)
        question = invalid["questions"][1]
        del question["score_bands"]["minimal_relevant"]
        question["score_bands"]["partially_correct"] = {"minimum": 4, "maximum": 3}
        question["material_errors"][0]["cap"] = 11
        errors = validate_concept_rubric(invalid, self.course)
        self.assertIn("Q2 score_bands must define exactly: full, substantially_correct, partially_correct, minimal_relevant, no_credit", errors)
        self.assertIn("Q2 partially_correct band minimum must not exceed maximum", errors)
        self.assertIn(
            "Q2 material_errors[0] cap must be within 0..10.0 and use the 1.0 score step",
            errors,
        )

    def test_score_bands_must_cover_ordered_range_without_gaps_or_overlaps(self) -> None:
        invalid_cases = {
            "wrong_start": (
                "no_credit",
                {"minimum": 1, "maximum": 1},
                "Q2 no_credit band minimum must be 0.0",
            ),
            "wrong_end": (
                "full",
                {"minimum": 9, "maximum": 9},
                "Q2 full band maximum must be 10.0",
            ),
            "gap": (
                "partially_correct",
                {"minimum": 3, "maximum": 7},
                "Q2 minimal_relevant -> partially_correct bands must be ordered, non-overlapping, and contiguous by the 1.0 score step",
            ),
            "overlap": (
                "partially_correct",
                {"minimum": 1, "maximum": 7},
                "Q2 minimal_relevant -> partially_correct bands must be ordered, non-overlapping, and contiguous by the 1.0 score step",
            ),
            "reversed": (
                "substantially_correct",
                {"minimum": 5, "maximum": 7},
                "Q2 partially_correct -> substantially_correct bands must be ordered, non-overlapping, and contiguous by the 1.0 score step",
            ),
        }
        for name, (band, bounds, expected) in invalid_cases.items():
            with self.subTest(name=name):
                invalid = copy.deepcopy(self.valid_rubric)
                invalid["questions"][1]["score_bands"][band] = bounds
                errors = validate_concept_rubric(invalid, self.course)
                self.assertIn(expected, errors)

    def test_every_material_error_must_be_an_object_with_valid_numeric_cap(self) -> None:
        invalid = copy.deepcopy(self.valid_rubric)
        invalid["questions"][1]["material_errors"] = [
            {},
            "not-an-object",
            {"cap": "10"},
            {"cap": 2.5},
        ]
        errors = validate_concept_rubric(invalid, self.course)
        self.assertIn("Q2 material_errors[0] must define cap", errors)
        self.assertIn("Q2 material_errors[1] must be an object", errors)
        self.assertIn("Q2 material_errors[2] cap must be numeric", errors)
        self.assertIn(
            "Q2 material_errors[3] cap must be within 0..10.0 and use the 1.0 score step",
            errors,
        )

    def test_rejects_forbidden_keys_recursively(self) -> None:
        invalid = copy.deepcopy(self.valid_rubric)
        invalid["questions"][1]["full_credit_rule"] = {
            "text": "rule",
            "example_student_answer": "not allowed",
        }
        invalid["gold_score"] = 10
        errors = validate_concept_rubric(invalid, self.course)
        self.assertIn("forbidden rubric key: example_student_answer", errors)
        self.assertIn("forbidden rubric key: gold_score", errors)

    def test_require_valid_rubric_reports_all_findings(self) -> None:
        invalid = copy.deepcopy(self.valid_rubric)
        invalid["student_id"] = "S001"
        with self.assertRaisesRegex(ValueError, "forbidden rubric key: student_id"):
            require_valid_rubric(invalid, self.course)

    def test_invalid_concept_rubric_blocks_packet_directory_creation(self) -> None:
        invalid = copy.deepcopy(self.valid_rubric)
        invalid["questions"][0]["scoring_elements"][0]["levels"]["mentioned_only"] = 1.5
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_root = root / "packets"
            with self.assertRaisesRegex(ValueError, "invalid concept-keyterm rubric"):
                build_prompt_packet(
                    PromptPacketSpec(
                        course=self.course,
                        packet_id="G1-dev-r1",
                        condition="G1",
                        task="grade",
                        prompt_text="Grade the answer.",
                        student_ids=("S001",),
                        input_root=root / "inputs",
                        output_root=output_root,
                        rubric=invalid,
                    )
                )
            self.assertFalse((output_root / "G1-dev-r1").exists())
