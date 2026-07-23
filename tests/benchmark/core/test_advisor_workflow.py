import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.core.advisor_workflow import (
    WorkflowError,
    _approved_images,
    _comparison_contract,
    _github_repo_slug,
    _text_provenance,
    build_preset_config,
    package_results,
    privacy_scan_record,
    run_experiment,
    validate_config,
)


class AdvisorWorkflowTests(unittest.TestCase):
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
        self.assertTrue(config["submission"]["branch"].startswith("advisor-results/"))
        self.assertNotIn("MOONSHOT_API_KEY", json.dumps(config))

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
