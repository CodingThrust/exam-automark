import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.model_policy import (
    bind_model_release_policy,
    load_model_release_policy,
    validate_model_release_policy,
)
from benchmark.core.model_runner import ModelPacketRunConfig, run_model_packet
from benchmark.core.packets import PromptPacketSpec, build_prompt_packet
from benchmark.core.schema import CourseSpec, QuestionSpec


POLICY_PATH = Path("experiments/model_policies/deepseek_v4_release_policy.json")


class ModelReleasePolicyTests(unittest.TestCase):
    @staticmethod
    def _packet(root: Path) -> Path:
        input_root = root / "inputs"
        student_dir = input_root / "S001"
        student_dir.mkdir(parents=True)
        (student_dir / "answer.txt").write_text("synthetic work", encoding="utf-8")
        course = CourseSpec(
            course_id="synthetic",
            assessment_id="model_policy",
            questions=(QuestionSpec("Q1", 5, score_step=1),),
        )
        return build_prompt_packet(
            PromptPacketSpec(
                course=course,
                packet_id="G1-dev-r1",
                condition="G1",
                task="grade",
                prompt_text="Grade synthetic work.",
                student_ids=("S001",),
                input_root=input_root,
                output_root=root / "packets",
                rubric={"questions": []},
            )
        ).packet_path

    def test_course_owner_policy_uses_flash_as_the_current_default(self):
        policy = load_model_release_policy(POLICY_PATH)

        self.assertEqual(policy["provider"], "deepseek")
        self.assertTrue(policy["models"]["deepseek-v4-flash"]["default_for_new_runs"])
        self.assertEqual(
            policy["models"]["deepseek-v4-pro"]["release_channel"],
            "provisional",
        )

    def test_stable_flash_binds_without_a_provisional_override(self):
        binding = bind_model_release_policy(
            policy_path=POLICY_PATH,
            provider="deepseek",
            model="deepseek-v4-flash",
        )

        self.assertEqual(binding["model_release_channel"], "stable")
        self.assertEqual(len(binding["model_release_policy_sha256"]), 64)

    def test_provisional_pro_requires_explicit_acknowledgement(self):
        with self.assertRaisesRegex(ValueError, "allow-provisional-model"):
            bind_model_release_policy(
                policy_path=POLICY_PATH,
                provider="deepseek",
                model="deepseek-v4-pro",
            )

        binding = bind_model_release_policy(
            policy_path=POLICY_PATH,
            provider="deepseek",
            model="deepseek-v4-pro",
            allow_provisional=True,
        )
        self.assertEqual(binding["model_release_channel"], "provisional")

    def test_policy_requires_one_stable_default_and_retest_trigger(self):
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        policy["models"]["deepseek-v4-flash"]["default_for_new_runs"] = False
        del policy["models"]["deepseek-v4-pro"]["retest_required_on"]

        errors = validate_model_release_policy(policy)

        self.assertIn(
            "model policy must declare exactly one default_for_new_runs model",
            errors,
        )
        self.assertIn(
            "model policy model deepseek-v4-pro provisional model requires retest_required_on",
            errors,
        )

    def test_invalid_policy_file_is_rejected_before_a_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "JSON object"):
                load_model_release_policy(path)

    def test_runner_records_policy_binding_and_rejects_unacknowledged_provisional(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self._packet(root)
            result = run_model_packet(
                ModelPacketRunConfig(
                    provider="deepseek",
                    model="deepseek-v4-flash",
                    input_mode="text-only",
                    packet=packet,
                    output=root / "flash-run",
                    dry_run=True,
                    model_release_policy=POLICY_PATH,
                    run_commit="abc1234",
                )
            )
            metadata = json.loads(
                (root / "flash-run" / "run-metadata.json").read_text(
                    encoding="utf-8"
                )
            )
            command_argv = json.loads(
                (root / "flash-run" / "command.argv.json").read_text(
                    encoding="utf-8"
                )
            )
            with self.assertRaisesRegex(ValueError, "allow-provisional-model"):
                run_model_packet(
                    ModelPacketRunConfig(
                        provider="deepseek",
                        model="deepseek-v4-pro",
                        input_mode="text-only",
                        packet=packet,
                        output=root / "pro-run",
                        dry_run=True,
                        model_release_policy=POLICY_PATH,
                    )
                )

        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual(metadata["model_release_channel"], "stable")
        self.assertEqual(
            metadata["model_release_policy_id"],
            "deepseek_v4_release_policy_2026_08",
        )
        self.assertIn("--model-release-policy", command_argv)


if __name__ == "__main__":
    unittest.main()
