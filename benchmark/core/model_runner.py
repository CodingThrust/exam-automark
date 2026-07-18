import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .packets import directory_digest
from .run_metadata import validate_run_metadata
from .schema import CONFIDENCE_LEVELS, CourseSpec, ScoreRecord, validate_score_records


IMAGE_OR_DOCUMENT_SUFFIXES = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
TEXT_SUFFIXES = {".csv", ".json", ".md", ".text", ".txt"}


@dataclass(frozen=True)
class ModelPacketRunConfig:
    provider: str
    model: str
    input_mode: str
    packet: Path
    output: Path
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    response_format: str = "json_object"
    endpoint: str = "https://api.deepseek.com"
    max_retries: int = 0
    dry_run: bool = False
    command_argv: tuple[str, ...] = ()
    run_commit: str | None = None


@dataclass(frozen=True)
class ModelProviderResult:
    raw_text: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    system_fingerprint: str | None = None


class TextModelProvider(Protocol):
    def complete_text(
        self,
        prompt: str,
        *,
        student_id: str,
        course: CourseSpec,
    ) -> ModelProviderResult:
        ...


def run_model_packet(config: ModelPacketRunConfig) -> dict[str, Any]:
    packet = config.packet
    output = config.output
    if output.exists():
        raise FileExistsError(f"run output already exists: {output}")
    if config.provider != "deepseek":
        raise ValueError(f"unsupported provider: {config.provider}")
    if config.input_mode != "text-only":
        raise ValueError("only --input-mode text-only is supported for DeepSeek")
    if config.max_retries < 0:
        raise ValueError("--max-retries must be non-negative")

    manifest = _read_json(packet / "manifest.json")
    if manifest.get("task") != "grade":
        raise ValueError("run-model-packet currently supports grade packets only")
    course = CourseSpec.from_dict(_read_json(packet / "course.json"))
    prompt_text = (packet / "prompt.txt").read_text(encoding="utf-8")
    rubric = _read_json(packet / "rubric.json")
    student_ids = tuple(manifest.get("student_ids", ()))
    if not student_ids:
        raise ValueError("packet manifest has no student_ids")

    text_inputs = _load_text_inputs(packet, student_ids)
    provider = _provider_from_config(config)
    output.mkdir(parents=True)
    (output / "outputs").mkdir()
    command = _write_command_records(output, config)

    raw_responses = output / "raw-responses.jsonl"
    failures = output / "failures.jsonl"
    raw_responses.write_text("", encoding="utf-8", newline="\n")
    failures.write_text("", encoding="utf-8", newline="\n")
    validation_rows: list[dict[str, Any]] = []
    usage: dict[str, int | float] = {}
    successful = 0

    metadata = _metadata(config, packet, manifest, command=command)
    validate_run_metadata(metadata)
    metadata["started_at"] = _utc_now()
    _write_json(output / "run-metadata.json", metadata)

    for student_id in student_ids:
        prompt = _compose_student_prompt(prompt_text, student_id, course, rubric, text_inputs[student_id])
        success = _run_student(
            provider=provider,
            course=course,
            prompt=prompt,
            student_id=student_id,
            output=output,
            raw_responses=raw_responses,
            failures=failures,
            usage=usage,
            max_retries=config.max_retries,
        )
        if success["status"] == "passed":
            successful += 1
        validation_rows.append(success)

    validation = {
        "status": "passed" if successful == len(student_ids) else "failed",
        "students_expected": len(student_ids),
        "students_passed": successful,
        "students_failed": len(student_ids) - successful,
        "rows": validation_rows,
    }
    _write_json(output / "validation.json", validation)
    _write_json(output / "usage.json", usage)
    metadata["ended_at"] = _utc_now()
    metadata["validation_status"] = validation["status"]
    metadata["usage"] = usage
    _write_json(output / "run-metadata.json", metadata)
    return {
        "output": str(output),
        "provider": config.provider,
        "model": config.model,
        "dry_run": config.dry_run,
        "validation_status": validation["status"],
        "students_passed": successful,
        "students_expected": len(student_ids),
    }


def _provider_from_config(config: ModelPacketRunConfig) -> TextModelProvider:
    if config.dry_run:
        return DryRunTextProvider(config.model)
    return DeepSeekTextProvider(
        model=config.model,
        endpoint=config.endpoint,
        temperature=config.temperature,
        top_p=config.top_p,
        max_tokens=config.max_tokens,
        response_format=config.response_format,
    )


class DryRunTextProvider:
    def __init__(self, model: str):
        self.model = model

    def complete_text(
        self,
        prompt: str,
        *,
        student_id: str,
        course: CourseSpec,
    ) -> ModelProviderResult:
        payload = {
            "student_id": student_id,
            "scores": [
                {
                    "question_id": question.id,
                    "extracted_evidence": "dry-run placeholder",
                    "score": 0,
                    "evidence": "Dry-run response; no model call was made.",
                    "confidence": "low",
                    "flags": ["dry_run"],
                }
                for question in course.questions
            ],
            "total": 0,
        }
        return ModelProviderResult(
            raw_text=json.dumps(payload, sort_keys=True),
            model=self.model,
            usage={"dry_run_prompt_chars": len(prompt)},
        )


class DeepSeekTextProvider:
    def __init__(
        self,
        *,
        model: str,
        endpoint: str,
        temperature: float | None,
        top_p: float | None,
        max_tokens: int | None,
        response_format: str,
    ):
        self.model = model
        self.endpoint = endpoint
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.response_format = response_format

    def complete_text(
        self,
        prompt: str,
        *,
        student_id: str,
        course: CourseSpec,
    ) -> ModelProviderResult:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for non-dry DeepSeek runs")
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=self.endpoint)
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": self.response_format},
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature
        if self.top_p is not None:
            request["top_p"] = self.top_p
        if self.max_tokens is not None:
            request["max_tokens"] = self.max_tokens
        response = client.chat.completions.create(**request)
        message = response.choices[0].message.content
        return ModelProviderResult(
            raw_text=message or "",
            model=getattr(response, "model", self.model),
            usage=_usage_to_dict(getattr(response, "usage", None)),
        )


def _load_text_inputs(packet: Path, student_ids: tuple[str, ...]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for student_id in student_ids:
        input_dir = packet / "inputs" / student_id
        if not input_dir.is_dir():
            raise FileNotFoundError(f"input directory missing for: {student_id}")
        files = sorted(path for path in input_dir.rglob("*") if path.is_file())
        if not files:
            raise FileNotFoundError(f"no input files for: {student_id}")
        blocked = [
            path.relative_to(input_dir).as_posix()
            for path in files
            if path.suffix.lower() in IMAGE_OR_DOCUMENT_SUFFIXES
        ]
        if blocked:
            raise ValueError(
                "text-only runner cannot use image/PDF inputs for "
                f"{student_id}: {', '.join(blocked)}"
            )
        unsupported = [
            path.relative_to(input_dir).as_posix()
            for path in files
            if path.suffix.lower() not in TEXT_SUFFIXES
        ]
        if unsupported:
            raise ValueError(
                "text-only runner found unsupported input files for "
                f"{student_id}: {', '.join(unsupported)}"
            )
        result[student_id] = [
            {
                "path": path.relative_to(input_dir).as_posix(),
                "text": path.read_text(encoding="utf-8"),
            }
            for path in files
        ]
    return result


def _compose_student_prompt(
    prompt_text: str,
    student_id: str,
    course: CourseSpec,
    rubric: dict[str, Any],
    inputs: list[dict[str, str]],
) -> str:
    context = {
        "student_id": student_id,
        "course": course.to_dict(),
        "rubric": rubric,
        "inputs": inputs,
    }
    return (
        prompt_text.rstrip()
        + f"\n\nOutput student_id must be {student_id}."
        + "\nPacket context:\n"
        + json.dumps(context, ensure_ascii=True, sort_keys=True)
    )


def _run_student(
    *,
    provider: TextModelProvider,
    course: CourseSpec,
    prompt: str,
    student_id: str,
    output: Path,
    raw_responses: Path,
    failures: Path,
    usage: dict[str, int | float],
    max_retries: int,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 2):
        result: ModelProviderResult | None = None
        try:
            attempt_prompt = prompt
            if attempt > 1:
                attempt_prompt += (
                    "\nThe previous response failed validation. Return one corrected "
                    "JSON object only, following the required schema exactly."
                )
            result = provider.complete_text(
                attempt_prompt,
                student_id=student_id,
                course=course,
            )
            payload = _parse_json_result(result.raw_text)
            _validate_grade_payload(payload, student_id, course)
            _write_json(output / "outputs" / f"{student_id}.json", payload)
            _append_jsonl(
                raw_responses,
                {
                    "student_id": student_id,
                    "attempt": attempt,
                    "status": "ok",
                    "timestamp": _utc_now(),
                    "model": result.model,
                    "raw_text": result.raw_text,
                    "usage": result.usage,
                    "system_fingerprint": result.system_fingerprint,
                },
            )
            _merge_usage(usage, result.usage)
            return {"student_id": student_id, "status": "passed", "attempts": attempt}
        except Exception as error:
            last_error = error
            status = "retry" if attempt <= max_retries else "failed"
            row: dict[str, Any] = {
                "student_id": student_id,
                "attempt": attempt,
                "status": status,
                "timestamp": _utc_now(),
                "error_type": type(error).__name__,
                "error": str(error),
            }
            if result is not None:
                row.update(
                    {
                        "model": result.model,
                        "raw_text": result.raw_text,
                        "usage": result.usage,
                        "system_fingerprint": result.system_fingerprint,
                    }
                )
            _append_jsonl(raw_responses, row)

    assert last_error is not None
    _append_jsonl(
        failures,
        {
            "student_id": student_id,
            "status": "failed",
            "attempts": max_retries + 1,
            "timestamp": _utc_now(),
            "error_type": type(last_error).__name__,
            "error": str(last_error),
        },
    )
    return {
        "student_id": student_id,
        "status": "failed",
        "attempts": max_retries + 1,
        "error_type": type(last_error).__name__,
        "error": str(last_error),
    }


def _validate_grade_payload(payload: dict[str, Any], student_id: str, course: CourseSpec) -> None:
    if payload.get("student_id") != student_id:
        raise ValueError(f"student_id mismatch: expected {student_id}")
    records = []
    for row in payload.get("scores", []):
        if not isinstance(row.get("extracted_evidence"), str):
            raise ValueError("extracted_evidence must be text")
        flags = row.get("flags")
        if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
            raise ValueError("flags must be a list of strings")
        records.append(
            ScoreRecord(
                student_id=student_id,
                question_id=row["question_id"],
                score=float(row["score"]),
                confidence=row["confidence"],
                evidence=row["evidence"],
                flags=tuple(flags),
            )
        )
    total = validate_score_records(records, course)
    if "total" not in payload or abs(float(payload["total"]) - total) > 1e-9:
        raise ValueError("total must equal the sum of question scores")
    for row in payload["scores"]:
        if row["confidence"] not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {row['confidence']}")


def _metadata(
    config: ModelPacketRunConfig,
    packet: Path,
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
        "provider": config.provider,
        "model": config.model,
        "dry_run": config.dry_run,
        "input_mode": config.input_mode,
        "endpoint": config.endpoint,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "response_format": config.response_format,
        "max_retries": config.max_retries,
        "retry_policy": (
            "append JSON repair instruction after validation or provider failure"
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
        "packet": packet.as_posix(),
        "packet_hash": directory_digest(packet),
        "prompt_hash": manifest["prompt_hash"],
        "rubric_hash": manifest.get("rubric_hash"),
        "text_source_hash": directory_digest(packet / "inputs"),
        "student_ids": list(manifest.get("student_ids", ())),
        "run_commit": config.run_commit or _git_commit(),
        "api_key_source": "DEEPSEEK_API_KEY environment variable",
        "cost_estimate": {
            "estimated": True,
            "currency": "USD",
            "input_tokens": None,
            "output_tokens": None,
            "total_cost": None,
        },
    }


def _write_command_records(output: Path, config: ModelPacketRunConfig) -> str:
    argv = list(config.command_argv)
    if not argv:
        argv = [
            "run-model-packet",
            "--provider",
            config.provider,
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
    _write_json(output / "command.argv.json", argv)
    (output / "command.txt").write_text(command + "\n", encoding="utf-8", newline="\n")
    return command


def _parse_json_result(raw_text: str) -> dict[str, Any]:
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("model response must be a JSON object")
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _merge_usage(total: dict[str, int | float], usage: dict[str, Any]) -> None:
    for key, value in usage.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total[key] = total.get(key, 0) + value


def _usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if hasattr(usage, "__dict__"):
        return dict(vars(usage))
    return {}


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
