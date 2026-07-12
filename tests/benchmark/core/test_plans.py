import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.inventory import write_data_inventory
from benchmark.core.plans import (
    BuiltPacket,
    ExperimentPlan,
    build_standard_experiment_plan,
    record_built_packet,
    write_experiment_plan,
)


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class ExperimentPlanTests(unittest.TestCase):
    def test_builds_standard_plan_from_inventory_course_and_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_course = root / "Data" / "dsaa3073"
            data_course.mkdir(parents=True)
            (data_course / "exam.pdf").write_bytes(b"exam")
            inventory_path = root / "inventory.json"
            write_data_inventory(root / "Data", "dsaa3073", inventory_path)

            plan = build_standard_experiment_plan(
                experiment_id="dsaa3073-week1-planned",
                status="planned",
                git_branch="codex/repro-experiment-framework",
                git_commit="abc1234",
                inventory_path=inventory_path,
                course_spec_path=FIXTURES / "course_dsaa3073_hw1.json",
                skill_snapshot_path=Path(
                    "experiments/skill_versions/skill_baseline_v1.json"
                ),
                transcribe_prompt_path=FIXTURES / "transcribe_prompt.txt",
                grade_prompt_path=FIXTURES / "grade_prompt.txt",
                notes=("synthetic plan",),
            )

        self.assertEqual(plan.course_id, "dsaa3073")
        self.assertEqual(plan.status, "planned")
        self.assertEqual(plan.skill_version_id, "skill_baseline_v1")
        self.assertIn("agents", plan.skill_hashes)
        self.assertIn("transcribe_standard_v1", plan.prompt_template_hashes)
        self.assertIn("grade_standard_v1", plan.prompt_template_hashes)
        self.assertEqual(len(plan.planned_packets), 4)

    def test_prompt_template_hashes_normalize_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_course = root / "Data" / "dsaa3073"
            data_course.mkdir(parents=True)
            (data_course / "exam.pdf").write_bytes(b"exam")
            inventory_path = root / "inventory.json"
            write_data_inventory(root / "Data", "dsaa3073", inventory_path)
            transcribe_lf = root / "transcribe_lf.txt"
            transcribe_crlf = root / "transcribe_crlf.txt"
            grade_lf = root / "grade_lf.txt"
            grade_crlf = root / "grade_crlf.txt"
            transcribe_lf.write_bytes(b"Line one\nLine two\n")
            transcribe_crlf.write_bytes(b"Line one\r\nLine two\r\n")
            grade_lf.write_bytes(b"Grade one\nGrade two\n")
            grade_crlf.write_bytes(b"Grade one\r\nGrade two\r\n")

            plan_lf = build_standard_experiment_plan(
                experiment_id="dsaa3073-week1-planned",
                status="planned",
                git_branch="codex/repro-experiment-framework",
                git_commit="abc1234",
                inventory_path=inventory_path,
                course_spec_path=FIXTURES / "course_dsaa3073_hw1.json",
                skill_snapshot_path=Path(
                    "experiments/skill_versions/skill_baseline_v1.json"
                ),
                transcribe_prompt_path=transcribe_lf,
                grade_prompt_path=grade_lf,
            )
            plan_crlf = build_standard_experiment_plan(
                experiment_id="dsaa3073-week1-planned",
                status="planned",
                git_branch="codex/repro-experiment-framework",
                git_commit="abc1234",
                inventory_path=inventory_path,
                course_spec_path=FIXTURES / "course_dsaa3073_hw1.json",
                skill_snapshot_path=Path(
                    "experiments/skill_versions/skill_baseline_v1.json"
                ),
                transcribe_prompt_path=transcribe_crlf,
                grade_prompt_path=grade_crlf,
            )

        self.assertEqual(
            plan_lf.prompt_template_hashes,
            plan_crlf.prompt_template_hashes,
        )

    def test_builds_plan_with_custom_grade_template_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_course = root / "Data" / "dsaa3073"
            data_course.mkdir(parents=True)
            (data_course / "exam.pdf").write_bytes(b"exam")
            inventory_path = root / "inventory.json"
            write_data_inventory(root / "Data", "dsaa3073", inventory_path)

            plan = build_standard_experiment_plan(
                experiment_id="dsaa3073-week1-candidate",
                status="planned",
                git_branch="codex/repro-experiment-framework",
                git_commit="abc1234",
                inventory_path=inventory_path,
                course_spec_path=FIXTURES / "course_dsaa3073_hw1.json",
                skill_snapshot_path=Path(
                    "experiments/skill_versions/skill_candidate_v2.json"
                ),
                transcribe_prompt_path=FIXTURES / "transcribe_prompt.txt",
                grade_prompt_path=FIXTURES / "grade_prompt.txt",
                grade_template_id="grade_candidate_v2",
            )

        self.assertIn("grade_candidate_v2", plan.prompt_template_hashes)
        self.assertNotIn("grade_standard_v1", plan.prompt_template_hashes)
        self.assertEqual(
            plan.planned_packets[2].prompt_template_id,
            "grade_candidate_v2",
        )

    def test_writes_and_reads_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "assessment_id": "hw1",
                "course_id": "dsaa3073",
                "course_spec_path": "experiments/course_specs/dsaa3073_hw1.json",
                "data_inventory_path": "experiments/data_inventory/dsaa3073.json",
                "data_snapshot_hash": "a" * 64,
                "experiment_id": "dsaa3073-hw1-planned",
                "git_branch": "codex/repro-experiment-framework",
                "git_commit": "abc1234",
                "notes": ["synthetic only"],
                "skill_hashes": {
                    "agents": "c" * 64
                },
                "skill_source_paths": {
                    "agents": ".agents/skills/grade-homework/SKILL.md"
                },
                "skill_version_id": "skill_baseline_v1",
                "planned_packets": [
                    {
                        "condition": "T1",
                        "packet_id": "T1-dev-r1",
                        "prompt_template_id": "transcribe_standard_v1",
                        "split": "development",
                        "task": "transcribe",
                    }
                ],
                "prompt_template_hashes": {
                    "transcribe_standard_v1": "b" * 64
                },
                "schema_version": 1,
                "status": "planned",
            }
            plan = ExperimentPlan.from_dict(payload)
            plan_path = root / "plan.json"

            write_experiment_plan(plan, plan_path)
            loaded = ExperimentPlan.from_json_path(plan_path)

        self.assertEqual(loaded.experiment_id, "dsaa3073-hw1-planned")
        self.assertEqual(loaded.planned_packets[0].task, "transcribe")

    def test_plan_can_record_an_audited_built_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "assessment_id": "hw1",
                "course_id": "dsaa3073",
                "course_spec_path": "experiments/course_specs/dsaa3073_hw1.json",
                "data_inventory_path": "experiments/data_inventory/dsaa3073.json",
                "data_snapshot_hash": "a" * 64,
                "experiment_id": "dsaa3073-hw1-planned",
                "git_branch": "codex/repro-experiment-framework",
                "git_commit": "abc1234",
                "notes": ["synthetic only"],
                "skill_hashes": {
                    "agents": "c" * 64
                },
                "skill_source_paths": {
                    "agents": ".agents/skills/grade-homework/SKILL.md"
                },
                "skill_version_id": "skill_baseline_v1",
                "planned_packets": [
                    {
                        "condition": "T1",
                        "packet_id": "T1-dev-r1",
                        "prompt_template_id": "transcribe_standard_v1",
                        "split": "development",
                        "task": "transcribe",
                    }
                ],
                "prompt_template_hashes": {
                    "transcribe_standard_v1": "b" * 64
                },
                "schema_version": 1,
                "status": "planned",
            }
            packet = root / "packets" / "T1-dev-r1"
            packet.mkdir(parents=True)
            (packet / "prompt.txt").write_text("transcribe anonymous work\n")
            (packet / "manifest.json").write_text(
                json.dumps(
                    {
                        "packet_id": "T1-dev-r1",
                        "condition": "T1",
                        "task": "transcribe",
                    }
                ),
                encoding="utf-8",
            )

            updated = record_built_packet(ExperimentPlan.from_dict(payload), packet)

        self.assertEqual(len(updated.built_packets), 1)
        self.assertEqual(updated.built_packets[0].packet_id, "T1-dev-r1")
        self.assertEqual(updated.built_packets[0].audit_status, "passed")
        self.assertTrue(updated.built_packets[0].prompt_path.endswith("prompt.txt"))

    def test_built_packet_requires_a_successful_audit(self):
        with self.assertRaisesRegex(ValueError, "audit-passed"):
            BuiltPacket(
                packet_id="T1-dev-r1",
                condition="T1",
                task="transcribe",
                split="development",
                packet_path="packets/T1-dev-r1",
                prompt_path="packets/T1-dev-r1/prompt.txt",
                manifest_path="packets/T1-dev-r1/manifest.json",
                packet_hash="d" * 64,
                audit_status="failed",
            )

    def test_plan_requires_real_template_hashes_for_packets(self):
        payload = {
            "assessment_id": "hw1",
            "course_id": "dsaa3073",
            "course_spec_path": "experiments/course_specs/dsaa3073_hw1.json",
            "data_inventory_path": "experiments/data_inventory/dsaa3073.json",
            "data_snapshot_hash": "a" * 64,
            "experiment_id": "dsaa3073-hw1-planned",
            "git_branch": "codex/repro-experiment-framework",
            "git_commit": "abc1234",
            "skill_hashes": {
                "agents": "c" * 64
            },
            "skill_source_paths": {
                "agents": ".agents/skills/grade-homework/SKILL.md"
            },
            "skill_version_id": "skill_baseline_v1",
            "planned_packets": [
                {
                    "condition": "T1",
                    "packet_id": "T1-dev-r1",
                    "prompt_template_id": "missing_template",
                    "split": "development",
                    "task": "transcribe",
                }
            ],
            "prompt_template_hashes": {
                "transcribe_standard_v1": "b" * 64
            },
            "status": "planned",
        }

        with self.assertRaisesRegex(ValueError, "template missing"):
            ExperimentPlan.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
