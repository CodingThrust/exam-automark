import re
from typing import Any


HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")

RUN_METADATA_REQUIRED_FIELDS = {
    "api_key_source",
    "assessment_id",
    "command",
    "condition",
    "cost_estimate",
    "course_id",
    "data_snapshot_hash",
    "dry_run",
    "endpoint",
    "input_mode",
    "max_retries",
    "max_tokens",
    "model",
    "packet",
    "packet_hash",
    "packet_id",
    "prompt_hash",
    "prompt_template_id",
    "provider",
    "record_type",
    "response_format",
    "rubric_hash",
    "run_commit",
    "schema_version",
    "skill_version_id",
    "split",
    "student_ids",
    "task",
    "temperature",
    "text_source_hash",
    "top_p",
}

HASH_FIELDS = {
    "data_snapshot_hash",
    "packet_hash",
    "prompt_hash",
    "rubric_hash",
    "text_source_hash",
}


def validate_run_metadata(payload: dict[str, Any]) -> None:
    missing = sorted(RUN_METADATA_REQUIRED_FIELDS - set(payload))
    if missing:
        raise ValueError(f"run metadata missing required field(s): {', '.join(missing)}")
    if payload["record_type"] != "model_packet_run":
        raise ValueError("record_type must be model_packet_run")
    if payload["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if not isinstance(payload["dry_run"], bool):
        raise ValueError("dry_run must be boolean")
    if not isinstance(payload["max_retries"], int) or payload["max_retries"] < 0:
        raise ValueError("max_retries must be a non-negative integer")
    if not isinstance(payload["student_ids"], list) or not payload["student_ids"]:
        raise ValueError("student_ids must be a non-empty list")
    if not all(isinstance(student_id, str) for student_id in payload["student_ids"]):
        raise ValueError("student_ids must contain only strings")
    if not isinstance(payload["cost_estimate"], dict):
        raise ValueError("cost_estimate must be an object")
    for field in HASH_FIELDS:
        value = payload[field]
        if value is not None and HEX_SHA256.fullmatch(str(value)) is None:
            raise ValueError(f"{field} must be a SHA-256 hex digest or null")
    run_commit = payload["run_commit"]
    if run_commit is not None and GIT_COMMIT.fullmatch(str(run_commit)) is None:
        raise ValueError("run_commit must be a short or full lowercase git commit")
