import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from benchmark.core.cli import main
from benchmark.core.headless_runner import _extract_headless_cli_raw_text


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class HeadlessRunnerCliTests(unittest.TestCase):
    def test_codex_headless_dry_run_writes_valid_packet_run_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = _write_text_grading_packet(root)
            output = root / "runs" / "codex-synthetic-G1-dev-r1"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-headless-packet",
                        "--engine",
                        "codex",
                        "--model",
                        "gpt-5.6-codex",
                        "--input-mode",
                        "text-only",
                        "--packet",
                        str(packet),
                        "--output",
                        str(output),
                        "--dry-run",
                        "--run-commit",
                        "abc1234",
                    ]
                )
            result = json.loads(stdout.getvalue())
            metadata = json.loads((output / "run-metadata.json").read_text())
            validation = json.loads((output / "validation.json").read_text())
            payload = json.loads((output / "outputs" / "S001.json").read_text())
            command = (output / "command.txt").read_text(encoding="utf-8")
            prompt = (output / "headless-prompts" / "S001.prompt.txt").read_text(
                encoding="utf-8"
            )
            raw_responses_exists = (output / "raw-responses.jsonl").exists()

        self.assertEqual(code, 0)
        self.assertEqual(result["provider"], "codex_cli")
        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual(metadata["record_type"], "model_packet_run")
        self.assertEqual(metadata["provider"], "codex_cli")
        self.assertEqual(metadata["engine"], "codex")
        self.assertEqual(metadata["model"], "gpt-5.6-codex")
        self.assertEqual(metadata["run_commit"], "abc1234")
        self.assertEqual(metadata["api_key_source"], "codex_cli_external_auth")
        self.assertEqual(validation["students_passed"], 1)
        self.assertEqual(payload["student_id"], "S001")
        self.assertTrue(raw_responses_exists)
        self.assertIn("exec --json", command)
        self.assertIn("--output-schema", command)
        self.assertNotIn("--ask-for-approval", command)
        self.assertIn("Blind headless grading run", prompt)
        self.assertIn("Packet context:", prompt)
        self.assertNotIn("DEEPSEEK_API_KEY", command)

    def test_claude_headless_dry_run_records_json_print_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = _write_text_grading_packet(root)
            output = root / "runs" / "claude-synthetic-G1-dev-r1"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-headless-packet",
                        "--engine",
                        "claude",
                        "--model",
                        "claude-sonnet-4-20250514",
                        "--input-mode",
                        "text-only",
                        "--packet",
                        str(packet),
                        "--output",
                        str(output),
                        "--dry-run",
                        "--run-commit",
                        "abc1234",
                    ]
                )
            result = json.loads(stdout.getvalue())
            metadata = json.loads((output / "run-metadata.json").read_text())
            validation = json.loads((output / "validation.json").read_text())
            command = (output / "command.txt").read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(result["provider"], "claude_cli")
        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual(metadata["provider"], "claude_cli")
        self.assertEqual(metadata["engine"], "claude")
        self.assertEqual(metadata["model"], "claude-sonnet-4-20250514")
        self.assertEqual(metadata["api_key_source"], "claude_cli_external_auth")
        self.assertEqual(validation["students_passed"], 1)
        self.assertIn("claude -p", command)
        self.assertIn("--output-format json", command)
        self.assertIn("--max-turns 1", command)
        self.assertIn("--model claude-sonnet-4-20250514", command)
        self.assertNotIn("--output-schema", command)
        self.assertNotIn("codex.cmd exec", command)
        self.assertNotIn("DEEPSEEK_API_KEY", command)

    def test_claude_json_print_output_uses_result_field_as_model_text(self):
        stdout = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": "{\"student_id\":\"S001\",\"scores\":[]}",
                "session_id": "claude-session-1",
            }
        )

        self.assertEqual(
            _extract_headless_cli_raw_text("claude", stdout, Path("missing.txt")),
            "{\"student_id\":\"S001\",\"scores\":[]}",
        )

    def test_reproducing_script_help_runs_from_repo_root(self):
        completed = subprocess.run(
            [sys.executable, "scripts/run_headless_packet.py", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("run-headless-packet", completed.stdout)


def _write_text_grading_packet(root: Path) -> Path:
    transcripts = root / "transcripts"
    transcripts.mkdir()
    (transcripts / "S001.json").write_text(
        json.dumps(
            {
                "student_id": "S001",
                "answers": [
                    {
                        "question_id": "Q1",
                        "text": "The dominant term is n log n.",
                        "unclear": False,
                    },
                    {
                        "question_id": "Q2a",
                        "text": "Proof outline by induction.",
                        "unclear": False,
                    },
                    {
                        "question_id": "Q2b",
                        "text": "Therefore the conclusion follows.",
                        "unclear": False,
                    },
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    packet_root = root / "packets"
    with contextlib.redirect_stdout(io.StringIO()):
        code = main(
            [
                "build-text-grading-packet",
                "--course",
                str(FIXTURES / "course_dsaa3073_hw1.json"),
                "--packet-id",
                "G1-dev-r1",
                "--condition",
                "G1",
                "--prompt",
                str(FIXTURES / "grade_prompt.txt"),
                "--rubric",
                str(FIXTURES / "rubric_dsaa3073_hw1.json"),
                "--student-id",
                "S001",
                "--transcript-source",
                str(transcripts),
                "--output-root",
                str(packet_root),
                "--metadata",
                "split=development",
                "--metadata",
                "skill_version_id=skill_baseline_v1",
                "--metadata",
                "prompt_template_id=grade_standard_v1",
                "--metadata",
                "data_snapshot_hash=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            ]
        )
    if code != 0:
        raise AssertionError("failed to build synthetic text grading packet")
    return packet_root / "G1-dev-r1"


if __name__ == "__main__":
    unittest.main()
