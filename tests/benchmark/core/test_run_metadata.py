import unittest

from benchmark.core.run_metadata import (
    RUN_METADATA_REQUIRED_FIELDS,
    validate_run_metadata,
)


class RunMetadataTests(unittest.TestCase):
    def test_accepts_complete_reproducible_run_metadata(self):
        payload = {
            "api_key_source": "DEEPSEEK_API_KEY environment variable",
            "assessment_id": "week5_test",
            "command": "python -m benchmark.core.cli run-model-packet ...",
            "condition": "G1",
            "cost_estimate": {
                "currency": "USD",
                "estimated": True,
                "input_tokens": 100,
                "output_tokens": 50,
                "total_cost": None,
            },
            "course_id": "DSAA3071",
            "data_snapshot_hash": "a" * 64,
            "dry_run": True,
            "endpoint": "https://api.deepseek.com",
            "input_mode": "text-only",
            "max_retries": 2,
            "max_tokens": 4096,
            "model": "deepseek-v4-pro",
            "packet": "Data/DSAA3071/week5-benchmark-redaction-v3/packets/G1-dev-r1",
            "packet_hash": "b" * 64,
            "packet_id": "G1-dev-r1",
            "prompt_hash": "c" * 64,
            "prompt_template_id": "grade_candidate_v2_strict_schema",
            "provider": "deepseek",
            "record_type": "model_packet_run",
            "response_format": "json_object",
            "rubric_hash": "d" * 64,
            "run_commit": "e" * 40,
            "schema_version": 1,
            "skill_version_id": "skill_candidate_v2",
            "split": "development",
            "student_ids": ["S001"],
            "task": "grade",
            "temperature": None,
            "text_source_hash": "f" * 64,
            "top_p": None,
        }

        validate_run_metadata(payload)

        self.assertLessEqual(RUN_METADATA_REQUIRED_FIELDS, set(payload))

    def test_rejects_missing_reproducibility_anchor(self):
        payload = {
            field: "placeholder"
            for field in RUN_METADATA_REQUIRED_FIELDS
        }
        payload.update(
            {
                "cost_estimate": {"estimated": True},
                "dry_run": True,
                "max_retries": 0,
                "schema_version": 1,
                "student_ids": ["S001"],
            }
        )
        del payload["data_snapshot_hash"]

        with self.assertRaisesRegex(ValueError, "data_snapshot_hash"):
            validate_run_metadata(payload)


if __name__ == "__main__":
    unittest.main()
