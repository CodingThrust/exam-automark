import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from benchmark.core.cli import main
from benchmark.core.model_runner import (
    DeepSeekResponsesJsonSchemaProvider,
    ModelPacketRunConfig,
    OpenAICompatibleTextProvider,
    _compose_multimodal_prompt,
    _compose_student_prompt,
    _provider_from_config,
    _retry_validation_prompt_suffix,
    _submission_page_order,
    _validate_grade_payload,
)
from benchmark.core.schema import (
    GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
    CourseSpec,
    QuestionSpec,
)


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class ModelPacketRunnerTests(unittest.TestCase):
    def test_grade_payload_canonicalizes_total_from_capped_bonus_leaf_scores(self):
        course = CourseSpec(
            course_id="synthetic",
            assessment_id="quiz",
            questions=(
                QuestionSpec("Q1", 95, score_step=1),
                QuestionSpec("Q2", 5, score_step=1),
                QuestionSpec(
                    "Q2bonus",
                    10,
                    score_step=1,
                    parent_question_id="Q2",
                    allowed_scores=(0, 10),
                    is_bonus=True,
                ),
            ),
            base_total_points=100,
            final_score_cap=100,
        )
        payload = {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "Q1",
                    "extracted_evidence": "complete work",
                    "score": 95,
                    "evidence": "full credit",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q2",
                    "extracted_evidence": "complete work",
                    "score": 5,
                    "evidence": "full credit",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q2bonus",
                    "extracted_evidence": "second valid method",
                    "score": 10,
                    "evidence": "bonus condition met",
                    "confidence": "high",
                    "flags": [],
                },
            ],
            "total": 110,
        }

        _validate_grade_payload(payload, "S001", course)

        self.assertEqual(payload["total"], 100)

    def test_grade_payload_still_rejects_malformed_leaf_scores(self):
        course = CourseSpec(
            course_id="synthetic",
            assessment_id="quiz",
            questions=(
                QuestionSpec("Q1", 5, score_step=1),
                QuestionSpec(
                    "Q1bonus",
                    10,
                    score_step=1,
                    parent_question_id="Q1",
                    allowed_scores=(0, 10),
                    is_bonus=True,
                ),
            ),
            base_total_points=5,
            final_score_cap=5,
        )
        payload = {
            "student_id": "S001",
            "scores": [
                {
                    "question_id": "Q1",
                    "extracted_evidence": "complete work",
                    "score": 5,
                    "evidence": "full credit",
                    "confidence": "high",
                    "flags": [],
                },
                {
                    "question_id": "Q1bonus",
                    "extracted_evidence": "extra method",
                    "score": 9,
                    "evidence": "bonus condition met",
                    "confidence": "high",
                    "flags": [],
                },
            ],
            "total": 5,
        }

        with self.assertRaisesRegex(ValueError, "Q1bonus score"):
            _validate_grade_payload(payload, "S001", course)

    def test_text_prompt_inlines_cross_provider_scores_contract(self):
        course = CourseSpec.from_dict(
            json.loads((FIXTURES / "course_dsaa3073_hw1.json").read_text(encoding="utf-8"))
        )

        prompt = _compose_student_prompt(
            "Return JSON.",
            "S001",
            course,
            rubric={},
            inputs=[],
            task="grade",
        )

        self.assertIn("Required response contract", prompt)
        self.assertIn('"scores"', prompt)
        self.assertIn("Do not rename `scores` to `items`", prompt)
        self.assertIn("independently scored or transcribed leaf item", prompt)
        self.assertIn("input index, source-page number, or image filename", prompt)
        self.assertIn("Question order may vary by submission", prompt)
        self.assertIn('"student_id":"S001"', prompt)

    def test_deduction_trace_prompt_lists_the_only_allowed_deduction_types(self):
        course = CourseSpec.from_dict(
            json.loads((FIXTURES / "course_dsaa3073_hw1.json").read_text(encoding="utf-8"))
        )

        prompt = _compose_student_prompt(
            "Return JSON.",
            "S001",
            course,
            rubric={},
            inputs=[],
            task="grade",
            output_contract=GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
        )

        self.assertIn("Use deduction_type exactly as one of:", prompt)
        self.assertIn("incorrect_final_result", prompt)
        self.assertIn("Do not invent aliases.", prompt)

    def test_deduction_trace_retry_feedback_repeats_exact_deduction_invariant(self):
        suffix = _retry_validation_prompt_suffix(
            GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1
        )

        self.assertIn("deduction_trace=null", suffix)
        self.assertIn("sum exactly to max_score minus score", suffix)
        self.assertNotIn("student_id", suffix)

    def test_multimodal_prompt_repeats_page_locator_rule(self):
        course = CourseSpec.from_dict(
            json.loads((FIXTURES / "course_dsaa3073_hw1.json").read_text(encoding="utf-8"))
        )

        prompt = _compose_multimodal_prompt(
            "Return JSON.",
            "S001",
            course,
            rubric={},
            images=[{"path": "pages/p0001.png"}],
            task="grade",
            submission_scope=None,
        )

        self.assertIn("source-page number, and image filename are locators only", prompt)
        self.assertIn("Never infer a question_id from them", prompt)
        self.assertIn("Question order may vary by submission", prompt)

    def test_deepseek_provider_disables_thinking_via_extra_body(self):
        captured: dict[str, object] = {}

        class FakeCompletions:
            def create(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
                    model="deepseek-v4-pro",
                    usage=None,
                )

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.chat = SimpleNamespace(completions=FakeCompletions())

        provider = OpenAICompatibleTextProvider(
            model="deepseek-v4-pro",
            endpoint="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            display_name="DeepSeek",
            temperature=None,
            top_p=None,
            max_tokens=4096,
            response_format="json_object",
            request_extra_body={"thinking": {"type": "disabled"}},
        )
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}), patch.dict(
            sys.modules, {"openai": SimpleNamespace(OpenAI=FakeOpenAI)}
        ):
            provider.complete_text(
                "Return JSON.",
                student_id="S001",
                course=None,
                task="grade",
            )

        self.assertEqual(captured["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(captured["max_tokens"], 4096)

    def test_deepseek_responses_provider_binds_packet_schema_and_disables_thinking(self):
        captured: dict[str, object] = {}
        output_schema = {
            "type": "object",
            "properties": {"total": {"type": "number"}},
            "required": ["total"],
            "additionalProperties": False,
        }

        class FakeResponses:
            def create(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    status="completed",
                    output_text='{"total": 5}',
                    model="deepseek-v4-flash",
                    usage=None,
                )

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.responses = FakeResponses()

        provider = DeepSeekResponsesJsonSchemaProvider(
            model="deepseek-v4-flash",
            endpoint="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            display_name="DeepSeek",
            temperature=0,
            top_p=None,
            max_tokens=4096,
            output_schema=output_schema,
        )
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}), patch.dict(
            sys.modules, {"openai": SimpleNamespace(OpenAI=FakeOpenAI)}
        ):
            result = provider.complete_text(
                "Return JSON.",
                student_id="S001",
                course=None,
                task="grade",
            )

        self.assertEqual(result.raw_text, '{"total": 5}')
        self.assertEqual(captured["input"], "Return JSON.")
        self.assertEqual(captured["reasoning"], {"effort": "none"})
        self.assertEqual(captured["max_output_tokens"], 4096)
        self.assertEqual(
            captured["text"],
            {
                "format": {
                    "type": "json_schema",
                    "name": "grading_packet_output",
                    "schema": output_schema,
                }
            },
        )

    def test_deepseek_responses_schema_transport_rejects_other_providers(self):
        config = ModelPacketRunConfig(
            provider="kimi",
            model="kimi-k2.6",
            input_mode="text-only",
            packet=Path("packet"),
            output=Path("output"),
            transport="deepseek_responses_json_schema",
        )

        with self.assertRaisesRegex(ValueError, "requires provider deepseek"):
            _provider_from_config(config, output_schema={"type": "object"})

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

    def test_run_model_packet_records_deepseek_responses_schema_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self._build_grade_packet(root, "transcript.json", b'{"answer":"ok"}')
            output = root / "runs" / "deepseek-responses-schema-G1-dev-r1"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-model-packet",
                        "--provider",
                        "deepseek",
                        "--model",
                        "deepseek-v4-flash",
                        "--input-mode",
                        "text-only",
                        "--packet",
                        str(packet),
                        "--output",
                        str(output),
                        "--transport",
                        "deepseek_responses_json_schema",
                        "--dry-run",
                    ]
                )

            metadata = json.loads((output / "run-metadata.json").read_text(encoding="utf-8"))
            command_argv = json.loads((output / "command.argv.json").read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(metadata["transport"], "deepseek_responses_json_schema")
        self.assertEqual(metadata["response_format"], "json_schema")
        self.assertIn("--transport", command_argv)
        self.assertIn("deepseek_responses_json_schema", command_argv)

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

    def test_submission_metadata_rejects_page_question_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "S001"
            pages = input_dir / "pages"
            pages.mkdir(parents=True)
            (pages / "p0001.png").write_bytes(b"fixture image")
            metadata = input_dir / "submission.json"
            metadata.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "grading_unit": "anonymous_submission",
                        "student_id": "S001",
                        "missing_question_ids": [],
                        "pages": [
                            {
                                "source_page": 1,
                                "file": "pages/p0001.png",
                                "question_ids": ["Q1"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "not assign question IDs"):
                _submission_page_order(metadata, input_dir, "S001")

    def test_submission_metadata_accepts_a_junction_or_symlink_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            physical = root / "physical-inputs"
            student_dir = physical / "S001"
            pages = student_dir / "pages"
            pages.mkdir(parents=True)
            (pages / "p0001.png").write_bytes(b"fixture image")
            (student_dir / "submission.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "grading_unit": "anonymous_submission",
                        "student_id": "S001",
                        "missing_question_ids": [],
                        "pages": [{"source_page": 1, "file": "pages/p0001.png"}],
                    }
                ),
                encoding="utf-8",
            )
            logical = root / "logical-inputs"
            try:
                os.symlink(physical, logical, target_is_directory=True)
            except OSError as error:
                if os.name != "nt":
                    self.skipTest(f"directory symlinks are unavailable: {error}")
                junction = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(logical), str(physical)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if junction.returncode:
                    self.skipTest(
                        "directory links are unavailable: "
                        + (junction.stderr or junction.stdout).strip()
                    )

            from benchmark.core.model_runner import _submission_page_order

            self.assertEqual(
                _submission_page_order(
                    logical / "S001" / "submission.json",
                    logical / "S001",
                    "S001",
                ),
                ["pages/p0001.png"],
            )

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
