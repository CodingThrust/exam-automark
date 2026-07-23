import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.core.advisor_workflow import (
    WorkflowError,
    _approved_images,
    _comparison_contract,
    _create_pr_with_token,
    _github_repo_slug,
    _private_roots_ignored,
    _probe_receipt_matches,
    _run_metadata_matches,
    _scan_public_json,
    _text_provenance,
    build_preset_config,
    package_results,
    plan,
    probe_models,
    privacy_scan_record,
    run_experiment,
    validate_config,
)


class AdvisorWorkflowTests(unittest.TestCase):
    def test_private_roots_check_requires_both_ignore_rules(self):
        calls = []

        def fake_git(_repo, *args, **_kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(
                ["git", *args],
                0 if args[-1] == "Data/" else 1,
                "",
                "",
            )

        with patch("benchmark.core.advisor_workflow._git", side_effect=fake_git):
            self.assertFalse(_private_roots_ignored(Path("repo")))

        self.assertEqual(
            calls,
            [
                ("check-ignore", "--no-index", "--quiet", "--", "Data/"),
                ("check-ignore", "--no-index", "--quiet", "--", ".private-data/"),
            ],
        )

    def test_preset_has_full_kimi_claude_text_image_matrix(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-test",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )

        arms = {
            (run["engine"], run["input_mode"], run["condition"])
            for run in config["runs"]
        }
        self.assertEqual(len(config["runs"]), 8)
        self.assertEqual(
            arms,
            {
                (engine, mode, condition)
                for engine in ("kimi", "claude")
                for mode in ("text-only", "multimodal")
                for condition in ("baseline", "candidate")
            },
        )
        self.assertEqual(len(config["comparisons"]), 8)
        self.assertEqual(config["split"], "development")
        self.assertTrue(all(run["timeout_seconds"] == 600 for run in config["runs"]))
        self.assertTrue(config["submission"]["branch"].startswith("advisor-results/"))
        self.assertNotIn("MOONSHOT_API_KEY", json.dumps(config))

    def test_test_preset_uses_frozen_test_packets(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-heldout-test",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
            split="test",
        )

        self.assertEqual(config["split"], "test")
        self.assertEqual(len(config["runs"]), 8)
        self.assertTrue(
            all(run["packet"].endswith("G1-test-r1") for run in config["runs"])
        )
        self.assertTrue(
            all(build["id"].endswith("-test") for build in config["packet_builds"])
        )
        self.assertTrue(
            all(
                build["source_text_packet"].endswith("G1-test-r1")
                for build in config["packet_builds"]
            )
        )

    def test_config_rejects_secret_like_fields(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-test",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )
        config["github_token"] = "must-not-be-here"

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "Data").mkdir()
            (repo / "experiments" / "records").mkdir(parents=True)
            (repo / "local").mkdir()
            with self.assertRaisesRegex(WorkflowError, "secret-like"):
                from benchmark.core.advisor_workflow import _reject_secret_keys

                _reject_secret_keys(config)

    def test_validate_config_requires_every_engine_mode_condition_arm(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-test",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )
        config["runs"] = [
            run for run in config["runs"] if run["id"] != "claude-image-candidate"
        ]

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with self.assertRaisesRegex(WorkflowError, "missing required run arms"):
                validate_config(config, repo)

    def test_plan_marks_missing_packets_as_action_required(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-test",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = plan(Path(tmp), config)

        self.assertEqual(result["status"], "action_required")
        self.assertEqual(len(result["missing_packets"]), 8)

    def test_model_probe_requires_explicit_approval(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-test",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(WorkflowError, "approve-model-probes"):
                probe_models(Path(tmp), config)

    def test_model_probe_sends_no_student_data_and_writes_matching_receipt(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-probe",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )
        prompts = []

        def fake_git(_repo, *args, **_kwargs):
            return subprocess.CompletedProcess(["git", *args], 0, "abc1234\n", "")

        def fake_subprocess(argv, **kwargs):
            if "--prompt" in argv:
                prompts.append(argv[argv.index("--prompt") + 1])
                stdout = json.dumps({"role": "assistant", "content": "OK"})
            else:
                prompts.append(kwargs.get("input", ""))
                stdout = json.dumps({"is_error": False, "result": "OK"})
            return subprocess.CompletedProcess(argv, 0, stdout, "")

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with (
                patch("benchmark.core.advisor_workflow._git", side_effect=fake_git),
                patch("benchmark.core.advisor_workflow.shutil.which", return_value="cli"),
                patch(
                    "benchmark.core.advisor_workflow.subprocess.run",
                    side_effect=fake_subprocess,
                ),
            ):
                result = probe_models(repo, config, approved=True)

            self.assertTrue(
                _probe_receipt_matches(
                    repo,
                    config,
                    run_commit="abc1234",
                )
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["probes"]), 2)
        self.assertTrue(all("zero-data" in prompt for prompt in prompts))
        self.assertTrue(all("S001" not in prompt for prompt in prompts))

    def test_multimodal_images_require_explicit_page_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            student = root / "S001"
            student.mkdir()
            page = student / "S001-p01.jpg"
            page.write_bytes(b"image")

            selected = _approved_images(root, ["S001"], {"S001-p01.jpg": True})
            self.assertEqual(selected, [page])
            with self.assertRaisesRegex(WorkflowError, "privacy approval"):
                _approved_images(root, ["S001"], {"S001-p01.jpg": False})

    def test_transcript_provenance_distinguishes_automatic_from_reviewed(self):
        automatic, findings = _text_provenance(
            {
                "metadata": {
                    "text_source_kind": "transcript",
                    "text_source_path": "Data/course/transcripts/automatic/T1-dev-r1",
                    "source_run_id": "T1-dev-r1",
                }
            }
        )
        reviewed, reviewed_findings = _text_provenance(
            {
                "metadata": {
                    "text_source_kind": "human_reviewed_transcript",
                    "text_source_path": "Data/course/transcripts/reviewed/T1-dev-r2",
                    "source_run_id": "T1-dev-r2",
                }
            }
        )

        self.assertEqual(automatic, "automatic-transcript")
        self.assertEqual(reviewed, "human-reviewed-transcript")
        self.assertEqual(findings, [])
        self.assertEqual(reviewed_findings, [])

    def test_comparison_contract_rejects_second_changed_axis(self):
        left = {
            "engine": "kimi",
            "model": "kimi-code/k3",
            "input_mode": "text-only",
            "condition": "baseline",
        }
        right = {
            "engine": "claude",
            "model": "sonnet",
            "input_mode": "text-only",
            "condition": "candidate",
        }
        manifest = {
            "course_id": "physics",
            "assessment_id": "week9",
            "rubric_hash": "same-rubric",
            "prompt_hash": "same-prompt",
            "student_ids": ["S001"],
            "metadata": {"split": "development"},
        }

        matched, reason = _comparison_contract(
            left,
            right,
            manifest,
            manifest,
            split="development",
        )

        self.assertFalse(matched)
        self.assertIn("changes another axis", reason)

    def test_package_aggregates_failure_without_student_id(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-test",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            failed_output = repo / config["runs"][0]["output"]
            failed_output.mkdir(parents=True)
            (failed_output / "validation.json").write_text(
                json.dumps(
                    {
                        "status": "failed",
                        "students_expected": 1,
                        "students_passed": 0,
                        "rows": [
                            {
                                "student_id": "S001",
                                "status": "failed",
                                "error_type": "JSONDecodeError",
                                "error": "raw private detail",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "benchmark.core.advisor_workflow.privacy_scan_record",
                return_value={"status": "passed"},
            ):
                result = package_results(repo, config)

            self.assertEqual(result["status"], "failed")
            record = repo / config["record_dir"]
            summary_text = (record / "summary.json").read_text(encoding="utf-8")
            report_text = (record / "RUN-REPORT.md").read_text(encoding="utf-8")
            self.assertNotIn("S001", summary_text + report_text)
            self.assertNotIn("raw private detail", summary_text + report_text)
            self.assertIn("JSONDecodeError", summary_text + report_text)

    def test_public_json_scan_rejects_student_ids_in_keys(self):
        with self.assertRaisesRegex(WorkflowError, "student ID"):
            _scan_public_json(
                {"by_student": {"S001": {"exact_agreement": 1.0}}},
                label="metric",
            )

    def test_packaged_metric_omits_local_absolute_paths(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-public-metric",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )
        comparison = config["comparisons"][0]
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            metric_path = repo / comparison["output_json"]
            metric_path.parent.mkdir(parents=True)
            metric_path.write_text(
                json.dumps(
                    {
                        "record_type": "physics_run_metrics_comparison",
                        "generated_at": "2026-07-23T00:00:00Z",
                        "benchmark_root": str(repo / "Data" / "physics"),
                        "baseline_run": {
                            "path": str(repo / "Data" / "runs" / "baseline"),
                            "provider": "kimi_cli",
                        },
                        "candidate_run": {
                            "path": str(repo / "Data" / "runs" / "candidate"),
                            "provider": "kimi_cli",
                        },
                        "student_count": 8,
                        "score_count": 96,
                        "bootstrap": {
                            "exact_agreement_candidate_minus_baseline": {
                                "mean_difference": 0.1,
                                "lower": 0.0,
                                "upper": 0.2,
                            }
                        },
                        "baseline": {"exact_agreement": 0.5},
                        "candidate": {"exact_agreement": 0.6},
                        "candidate_minus_baseline": {"exact_agreement": 0.1},
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "benchmark.core.advisor_workflow.privacy_scan_record",
                return_value={"status": "passed"},
            ):
                package_results(repo, config)

            record = repo / config["record_dir"] / "metrics"
            public_json = (record / f"{comparison['id']}.json").read_text(
                encoding="utf-8"
            )
            public_md = (record / f"{comparison['id']}.md").read_text(
                encoding="utf-8"
            )

        self.assertNotIn(str(repo), public_json + public_md)
        self.assertNotIn("benchmark_root", public_json)
        self.assertNotIn('"path"', public_json)
        self.assertIn("exact_agreement", public_json + public_md)

    def test_package_preserves_privacy_safe_blocking_gate(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-blocked",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            state_path = repo / config["state_path"]
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "blockers": [
                            {
                                "gate": "kimi-cli",
                                "category": "environment/authentication",
                                "reason": "engine-cli-unavailable",
                                "private_detail": "must not be copied",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "benchmark.core.advisor_workflow.privacy_scan_record",
                return_value={"status": "passed"},
            ):
                result = package_results(repo, config)

            record = repo / config["record_dir"]
            summary = (record / "summary.json").read_text(encoding="utf-8")
            report = (record / "RUN-REPORT.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "blocked")
        self.assertIn("engine-cli-unavailable", summary + report)
        self.assertNotIn("private_detail", summary + report)
        self.assertNotIn("must not be copied", summary + report)

    def test_reused_run_must_match_current_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            output = repo / "Data" / "runs" / "one"
            output.mkdir(parents=True)
            (output / "validation.json").write_text(
                json.dumps({"status": "passed"}),
                encoding="utf-8",
            )
            (output / "run-metadata.json").write_text(
                json.dumps(
                    {
                        "engine": "kimi",
                        "model": "kimi-code/k3",
                        "input_mode": "text-only",
                        "experiment_condition": "baseline",
                        "max_retries": 2,
                        "timeout_seconds": 600,
                        "packet": str(repo / "Data" / "packet"),
                        "run_commit": "abc1234",
                    }
                ),
                encoding="utf-8",
            )
            run = {
                "id": "kimi-text-baseline",
                "engine": "kimi",
                "model": "kimi-code/k3",
                "input_mode": "text-only",
                "condition": "baseline",
                "max_retries": 2,
                "timeout_seconds": 600,
                "packet": "Data/packet",
            }

            self.assertTrue(
                _run_metadata_matches(
                    repo,
                    run,
                    output,
                    run_commit="abc1234",
                )
            )
            self.assertFalse(
                _run_metadata_matches(
                    repo,
                    run,
                    output,
                    run_commit="different",
                )
            )

    def test_failed_arm_does_not_prevent_next_engine_arm(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for name in ("packet-one", "packet-two"):
                (repo / "Data" / name).mkdir(parents=True)
            first_output = repo / "Data" / "runs" / "first-dry-run"
            first_output.mkdir(parents=True)
            config = {
                "experiment_id": "continue-after-failure",
                "split": "development",
                "state_path": "Data/runs/state.json",
                "runs": [
                    {
                        "id": "kimi-text-baseline",
                        "engine": "kimi",
                        "model": "kimi-code/k3",
                        "input_mode": "text-only",
                        "condition": "baseline",
                        "packet": "Data/packet-one",
                        "output": "Data/runs/first",
                    },
                    {
                        "id": "claude-text-baseline",
                        "engine": "claude",
                        "model": "sonnet",
                        "input_mode": "text-only",
                        "condition": "baseline",
                        "packet": "Data/packet-two",
                        "output": "Data/runs/second",
                    },
                ],
                "comparisons": [],
            }

            def fake_git(_repo, *args, **_kwargs):
                stdout = "abc1234\n" if args[:2] == ("rev-parse", "--short") else ""
                return subprocess.CompletedProcess(["git", *args], 0, stdout, "")

            captures = []

            def fake_run(argv, **kwargs):
                captures.append(kwargs.get("capture"))
                output = Path(argv[argv.index("--output") + 1])
                output.mkdir(parents=True)
                (output / "validation.json").write_text(
                    json.dumps(
                        {
                            "status": "passed",
                            "students_expected": 1,
                            "students_passed": 1,
                            "rows": [],
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(argv, 0, "", "")

            with (
                patch(
                    "benchmark.core.advisor_workflow._packet_mode_findings",
                    return_value=[],
                ),
                patch(
                    "benchmark.core.advisor_workflow.plan",
                    return_value={
                        "status": "planned",
                        "blocking_mismatches": [],
                        "comparisons": [],
                    },
                ),
                patch("benchmark.core.advisor_workflow._git", side_effect=fake_git),
                patch("benchmark.core.advisor_workflow._run", side_effect=fake_run),
            ):
                result = run_experiment(repo, config, dry_run=True)

        self.assertEqual(result["runs"]["kimi-text-baseline"]["status"], "failed")
        self.assertEqual(result["runs"]["claude-text-baseline"]["status"], "passed")
        self.assertEqual(captures, [True])

    def test_token_pr_creation_requests_a_draft(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({"html_url": "https://github.com/o/r/pull/1"}).encode()

        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        with (
            patch.dict("os.environ", {"GITHUB_TOKEN": "test-only-token"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            url = _create_pr_with_token(
                owner="o",
                repo_name="r",
                branch="advisor-results/test",
                base="main",
                title="Result",
                body="Safe aggregate",
            )

        self.assertEqual(url, "https://github.com/o/r/pull/1")
        self.assertIs(captured["payload"]["draft"], True)

    def test_privacy_scan_rejects_anonymous_student_ids_before_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            record = repo / "experiments" / "records" / "unsafe"
            record.mkdir(parents=True)
            (record / "RUN-REPORT.md").write_text(
                "Example failure for S001", encoding="utf-8"
            )

            with self.assertRaisesRegex(WorkflowError, "student ID"):
                privacy_scan_record(repo, record)

    def test_heldout_run_requires_explicit_approval_before_any_execution(self):
        config = build_preset_config(
            experiment_id="physics-week9-advisor-test",
            kimi_model="kimi-code/k3",
            claude_model="sonnet",
        )
        config["split"] = "heldout"

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(WorkflowError, "explicit --approve-heldout"):
                run_experiment(Path(tmp), config)

    def test_github_origin_parser_supports_ssh_and_https(self):
        self.assertEqual(
            _github_repo_slug("git@github.com:CodingThrust/exam-automark.git"),
            ("CodingThrust", "exam-automark"),
        )
        self.assertEqual(
            _github_repo_slug("https://github.com/CodingThrust/exam-automark.git"),
            ("CodingThrust", "exam-automark"),
        )


if __name__ == "__main__":
    unittest.main()
