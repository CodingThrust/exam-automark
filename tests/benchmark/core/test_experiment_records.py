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
            elif plan.experiment_id == "DSAA3071-week5-test-plan":
                self.assertEqual(plan.skill_version_id, "skill_baseline_v1")
                self.assertIn(
                    "grade_standard_v1_strict_schema",
                    plan.prompt_template_hashes,
                )
            elif plan.experiment_id == "linearalgebra-quiz1-plan":
                self.assertEqual(plan.skill_version_id, "skill_candidate_v5_1")
                self.assertIn("grade_candidate_v5_1", plan.prompt_template_hashes)
                self.assertEqual(plan.status, "cohort_scoped")
                self.assertEqual(
                    {
                        packet.prompt_template_id
                        for packet in plan.planned_packets
                        if packet.task == "grade"
                    },
                    {"grade_candidate_v5_1"},
                )
            else:
                self.assertEqual(plan.skill_version_id, "skill_baseline_v1")
                self.assertIn("grade_standard_v1", plan.prompt_template_hashes)

    def test_course_specs_are_loadable(self):
        spec_paths = [
            Path("experiments/course_specs/physics_week9.json"),
            Path("experiments/course_specs/DSAA3073_week2_test.json"),
            Path("experiments/course_specs/DSAA3071_week5_test.json"),
            Path("experiments/course_specs/linearalgebra_quiz1.json"),
            Path("experiments/course_specs/linearalgebra_quiz1_v2.json"),
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

    def test_dsaa3071_candidate_v3_dev_ablation_record_is_ready_without_model_calls(self):
        record_dir = Path("experiments/records/DSAA3071-week5-candidate-v3-dev-plan")
        plan = json.loads((record_dir / "ablation-plan.json").read_text(encoding="utf-8"))
        readiness = json.loads(
            (record_dir / "ablation-readiness.json").read_text(encoding="utf-8")
        )
        protocol = (record_dir / "RUN-PROTOCOL.md").read_text(encoding="utf-8")

        self.assertEqual(plan["conditions"], ["B0", "R1", "C3"])
        self.assertEqual(plan["model_calls"], 0)
        self.assertEqual(
            plan["source_run_id"],
            "T1-dev-human-reviewed-r1",
        )
        self.assertEqual(
            plan["data_snapshot_hash"],
            "95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37",
        )
        self.assertEqual(plan["split"], "development")
        self.assertEqual(
            plan["students_file"],
            "experiments/records/DSAA3071-week5-test-plan/students-development.txt",
        )
        self.assertEqual(len(plan["student_ids"]), 7)
        self.assertEqual(
            plan["shared_run_settings"],
            {
                "input_mode": "text-only",
                "model": "deepseek-v4-pro",
                "provider": "deepseek",
                "repetition": 1,
            },
        )
        self.assertEqual(
            plan["controlled_differences"],
            {
                "B0_R1": "rubric only; prompt and skill must match",
                "R1_C3": "prompt and skill only; rubric must match",
            },
        )
        self.assertEqual(
            set(plan["packets"]),
            {"B0", "R1", "C3"},
        )
        self.assertEqual(
            plan["packets"]["B0"]["packet_path"],
            "Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/"
            "DSAA3071-week5-B0-v0-reviewed-dev/B0-dev-reviewed-r1",
        )
        self.assertEqual(
            plan["packets"]["B0"]["prompt_hash"],
            plan["packets"]["R1"]["prompt_hash"],
        )
        self.assertNotEqual(
            plan["packets"]["B0"]["rubric_hash"],
            plan["packets"]["R1"]["rubric_hash"],
        )
        self.assertEqual(
            plan["packets"]["R1"]["rubric_hash"],
            plan["packets"]["C3"]["rubric_hash"],
        )
        self.assertNotEqual(
            plan["packets"]["R1"]["prompt_hash"],
            plan["packets"]["C3"]["prompt_hash"],
        )
        self.assertEqual(
            plan["packets"]["B0"]["skill_hash"],
            plan["packets"]["R1"]["skill_hash"],
        )
        self.assertNotEqual(
            plan["packets"]["R1"]["skill_hash"],
            plan["packets"]["C3"]["skill_hash"],
        )
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["failed_checks"], [])
        self.assertEqual(readiness["model_run_status"], "not_started")
        self.assertIn("Windows PowerShell", protocol)
        self.assertIn("macOS/Linux", protocol)
        self.assertIn("Read-Host \"DeepSeek API key\" -AsSecureString", protocol)
        self.assertIn("run-model-packet", protocol)
        self.assertNotIn("DEEPSEEK_API_KEY=sk-", protocol)

    def test_dsaa3071_candidate_v31_dev_ablation_record_is_ready_without_model_calls(self):
        record_dir = Path("experiments/records/DSAA3071-week5-candidate-v31-dev-plan")
        plan = json.loads((record_dir / "ablation-plan.json").read_text(encoding="utf-8"))
        readiness = json.loads(
            (record_dir / "ablation-readiness.json").read_text(encoding="utf-8")
        )
        protocol = (record_dir / "RUN-PROTOCOL.md").read_text(encoding="utf-8")

        self.assertEqual(plan["conditions"], ["B0", "R1", "C3-v3.1"])
        self.assertEqual(plan["model_calls"], 0)
        self.assertEqual(plan["source_run_id"], "T1-dev-human-reviewed-r1")
        self.assertEqual(
            plan["data_snapshot_hash"],
            "95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37",
        )
        self.assertEqual(plan["split"], "development")
        self.assertEqual(len(plan["student_ids"]), 7)
        self.assertEqual(
            plan["controlled_differences"],
            {
                "B0_R1": "rubric only; prompt and skill must match",
                "R1_C3-v3.1": "prompt and skill only; rubric must match",
            },
        )
        self.assertEqual(set(plan["packets"]), {"B0", "R1", "C3-v3.1"})
        self.assertEqual(
            plan["packets"]["B0"]["prompt_hash"],
            plan["packets"]["R1"]["prompt_hash"],
        )
        self.assertNotEqual(
            plan["packets"]["B0"]["rubric_hash"],
            plan["packets"]["R1"]["rubric_hash"],
        )
        self.assertEqual(
            plan["packets"]["R1"]["rubric_hash"],
            plan["packets"]["C3-v3.1"]["rubric_hash"],
        )
        self.assertNotEqual(
            plan["packets"]["R1"]["prompt_hash"],
            plan["packets"]["C3-v3.1"]["prompt_hash"],
        )
        self.assertEqual(
            plan["packets"]["B0"]["skill_hash"],
            plan["packets"]["R1"]["skill_hash"],
        )
        self.assertNotEqual(
            plan["packets"]["R1"]["skill_hash"],
            plan["packets"]["C3-v3.1"]["skill_hash"],
        )
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["failed_checks"], [])
        self.assertEqual(readiness["model_run_status"], "not_started")
        self.assertIn("C3-dev-reviewed-v31-r1", protocol)
        self.assertIn("Windows PowerShell", protocol)
        self.assertIn("macOS/Linux", protocol)
        self.assertIn("Read-Host \"DeepSeek API key\" -AsSecureString", protocol)
        self.assertIn("run-model-packet", protocol)
        self.assertNotIn("DEEPSEEK_API_KEY=sk-", protocol)

    def test_dsaa3071_candidate_v31_r2_dev_record_is_ready_without_model_calls(self):
        record_dir = Path("experiments/records/DSAA3071-week5-candidate-v31-dev-plan")
        plan = json.loads(
            (record_dir / "ablation-plan-r2.json").read_text(encoding="utf-8")
        )
        readiness = json.loads(
            (record_dir / "ablation-readiness-r2.json").read_text(encoding="utf-8")
        )
        protocol = (record_dir / "RUN-PROTOCOL-R2.md").read_text(encoding="utf-8")
        note = (record_dir / "CANDIDATE-V31-R2-OPEN-ENDED-ADEQUACY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(plan["conditions"], ["B0", "R1", "C3-v3.1-r2"])
        self.assertEqual(plan["model_calls"], 0)
        self.assertEqual(plan["model_run_status"], "not_started")
        self.assertEqual(plan["supersedes_before_model_evidence"], "C3-dev-reviewed-v31-r1")
        self.assertEqual(
            plan["data_snapshot_hash"],
            "95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37",
        )
        self.assertEqual(
            plan["controlled_differences"],
            {
                "B0_R1": "rubric only; prompt and skill must match",
                "R1_C3-v3.1-r2": "prompt and skill only; rubric must match",
            },
        )
        self.assertEqual(set(plan["packets"]), {"B0", "R1", "C3-v3.1-r2"})
        self.assertEqual(
            plan["packets"]["R1"]["rubric_hash"],
            plan["packets"]["C3-v3.1-r2"]["rubric_hash"],
        )
        self.assertNotEqual(
            plan["packets"]["R1"]["prompt_hash"],
            plan["packets"]["C3-v3.1-r2"]["prompt_hash"],
        )
        self.assertNotEqual(
            plan["packets"]["R1"]["skill_hash"],
            plan["packets"]["C3-v3.1-r2"]["skill_hash"],
        )
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["failed_checks"], [])
        self.assertEqual(readiness["model_run_status"], "not_started")
        self.assertIn("C3-dev-reviewed-v31-r2", protocol)
        self.assertIn("deepseek-C31-r2-text-dev-reviewed-r1", protocol)
        self.assertIn("Windows PowerShell", protocol)
        self.assertIn("macOS/Linux", protocol)
        self.assertIn("Read-Host \"DeepSeek API key\" -AsSecureString", protocol)
        self.assertNotIn("DEEPSEEK_API_KEY=sk-", protocol)
        self.assertIn("open-ended adequacy", note)
        self.assertIn("not as an exhaustive whitelist", note)

    def test_dsaa3071_candidate_v32_dev_record_is_ready_without_model_calls(self):
        record_dir = Path("experiments/records/DSAA3071-week5-candidate-v31-dev-plan")
        plan = json.loads(
            (record_dir / "ablation-plan-c32.json").read_text(encoding="utf-8")
        )
        readiness = json.loads(
            (record_dir / "ablation-readiness-c32.json").read_text(encoding="utf-8")
        )
        protocol = (record_dir / "RUN-PROTOCOL-C32.md").read_text(encoding="utf-8")

        self.assertEqual(plan["conditions"], ["B0", "R1", "C32-v3.2-rubric-v2"])
        self.assertEqual(plan["model_calls"], 0)
        self.assertEqual(plan["model_run_status"], "not_started")
        self.assertEqual(plan["calibration_scope"], "Q7_Q8_Q9_dev_only")
        self.assertEqual(
            plan["controlled_differences"],
            {
                "B0_R1": "rubric only; prompt and skill must match",
                "R1_C32-v3.2-rubric-v2": "rubric, prompt, and skill jointly differ by design",
            },
        )
        self.assertEqual(set(plan["packets"]), {"B0", "R1", "C32-v3.2-rubric-v2"})
        self.assertEqual(
            plan["packets"]["C32-v3.2-rubric-v2"]["skill_version_id"],
            "skill_candidate_v3_2",
        )
        self.assertEqual(
            plan["packets"]["C32-v3.2-rubric-v2"]["rubric_path"],
            "experiments/records/DSAA3071-week5-prep/rubric_v2.json",
        )
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["failed_checks"], [])
        self.assertEqual(readiness["legacy_gate_expected_failure"], "r1_c3_rubric_matches")
        self.assertEqual(readiness["model_run_status"], "not_started")
        self.assertIn("C32-dev-reviewed-r1", protocol)
        self.assertIn("Windows PowerShell", protocol)
        self.assertIn("macOS/Linux", protocol)
        self.assertIn("Read-Host \"DeepSeek API key\" -AsSecureString", protocol)
        self.assertNotIn("DEEPSEEK_API_KEY=sk-", protocol)

    def test_dsaa3071_candidate_v3_dev_metrics_record_summarizes_passed_runs(self):
        record_dir = Path("experiments/records/DSAA3071-week5-candidate-v3-dev-plan")
        metrics = json.loads(
            (record_dir / "dev-metrics-deepseek-r3.json").read_text(encoding="utf-8")
        )
        markdown = (record_dir / "DEV-METRICS-DEEPSEEK-R3.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(metrics["report_type"], "dsaa3071_week5_dev_metrics")
        self.assertEqual(metrics["split"], "development")
        self.assertEqual(set(metrics["runs"]), {"B0", "R1", "C3"})
        self.assertTrue(
            all(run["validation_status"] == "passed" for run in metrics["runs"].values())
        )
        self.assertLess(
            metrics["comparisons"]["R1_minus_B0"]["question_score_mae_delta"],
            0,
        )
        self.assertGreater(
            metrics["comparisons"]["C3_minus_R1"]["question_score_mae_delta"],
            0,
        )
        self.assertIn("held-out not run", markdown)
        self.assertIn("not a final accuracy claim", markdown)

    def test_dsaa3071_candidate_v32_dev_metrics_record_summarizes_result(self):
        record_dir = Path("experiments/records/DSAA3071-week5-candidate-v31-dev-plan")
        metrics = json.loads(
            (record_dir / "dev-metrics-deepseek-c32.json").read_text(encoding="utf-8")
        )
        markdown = (record_dir / "DEV-METRICS-DEEPSEEK-C32.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(
            metrics["report_type"],
            "dsaa3071_week5_candidate_v32_dev_metrics",
        )
        self.assertEqual(metrics["split"], "development")
        self.assertEqual(set(metrics["runs"]), {"B0", "R1", "C3", "C31_r2", "C32"})
        self.assertEqual(
            metrics["runs"]["C31_r2"]["validation_status"],
            "passed_after_recovery",
        )
        self.assertEqual(metrics["runs"]["C31_r2"]["students_passed"], 7)
        self.assertEqual(metrics["runs"]["C31_r2"]["students_expected"], 7)
        self.assertEqual(metrics["runs"]["C32"]["validation_status"], "passed")
        self.assertEqual(metrics["runs"]["C32"]["students_passed"], 7)
        self.assertLess(
            metrics["comparisons"]["C32_minus_R1"]["question_score_mae_delta"],
            0,
        )
        self.assertLess(
            metrics["comparisons"]["C32_minus_R1"]["total_score_mae_delta"],
            0,
        )
        self.assertLess(
            metrics["comparisons"]["C32_minus_C31_r2"]["question_score_mae_delta"],
            0,
        )
        self.assertGreater(
            metrics["comparisons"]["C32_minus_R1"][
                "severe_error_rate_abs_ge_5_delta"
            ],
            0,
        )
        self.assertIn("held-out not run", markdown)
        self.assertIn("not a final accuracy claim", markdown)
        self.assertIn("Q8 remains", markdown)
        self.assertIn("90%", markdown)
        self.assertIn("cancellation", markdown)

    def test_dsaa3071_candidate_v32_typst_note_records_dev_result(self):
        record_dir = Path("experiments/records/DSAA3071-week5-candidate-v31-dev-plan")
        note = (record_dir / "note.typ").read_text(encoding="utf-8")

        self.assertTrue((record_dir / "note.pdf").exists())
        self.assertIn("DSAA3071 Week 5 Candidate-v3.2", note)
        self.assertIn("C32", note)
        self.assertIn("held-out not run", note)
        self.assertIn("not a final accuracy claim", note)
        self.assertIn("Q8 remains", note)
        self.assertIn("dev-metrics-deepseek-c32.json", note)
        self.assertIn("RUN-PROTOCOL-C32.md", note)
        self.assertIn("rubric_v2.json", note)

    def test_codex_cli_headless_mode_record_has_prompt_script_and_protocol(self):
        record_dir = Path("experiments/records/Codex-CLI-headless-mode")
        protocol = (record_dir / "HEADLESS-RUN-PROTOCOL.md").read_text(
            encoding="utf-8"
        )
        prompt = (record_dir / "headless-mode-prompt.md").read_text(encoding="utf-8")
        script = Path("scripts/run_headless_packet.py").read_text(encoding="utf-8")

        self.assertIn("Codex CLI headless", protocol)
        self.assertIn("codex.cmd exec", protocol)
        self.assertIn("codex exec", protocol)
        self.assertIn("claude", protocol)
        self.assertIn("--output-format json", protocol)
        self.assertIn("--max-turns 1", protocol)
        self.assertIn("result", protocol)
        self.assertIn("CLAUDE-CODE-REPRODUCTION.md", protocol)
        self.assertIn("DeepSeek", protocol)
        self.assertIn("git rev-parse --short HEAD", protocol)
        self.assertIn("run-headless-packet", protocol)
        self.assertIn("Blind headless grading run", prompt)
        self.assertIn("Do not inspect parent directories", prompt)
        self.assertIn("benchmark.core.cli", script)
        self.assertIn("run-headless-packet", script)

    def test_claude_code_reproduction_guide_is_actionable(self):
        guide = Path(
            "experiments/records/Codex-CLI-headless-mode/"
            "CLAUDE-CODE-REPRODUCTION.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Claude Code Reproduction Guide", guide)
        self.assertIn("claude --version", guide)
        self.assertIn("claude -p", guide)
        self.assertIn("--output-format json", guide)
        self.assertIn("--max-turns 1", guide)
        self.assertIn("claude-sonnet-4-20250514", guide)
        self.assertIn("codex/claude-headless-support", guide)
        self.assertIn("Data/physics/benchmark/text_packets", guide)
        self.assertIn("physics-week9-baseline-text-strict-schema", guide)
        self.assertIn("physics-week9-candidate-v2-text-strict-schema", guide)
        self.assertIn("benchmark.physics.cli metrics", guide)
        self.assertIn("Do not commit", guide)
        self.assertIn("raw-responses.jsonl", guide)
        self.assertIn("run-metadata.json", guide)

    def test_physics_codex_headless_attempt_1_records_cli_argument_failure(self):
        record = Path(
            "experiments/records/physics-week9-codex-headless-run/"
            "CODEX-DEV-ATTEMPT-1.md"
        ).read_text(encoding="utf-8")

        self.assertIn("CLI argument failure", record)
        self.assertIn("--ask-for-approval", record)
        self.assertIn("exit 2", record)
        self.assertIn("0/8", record)
        self.assertIn("not an accuracy result", record)
        self.assertIn("No raw student transcript", record)

    def test_physics_codex_headless_dev_metrics_records_passed_argfix_runs(self):
        record_dir = Path("experiments/records/physics-week9-codex-headless-run")
        metrics = json.loads(
            (record_dir / "dev-metrics-codex-argfix.json").read_text(encoding="utf-8")
        )
        markdown = (record_dir / "DEV-METRICS-CODEX-ARGFIX.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(
            metrics["report_type"],
            "physics_week9_codex_headless_dev_metrics",
        )
        self.assertEqual(metrics["split"], "development")
        self.assertEqual(metrics["provider"], "codex_cli")
        self.assertEqual(metrics["model"], "gpt-5.5")
        self.assertEqual(metrics["run_commit"], "0b38ebd")
        self.assertEqual(set(metrics["runs"]), {"baseline", "candidate_v2"})
        self.assertTrue(
            all(run["validation_status"] == "passed" for run in metrics["runs"].values())
        )
        self.assertTrue(
            all(run["students_passed"] == 8 for run in metrics["runs"].values())
        )
        self.assertGreater(
            metrics["metrics"]["candidate_v2_minus_baseline"]["exact_agreement"],
            0,
        )
        self.assertEqual(
            metrics["metrics"]["candidate_v2_minus_baseline"]["severe_error_rate"],
            0.0,
        )
        self.assertFalse(metrics["privacy"]["raw_student_transcripts_tracked"])
        self.assertIn("not a held-out test result", markdown)
        self.assertIn("aggregate metrics", markdown)
        self.assertIn("DeepSeek-vs-Codex", markdown)

    def test_physics_model_benchmark_report_summarizes_available_evidence(self):
        record_dir = Path("experiments/records/physics-codex-benchmark-report")
        summary = json.loads(
            (record_dir / "model-benchmark-summary.json").read_text(encoding="utf-8")
        )
        report = (record_dir / "MODEL-BENCHMARK-REPORT.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(summary["report_type"], "physics_week9_model_benchmark_v1")
        self.assertEqual(summary["course_id"], "physics")
        self.assertEqual(summary["assessment_id"], "week9")
        self.assertEqual(summary["current_answer"]["meets_good_enough_bar"], True)
        self.assertIn(
            "Codex CLI", summary["current_answer"]["best_supported_condition"]
        )
        self.assertEqual(
            summary["evidence"]["deepseek_public_api_held_out"]["validation_status"],
            "passed",
        )
        self.assertEqual(
            summary["evidence"]["deepseek_public_api_held_out"]["students"],
            18,
        )
        self.assertGreater(
            summary["evidence"]["deepseek_public_api_held_out"][
                "candidate_v2_minus_baseline"
            ]["exact_agreement"],
            0,
        )
        self.assertEqual(
            summary["evidence"]["codex_cli_held_out"]["validation_status"],
            "passed",
        )
        self.assertEqual(summary["evidence"]["codex_cli_held_out"]["students"], 18)
        self.assertGreater(
            summary["evidence"]["codex_cli_held_out"][
                "candidate_v2_minus_baseline"
            ]["exact_agreement"],
            0,
        )
        self.assertGreater(
            summary["evidence"]["codex_cli_held_out"]["candidate_v2"][
                "exact_agreement"
            ],
            summary["evidence"]["deepseek_public_api_held_out"]["candidate_v2"][
                "exact_agreement"
            ],
        )
        self.assertEqual(
            summary["evidence"]["claude_code_headless"]["validation_status"],
            "not_run",
        )
        self.assertFalse(summary["privacy"]["raw_student_data_tracked"])
        self.assertIn("Codex CLI + candidate-v2", report)
        self.assertIn("0.8981", report)
        self.assertIn("Held-Out Provider Comparison", report)
        self.assertIn("DeepSeek public API", report)
        self.assertIn("Claude Code is not evaluated yet", report)
        self.assertIn("bootstrap interval", report)
        self.assertIn("codex-baseline-text-G1-test-r1", report)
        self.assertIn("codex-candidate-text-G1-test-r1", report)
        self.assertIn("codex-heldout-G1-baseline-vs-candidate.metrics.json", report)
        self.assertIn("Raw student transcripts", report)

    def test_physics_kimi_benchmark_protocol_records_reproducible_commands(self):
        protocol = Path(
            "experiments/records/physics-kimi-benchmark-run/RUN-PROTOCOL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("kimi-k2.6", protocol)
        self.assertIn("MOONSHOT_API_KEY", protocol)
        self.assertIn("https://api.moonshot.ai/v1", protocol)
        self.assertIn("--provider kimi", protocol)
        self.assertIn("G1-dev-r1", protocol)
        self.assertIn("G1-test-r1", protocol)
        self.assertIn("kimi-heldout-G1-baseline-vs-candidate.metrics.json", protocol)
        self.assertIn("Windows PowerShell", protocol)
        self.assertIn("macOS/Linux", protocol)
        self.assertIn("Raw student transcripts", protocol)
        self.assertNotIn("MOONSHOT_API_KEY=sk-", protocol)

    def test_github_pages_ai_grading_handoff_is_actionable(self):
        index = Path("docs/index.md").read_text(encoding="utf-8")
        handoff = Path("docs/ai-grading-test-handoff.md").read_text(encoding="utf-8")

        self.assertIn("AI Grading Test Handoff", index)
        self.assertIn("AI Grading Test Handoff", handoff)
        self.assertIn("Kimi Route", handoff)
        self.assertIn("Claude Code Route", handoff)
        self.assertIn("Private Data Handoff", handoff)
        self.assertIn("Kimi Auth Preflight", handoff)
        self.assertIn("Kimi Held-Out Run", handoff)
        self.assertIn("Claude Code Held-Out Run", handoff)
        self.assertIn("physics-week9-baseline-text-strict-schema/G1-dev-r1", handoff)
        self.assertIn("physics-week9-candidate-v2-text-strict-schema/G1-test-r1", handoff)
        self.assertIn("private HKUST-GZ GitLab", handoff)
        self.assertIn("Test-Path Data\\physics\\benchmark\\text_packets", handoff)
        self.assertIn("MOONSHOT_API_KEY", handoff)
        self.assertIn("claude -p", handoff)
        self.assertIn("Required Per-Student Output Shape", handoff)
        self.assertIn("\"confidence\": \"high\"", handoff)
        self.assertIn("Return This Summary To YY", handoff)
        self.assertIn("Do not commit", handoff)
        self.assertNotIn("MOONSHOT_API_KEY=sk-", handoff)

    def test_dsaa3071_w2_w6_source_inventory_records_private_pdf_pairs(self):
        record_dir = Path("experiments/records/DSAA3071-w2-w6-source-inventory")
        inventory = json.loads(
            (record_dir / "source-inventory.json").read_text(encoding="utf-8")
        )

        self.assertEqual(inventory["course_id"], "DSAA3071")
        self.assertEqual(inventory["scope"]["weeks"], [2, 3, 4, 6])
        self.assertEqual(inventory["git_policy"]["data_root"], "Data/")
        self.assertFalse(inventory["git_policy"]["raw_pdfs_git_tracked"])

        assets = inventory["assets"]
        self.assertEqual(len(assets), 8)
        by_week = {}
        for asset in assets:
            by_week.setdefault(asset["week"], set()).add(asset["role"])
            self.assertTrue(asset["local_path"].startswith("Data/DSAA3071/"))
            self.assertNotIn("D:", asset["local_path"])
            self.assertEqual(asset["git_status"], "ignored_by_Data_rule")
            self.assertRegex(asset["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(asset["pages"], 0)

        self.assertEqual(
            by_week,
            {
                2: {"student_answer_combined_pdf", "question_solution_pdf"},
                3: {"student_answer_combined_pdf", "question_solution_pdf"},
                4: {"student_answer_combined_pdf", "question_solution_pdf"},
                6: {"student_answer_combined_pdf", "question_solution_pdf"},
            },
        )
        student_assets = [
            asset
            for asset in assets
            if asset["role"] == "student_answer_combined_pdf"
        ]
        self.assertTrue(
            all(
                asset["privacy_status"] == "raw_private_not_anonymized"
                for asset in student_assets
            )
        )
        self.assertTrue(all(asset["model_run_allowed"] is False for asset in assets))

    def test_quantum_harness_review_is_readable_and_evidence_mapped(self):
        report = Path(
            "experiments/records/tooling-surveys/"
            "quantum-harness-beginner-training.md"
        ).read_text(encoding="utf-8")
        record_dir = Path("experiments/records/weekly-todo-integration-2026-07")
        settlement = (record_dir / "TASK3-ZULIP-SETTLEMENT.md").read_text(
            encoding="utf-8"
        )
        ledger = (record_dir / "WEEKLY-PROGRESS-2026-07-25.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "3bed20a166fe0228cf40b82d7d6dbd0a77014df1",
            report,
        )
        self.assertIn("我们已经实际借鉴的内容", report)
        self.assertIn("已经实现", report)
        self.assertIn("部分实现", report)
        self.assertIn("尚未实现", report)
        self.assertIn("选项 A", report)
        self.assertIn("选项 E", report)
        self.assertIn("不建议直接迁移的内容", report)
        self.assertIn("## 中文版", settlement)
        self.assertIn("## English version", settlement)
        task3_line = next(
            line for line in ledger.splitlines() if line.startswith("| TASK3 |")
        )
        self.assertIn("`completed`", task3_line)
        self.assertIn("PR #31", task3_line)
        self.assertIn("PR #32 merged", task3_line)
        self.assertIn("Bilingual settlement ready, not posted", task3_line)
        for text in (report, settlement):
            self.assertNotRegex(text, r"[鍙鐨鏄]")
            self.assertNotRegex(text, r"\bS[0-9]{3}\b")
            self.assertNotIn("API_KEY=", text)

    def test_todo1_retrospective_keeps_only_decision_relevant_negative_results(self):
        record_dir = Path("experiments/records/weekly-todo-integration-2026-07")
        physics_record_dir = Path(
            "experiments/records/physics-skillopt-deepseek-r4-run"
        )
        metrics = json.loads(
            (record_dir / "TODO1-MEANINGFUL-NEGATIVE-RESULTS.json").read_text(
                encoding="utf-8"
            )
        )
        report = (record_dir / "TODO1-MEANINGFUL-NEGATIVE-RESULTS.md").read_text(
            encoding="utf-8"
        )
        settlement = (record_dir / "TODO1-ZULIP-SETTLEMENT.md").read_text(
            encoding="utf-8"
        )
        physics_report = (physics_record_dir / "FAILURE-ANALYSIS.md").read_text(
            encoding="utf-8"
        )
        physics_settlement = (physics_record_dir / "ZULIP-SETTLEMENT.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(
            metrics["report_type"],
            "todo1_meaningful_negative_result_retrospective",
        )
        self.assertTrue(
            any("command" in item for item in metrics["scope"]["excluded"])
        )
        self.assertEqual(
            metrics["results"]["physics_skillopt_r4"]["classification"],
            "negative_result",
        )

        c3 = metrics["results"]["dsaa3071_candidate_v3"]
        self.assertGreater(
            c3["candidate_metrics"]["question_score_mae"],
            c3["baseline_metrics"]["question_score_mae"],
        )
        self.assertEqual(
            sum(c3["question_absolute_error_point_contributions"].values()),
            c3["candidate_minus_baseline"]["item_absolute_error_points"],
        )

        c31 = metrics["results"]["dsaa3071_candidate_v31_r2"]
        self.assertGreater(
            c31["candidate_minus_baseline"]["item_absolute_error_points"],
            0,
        )
        self.assertLess(
            c31["candidate_minus_baseline"]["student_total_absolute_error_points"],
            0,
        )

        c32 = metrics["results"]["dsaa3071_candidate_v32"]
        decomposition = c32["total_score_improvement_decomposition"]
        self.assertEqual(
            decomposition["question_level_absolute_error_points_reduced"]
            + decomposition["additional_cancellation_points"],
            decomposition["total_absolute_error_points_reduced"],
        )
        self.assertEqual(decomposition["share_from_additional_cancellation"], 0.9)
        self.assertEqual(
            c32["candidate_minus_baseline"]["severe_error_pairs"],
            1,
        )
        self.assertEqual(
            sum(c32["question_absolute_error_point_contributions"].values()),
            c32["candidate_minus_baseline"]["item_absolute_error_points"],
        )

        for public_text in (report, settlement):
            self.assertNotRegex(public_text, r"\bS[0-9]{3}\b")
            self.assertNotIn("DEEPSEEK_API_KEY=", public_text)
        self.assertIn("90%", report)
        self.assertIn("ordinary command", report.lower())
        for bilingual_text in (
            report,
            settlement,
            physics_report,
            physics_settlement,
        ):
            self.assertIn("## 中文版", bilingual_text)
            self.assertIn("## English version", bilingual_text)
            self.assertRegex(bilingual_text, r"[\u4e00-\u9fff]")


class CandidateV33RulePrecedenceRecordTests(unittest.TestCase):
    RECORD_ROOT = Path(
        "experiments/records/DSAA3071-week5-candidate-v33-q9-precedence"
    )

    def test_candidate_v33_is_rejected_by_the_frozen_severe_error_gate(self):
        decision = json.loads(
            (self.RECORD_ROOT / "acceptance-decision.json").read_text(
                encoding="utf-8"
            )
        )
        conditions = {
            row["metric"]: row for row in decision["conditions"]
        }

        self.assertEqual(decision["decision"], "rejected")
        self.assertEqual(
            decision["active_skill_version_after_decision"],
            "skill_candidate_v3_2",
        )
        self.assertEqual(
            [row["metric"] for row in decision["conditions"] if not row["passed"]],
            ["severe_error_pairs"],
        )
        self.assertEqual(conditions["severe_error_pairs"]["observed"], 17)
        self.assertEqual(conditions["q9_mae"]["observed"], 7.0)
        self.assertFalse(decision["heldout_or_test_accessed"])
        self.assertFalse(decision["post_result_rerun_performed"])

    def test_candidate_v33_complete_public_error_lifecycle_is_present(self):
        summary = json.loads(
            (self.RECORD_ROOT / "public-summary.json").read_text(
                encoding="utf-8"
            )
        )
        diagnoses = json.loads(
            (self.RECORD_ROOT / "diagnosis-summary.json").read_text(
                encoding="utf-8"
            )
        )
        delta = json.loads(
            (self.RECORD_ROOT / "iteration-delta-v32-v33.json").read_text(
                encoding="utf-8"
            )
        )
        confidence = json.loads(
            (self.RECORD_ROOT / "confidence-taxonomy-summary.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(summary["population"]["student_question_pairs"], 70)
        self.assertEqual(summary["population"]["error_pairs"], 31)
        self.assertEqual(summary["population"]["severe_error_pairs"], 17)
        self.assertEqual(diagnoses["review"]["case_count"], 31)
        self.assertTrue(diagnoses["review"]["all_error_cases_reviewed"])
        self.assertEqual(delta["counts"]["resolved"], 3)
        self.assertEqual(delta["counts"]["regression"], 1)
        self.assertEqual(confidence["population"]["error_pairs"], 31)
        self.assertEqual(confidence["population"]["technical_failure_count"], 0)

    def test_candidate_v33_failure_and_settlement_are_fully_bilingual_and_private(self):
        failure = (self.RECORD_ROOT / "FAILURE-ANALYSIS.md").read_text(
            encoding="utf-8"
        )
        audit = (self.RECORD_ROOT / "CONFIDENCE-TAXONOMY.md").read_text(
            encoding="utf-8"
        )
        settlement = Path(
            "experiments/records/weekly-todo-integration-2026-07/"
            "TASK9-ZULIP-SETTLEMENT.md"
        ).read_text(encoding="utf-8")

        for text in (failure, audit):
            self.assertIn("## 中文版", text)
            self.assertIn("## English Version", text)
        self.assertIn("## 中文", settlement)
        self.assertIn("## English", settlement)
        for public_text in (failure, audit, settlement):
            self.assertNotRegex(public_text, r"\bS[0-9]{3}\b")
            self.assertNotIn("DEEPSEEK_API_KEY=", public_text)
        self.assertNotIn("TASK6", audit)
        self.assertNotIn("candidate-v3.3 先处理", audit)

        plan_text = (self.RECORD_ROOT / "experiment-plan.json").read_text(
            encoding="utf-8"
        )
        protocol = (self.RECORD_ROOT / "RUN-PROTOCOL.md").read_text(
            encoding="utf-8"
        )
        self.assertNotRegex(plan_text + protocol, r"\bS[0-9]{3}\b")
        self.assertEqual(json.loads(plan_text)["student_count"], 7)


if __name__ == "__main__":
    unittest.main()
