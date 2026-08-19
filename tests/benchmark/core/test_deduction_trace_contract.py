import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.error_book import audit_public_error_summary
from benchmark.core.error_book_iteration import validate_error_book_registry
from benchmark.core.headless_runner import HeadlessPacketRunConfig, run_headless_packet
from benchmark.core.model_runner import (
    ModelPacketRunConfig,
    _validate_grade_payload,
    run_model_packet,
)
from benchmark.core.packets import (
    PromptPacketSpec,
    build_prompt_packet,
    grading_output_schema,
    validate_packet_output_contract,
)
from benchmark.core.schema import (
    GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
    CourseSpec,
    QuestionSpec,
)


class DeductionTraceContractTests(unittest.TestCase):
    def _course(self) -> CourseSpec:
        return CourseSpec(
            course_id="synthetic",
            assessment_id="leaf_contract",
            questions=(
                QuestionSpec("Q1a", 5, score_step=1, parent_question_id="Q1"),
                QuestionSpec("Q1b", 5, score_step=1, parent_question_id="Q1"),
                QuestionSpec("Q2", 10, score_step=1),
                QuestionSpec(
                    "Q2bonus",
                    10,
                    score_step=1,
                    parent_question_id="Q2",
                    is_bonus=True,
                ),
            ),
            base_total_points=20,
            final_score_cap=20,
        )

    @staticmethod
    def _trace(points: int = 1, *, observation: str = "Required evidence is absent."):
        return [
            {
                "rubric_criterion": "required criterion",
                "observed_evidence_or_missing_or_incorrect_part": observation,
                "deduction_type": "missing_required_evidence",
                "points_deducted": points,
            }
        ]

    def _payload(self) -> dict:
        return {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "Q1a",
                    "extracted_evidence": "Type: objective_selection; selected T.",
                    "score": 5,
                    "evidence": "The required selection is visible.",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q1b",
                    "extracted_evidence": "Type: objective_selection; selection is blank.",
                    "score": 4,
                    "evidence": "One required criterion is not demonstrated.",
                    "confidence": "high",
                    "flags": [],
                    "deduction_trace": self._trace(),
                },
                {
                    "question_id": "Q2",
                    "extracted_evidence": "Type: calculation; valid setup and result.",
                    "score": 10,
                    "evidence": "All required evidence is present.",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q2bonus",
                    "extracted_evidence": "Type: calculation; bonus requirement is absent.",
                    "score": 0,
                    "evidence": "The independent bonus criterion is not demonstrated.",
                    "confidence": "high",
                    "flags": [],
                    "deduction_trace": self._trace(10),
                },
            ],
            "total": 0,
        }

    def _validate(self, payload: dict) -> None:
        _validate_grade_payload(
            payload,
            "S001",
            self._course(),
            output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
        )

    def test_full_credit_leaf_may_omit_trace_and_leaf_deductions_are_independent(self):
        payload = self._payload()

        self._validate(payload)

        self.assertNotIn("deduction_trace", payload["scores"][0])
        self.assertEqual(payload["total"], 19)

    def test_rejects_nonfull_leaf_without_trace(self):
        payload = self._payload()
        del payload["scores"][1]["deduction_trace"]

        with self.assertRaisesRegex(ValueError, "Q1b non-full score requires deduction_trace"):
            self._validate(payload)

    def test_rejects_deduction_sum_that_does_not_match_one_leaf(self):
        payload = self._payload()
        payload["scores"][1]["deduction_trace"] = self._trace(2)

        with self.assertRaisesRegex(ValueError, "Q1b deduction total"):
            self._validate(payload)

    def test_rejects_unsafe_trace_text(self):
        unsafe_observations = (
            "See D:\\private\\answer.png.",
            "student_id: S001",
            "Email student@example.edu for clarification.",
        )
        for observation in unsafe_observations:
            with self.subTest(observation=observation):
                payload = self._payload()
                payload["scores"][1]["deduction_trace"] = self._trace(
                    observation=observation
                )
                with self.assertRaisesRegex(ValueError, "private|identity|student"):
                    self._validate(payload)

    def test_rejects_flagged_or_low_confidence_leaf_without_attention_note(self):
        payload = self._payload()
        payload["scores"][0]["flags"] = ["page_order_uncertain"]

        with self.assertRaisesRegex(ValueError, "attention_note"):
            self._validate(payload)

        payload["scores"][0]["attention_note"] = "Review locator ambiguity."
        self._validate(payload)

    def test_schema_and_packet_bind_deduction_trace_contract(self):
        course = self._course()
        schema = grading_output_schema(
            course, GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1
        )
        score_properties = schema["properties"]["scores"]["items"]["properties"]
        self.assertIn("deduction_trace", score_properties)
        self.assertIn("attention_note", score_properties)
        self.assertEqual(
            score_properties["deduction_trace"]["items"]["required"],
            [
                "rubric_criterion",
                "observed_evidence_or_missing_or_incorrect_part",
                "deduction_type",
                "points_deducted",
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "inputs" / "S001"
            input_dir.mkdir(parents=True)
            (input_dir / "answer.txt").write_text("synthetic work", encoding="utf-8")
            result = build_prompt_packet(
                PromptPacketSpec(
                    course=course,
                    packet_id="G1-dev-v53",
                    condition="G1",
                    task="grade",
                    prompt_text="Grade synthetic work.",
                    student_ids=("S001",),
                    input_root=root / "inputs",
                    output_root=root / "packets",
                    rubric={"rubric_version": "synthetic_v1", "questions": []},
                    grading_output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
                )
            )
            manifest = json.loads(
                (result.packet_path / "manifest.json").read_text(encoding="utf-8")
            )

            contract = validate_packet_output_contract(
                result.packet_path, manifest, course, "grade"
            )

            model_run = run_model_packet(
                ModelPacketRunConfig(
                    provider="kimi",
                    model="synthetic-dry-run",
                    input_mode="text-only",
                    packet=result.packet_path,
                    output=root / "model-run",
                    dry_run=True,
                    run_commit="abc1234",
                )
            )
            headless_run = run_headless_packet(
                HeadlessPacketRunConfig(
                    engine="codex",
                    model="synthetic-dry-run",
                    input_mode="text-only",
                    packet=result.packet_path,
                    output=root / "headless-run",
                    dry_run=True,
                    run_commit="abc1234",
                )
            )
            model_metadata = json.loads(
                (root / "model-run" / "run-metadata.json").read_text(
                    encoding="utf-8"
                )
            )
            headless_metadata = json.loads(
                (root / "headless-run" / "run-metadata.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(contract, GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1)
        self.assertEqual(model_run["validation_status"], "passed")
        self.assertEqual(headless_run["validation_status"], "passed")
        for metadata in (model_metadata, headless_metadata):
            self.assertEqual(
                metadata["output_contract"],
                GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
            )
            self.assertEqual(
                metadata["output_schema_hash"], manifest["output_schema_hash"]
            )

    def test_public_v5_3_plan_is_privacy_safe_and_registry_tracks_pending_contract(self):
        repo_root = Path(__file__).parents[3]
        plan_path = (
            repo_root
            / "experiments"
            / "records"
            / "candidate-v5_3-deduction-trace-plan"
            / "plan.json"
        )
        registry_path = (
            repo_root
            / "experiments"
            / "records"
            / "grading-skill-error-book-registry.json"
        )
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        registry = json.loads(registry_path.read_text(encoding="utf-8"))

        self.assertEqual(audit_public_error_summary(plan), [])
        self.assertEqual(plan["evaluation_status"], "not_run")
        self.assertFalse(plan["heldout_accessed"])
        self.assertEqual(registry["active_skill_version_id"], "skill_candidate_v5_3_r3")
        self.assertEqual(registry["entries"][-1]["evaluation_status"], "pending")
        self.assertEqual(
            validate_error_book_registry(
                repo_root=repo_root, registry_path=registry_path
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
