import copy
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.error_book import audit_public_error_summary
from benchmark.core.model_runner import _validate_grade_payload
from benchmark.core.packets import PromptPacketSpec, build_prompt_packet
from benchmark.core.rubrics import (
    EXECUTION_GLOBAL_RULES,
    execution_criterion_ids,
    require_valid_rubric,
    validate_execution_contract_rubric,
)
from benchmark.core.schema import (
    GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
    CourseSpec,
    QuestionSpec,
)


def _course() -> CourseSpec:
    return CourseSpec(
        course_id="synthetic",
        assessment_id="execution_contract",
        questions=(
            QuestionSpec("Q1", 5, score_step=1),
            QuestionSpec("Q2", 10, score_step=1),
        ),
        base_total_points=15,
        final_score_cap=15,
    )


def _rubric() -> dict:
    return {
        "rubric_format": "execution_contract_v1",
        "rubric_version": "synthetic_v1",
        "global_scoring_rules": EXECUTION_GLOBAL_RULES,
        "questions": [
            {
                "id": "Q1",
                "max_score": 5,
                "question_type": "true_false",
                "answer_form_requirements": {
                    "simplification": "not_required",
                    "explanation": "not_required",
                    "working": "not_required",
                },
                "criteria": [
                    {
                        "id": "Q1.selection",
                        "points": 5,
                        "award_condition": "The selected response is T.",
                        "withhold_condition": "The selection is blank, ambiguous, or not T.",
                    }
                ],
            },
            {
                "id": "Q2",
                "max_score": 10,
                "question_type": "calculation",
                "answer_form_requirements": {
                    "simplification": "required",
                    "explanation": "not_required",
                    "working": "answer_only_cap",
                },
                "answer_only_cap": 3,
                "criteria": [
                    {
                        "id": "Q2.setup",
                        "points": 3,
                        "award_condition": "A valid setup uses the stated quantities.",
                        "withhold_condition": "No valid setup is shown.",
                    },
                    {
                        "id": "Q2.simplification",
                        "points": 4,
                        "award_condition": "The expression is simplified to the required form.",
                        "withhold_condition": "The required simplification is absent or incorrect.",
                    },
                    {
                        "id": "Q2.final_result",
                        "points": 3,
                        "award_condition": "The final result is correct.",
                        "withhold_condition": "The final result is missing or incorrect.",
                    },
                ],
            },
        ],
    }


class ExecutionContractRubricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.course = _course()
        self.rubric = _rubric()

    def test_detailed_rubric_is_valid_and_exposes_leaf_criterion_ids(self):
        self.assertEqual(
            validate_execution_contract_rubric(self.rubric, self.course), []
        )
        self.assertEqual(
            execution_criterion_ids(self.rubric, "Q2"),
            {"Q2.setup", "Q2.simplification", "Q2.final_result"},
        )

    def test_rejects_vague_conditions_missing_answer_form_and_point_mismatch(self):
        rubric = copy.deepcopy(self.rubric)
        rubric["questions"][1]["criteria"][1]["award_condition"] = (
            "Normally simplify the expression."
        )
        rubric["questions"][1]["criteria"][2]["points"] = 2
        del rubric["questions"][0]["answer_form_requirements"]["simplification"]

        errors = validate_execution_contract_rubric(rubric, self.course)

        self.assertIn(
            "Q2 criteria[1] award_condition must avoid unresolved discretionary language",
            errors,
        )
        self.assertIn("Q2 criterion points must total 10.0", errors)
        self.assertIn(
            "Q1 answer_form_requirements must define exactly: simplification, explanation, working",
            errors,
        )

    def test_rejects_extra_content_policy_that_can_penalize_irrelevant_work(self):
        rubric = copy.deepcopy(self.rubric)
        rubric["global_scoring_rules"] = dict(EXECUTION_GLOBAL_RULES)
        rubric["global_scoring_rules"]["irrelevant_extra_content"] = "penalize"

        self.assertIn(
            "execution rubric global_scoring_rules must exactly declare the shared scoring rules",
            validate_execution_contract_rubric(rubric, self.course),
        )

    def test_non_full_trace_must_reference_a_declared_leaf_criterion(self):
        payload = {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "Q1",
                    "extracted_evidence": "Selected T.",
                    "score": 5,
                    "evidence": "The required selection is visible.",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q2",
                    "extracted_evidence": "A valid setup is visible; final result is wrong.",
                    "score": 7,
                    "evidence": "Setup and simplification are correct.",
                    "confidence": "high",
                    "flags": [],
                    "deduction_trace": [
                        {
                            "rubric_criterion": "Q2.final_result",
                            "observed_evidence_or_missing_or_incorrect_part": "The final result is incorrect.",
                            "deduction_type": "incorrect_final_result",
                            "points_deducted": 3,
                        }
                    ],
                },
            ],
            "total": 12,
        }

        _validate_grade_payload(
            payload,
            "S001",
            self.course,
            output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
            rubric=self.rubric,
        )
        payload["scores"][1]["deduction_trace"][0]["rubric_criterion"] = "Q2.other"
        with self.assertRaisesRegex(ValueError, "declared criterion ID"):
            _validate_grade_payload(
                payload,
                "S001",
                self.course,
                output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
                rubric=self.rubric,
            )

    def test_invalid_execution_rubric_blocks_packet_creation(self):
        rubric = copy.deepcopy(self.rubric)
        rubric["questions"][1]["criteria"][0]["points"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "invalid execution-contract rubric"):
                build_prompt_packet(
                    PromptPacketSpec(
                        course=self.course,
                        packet_id="G1-dev-r1",
                        condition="G1",
                        task="grade",
                        prompt_text="Grade synthetic work.",
                        student_ids=("S001",),
                        input_root=root / "inputs",
                        output_root=root / "packets",
                        rubric=rubric,
                    )
                )
            self.assertFalse((root / "packets" / "G1-dev-r1").exists())

    def test_trace_allows_bounded_partial_deduction_for_a_declared_criterion(self):
        payload = {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "Q1",
                    "extracted_evidence": "Selected T.",
                    "score": 5,
                    "evidence": "The required selection is visible.",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q2",
                    "extracted_evidence": "A valid setup is visible; final result is wrong.",
                    "score": 8,
                    "evidence": "Setup and simplification are correct.",
                    "confidence": "high",
                    "flags": [],
                    "deduction_trace": [
                        {
                            "rubric_criterion": "Q2.final_result",
                            "observed_evidence_or_missing_or_incorrect_part": "The final result is incorrect.",
                            "deduction_type": "incorrect_final_result",
                            "points_deducted": 2,
                        }
                    ],
                },
            ],
            "total": 13,
        }

        _validate_grade_payload(
            payload,
            "S001",
            self.course,
            output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
            rubric=self.rubric,
        )

    def test_trace_rejects_partial_deduction_above_declared_criterion_cap(self):
        payload = {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "Q1",
                    "extracted_evidence": "Selected T.",
                    "score": 5,
                    "evidence": "The required selection is visible.",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q2",
                    "extracted_evidence": "A valid setup is visible; final result is wrong.",
                    "score": 6,
                    "evidence": "Setup and simplification are correct.",
                    "confidence": "high",
                    "flags": [],
                    "deduction_trace": [
                        {
                            "rubric_criterion": "Q2.final_result",
                            "observed_evidence_or_missing_or_incorrect_part": "The final result is incorrect.",
                            "deduction_type": "incorrect_final_result",
                            "points_deducted": 4,
                        }
                    ],
                },
            ],
            "total": 11,
        }

        with self.assertRaisesRegex(ValueError, "must not exceed the declared criterion points"):
            _validate_grade_payload(
                payload,
                "S001",
                self.course,
                output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
                rubric=self.rubric,
            )

    def test_unambiguous_bounded_trace_arithmetic_is_normalized_without_score_change(self):
        payload = {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "Q1",
                    "extracted_evidence": "Selected T.",
                    "score": 5,
                    "evidence": "The required selection is visible.",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q2",
                    "extracted_evidence": "A valid setup is visible; final result is partly incorrect.",
                    "score": 7,
                    "evidence": "Setup and simplification are correct.",
                    "confidence": "high",
                    "flags": [],
                    "deduction_trace": [
                        {
                            "rubric_criterion": "Q2.final_result",
                            "observed_evidence_or_missing_or_incorrect_part": "The final result is partly incorrect.",
                            "deduction_type": "incorrect_final_result",
                            "points_deducted": 2,
                        }
                    ],
                },
            ],
            "total": 12,
        }

        normalizations = _validate_grade_payload(
            payload,
            "S001",
            self.course,
            output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
            rubric=self.rubric,
        )

        self.assertEqual(payload["scores"][1]["score"], 7)
        self.assertEqual(payload["scores"][1]["deduction_trace"][0]["points_deducted"], 3)
        self.assertEqual(
            normalizations,
            [
                {
                    "question_id": "Q2",
                    "kind": "bounded_trace_arithmetic",
                    "entry_index": 0,
                }
            ],
        )

    def test_ambiguous_bounded_trace_arithmetic_still_requires_a_model_retry(self):
        payload = {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "Q1",
                    "extracted_evidence": "Selected T.",
                    "score": 5,
                    "evidence": "The required selection is visible.",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q2",
                    "extracted_evidence": "Two criteria are partly incorrect.",
                    "score": 5,
                    "evidence": "Two deductions are recorded.",
                    "confidence": "high",
                    "flags": [],
                    "deduction_trace": [
                        {
                            "rubric_criterion": "Q2.setup",
                            "observed_evidence_or_missing_or_incorrect_part": "The setup is partly incomplete.",
                            "deduction_type": "missing_required_evidence",
                            "points_deducted": 1,
                        },
                        {
                            "rubric_criterion": "Q2.simplification",
                            "observed_evidence_or_missing_or_incorrect_part": "The simplification is partly incomplete.",
                            "deduction_type": "missing_required_evidence",
                            "points_deducted": 3,
                        },
                    ],
                },
            ],
            "total": 10,
        }

        with self.assertRaisesRegex(ValueError, "Q2 deduction total"):
            _validate_grade_payload(
                payload,
                "S001",
                self.course,
                output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
                rubric=self.rubric,
            )

    def test_public_contract_plan_is_aggregate_only_and_model_blocked(self):
        plan = json.loads(
            Path(
                "experiments/records/rubric-execution-contract-v1/plan.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(audit_public_error_summary(plan), [])
        self.assertEqual(plan["evaluation_status"], "not_run")
        self.assertFalse(plan["heldout_accessed"])


if __name__ == "__main__":
    unittest.main()
