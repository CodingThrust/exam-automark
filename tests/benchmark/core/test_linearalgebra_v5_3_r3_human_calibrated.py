import copy
import hashlib
import json
import unittest
from pathlib import Path

from benchmark.core.error_book import audit_public_error_summary
from benchmark.core.model_runner import _validate_grade_payload
from benchmark.core.rubrics import (
    execution_criterion_points,
    execution_scoring_gates,
    validate_execution_contract_rubric,
)
from benchmark.core.schema import (
    GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
    CourseSpec,
)


REPO_ROOT = Path(__file__).parents[3]
COURSE_PATH = REPO_ROOT / "experiments/course_specs/linearalgebra_quiz1_v2.json"
RECORD_DIR = (
    REPO_ROOT / "experiments/records/linearalgebra-quiz1-v5-3-r3-human-calibrated"
)
RUBRIC_PATH = RECORD_DIR / "rubric_human_calibrated_v3.json"
DECISIONS_PATH = RECORD_DIR / "calibration_decisions.json"
PLAN_PATH = RECORD_DIR / "plan.json"
PROMPT_PATH = REPO_ROOT / "experiments/prompt_templates/grade_candidate_v5_3_r3.txt"
SNAPSHOT_PATH = REPO_ROOT / "experiments/skill_versions/skill_candidate_v5_3_r3.json"


class LinearAlgebraV53R3HumanCalibratedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.course = CourseSpec.from_json_path(COURSE_PATH)
        self.rubric = json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))

    def test_rubric_is_complete_and_human_calibration_is_public_safe(self):
        self.assertEqual(validate_execution_contract_rubric(self.rubric, self.course), [])
        self.assertEqual(
            {question["id"] for question in self.rubric["questions"]},
            set(self.course.question_ids),
        )
        decisions = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(decisions["status"], "recorded_for_r3_candidate")
        self.assertTrue(decisions["scope"]["development_only"])
        self.assertFalse(decisions["scope"]["heldout_accessed"])
        self.assertEqual(decisions["scope"]["model_calls"], 0)
        self.assertEqual(audit_public_error_summary(decisions), [])

    def test_calibrated_criteria_match_confirmed_score_anchors(self):
        q2a = execution_criterion_points(self.rubric, "Q2a")
        q2b = execution_criterion_points(self.rubric, "Q2b")
        q3 = execution_criterion_points(self.rubric, "Q3")
        q4 = execution_criterion_points(self.rubric, "Q4")
        self.assertEqual(
            q2a,
            {
                "Q2a.determinant_method": 3.0,
                "Q2a.expansion_structure": 3.0,
                "Q2a.signed_core_expansion": 3.0,
                "Q2a.intermediate_term_calculation": 2.0,
                "Q2a.final_numerical_combination": 1.0,
                "Q2a.final_result": 3.0,
            },
        )
        self.assertEqual(sum(q2a.values()) - 4.0, 11.0)
        self.assertEqual(sum(q2a.values()) - 9.0, 6.0)
        self.assertEqual(q2b["Q2b.local_term_or_sign_accuracy"], 1.0)
        self.assertEqual(q2b["Q2b.conditional_simplification"], 3.0)
        self.assertEqual(q2b["Q2b.final_expression"], 3.0)
        self.assertEqual(sum(q2b.values()) - 4.0, 11.0)
        self.assertEqual(
            q3,
            {
                "Q3.unique_solution_principle": 4.0,
                "Q3.equivalent_system_setup": 4.0,
                "Q3.actual_determinant_or_rank_derivation": 7.0,
                "Q3.actual_condition_simplification": 7.0,
                "Q3.final_exceptional_values_and_unique_condition": 3.0,
                "Q3.fundamental_unique_condition_reversal": 25.0,
            },
        )
        self.assertEqual(sum(value for key, value in q3.items() if key.startswith("Q3.") and not key.endswith("reversal")) - 3.0, 22.0)
        self.assertEqual(sum(value for key, value in q3.items() if key in {"Q3.unique_solution_principle", "Q3.equivalent_system_setup"}), 8.0)
        self.assertEqual(q4["Q4.scalar_triple_product_setup"], 4.0)
        self.assertEqual(q4["Q4.common_vertex_vectors"], 5.0)
        self.assertEqual(q4["Q4.original_triple_product_evaluation"], 4.0)
        self.assertEqual(q4["Q4.tetrahedron_conversion_factor"], 2.0)
        self.assertEqual(q4["Q4.final_volume"], 3.0)
        self.assertEqual(sum(q4.values()) - 5.0, 15.0)
        self.assertEqual(4.0 + 1.0 + 2.0, 7.0)

    def test_q3_fundamental_reversal_gate_is_strictly_validated_in_trace_output(self):
        gates = execution_scoring_gates(self.rubric, "Q3")
        self.assertEqual(
            gates,
            {
                "Q3.fundamental_unique_condition_reversal": {
                    "score_cap": 0.0,
                    "deduction_type": "material_method_error",
                }
            },
        )
        payload = {"student_id": "S000", "scores": [], "total": 0}
        for question in self.course.questions:
            row = {
                "question_id": question.id,
                "extracted_evidence": "Synthetic contract validation evidence.",
                "score": question.max_score,
                "evidence": "Synthetic full-credit evidence.",
                "confidence": "high",
                "flags": [],
            }
            if question.id == "Q3":
                row.update(
                    {
                        "score": 0,
                        "evidence": "Synthetic fundamental-method gate evidence.",
                        "deduction_trace": [
                            {
                                "rubric_criterion": "Q3.fundamental_unique_condition_reversal",
                                "observed_evidence_or_missing_or_incorrect_part": "Synthetic fundamental-condition reversal.",
                                "deduction_type": "material_method_error",
                                "points_deducted": 25,
                            }
                        ],
                    }
                )
            payload["scores"].append(row)
        _validate_grade_payload(
            payload,
            "S000",
            self.course,
            output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
            rubric=self.rubric,
        )
        self.assertEqual(payload["total"], 85)

        invalid = copy.deepcopy(payload)
        invalid["scores"][7]["deduction_trace"][0]["deduction_type"] = (
            "incorrect_final_result"
        )
        with self.assertRaisesRegex(ValueError, "scoring-gate deduction_type"):
            _validate_grade_payload(
                invalid,
                "S000",
                self.course,
                output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
                rubric=self.rubric,
            )

    def test_scoring_gate_schema_rejects_missing_trigger(self):
        invalid = copy.deepcopy(self.rubric)
        del invalid["questions"][7]["scoring_gates"][0]["trigger"]
        findings = validate_execution_contract_rubric(invalid, self.course)
        self.assertTrue(any("scoring_gates[0]" in finding for finding in findings))

    def test_r3_bindings_are_hashed_and_model_blocked(self):
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(audit_public_error_summary(plan), [])
        self.assertEqual(
            plan["candidate_status"],
            "human_calibrated_development_candidate_not_frozen_not_run",
        )
        self.assertFalse(plan["scope"]["heldout_accessed"])
        self.assertEqual(plan["scope"]["model_calls"], 0)
        bindings = plan["candidate_bindings"]
        for name, path in (
            ("course_spec", COURSE_PATH),
            ("rubric", RUBRIC_PATH),
            ("course_owner_calibration", DECISIONS_PATH),
            ("prompt_template", PROMPT_PATH),
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    bindings[name]["sha256"],
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["skill_version_id"], "skill_candidate_v5_3_r3")
        self.assertEqual(bindings["skill"]["canonical_hash"], snapshot["canonical_hash"])


if __name__ == "__main__":
    unittest.main()
