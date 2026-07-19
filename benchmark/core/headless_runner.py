import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model_runner import (
    DryRunTextProvider,
    ModelProviderResult,
    _append_jsonl,
    _compose_student_prompt,
    _git_commit,
    _load_text_inputs,
    _merge_usage,
    _parse_json_result,
    _utc_now,
    _validate_grade_payload,
    _write_json,
)
from .packets import directory_digest
from .run_metadata import validate_run_metadata
from .schema import CourseSpec


SUPPORTED_HEADLESS_ENGINES = {"codex", "claude"}

HEADLESS_GRADING_WRAPPER = """# Blind headless grading run

You are grading one anonymous student's answer in a reproducible headless run.
Use only the packet context included below. Do not inspect parent directories,
gold scores, previous run outputs, reports, or any file outside the packet.

Return exactly one JSON object matching the supplied output schema. Do not wrap
the JSON in Markdown. Preserve the anonymous student_id exactly.
"""


@dataclass(frozen=True)
class HeadlessPacketRunConfig:
    engine: str
    model: str
    input_mode: str
    packet: Path
    output: Path
    engine_bin: str | None = None
    max_retries: int = 0
    dry_run: bool = False
    command_argv: tuple[str, ...] = ()
    run_commit: str | None = None


def run_headless_packet(config: HeadlessPacketRunConfig) -> dict[str, Any]:
    if config.engine not in SUPPORTED_HEADLESS_ENGINES:
        raise ValueError(f"unsupported headless engine: {config.engine}")
    if config.input_mode != "text-only":
        raise ValueError("headless packet runner currently supports text-only packets")
    if config.max_retries < 0:
        raise ValueError("--max-retries must be non-negative")
    if config.output.exists():
        raise FileExistsError(f"run output already exists: {config.output}")

    manifest = _read_json(config.packet / "manifest.json")
    if manifest.get("task") != "grade":
        raise ValueError("run-headless-packet currently supports grade packets only")
    course = CourseSpec.from_dict(_read_json(config.packet / "course.json"))
    prompt_text = (config.packet / "prompt.txt").read_text(encoding="utf-8")
    rubric = _read_json(config.packet / "rubric.json")
    student_ids = tuple(manifest.get("student_ids", ()))
    if not student_ids:
        raise ValueError("packet manifest has no student_ids")

    text_inputs = _load_text_inputs(config.packet, student_ids)
    config.output.mkdir(parents=True)
    for child in ("outputs", "headless-prompts", "last-messages", "cli-logs"):
        (config.output / child).mkdir()

    command = _write_command_records(config)
    raw_responses = config.output / "raw-responses.jsonl"
    failures = config.output / "failures.jsonl"
    raw_responses.write_text("", encoding="utf-8", newline="\n")
    failures.write_text("", encoding="utf-8", newline="\n")

    metadata = _metadata(config, manifest, command=command)
    validate_run_metadata(metadata)
    metadata["started_at"] = _utc_now()
    _write_json(config.output / "run-metadata.json", metadata)

    successful = 0
    validation_rows: list[dict[str, Any]] = []
    usage: dict[str, int | float] = {}
    for student_id in student_ids:
        prompt = _compose_headless_prompt(
            prompt_text,
            student_id,
            course,
            rubric,
            text_inputs[student_id],
        )
        (config.output / "headless-prompts" / f"{student_id}.prompt.txt").write_text(
            prompt,
            encoding="utf-8",
            newline="\n",
        )
        result = _run_student(
            config=config,
            course=course,
            prompt=prompt,
            student_id=student_id,
            raw_responses=raw_responses,
            failures=failures,
            usage=usage,
        )
        if result["status"] == "passed":
            successful += 1
        validation_rows.append(result)

    validation = {
        "status": "passed" if successful == len(student_ids) else "failed",
        "students_expected": len(student_ids),
        "students_passed": successful,
        "students_failed": len(student_ids) - successful,
        "rows": validation_rows,
    }
    _write_json(config.output / "validation.json", validation)
    _write_json(config.output / "usage.json", usage)
    metadata["ended_at"] = _utc_now()
    metadata["validation_status"] = validation["status"]
    metadata["usage"] = usage
    _write_json(config.output / "run-metadata.json", metadata)
    return {
        "output": str(config.output),
        "provider": _provider_name(config.engine),
        "model": config.model,
        "dry_run": config.dry_run,
        "validation_status": validation["status"],
        "students_passed": successful,
        "students_expected": len(student_ids),
    }


def _compose_headless_prompt(
    prompt_text: str,
    student_id: str,
    course: CourseSpec,
    rubric: dict[str, Any],
    inputs: list[dict[str, str]],
) -> str:
    return (
        HEADLESS_GRADING_WRAPPER.rstrip()
        + "\n\n## Packet grading prompt\n\n"
        + _compose_student_prompt(prompt_text, student_id, course, rubric, inputs)
    )


def _run_student(
    *,
    config: HeadlessPacketRunConfig,
    course: CourseSpec,
    prompt: str,
    student_id: str,
    raw_responses: Path,
    failures: Path,
    usage: dict[str, int | float],
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, config.max_retries + 2):
        raw_text = ""
        response: ModelProviderResult | None = None
        try:
            attempt_prompt = prompt
            if attempt > 1:
                attempt_prompt += (
                    "\nThe previous response failed validation. Return one corrected "
                    "JSON object only, following the required schema exactly."
                )
            if config.dry_run:
                provider = DryRunTextProvider(config.model)
                response = provider.complete_text(
                    attempt_prompt,
                    student_id=student_id,
                    course=course,
                )
            else:
                response = _complete_with_headless_cli(
                    config,
                    attempt_prompt,
                    student_id=student_id,
                    attempt=attempt,
                )
            raw_text = response.raw_text
            payload = _parse_json_result(raw_text)
            _validate_grade_payload(payload, student_id, course)
            _write_json(config.output / "outputs" / f"{student_id}.json", payload)
            _append_jsonl(
                raw_responses,
                {
                    "student_id": student_id,
                    "attempt": attempt,
                    "status": "ok",
                    "timestamp": _utc_now(),
                    "engine": config.engine,
                    "model": response.model,
                    "raw_text": raw_text,
                    "usage": response.usage,
                    "system_fingerprint": response.system_fingerprint,
                },
            )
            _merge_usage(usage, response.usage)
            return {"student_id": student_id, "status": "passed", "attempts": attempt}
        except Exception as error:
            last_error = error
            status = "retry" if attempt <= config.max_retries else "failed"
            _append_jsonl(
                raw_responses,
                {
                    "student_id": student_id,
                    "attempt": attempt,
                    "status": status,
                    "timestamp": _utc_now(),
                    "engine": config.engine,
                    "model": config.model,
                    "raw_text": raw_text,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )

    assert last_error is not None
    _append_jsonl(
        failures,
        {
            "student_id": student_id,
            "status": "failed",
            "attempts": config.max_retries + 1,
            "timestamp": _utc_now(),
            "error_type": type(last_error).__name__,
            "error": str(last_error),
        },
    )
    return {
        "student_id": student_id,
        "status": "failed",
        "attempts": config.max_retries + 1,
        "error_type": type(last_error).__name__,
        "error": str(last_error),
    }


def _complete_with_headless_cli(
    config: HeadlessPacketRunConfig,
    prompt: str,
    *,
    student_id: str,
    attempt: int,
) -> ModelProviderResult:
    last_message = (
        config.output / "last-messages" / f"{student_id}-a{attempt}.txt"
    ).resolve()
    argv = _student_command_argv(config, last_message)
    completed = subprocess.run(
        argv,
        input=prompt,
        cwd=config.packet.resolve(),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    (config.output / "cli-logs" / f"{student_id}-a{attempt}.stdout").write_text(
        completed.stdout,
        encoding="utf-8",
        newline="\n",
    )
    (config.output / "cli-logs" / f"{student_id}-a{attempt}.stderr").write_text(
        completed.stderr,
        encoding="utf-8",
        newline="\n",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{config.engine} headless command failed with exit {completed.returncode}"
        )
    raw_text = _extract_headless_cli_raw_text(
        config.engine,
        completed.stdout,
        last_message,
    )
    return ModelProviderResult(raw_text=raw_text.strip(), model=config.model)


def _write_command_records(config: HeadlessPacketRunConfig) -> str:
    argv = list(config.command_argv)
    if not argv:
        argv = [
            "run-headless-packet",
            "--engine",
            config.engine,
            "--model",
            config.model,
            "--input-mode",
            config.input_mode,
            "--packet",
            str(config.packet),
            "--output",
            str(config.output),
        ]
    command = "python -m benchmark.core.cli " + shlex.join(argv)
    _write_json(config.output / "command.argv.json", argv)
    (config.output / "command.txt").write_text(
        command + "\n\nHeadless CLI template:\n" + _template_command_text(config) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return command


def _template_command_text(config: HeadlessPacketRunConfig) -> str:
    last_message = Path("<run-output>/last-messages/<student_id>-a<attempt>.txt")
    return shlex.join(_student_command_argv(config, last_message, resolve_paths=False))


def _student_command_argv(
    config: HeadlessPacketRunConfig,
    last_message: Path,
    *,
    resolve_paths: bool = True,
) -> list[str]:
    packet = config.packet.resolve() if resolve_paths else config.packet
    schema = (
        (config.packet / "output.schema.json").resolve()
        if resolve_paths
        else config.packet / "output.schema.json"
    )
    message_path = last_message.resolve() if resolve_paths else last_message
    if config.engine == "codex":
        argv = [
            config.engine_bin or _default_codex_binary(),
            "exec",
            "--json",
            "--output-last-message",
            str(message_path),
            "--output-schema",
            str(schema),
            "--sandbox",
            "read-only",
            "--cd",
            str(packet),
        ]
        if config.model:
            argv.extend(["--model", config.model])
        argv.append("-")
        return argv
    return [
        config.engine_bin or "claude",
        "-p",
        "--output-format",
        "json",
        "--max-turns",
        "1",
        "--model",
        config.model,
    ]


def _extract_headless_cli_raw_text(
    engine: str,
    stdout: str,
    last_message: Path,
) -> str:
    if engine == "codex":
        return (
            last_message.read_text(encoding="utf-8")
            if last_message.exists()
            else stdout
        )

    payload = json.loads(stdout)
    if not isinstance(payload, dict):
        raise ValueError("Claude CLI JSON output must be an object")
    if payload.get("is_error") is True:
        raise ValueError(f"Claude CLI reported an error: {payload}")
    result = payload.get("result")
    if not isinstance(result, str):
        raise ValueError("Claude CLI JSON output missing string result")
    return result


def _metadata(
    config: HeadlessPacketRunConfig,
    manifest: dict[str, Any],
    *,
    command: str,
) -> dict[str, Any]:
    manifest_metadata = manifest.get("metadata", {})
    if not isinstance(manifest_metadata, dict):
        manifest_metadata = {}
    return {
        "schema_version": 1,
        "record_type": "model_packet_run",
        "provider": _provider_name(config.engine),
        "engine": config.engine,
        "model": config.model,
        "dry_run": config.dry_run,
        "input_mode": config.input_mode,
        "endpoint": f"{config.engine}_cli",
        "temperature": None,
        "top_p": None,
        "max_tokens": None,
        "response_format": "json_object",
        "max_retries": config.max_retries,
        "retry_policy": (
            "append JSON repair instruction after validation or CLI failure"
            if config.max_retries
            else "no retries"
        ),
        "command": command,
        "course_id": manifest.get("course_id"),
        "assessment_id": manifest.get("assessment_id"),
        "packet_id": manifest.get("packet_id"),
        "condition": manifest.get("condition"),
        "task": manifest.get("task"),
        "split": manifest_metadata.get("split"),
        "skill_version_id": manifest_metadata.get("skill_version_id"),
        "prompt_template_id": manifest_metadata.get("prompt_template_id"),
        "data_snapshot_hash": manifest_metadata.get("data_snapshot_hash"),
        "packet": config.packet.as_posix(),
        "packet_hash": directory_digest(config.packet),
        "prompt_hash": manifest["prompt_hash"],
        "rubric_hash": manifest.get("rubric_hash"),
        "text_source_hash": directory_digest(config.packet / "inputs"),
        "student_ids": list(manifest.get("student_ids", ())),
        "run_commit": config.run_commit or _git_commit(),
        "api_key_source": f"{config.engine}_cli_external_auth",
        "engine_binary": config.engine_bin or (
            _default_codex_binary() if config.engine == "codex" else "claude"
        ),
        "engine_version": None if config.dry_run else _engine_version(config),
        "cost_estimate": {
            "estimated": True,
            "currency": "provider_usage_or_api_billing",
            "input_tokens": None,
            "output_tokens": None,
            "total_cost": None,
        },
    }


def _engine_version(config: HeadlessPacketRunConfig) -> str | None:
    binary = config.engine_bin or (_default_codex_binary() if config.engine == "codex" else "claude")
    try:
        completed = subprocess.run(
            [binary, "--version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        return None
    text = (completed.stdout or completed.stderr).strip()
    return text or None


def _provider_name(engine: str) -> str:
    return f"{engine}_cli"


def _default_codex_binary() -> str:
    return "codex.cmd" if os.name == "nt" else "codex"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload
