import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from benchmark.core.packets import PromptPacketSpec, build_prompt_packet
from benchmark.core.rubrics import require_valid_rubric, validate_concept_rubric
from benchmark.core.schema import CourseSpec, QuestionSpec


DSAA3071_V1_ELEMENT_CREDIT = {
    "Q5": {
        "virtual_tape_encoding": (6, 1),
        "virtual_head_tracking": (6, 1),
        "simulated_step": (8, 2),
    },
    "Q6": {
        "branch_address": (5, 1),
        "systematic_exploration": (6, 1),
        "branch_simulation_and_acceptance": (6, 1),
        "resource_or_overhead_awareness": (3, 1),
    },
    "Q7": {
        "recognizer_to_enumerator": (9, 2),
        "enumerator_to_recognizer": (8, 2),
        "correctness_and_nonmembership": (3, 1),
    },
    "Q8": {
        "power_of_two_outputs": (5, 1),
        "enumerator_loop_or_doubling": (5, 1),
    },
    "Q9": {
        "equivalent_computation_models": (8, 2),
        "tm_variant_robustness": (8, 2),
        "absence_of_counterexamples": (9, 2),
    },
    "Q10": {
        "stay_put_simulation": (5, 1),
        "finite_tape_restriction": (5, 1),
        "one_way_restriction": (5, 1),
    },
}

DSAA3071_V1_SCORE_BANDS = {
    10: {
        "no_credit": {"minimum": 0, "maximum": 0},
        "minimal_relevant": {"minimum": 1, "maximum": 2},
        "partially_correct": {"minimum": 3, "maximum": 5},
        "substantially_correct": {"minimum": 6, "maximum": 9},
        "full": {"minimum": 10, "maximum": 10},
    },
    15: {
        "no_credit": {"minimum": 0, "maximum": 0},
        "minimal_relevant": {"minimum": 1, "maximum": 4},
        "partially_correct": {"minimum": 5, "maximum": 9},
        "substantially_correct": {"minimum": 10, "maximum": 14},
        "full": {"minimum": 15, "maximum": 15},
    },
    20: {
        "no_credit": {"minimum": 0, "maximum": 0},
        "minimal_relevant": {"minimum": 1, "maximum": 5},
        "partially_correct": {"minimum": 6, "maximum": 12},
        "substantially_correct": {"minimum": 13, "maximum": 19},
        "full": {"minimum": 20, "maximum": 20},
    },
    25: {
        "no_credit": {"minimum": 0, "maximum": 0},
        "minimal_relevant": {"minimum": 1, "maximum": 7},
        "partially_correct": {"minimum": 8, "maximum": 16},
        "substantially_correct": {"minimum": 17, "maximum": 24},
        "full": {"minimum": 25, "maximum": 25},
    },
}

DSAA3071_V1_BAND_ASSIGNMENTS = {
    "Q5": 20,
    "Q6": 20,
    "Q7": 20,
    "Q8": 10,
    "Q9": 25,
    "Q10": 15,
}

DSAA3071_V1_MATERIAL_ERROR_CAPS = {
    "Q5": 9,
    "Q6": 10,
    "Q7": 16,
    "Q8": 4,
    "Q9": 16,
}


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

    def test_every_required_score_band_must_be_an_object(self) -> None:
        invalid = copy.deepcopy(self.valid_rubric)
        invalid["questions"][1]["score_bands"]["full"] = []
        errors = validate_concept_rubric(invalid, self.course)
        self.assertIn("Q2 full band must be an object", errors)

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


class DSAA3071RubricV1AssetTests(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        self.course = CourseSpec.from_json_path(
            repo_root / "experiments" / "course_specs" / "DSAA3071_week5_test.json"
        )
        rubric_path = (
            repo_root
            / "experiments"
            / "records"
            / "DSAA3071-week5-prep"
            / "rubric_v1.json"
        )
        self.rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
        self.questions = {
            question["id"]: question for question in self.rubric["questions"]
        }

    def test_rubric_v1_is_valid_calibrated_and_privacy_safe(self) -> None:
        self.assertEqual(self.rubric["rubric_format"], "concept_keyterm_v1")
        self.assertEqual(validate_concept_rubric(self.rubric, self.course), [])
        self.assertEqual(
            sum(question["max_score"] for question in self.rubric["questions"]),
            130,
        )
        for question in self.rubric["questions"][4:]:
            self.assertTrue(question["scoring_elements"])
            self.assertTrue(
                any(
                    element["levels"]["mentioned_only"] > 0
                    for element in question["scoring_elements"]
                )
            )

        serialized = json.dumps(self.rubric, sort_keys=True)
        self.assertIsNone(re.search(r"S[0-9]{3}", serialized))
        self.assertNotIn("primary_scores", serialized)
        self.assertNotIn("student_answer", serialized)

    def test_q5_to_q10_element_allocations_and_keyword_credit_are_exact(self) -> None:
        actual = {}
        for question_id in DSAA3071_V1_ELEMENT_CREDIT:
            actual[question_id] = {
                element["id"]: (
                    element["levels"]["demonstrated"],
                    element["levels"]["mentioned_only"],
                )
                for element in self.questions[question_id]["scoring_elements"]
            }

        self.assertEqual(actual, DSAA3071_V1_ELEMENT_CREDIT)

    def test_score_band_boundaries_and_question_assignments_are_exact(self) -> None:
        for question_id, maximum in DSAA3071_V1_BAND_ASSIGNMENTS.items():
            with self.subTest(question_id=question_id):
                question = self.questions[question_id]
                self.assertEqual(question["max_score"], maximum)
                self.assertEqual(
                    question["score_bands"],
                    DSAA3071_V1_SCORE_BANDS[maximum],
                )

    def test_question_level_material_error_caps_are_exact(self) -> None:
        actual = {
            question_id: [
                error["cap"]
                for error in self.questions[question_id]["material_errors"]
            ]
            for question_id in DSAA3071_V1_MATERIAL_ERROR_CAPS
        }
        expected = {
            question_id: [cap]
            for question_id, cap in DSAA3071_V1_MATERIAL_ERROR_CAPS.items()
        }

        self.assertEqual(actual, expected)

    def test_q8_material_error_distinguishes_2n_from_2_to_the_n(self) -> None:
        material_errors = self.questions["Q8"]["material_errors"]

        self.assertEqual(len(material_errors), 1)
        self.assertEqual(
            material_errors[0]["description"],
            "Generates lengths 2n rather than 2^n.",
        )

    def test_q9_has_exactly_three_point_bearing_evidence_families(self) -> None:
        element_ids = [
            element["id"] for element in self.questions["Q9"]["scoring_elements"]
        ]

        self.assertEqual(
            element_ids,
            [
                "equivalent_computation_models",
                "tm_variant_robustness",
                "absence_of_counterexamples",
            ],
        )
        self.assertNotIn("thesis_not_a_theorem", element_ids)

    def test_q10_has_only_local_elements_and_no_question_level_cap(self) -> None:
        question = self.questions["Q10"]
        element_ids = [element["id"] for element in question["scoring_elements"]]

        self.assertEqual(
            element_ids,
            [
                "stay_put_simulation",
                "finite_tape_restriction",
                "one_way_restriction",
            ],
        )
        self.assertEqual(question["material_errors"], [])
