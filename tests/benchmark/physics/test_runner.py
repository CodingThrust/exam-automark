import json
import tempfile
import unittest
from pathlib import Path

from benchmark.physics.runner import (
    ValidationFailure,
    create_run_directory,
    run_student_with_retries,
)
from benchmark.physics.schema import ProviderResult


class RunnerTests(unittest.TestCase):
    def test_insufficient_quota_is_terminal_without_retry(self):
        class QuotaError(Exception):
            status_code = 429
            code = "insufficient_quota"

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = create_run_directory(Path(tmp), "G1-dev-r1")
            calls = []

            def operation(attempt):
                calls.append(attempt)
                raise QuotaError("quota exhausted")

            result = run_student_with_retries(run_dir, "S001", operation)

            self.assertIsNone(result)
            self.assertEqual(calls, [1])
            failure = json.loads(
                (run_dir / "failures.jsonl").read_text(encoding="utf-8").strip()
            )
            self.assertEqual(failure["attempts"], 1)

    def test_run_directory_is_immutable_and_initializes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = create_run_directory(
                root,
                "G1-dev-r1",
                manifest={
                    "condition": "G1",
                    "split": "dev",
                    "repetition": 1,
                    "provider": "openai",
                    "model": "gpt-5.4",
                    "prompt_hash": "prompt",
                    "rubric_hash": "rubric",
                    "input_hashes": {"S001": "hash"},
                    "parameters": {"temperature": 0},
                },
            )

            self.assertTrue((run_dir / "manifest.json").exists())
            self.assertTrue((run_dir / "predictions.csv").exists())
            self.assertTrue((run_dir / "raw_responses.jsonl").exists())
            self.assertTrue((run_dir / "failures.jsonl").exists())
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                create_run_directory(root, "G1-dev-r1")

    def test_retryable_failures_then_success_record_three_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = create_run_directory(Path(tmp), "G1-dev-r1")
            calls = []

            def operation(attempt):
                calls.append(attempt)
                if attempt < 3:
                    raise TimeoutError("temporary timeout")
                return ProviderResult(
                    raw_text='{"student_id":"S001","scores":[]}',
                    model="gpt-5.4",
                    usage={"input_tokens": 3},
                )

            result = run_student_with_retries(run_dir, "S001", operation)

            self.assertEqual(result.raw_text, '{"student_id":"S001","scores":[]}')
            self.assertEqual(calls, [1, 2, 3])
            attempts = [
                json.loads(line)
                for line in (run_dir / "raw_responses.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual([row["status"] for row in attempts], ["retry", "retry", "ok"])

    def test_persistent_failure_records_missing_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = create_run_directory(Path(tmp), "D1-dev-r1")

            def operation(attempt):
                raise ConnectionError("network down")

            result = run_student_with_retries(run_dir, "S001", operation)

            self.assertIsNone(result)
            failures = [
                json.loads(line)
                for line in (run_dir / "failures.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(failures[0]["student_id"], "S001")
            self.assertEqual(failures[0]["status"], "missing")
            self.assertNotIn("score", failures[0])
            predictions = (run_dir / "predictions.csv").read_text(encoding="utf-8")
            self.assertNotIn("S001", predictions)

    def test_validation_failure_gets_one_repair_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = create_run_directory(Path(tmp), "G2-dev-r1")
            calls = []

            def operation(attempt):
                calls.append(attempt)
                if attempt == 1:
                    raise ValidationFailure("invalid score JSON")
                return ProviderResult(
                    raw_text='{"student_id":"S001","scores":[]}',
                    model="gpt-5.4",
                )

            result = run_student_with_retries(run_dir, "S001", operation)

            self.assertEqual(result.raw_text, '{"student_id":"S001","scores":[]}')
            self.assertEqual(calls, [1, 2])
            attempts = [
                json.loads(line)
                for line in (run_dir / "raw_responses.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual([row["status"] for row in attempts], ["repair", "ok"])

    def test_validation_failure_retains_invalid_raw_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = create_run_directory(Path(tmp), "G1-dev-r1")

            def operation(attempt):
                if attempt == 1:
                    invalid = ProviderResult(
                        raw_text="{not-json",
                        model="gpt-5.4",
                        usage={"output_tokens": 2},
                    )
                    raise ValidationFailure("invalid JSON", result=invalid)
                return ProviderResult(
                    raw_text='{"student_id":"S001","scores":[]}',
                    model="gpt-5.4",
                )

            run_student_with_retries(run_dir, "S001", operation)

            attempts = [
                json.loads(line)
                for line in (run_dir / "raw_responses.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(attempts[0]["status"], "repair")
            self.assertEqual(attempts[0]["raw_text"], "{not-json")
            self.assertEqual(attempts[0]["usage"], {"output_tokens": 2})


if __name__ == "__main__":
    unittest.main()
