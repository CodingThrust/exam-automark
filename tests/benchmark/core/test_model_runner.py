import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.cli import main


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class ModelPacketRunnerTests(unittest.TestCase):
    def test_run_model_packet_dry_run_records_command_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self._build_grade_packet(root, "transcript.json", b'{"answer":"ok"}')
            output = root / "runs" / "deepseek-baseline-text-G1-dev-r1"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-model-packet",
                        "--provider",
                        "deepseek",
                        "--model",
                        "deepseek-test",
                        "--input-mode",
                        "text-only",
                        "--packet",
                        str(packet),
                        "--output",
                        str(output),
                        "--temperature",
                        "0",
                        "--response-format",
                        "json_object",
                        "--max-retries",
                        "1",
                        "--dry-run",
                    ]
                )

            result = json.loads(stdout.getvalue())
            metadata = json.loads((output / "run-metadata.json").read_text(encoding="utf-8"))
            validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
            command = (output / "command.txt").read_text(encoding="utf-8")
            argv = json.loads((output / "command.argv.json").read_text(encoding="utf-8"))
            response = json.loads((output / "outputs" / "S001.json").read_text(encoding="utf-8"))
            raw_responses = (output / "raw-responses.jsonl").read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(result["validation_status"], "passed")
        self.assertTrue(result["dry_run"])
        self.assertEqual(metadata["provider"], "deepseek")
        self.assertTrue(metadata["dry_run"])
        self.assertEqual(metadata["input_mode"], "text-only")
        self.assertEqual(metadata["max_retries"], 1)
        self.assertEqual(validation["students_passed"], 1)
        self.assertEqual(response["student_id"], "S001")
        self.assertIn("run-model-packet", command)
        self.assertIn("--dry-run", argv)
        self.assertNotIn("sk-", command)
        self.assertIn("raw_text", raw_responses)
        self.assertEqual(len(metadata["text_source_hash"]), 64)

    def test_run_model_packet_rejects_image_inputs_for_text_only_deepseek(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self._build_grade_packet(root, "page-001.jpg", b"fake image")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "run-model-packet",
                        "--provider",
                        "deepseek",
                        "--model",
                        "deepseek-test",
                        "--input-mode",
                        "text-only",
                        "--packet",
                        str(packet),
                        "--output",
                        str(root / "runs" / "image-run"),
                        "--dry-run",
                    ]
                )

        self.assertNotEqual(code, 0)
        self.assertIn("text-only runner cannot use image/PDF inputs", stderr.getvalue())

    def _build_grade_packet(self, root: Path, input_name: str, input_bytes: bytes) -> Path:
        input_root = root / "inputs"
        student_dir = input_root / "S001"
        student_dir.mkdir(parents=True)
        (student_dir / input_name).write_bytes(input_bytes)
        packet_root = root / "packets"
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
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

        self.assertEqual(code, 0)
        return packet_root / "G1-dev-r1"


if __name__ == "__main__":
    unittest.main()
