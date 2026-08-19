import json
import hashlib
import unittest
from pathlib import Path

from benchmark.core.rubrics import execution_criterion_points, require_valid_rubric, validate_execution_contract_rubric
from benchmark.core.schema import CourseSpec
from benchmark.core.error_book import audit_public_error_summary


REPO_ROOT = Path(__file__).resolve().parents[3]
COURSE_PATH = REPO_ROOT / "experiments" / "course_specs" / "linearalgebra_quiz1_v2.json"
RUBRIC_PATH = REPO_ROOT / "experiments" / "records" / "linearalgebra-quiz1-v5-3-r2-rubric-candidate" / "rubric_candidate_v3.json"
PLAN_PATH = REPO_ROOT / "experiments" / "records" / "linearalgebra-quiz1-v5-3-r2-rubric-candidate" / "plan.json"
CALIBRATION_CONTRACT_PATH = (
    REPO_ROOT
    / "experiments"
    / "records"
    / "linearalgebra-quiz1-v5-3-r2-rubric-candidate"
    / "human_calibration_contract.json"
)
CALIBRATION_WORKSHEET_PATH = (
    REPO_ROOT
    / "experiments"
    / "records"
    / "linearalgebra-quiz1-v5-3-r2-rubric-candidate"
    / "HUMAN-CALIBRATION.md"
)


class LinearAlgebraV53R2RubricCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.course = CourseSpec.from_json_path(COURSE_PATH)
        self.rubric = json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))

    def test_candidate_is_a_complete_valid_execution_contract(self):
        self.assertEqual(validate_execution_contract_rubric(self.rubric, self.course), [])
        require_valid_rubric(self.rubric, self.course)
        self.assertEqual({question["id"] for question in self.rubric["questions"]}, set(self.course.question_ids))

    def test_objective_leaves_require_only_the_selection(self):
        questions = {question["id"]: question for question in self.rubric["questions"]}
        expected = {"simplification": "not_required", "explanation": "not_required", "working": "not_required"}
        for question_id in ("Q1a", "Q1b", "Q1c", "Q1d", "Q1e"):
            with self.subTest(question_id=question_id):
                self.assertEqual(questions[question_id]["answer_form_requirements"], expected)

    def test_sensitive_calculation_leaves_have_explicit_local_error_units(self):
        q2a = execution_criterion_points(self.rubric, "Q2a")
        q2b = execution_criterion_points(self.rubric, "Q2b")
        q4 = execution_criterion_points(self.rubric, "Q4")
        self.assertEqual(q2a["Q2a.local_sign_accuracy"], 1)
        self.assertEqual(q2a["Q2a.local_arithmetic_accuracy"], 2)
        self.assertEqual(q2b["Q2b.local_term_or_sign_accuracy"], 1)
        self.assertEqual(q2b["Q2b.local_symbolic_combination"], 2)
        self.assertEqual(q4["Q4.tetrahedron_conversion_factor"], 4)
        self.assertEqual(q4["Q4.local_arithmetic_accuracy"], 1)

    def test_answer_only_caps_and_bonus_independence_are_explicit(self):
        questions = {question["id"]: question for question in self.rubric["questions"]}
        for question_id in ("Q2a", "Q2b", "Q3", "Q4"):
            with self.subTest(question_id=question_id):
                self.assertEqual(questions[question_id]["answer_only_cap"], 3)
        self.assertEqual(execution_criterion_points(self.rubric, "Q3bonus"), {"Q3bonus.two_distinct_correct_methods": 10.0})

    def test_candidate_plan_is_public_safe_and_does_not_authorize_a_run(self):
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(audit_public_error_summary(plan), [])
        self.assertEqual(plan["candidate_status"], "development_draft_not_frozen_not_run")
        self.assertFalse(plan["scope"]["heldout_accessed"])
        self.assertEqual(plan["scope"]["model_calls"], 0)

    def test_candidate_plan_hashes_bind_the_r2_artifacts(self):
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        bindings = plan["candidate_bindings"]
        for name in ("course_spec", "rubric", "prompt_template"):
            with self.subTest(name=name):
                path = REPO_ROOT / bindings[name]["path"]
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    bindings[name]["sha256"],
                )
        snapshot = json.loads(
            (REPO_ROOT / bindings["skill"]["snapshot_path"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(snapshot["skill_version_id"], "skill_candidate_v5_3_r2")
        self.assertEqual(snapshot["canonical_hash"], bindings["skill"]["canonical_hash"])

    def test_human_calibration_contract_covers_every_leaf_without_authorizing_a_run(self):
        contract = json.loads(CALIBRATION_CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(audit_public_error_summary(contract), [])
        self.assertEqual(contract["status"], "prepared_pending_course_owner_decisions")
        self.assertTrue(contract["scope"]["development_only"])
        self.assertFalse(contract["scope"]["heldout_accessed"])
        self.assertEqual(contract["scope"]["model_calls"], 0)

        rubric_questions = {question["id"]: question for question in self.rubric["questions"]}
        contract_questions = {
            review["leaf_id"]: review for review in contract["leaf_reviews"]
        }
        self.assertEqual(set(contract_questions), set(rubric_questions))
        for question_id, question in rubric_questions.items():
            with self.subTest(question_id=question_id):
                review = contract_questions[question_id]
                self.assertEqual(review["max_score"], question["max_score"])
                self.assertEqual(
                    {
                        criterion["id"]: criterion["points"]
                        for criterion in review["criteria"]
                    },
                    execution_criterion_points(self.rubric, question_id),
                )
                self.assertTrue(review["course_owner_decision"])
                self.assertEqual(
                    set(review["annotation"]),
                    {"deduction_anchor", "praise_anchor", "uncertainty_rule"},
                )

    def test_human_calibration_package_is_hash_bound_and_surfaces_all_decisions(self):
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        package = plan["human_calibration_package"]
        contract = json.loads(CALIBRATION_CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(package["status"], contract["status"])
        for binding in (package["contract"], package["worksheet"]):
            with self.subTest(path=binding["path"]):
                path = REPO_ROOT / binding["path"]
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), binding["sha256"]
                )

        decision_ids = {
            decision["decision_id"] for decision in contract["high_impact_decisions"]
        }
        self.assertEqual(decision_ids, set(package["required_decisions"]))
        self.assertEqual(
            decision_ids,
            {
                "D01_Q2a_local_sign",
                "D02_Q2b_equivalence",
                "D03_Q3_complete_derivation",
                "D04_Q4_conversion_factor",
                "D05_answer_only_caps",
                "D06_Q3bonus_distinctness",
            },
        )
        worksheet = CALIBRATION_WORKSHEET_PATH.read_text(encoding="utf-8")
        for decision_id in decision_ids:
            with self.subTest(decision_id=decision_id):
                self.assertIn(decision_id.split("_", 1)[0], worksheet)


if __name__ == "__main__":
    unittest.main()
