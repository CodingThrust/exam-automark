import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.cli import main


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class ModelPacketRunnerTests(unittest.TestCase):
    def test_build_text_grading_packet_can_feed_dry_run_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript_source = root / "transcripts" / "T1-dev-r1"
            self._write_transcript(transcript_source, "S001")
            packet_root = root / "text_packets"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
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
                        str(transcript_source),
                        "--output-root",
                        str(packet_root),
                        "--text-source-kind",
                        "transcript",
                        "--source-run-id",
                        "T1-dev-r1",
                        "--metadata",
                        "split=development",
                        "--metadata",
                        "input_snapshot_manifest_sha256=" + "a" * 64,
                        "--metadata",
                        "source_transcription_packet_hash=" + "b" * 64,
                    ]
                )

            result = json.loads(stdout.getvalue())
            packet = packet_root / "G1-dev-r1"
            manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(code, 0)
            self.assertEqual(result["packet_id"], "G1-dev-r1")
            self.assertEqual(manifest["metadata"]["input_mode"], "text-only")
            self.assertEqual(manifest["metadata"]["source_run_id"], "T1-dev-r1")
            self.assertEqual(manifest["metadata"]["split"], "development")
            self.assertEqual(len(manifest["metadata"]["text_source_hash"]), 64)
            self.assertTrue((packet / "inputs" / "S001" / "transcript.json").is_file())

            run_stdout = io.StringIO()
            with contextlib.redirect_stdout(run_stdout):
                run_code = main(
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
                        str(root / "runs" / "deepseek-text-G1-dev-r1"),
                        "--dry-run",
                    ]
                )
            run_metadata = json.loads(
                (root / "runs" / "deepseek-text-G1-dev-r1" / "run-metadata.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(run_code, 0)
        self.assertEqual(json.loads(run_stdout.getvalue())["validation_status"], "passed")
        self.assertEqual(run_metadata["data_snapshot_hash"], "a" * 64)
        self.assertEqual(run_metadata["source_run_id"], "T1-dev-r1")
        self.assertEqual(run_metadata["text_source_kind"], "transcript")
        self.assertEqual(run_metadata["source_transcription_packet_hash"], "b" * 64)

    def test_build_text_grading_packet_requires_each_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript_source = root / "transcripts"
            transcript_source.mkdir()
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
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
                        str(transcript_source),
                        "--output-root",
                        str(root / "text_packets"),
                    ]
                )

        self.assertNotEqual(code, 0)
        self.assertIn("transcript missing for: S001", stderr.getvalue())

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
                        "--run-id",
                        "G1-dev-r1",
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
        self.assertEqual(metadata["run_id"], "G1-dev-r1")
        self.assertEqual(validation["students_passed"], 1)
        self.assertEqual(response["student_id"], "S001")
        self.assertIn("run-model-packet", command)
        self.assertIn("--dry-run", argv)
        self.assertNotIn("sk-", command)
        self.assertIn("raw_text", raw_responses)
        self.assertEqual(len(metadata["text_source_hash"]), 64)

    def test_run_model_packet_supports_kimi_dry_run_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self._build_grade_packet(root, "transcript.json", b'{"answer":"ok"}')
            output = root / "runs" / "kimi-baseline-text-G1-dev-r1"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-model-packet",
                        "--provider",
                        "kimi",
                        "--model",
                        "kimi-k2.6",
                        "--input-mode",
                        "text-only",
                        "--packet",
                        str(packet),
                        "--output",
                        str(output),
                        "--dry-run",
                    ]
                )

            result = json.loads(stdout.getvalue())
            metadata = json.loads((output / "run-metadata.json").read_text(encoding="utf-8"))
            command = (output / "command.txt").read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(result["provider"], "kimi")
        self.assertEqual(result["model"], "kimi-k2.6")
        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual(metadata["provider"], "kimi")
        self.assertEqual(metadata["endpoint"], "https://api.moonshot.ai/v1")
        self.assertEqual(
            metadata["api_key_source"],
            "MOONSHOT_API_KEY environment variable",
        )
        self.assertNotIn("MOONSHOT_API_KEY=", command)
        self.assertNotIn("sk-", command)

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

    def test_run_model_packet_multimodal_dry_run_with_image_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self._build_grade_packet(root, "page-001.jpg", b"fake image")
            output = root / "runs" / "kimi-multimodal-G1-dev-r1"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-model-packet",
                        "--provider",
                        "kimi",
                        "--model",
                        "kimi-k3",
                        "--input-mode",
                        "multimodal",
                        "--packet",
                        str(packet),
                        "--output",
                        str(output),
                        "--dry-run",
                    ]
                )

            result = json.loads(stdout.getvalue())
            metadata = json.loads((output / "run-metadata.json").read_text(encoding="utf-8"))
            usage = json.loads((output / "usage.json").read_text(encoding="utf-8"))
            response = json.loads((output / "outputs" / "S001.json").read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual(result["model"], "kimi-k3")
        self.assertEqual(metadata["input_mode"], "multimodal")
        self.assertEqual(usage["dry_run_image_count"], 1)
        self.assertEqual(usage["dry_run_image_bytes"], len(b"fake image"))
        self.assertEqual(response["student_id"], "S001")

    def test_run_model_packet_multimodal_transcription_accepts_submission_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "inputs"
            student_dir = input_root / "S001"
            pages = student_dir / "pages"
            pages.mkdir(parents=True)
            (pages / "p0002.jpg").write_bytes(b"first page")
            (pages / "p0007.jpg").write_bytes(b"second page")
            (student_dir / "submission.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "grading_unit": "anonymous_submission",
                        "student_id": "S001",
                        "missing_question_ids": [],
                        "pages": [
                            {"source_page": 2, "file": "pages/p0002.jpg"},
                            {"source_page": 7, "file": "pages/p0007.jpg"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            packet_root = root / "packets"
            with contextlib.redirect_stdout(io.StringIO()):
                build_code = main(
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
                        str(FIXTURES / "grade_prompt.txt"),
                        "--student-id",
                        "S001",
                        "--input-root",
                        str(input_root),
                        "--output-root",
                        str(packet_root),
                    ]
                )
            output = root / "runs" / "kimi-T1-dev-r1"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                run_code = main(
                    [
                        "run-model-packet",
                        "--provider",
                        "kimi",
                        "--model",
                        "kimi-test",
                        "--input-mode",
                        "multimodal",
                        "--packet",
                        str(packet_root / "T1-dev-r1"),
                        "--output",
                        str(output),
                        "--dry-run",
                    ]
                )
            response = json.loads(
                (output / "outputs" / "S001.json").read_text(encoding="utf-8")
            )
            metadata = json.loads(
                (output / "run-metadata.json").read_text(encoding="utf-8")
            )

        self.assertEqual(build_code, 0)
        self.assertEqual(run_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["validation_status"], "passed")
        self.assertIn("answers", response)
        self.assertNotIn("scores", response)
        self.assertEqual(metadata["task"], "transcribe")

    def test_run_model_packet_multimodal_rejects_pdf_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self._build_grade_packet(root, "paper.pdf", b"fake pdf")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "run-model-packet",
                        "--provider",
                        "kimi",
                        "--model",
                        "kimi-k3",
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

    def test_run_model_packet_multimodal_rejects_text_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self._build_grade_packet(root, "transcript.json", b'{"answer":"ok"}')
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "run-model-packet",
                        "--provider",
                        "kimi",
                        "--model",
                        "kimi-k3",
                        "--input-mode",
                        "multimodal",
                        "--packet",
                        str(packet),
                        "--output",
                        str(root / "runs" / "text-run"),
                        "--dry-run",
                    ]
                )

        self.assertNotEqual(code, 0)
        self.assertIn("multimodal runner found non-image input files", stderr.getvalue())

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

    def _write_transcript(self, transcript_source: Path, student_id: str) -> None:
        transcript_source.mkdir(parents=True, exist_ok=True)
        payload = {
            "student_id": student_id,
            "answers": [
                {
                    "question_id": "Q1",
                    "text": "Asymptotic comparison answer.",
                    "unclear": False,
                },
                {
                    "question_id": "Q2a",
                    "text": "Proof outline answer.",
                    "unclear": False,
                },
                {
                    "question_id": "Q2b",
                    "text": "Conclusion answer.",
                    "unclear": False,
                },
            ],
        }
        (transcript_source / f"{student_id}.json").write_text(
            json.dumps(payload, sort_keys=True),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
