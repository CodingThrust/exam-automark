import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.core.cli import main
from benchmark.core.headless_runner import (
    HeadlessCLIError,
    HeadlessPacketRunConfig,
    _cli_failure_category,
    _extract_headless_cli_raw_text,
    _metadata,
    _resolve_executable_for_packet_cwd,
    _student_command_argv,
)


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class HeadlessRunnerCliTests(unittest.TestCase):
    def test_metadata_uses_input_snapshot_manifest_hash_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet"
            packet.mkdir()
            (packet / "input.txt").write_text("synthetic", encoding="utf-8")
            config = HeadlessPacketRunConfig(
                engine="codex",
                model="gpt-5.6-codex",
                input_mode="text-only",
                packet=packet,
                output=Path(tmp) / "output",
                run_commit="abc1234",
            )
            manifest = {
                "course_id": "dsaa3073",
                "assessment_id": "hw1",
                "packet_id": "G1-dev-r1",
                "condition": "G1",
                "prompt_hash": "a" * 64,
                "rubric_hash": "b" * 64,
                "student_ids": ["S001"],
                "metadata": {
                    "input_snapshot_manifest_sha256": "c" * 64,
                    "source_transcription_packet_hash": "e" * 64,
                },
            }

            fallback = _metadata(config, manifest, command="synthetic")
            manifest["metadata"]["data_snapshot_hash"] = "d" * 64
            explicit = _metadata(config, manifest, command="synthetic")

        self.assertEqual(fallback["data_snapshot_hash"], "c" * 64)
        self.assertEqual(
            fallback["source_transcription_packet_hash"], "e" * 64
        )
        self.assertEqual(explicit["data_snapshot_hash"], "d" * 64)

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
                        "--experiment-condition",
                        "baseline",
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
        self.assertEqual(metadata["experiment_condition"], "baseline")
        self.assertEqual(metadata["timeout_seconds"], 600)
        self.assertEqual(metadata["api_key_source"], "codex_cli_external_auth")
        self.assertEqual(metadata["source_run_id"], "T1-dev-r1")
        self.assertEqual(metadata["text_source_kind"], "automatic_transcript")
        self.assertEqual(validation["students_passed"], 1)
        self.assertEqual(payload["student_id"], "S001")
        self.assertTrue(raw_responses_exists)
        self.assertIn("exec --json", command)
        self.assertIn("--output-schema", command)
        self.assertIn("--skip-git-repo-check", command)
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
        self.assertIn("--tools ''", command)
        self.assertIn("--strict-mcp-config", command)
        self.assertIn("--model claude-sonnet-4-20250514", command)
        self.assertNotIn("--output-schema", command)
        self.assertNotIn("codex.cmd exec", command)
        self.assertNotIn("DEEPSEEK_API_KEY", command)

    def test_claude_multimodal_command_allows_read_and_multiple_turns(self):
        config = HeadlessPacketRunConfig(
            engine="claude",
            model="sonnet",
            input_mode="multimodal",
            packet=Path("packet"),
            output=Path("output"),
        )

        argv = _student_command_argv(
            config,
            Path("last-message.txt"),
            resolve_paths=False,
        )

        self.assertEqual(argv[argv.index("--max-turns") + 1], "12")
        self.assertEqual(argv[argv.index("--tools") + 1], "Read")
        self.assertIn("--strict-mcp-config", argv)

    def test_cli_failure_category_separates_auth_quota_and_runtime(self):
        self.assertEqual(
            _cli_failure_category("HTTP 401: please login"),
            "environment/authentication",
        )
        self.assertEqual(
            _cli_failure_category("429 rate limit exceeded"),
            "quota/timeout",
        )
        self.assertEqual(
            _cli_failure_category("unexpected process exit"),
            "cli/runtime",
        )

    def test_windows_codex_command_shim_is_resolved_before_packet_cwd(self):
        config = HeadlessPacketRunConfig(
            engine="codex",
            model="gpt-5.6-sol",
            input_mode="multimodal",
            packet=Path("packet"),
            output=Path("output"),
        )
        argv = [r"C:\tools\codex.cmd", "exec", "--json"]

        with (
            patch("benchmark.core.headless_runner.os.name", "nt"),
            patch(
                "benchmark.core.headless_runner._windows_codex_npm_script",
                return_value=Path(r"C:\tools\codex.js"),
            ),
            patch(
                "benchmark.core.headless_runner._windows_node_executable",
                return_value=Path(r"C:\tools\node.exe"),
            ),
        ):
            actual = _resolve_executable_for_packet_cwd(config, argv)

        self.assertEqual(
            actual,
            [r"C:\tools\node.exe", r"C:\tools\codex.js", "exec", "--json"],
        )
        self.assertEqual(argv, [r"C:\tools\codex.cmd", "exec", "--json"])

    def test_nonretryable_auth_failure_stops_after_one_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = _write_text_grading_packet(root)
            output = root / "runs" / "kimi-auth-failure"
            stdout = io.StringIO()
            error = HeadlessCLIError(
                "kimi headless command failed with exit 1",
                category="environment/authentication",
                retryable=False,
            )

            with (
                patch(
                    "benchmark.core.headless_runner._complete_with_headless_cli",
                    side_effect=error,
                ) as complete,
                contextlib.redirect_stdout(stdout),
            ):
                code = main(
                    [
                        "run-headless-packet",
                        "--engine",
                        "kimi",
                        "--model",
                        "kimi-code/k3",
                        "--input-mode",
                        "text-only",
                        "--packet",
                        str(packet),
                        "--output",
                        str(output),
                        "--max-retries",
                        "2",
                    ]
                )
            validation = json.loads((output / "validation.json").read_text())

        self.assertEqual(code, 1)
        self.assertEqual(complete.call_count, 1)
        self.assertEqual(validation["rows"][0]["attempts"], 1)
        self.assertEqual(
            validation["rows"][0]["error_category"],
            "environment/authentication",
        )

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

    def test_kimi_headless_dry_run_records_stream_json_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = _write_text_grading_packet(root)
            output = root / "runs" / "kimi-synthetic-G1-dev-r1"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-headless-packet",
                        "--engine",
                        "kimi",
                        "--model",
                        "kimi-code/kimi-for-coding",
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
        self.assertEqual(result["provider"], "kimi_cli")
        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual(metadata["provider"], "kimi_cli")
        self.assertEqual(metadata["engine"], "kimi")
        self.assertEqual(metadata["engine_binary"], "kimi")
        self.assertEqual(metadata["api_key_source"], "kimi_cli_external_auth")
        self.assertEqual(validation["students_passed"], 1)
        self.assertIn("kimi --model kimi-code/kimi-for-coding", command)
        self.assertIn("--output-format stream-json", command)
        self.assertIn("--prompt '<prompt>'", command)
        self.assertNotIn("MOONSHOT_API_KEY", command)

    def test_kimi_stream_json_output_uses_last_assistant_message(self):
        stdout = "\n".join(
            [
                json.dumps({"role": "assistant", "content": "draft"}),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": "{\"student_id\":\"S001\",\"scores\":[]}",
                    }
                ),
                json.dumps(
                    {
                        "role": "meta",
                        "type": "session.resume_hint",
                        "content": "To resume this session: ...",
                    }
                ),
            ]
        )

        self.assertEqual(
            _extract_headless_cli_raw_text("kimi", stdout, Path("missing.txt")),
            "{\"student_id\":\"S001\",\"scores\":[]}",
        )

    def test_kimi_stream_json_output_requires_an_assistant_message(self):
        stdout = json.dumps({"role": "meta", "type": "session.resume_hint"})

        with self.assertRaisesRegex(ValueError, "no assistant message"):
            _extract_headless_cli_raw_text("kimi", stdout, Path("missing.txt"))

    def test_kimi_headless_multimodal_dry_run_references_image_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = _write_image_grading_packet(root, "page-001.jpg", b"fake image")
            output = root / "runs" / "kimi-multimodal-G1-dev-r1"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-headless-packet",
                        "--engine",
                        "kimi",
                        "--model",
                        "kimi-code/k3",
                        "--input-mode",
                        "multimodal",
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
            prompt = (output / "headless-prompts" / "S001.prompt.txt").read_text(
                encoding="utf-8"
            )

        self.assertEqual(code, 0)
        self.assertEqual(result["provider"], "kimi_cli")
        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual(metadata["input_mode"], "multimodal")
        self.assertIn("Blind headless grading run (multimodal)", prompt)
        self.assertIn("inputs/S001/page-001.jpg", prompt)
        self.assertNotIn("fake image", prompt)

    def test_headless_transcription_dry_run_writes_strict_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = _write_transcription_packet(root)
            output = root / "runs" / "kimi-transcription"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-headless-packet",
                        "--engine",
                        "kimi",
                        "--model",
                        "kimi-code/k3",
                        "--input-mode",
                        "multimodal",
                        "--packet",
                        str(packet),
                        "--output",
                        str(output),
                        "--dry-run",
                        "--run-commit",
                        "abc1234",
                        "--experiment-condition",
                        "transcription",
                    ]
                )
            payload = json.loads((output / "outputs" / "S001.json").read_text())
            metadata = json.loads((output / "run-metadata.json").read_text())
            prompt = (output / "headless-prompts" / "S001.prompt.txt").read_text(
                encoding="utf-8"
            )

        self.assertEqual(code, 0)
        self.assertEqual(metadata["task"], "transcribe")
        self.assertEqual(metadata["rubric_hash"], None)
        self.assertEqual(
            [answer["question_id"] for answer in payload["answers"]],
            ["Q1", "Q2a", "Q2b"],
        )
        self.assertTrue(all(answer["unclear"] is False for answer in payload["answers"]))
        self.assertIn("Blind headless transcription run", prompt)
        self.assertIn("Do not grade", prompt)

    def test_headless_multimodal_rejects_pdf_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = _write_image_grading_packet(root, "paper.pdf", b"fake pdf")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "run-headless-packet",
                        "--engine",
                        "kimi",
                        "--model",
                        "kimi-code/k3",
                        "--input-mode",
                        "multimodal",
                        "--packet",
                        str(packet),
                        "--output",
                        str(root / "runs" / "pdf-run"),
                        "--dry-run",
                    ]
                )

        self.assertNotEqual(code, 0)
        self.assertIn("multimodal runner expects page images, not PDF", stderr.getvalue())

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
                "--source-run-id",
                "T1-dev-r1",
                "--text-source-kind",
                "automatic_transcript",
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


def _write_image_grading_packet(root: Path, input_name: str, input_bytes: bytes) -> Path:
    input_root = root / "inputs"
    student_dir = input_root / "S001"
    student_dir.mkdir(parents=True)
    (student_dir / input_name).write_bytes(input_bytes)
    packet_root = root / "packets"
    with contextlib.redirect_stdout(io.StringIO()):
        code = main(
            [
                "build-packet",
                "--course",
                str(FIXTURES / "course_dsaa3073_hw1.json"),
                "--packet-id",
                "G1-dev-r1",
                "--condition",
                "G1",
                "--task",
                "grade",
                "--prompt",
                str(FIXTURES / "grade_prompt.txt"),
                "--rubric",
                str(FIXTURES / "rubric_dsaa3073_hw1.json"),
                "--student-id",
                "S001",
                "--input-root",
                str(input_root),
                "--output-root",
                str(packet_root),
            ]
        )
    if code != 0:
        raise AssertionError("failed to build synthetic image grading packet")
    return packet_root / "G1-dev-r1"


def _write_transcription_packet(root: Path) -> Path:
    input_root = root / "transcription-inputs"
    student_dir = input_root / "S001"
    student_dir.mkdir(parents=True)
    (student_dir / "page-001.jpg").write_bytes(b"fake image")
    packet_root = root / "transcription-packets"
    with contextlib.redirect_stdout(io.StringIO()):
        code = main(
            [
                "build-packet",
                "--course",
                str(FIXTURES / "course_dsaa3073_hw1.json"),
                "--packet-id",
                "T1-dev-r1",
                "--condition",
                "T1",
                "--task",
                "transcribe",
                "--prompt",
                str(FIXTURES / "transcribe_prompt.txt"),
                "--student-id",
                "S001",
                "--input-root",
                str(input_root),
                "--output-root",
                str(packet_root),
            ]
        )
    if code != 0:
        raise AssertionError("failed to build synthetic transcription packet")
    return packet_root / "T1-dev-r1"


if __name__ == "__main__":
    unittest.main()
