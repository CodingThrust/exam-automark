import json
import unittest
from pathlib import Path

from benchmark.core.manifests import ExperimentRecord
from benchmark.core.plans import ExperimentPlan
from benchmark.core.schema import CourseSpec


class ExperimentRecordFileTests(unittest.TestCase):
    def test_physics_pilot_record_is_valid_and_marked_as_pilot(self):
        record = ExperimentRecord.from_json_path(
            Path("experiments/records/physics-week9-pilot/experiment.json")
        )

        self.assertEqual(record.course_id, "physics")
        self.assertEqual(record.assessment_id, "week9")
        self.assertIn("T1-dev-r1", record.prompt_packet_hashes)
        self.assertTrue(any("pilot" in note for note in record.notes))

    def test_planned_multi_course_records_are_valid(self):
        plan_paths = [
            Path("experiments/records/physics-week9-standard-plan/plan.json"),
            Path("experiments/records/physics-week9-candidate-v2-plan/plan.json"),
            Path("experiments/records/DSAA3073-week2-test-plan/plan.json"),
            Path("experiments/records/DSAA3071-week5-test-plan/plan.json"),
            Path("experiments/records/linearalgebra-quiz1-plan/plan.json"),
        ]

        plans = [ExperimentPlan.from_json_path(path) for path in plan_paths]
        plans_by_id = {plan.experiment_id: plan for plan in plans}
        physics_baseline = plans_by_id["physics-week9-standard-plan"]
        physics_candidate = plans_by_id["physics-week9-candidate-v2-plan"]

        self.assertEqual(
            {plan.course_id for plan in plans},
            {"physics", "DSAA3073", "DSAA3071", "linearalgebra"},
        )
        self.assertEqual(physics_baseline.status, "packets_built")
        self.assertEqual(
            {packet.packet_id for packet in physics_baseline.built_packets},
            {"T1-dev-r1", "T1-test-r1", "G1-dev-r1", "G1-test-r1"},
        )
        self.assertTrue(
            all(
                packet.audit_status == "passed"
                for packet in physics_baseline.built_packets
            )
        )
        self.assertTrue(
            all(
                packet.prompt_path.endswith("prompt.txt")
                for packet in physics_baseline.built_packets
            )
        )
        self.assertEqual(physics_candidate.status, "packets_built")
        self.assertEqual(physics_candidate.skill_version_id, "skill_candidate_v2")
        self.assertIn("grade_candidate_v2", physics_candidate.prompt_template_hashes)
        self.assertEqual(
            {
                packet.prompt_template_id
                for packet in physics_candidate.planned_packets
                if packet.task == "grade"
            },
            {"grade_candidate_v2"},
        )
        self.assertTrue(
            all(
                packet.audit_status == "passed"
                for packet in physics_candidate.built_packets
            )
        )
        self.assertTrue(all(plan.planned_packets for plan in plans))
        self.assertTrue(all("agents" in plan.skill_hashes for plan in plans))
        for plan in plans:
            if plan.experiment_id == "physics-week9-candidate-v2-plan":
                self.assertEqual(plan.skill_version_id, "skill_candidate_v2")
                self.assertIn("grade_candidate_v2", plan.prompt_template_hashes)
            else:
                self.assertEqual(plan.skill_version_id, "skill_baseline_v1")
                self.assertIn("grade_standard_v1", plan.prompt_template_hashes)

    def test_course_specs_are_loadable(self):
        spec_paths = [
            Path("experiments/course_specs/physics_week9.json"),
            Path("experiments/course_specs/DSAA3073_week2_test.json"),
            Path("experiments/course_specs/DSAA3071_week5_test.json"),
            Path("experiments/course_specs/linearalgebra_quiz1.json"),
        ]

        specs = [CourseSpec.from_json_path(path) for path in spec_paths]

        self.assertEqual(specs[0].max_total, 30.0)
        self.assertEqual(
            {spec.course_id for spec in specs},
            {"physics", "DSAA3073", "DSAA3071", "linearalgebra"},
        )

    def test_physics_readiness_report_records_pre_run_gate(self):
        report = json.loads(
            Path("experiments/records/physics-week9-run-readiness.json").read_text(
                encoding="utf-8"
            )
        )
        failed_checks = [
            check["id"] for check in report["checks"] if check["status"] == "failed"
        ]

        self.assertEqual(report["report_type"], "run_readiness")
        self.assertEqual(report["model_run_status"], "not_started")
        self.assertEqual(
            report["baseline_plan_path"],
            "experiments/records/physics-week9-standard-plan/plan.json",
        )
        self.assertEqual(
            report["candidate_plan_path"],
            "experiments/records/physics-week9-candidate-v2-plan/plan.json",
        )
        self.assertEqual(report["status"], "not_ready" if failed_checks else "ready")
        self.assertIn("grade_prompt_differs", {check["id"] for check in report["checks"]})


if __name__ == "__main__":
    unittest.main()
