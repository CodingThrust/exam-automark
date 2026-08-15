import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model_runner import (
    INPUT_MODES,
    DryRunTextProvider,
    ModelProviderResult,
    _append_jsonl,
    _compose_student_prompt,
    _structured_output_contract,
    _git_commit,
    _list_image_inputs,
    _load_text_inputs,
    _merge_usage,
    _parse_json_result,
    _utc_now,
    _validate_grade_payload,
    _write_json,
)
from .packets import directory_digest, validate_packet_output_contract
from .run_metadata import validate_run_metadata
from .schema import GRADING_OUTPUT_CONTRACT_V1, CourseSpec


SUPPORTED_HEADLESS_ENGINES = {"codex", "claude", "kimi"}

HEADLESS_GRADING_WRAPPER = """# Blind headless grading run

You are grading one anonymous student's answer in a reproducible headless run.
Use only the packet context included below. Do not inspect parent directories,
gold scores, previous run outputs, reports, or any file outside the packet.

Return exactly one JSON object matching the supplied output schema. Do not wrap
the JSON in Markdown. Preserve the anonymous student_id exactly.
"""

HEADLESS_MULTIMODAL_WRAPPER = """# Blind headless grading run (multimodal)

You are grading one anonymous student's scanned paper in a reproducible
headless run. Your working directory is the prompt packet.

The student's scanned paper pages are image files listed under input_images in
the packet context below, with paths relative to your working directory. Read
every listed image file with your file-reading tools and grade directly from
the page images. Do not inspect parent directories, gold scores, previous run
outputs, reports, or any other files.

Return exactly one JSON object matching the supplied output schema. Do not wrap
the JSON in Markdown. Preserve the anonymous student_id exactly.
"""

HEADLESS_TRANSCRIPTION_WRAPPER = """# Blind headless transcription run

You are transcribing one anonymous student's scanned paper in a reproducible
headless run. Your working directory is the prompt packet.

The student's scanned paper pages are image files listed under input_images in
the packet context below, with paths relative to your working directory. Read
every listed image file with your file-reading tools. Transcribe the student's
answer for every required question. Do not grade, correct, or infer an answer
that is not visible. Set unclear=true whenever the handwriting is uncertain.
Do not inspect parent directories, gold scores, previous run outputs, reports,
or any other files.

Return exactly one JSON object matching the supplied output schema. Do not wrap
the JSON in Markdown. Preserve the anonymous student_id exactly.
"""


class HeadlessCLIError(RuntimeError):
    """A local-only CLI failure carrying a privacy-safe aggregate category."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable


@dataclass(frozen=True)
class HeadlessPacketRunConfig:
    engine: str
    model: str
    input_mode: str
    packet: Path
    output: Path
    engine_bin: str | None = None
    max_retries: int = 0
    timeout_seconds: int = 600
    dry_run: bool = False
    command_argv: tuple[str, ...] = ()
    run_commit: str | None = None
    run_id: str | None = None
    experiment_condition: str | None = None


def run_headless_packet(config: HeadlessPacketRunConfig) -> dict[str, Any]:
    if config.engine not in SUPPORTED_HEADLESS_ENGINES:
        raise ValueError(f"unsupported headless engine: {config.engine}")
    if config.input_mode not in INPUT_MODES:
        raise ValueError(f"--input-mode must be one of {', '.join(INPUT_MODES)}")
    if config.max_retries < 0:
        raise ValueError("--max-retries must be non-negative")
    if config.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")
    if config.output.exists():
        raise FileExistsError(f"run output already exists: {config.output}")

    manifest = _read_json(config.packet / "manifest.json")
    task = manifest.get("task")
    if task is None and not (config.packet / "rubric.json").exists():
        # Physics T1 packets predate the task field but use the same strict
        # transcription schema and intentionally contain no grading rubric.
        task = "transcribe"
    if task not in {"grade", "transcribe"}:
        raise ValueError("run-headless-packet supports grade or transcribe packets")
    if task == "transcribe" and config.input_mode != "multimodal":
        raise ValueError("transcription packets require --input-mode multimodal")
    course = CourseSpec.from_dict(_read_json(config.packet / "course.json"))
    output_contract = validate_packet_output_contract(
        config.packet, manifest, course, str(task)
    )
    prompt_text = (config.packet / "prompt.txt").read_text(encoding="utf-8")
    rubric = (
        _read_json(config.packet / "rubric.json")
        if task == "grade"
        else None
    )
    student_ids = tuple(manifest.get("student_ids", ()))
    if not student_ids:
        raise ValueError("packet manifest has no student_ids")

    image_inputs: dict[str, list[str]] = {}
    text_inputs: dict[str, list[dict[str, str]]] = {}
    if config.input_mode == "multimodal":
        image_inputs = _list_image_inputs(config.packet, student_ids)
    else:
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
    for index, student_id in enumerate(student_ids):
        if task == "transcribe":
            prompt = _compose_headless_transcription_prompt(
                prompt_text,
                student_id,
                course,
                image_inputs[student_id],
            )
        elif config.input_mode == "multimodal":
            assert rubric is not None
            prompt = _compose_headless_multimodal_prompt(
                prompt_text,
                student_id,
                course,
                rubric,
                image_inputs[student_id],
                output_contract=output_contract,
            )
        else:
            assert rubric is not None
            prompt = _compose_headless_prompt(
                prompt_text,
                student_id,
                course,
                rubric,
                text_inputs[student_id],
                output_contract=output_contract,
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
            task=str(task),
            output_contract=output_contract,
        )
        if result["status"] == "passed":
            successful += 1
        validation_rows.append(result)
        if result.get("fatal"):
            for skipped_id in student_ids[index + 1 :]:
                validation_rows.append(
                    {
                        "student_id": skipped_id,
                        "status": "blocked",
                        "attempts": 0,
                        "error_type": "SkippedAfterSystemicCLIError",
                        "error_category": result["error_category"],
                    }
                )
            break

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
    *,
    output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
) -> str:
    return (
        HEADLESS_GRADING_WRAPPER.rstrip()
        + "\n\n## Packet grading prompt\n\n"
        + _compose_student_prompt(
            prompt_text,
            student_id,
            course,
            rubric,
            inputs,
            output_contract=output_contract,
        )
    )


def _compose_headless_multimodal_prompt(
    prompt_text: str,
    student_id: str,
    course: CourseSpec,
    rubric: dict[str, Any],
    image_paths: list[str],
    *,
    output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
) -> str:
    context = {
        "student_id": student_id,
        "course": course.to_dict(),
        "rubric": rubric,
        "input_images": [f"inputs/{student_id}/{path}" for path in image_paths],
    }
    return (
        HEADLESS_MULTIMODAL_WRAPPER.rstrip()
        + "\n\n## Packet grading prompt\n\n"
        + prompt_text.rstrip()
        + f"\n\nOutput student_id must be {student_id}."
        + "\nRequired response contract:\n"
        + _structured_output_contract(
            course,
            student_id,
            "grade",
            output_contract=output_contract,
        )
        + "\nPacket context:\n"
        + json.dumps(context, ensure_ascii=True, sort_keys=True)
    )

def _compose_headless_transcription_prompt(
    prompt_text: str,
    student_id: str,
    course: CourseSpec,
    image_paths: list[str],
) -> str:
    context = {
        "student_id": student_id,
        "course": course.to_dict(),
        "input_images": [f"inputs/{student_id}/{path}" for path in image_paths],
        "required_question_ids": list(course.question_ids),
    }
    return (
        HEADLESS_TRANSCRIPTION_WRAPPER.rstrip()
        + "\n\n## Packet transcription prompt\n\n"
        + prompt_text.rstrip()
        + f"\n\nOutput student_id must be {student_id}."
        + "\nPacket context:\n"
        + json.dumps(context, ensure_ascii=True, sort_keys=True)
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
    task: str = "grade",
    output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
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
                if task == "transcribe":
                    response = ModelProviderResult(
                        raw_text=json.dumps(
                            {
                                "student_id": student_id,
                                "answers": [
                                    {
                                        "question_id": question_id,
                                        "text": "dry-run transcript",
                                        "unclear": False,
                                    }
                                    for question_id in course.question_ids
                                ],
                            },
                            ensure_ascii=False,
                        ),
                        model=config.model,
                    )
                else:
                    provider = DryRunTextProvider(
                        config.model, output_contract=output_contract
                    )
                    response = provider.complete_text(
                        attempt_prompt,
                        student_id=student_id,
                        course=course,
                        task="grade",
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
            if task == "transcribe":
                _validate_transcript_payload(payload, student_id, course)
            else:
                _validate_grade_payload(
                    payload,
                    student_id,
                    course,
                    output_contract=output_contract,
                )
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
            nonretryable = isinstance(error, HeadlessCLIError) and not error.retryable
            status = (
                "failed"
                if nonretryable or attempt > config.max_retries
                else "retry"
            )
            error_category = _failure_category(error)
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
                    "error_category": error_category,
                    "error": str(error),
                },
            )
            if nonretryable:
                break

    assert last_error is not None
    _append_jsonl(
        failures,
        {
            "student_id": student_id,
            "status": "failed",
            "attempts": attempt,
            "timestamp": _utc_now(),
            "error_type": type(last_error).__name__,
            "error_category": _failure_category(last_error),
            "error": str(last_error),
        },
    )
    return {
        "student_id": student_id,
        "status": "failed",
        "attempts": attempt,
        "error_type": type(last_error).__name__,
        "error_category": _failure_category(last_error),
        "error": str(last_error),
        "fatal": isinstance(last_error, HeadlessCLIError),
    }

def _validate_transcript_payload(
    payload: dict[str, Any],
    student_id: str,
    course: CourseSpec,
) -> None:
    if set(payload) != {"student_id", "answers"}:
        raise ValueError("transcript output must contain only student_id and answers")
    if payload.get("student_id") != student_id:
        raise ValueError("student_id does not match the requested anonymous student")
    answers = payload.get("answers")
    if not isinstance(answers, list) or len(answers) != len(course.question_ids):
        raise ValueError("answers must contain exactly one row per required question")
    seen: list[str] = []
    for answer in answers:
        if not isinstance(answer, dict) or set(answer) != {
            "question_id",
            "text",
            "unclear",
        }:
            raise ValueError(
                "each transcript answer requires only question_id, text, and unclear"
            )
        question_id = answer.get("question_id")
        if question_id not in course.question_ids:
            raise ValueError(f"unknown transcript question_id: {question_id}")
        if not isinstance(answer.get("text"), str):
            raise ValueError("transcript text must be a string")
        if not isinstance(answer.get("unclear"), bool):
            raise ValueError("transcript unclear must be boolean")
        seen.append(str(question_id))
    if seen != list(course.question_ids):
        raise ValueError(
            "transcript answers must follow course question order without duplicates"
        )


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
    argv = _student_command_argv(config, last_message, prompt=prompt)
    argv = _resolve_executable_for_packet_cwd(config, argv)
    run_kwargs: dict[str, Any] = {
        "cwd": config.packet.resolve(),
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "timeout": config.timeout_seconds,
    }
    if config.engine == "kimi":
        # kimi takes the prompt as a --prompt argument; keep stdin closed.
        run_kwargs["stdin"] = subprocess.DEVNULL
    else:
        run_kwargs["input"] = prompt
    completed = subprocess.run(argv, **run_kwargs)
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
        detail = "\n".join((completed.stderr, completed.stdout))
        category = _cli_failure_category(detail)
        raise HeadlessCLIError(
            f"{config.engine} headless command failed with exit {completed.returncode}",
            category=category,
            retryable=category == "cli/runtime",
        )
    raw_text = _extract_headless_cli_raw_text(
        config.engine,
        completed.stdout,
        last_message,
    )
    return ModelProviderResult(raw_text=raw_text.strip(), model=config.model)


def _resolve_executable_for_packet_cwd(
    config: HeadlessPacketRunConfig,
    argv: list[str],
) -> list[str]:
    """Resolve the Windows Codex npm shim before changing into a packet.

    Python cannot execute a ``.cmd`` shim directly, and an elevated process may
    not inherit the user's npm path after changing into a junction-backed private
    packet.  Launch the npm-installed Codex JavaScript entry point through Node
    when it can be resolved.  The recorded reproduction command intentionally
    retains the canonical Codex command name.
    """

    if (
        config.engine != "codex"
        or os.name != "nt"
        or not argv
        or (
            Path(argv[0]).is_absolute()
            and Path(argv[0]).suffix.lower() != ".cmd"
        )
    ):
        return argv
    script = _windows_codex_npm_script(argv[0])
    node = _windows_node_executable()
    if script is None or node is None:
        return argv
    return [str(node), str(script), *argv[1:]]


def _windows_codex_npm_script(command: str) -> Path | None:
    """Return the JS entry point paired with a Windows npm ``codex.cmd`` shim."""

    candidates: list[Path] = []
    explicit = Path(command)
    if explicit.is_absolute():
        candidates.append(explicit)
    else:
        resolved = shutil.which(command)
        if resolved:
            candidates.append(Path(resolved))
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "npm" / command)
    for shim in candidates:
        if shim.suffix.lower() != ".cmd" or not shim.is_file():
            continue
        script = shim.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        if script.is_file():
            return script
    return None


def _windows_node_executable() -> Path | None:
    resolved = shutil.which("node.exe")
    if resolved:
        return Path(resolved)
    program_files = os.environ.get("ProgramFiles")
    if not program_files:
        return None
    candidate = Path(program_files) / "nodejs" / "node.exe"
    return candidate if candidate.is_file() else None


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
    prompt: str | None = None,
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
            "--skip-git-repo-check",
            "--cd",
            str(packet),
        ]
        if config.model:
            argv.extend(["--model", config.model])
        argv.append("-")
        return argv
    if config.engine == "kimi":
        argv = [config.engine_bin or "kimi"]
        if config.model:
            argv.extend(["--model", config.model])
        argv.extend(
            [
                "--output-format",
                "stream-json",
                "--prompt",
                prompt if prompt is not None else "<prompt>",
            ]
        )
        return argv
    max_turns = "12" if config.input_mode == "multimodal" else "1"
    tools = "Read" if config.input_mode == "multimodal" else ""
    return [
        config.engine_bin or "claude",
        "-p",
        "--output-format",
        "json",
        "--max-turns",
        max_turns,
        "--tools",
        tools,
        "--strict-mcp-config",
        "--model",
        config.model,
    ]


def _cli_failure_category(detail: str) -> str:
    lowered = detail.lower()
    if any(
        marker in lowered
        for marker in (
            "401",
            "403",
            "auth",
            "credential",
            "forbidden",
            "login",
            "not logged in",
            "permission denied",
            "unauthorized",
        )
    ):
        return "environment/authentication"
    if any(
        marker in lowered
        for marker in (
            "429",
            "quota",
            "rate limit",
            "rate-limit",
            "timed out",
            "timeout",
        )
    ):
        return "quota/timeout"
    return "cli/runtime"


def _failure_category(error: Exception) -> str:
    category = getattr(error, "category", None)
    if isinstance(category, str) and category:
        return category
    if isinstance(error, (json.JSONDecodeError, ValueError, TypeError, KeyError)):
        return "output-json/schema"
    if isinstance(error, (FileNotFoundError, IsADirectoryError, NotADirectoryError)):
        return "packet/input"
    if isinstance(error, subprocess.TimeoutExpired):
        return "quota/timeout"
    return "cli/runtime"


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
    if engine == "kimi":
        texts: list[str] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("role") != "assistant":
                continue
            content = event.get("content")
            if isinstance(content, str) and content.strip():
                texts.append(content)
            elif isinstance(content, list):
                joined = "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                ).strip()
                if joined:
                    texts.append(joined)
        if not texts:
            raise ValueError("Kimi CLI stream-json output had no assistant message")
        return texts[-1]

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
    data_snapshot_hash = (
        manifest_metadata.get("data_snapshot_hash")
        or manifest_metadata.get("input_snapshot_manifest_sha256")
    )
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
        "timeout_seconds": config.timeout_seconds,
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
        "experiment_condition": config.experiment_condition,
        "task": manifest.get("task")
        or ("transcribe" if not (config.packet / "rubric.json").exists() else "grade"),
        "split": manifest_metadata.get("split"),
        "skill_version_id": manifest_metadata.get("skill_version_id"),
        "prompt_template_id": manifest_metadata.get("prompt_template_id"),
        "data_snapshot_hash": data_snapshot_hash,
        "source_run_id": manifest_metadata.get("source_run_id"),
        "source_transcription_packet_hash": manifest_metadata.get(
            "source_transcription_packet_hash"
        ),
        "text_source_kind": manifest_metadata.get("text_source_kind"),
        "image_source_kind": manifest_metadata.get("image_source_kind"),
        "source_prompt_packet": manifest_metadata.get("source_prompt_packet"),
        "packet": config.packet.as_posix(),
        "packet_hash": directory_digest(config.packet),
        "output_contract": manifest.get(
            "output_contract",
            "transcript_v1"
            if manifest.get("task") == "transcribe"
            else GRADING_OUTPUT_CONTRACT_V1,
        ),
        "output_schema_hash": manifest.get("output_schema_hash"),
        "prompt_hash": manifest["prompt_hash"],
        "rubric_hash": manifest.get("rubric_hash"),
        "text_source_hash": directory_digest(config.packet / "inputs"),
        "student_ids": list(manifest.get("student_ids", ())),
        "run_commit": config.run_commit or _git_commit(),
        "run_id": config.run_id,
        "api_key_source": f"{config.engine}_cli_external_auth",
        "engine_binary": config.engine_bin or _default_engine_binary(config.engine),
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
    binary = config.engine_bin or _default_engine_binary(config.engine)
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


def _default_engine_binary(engine: str) -> str:
    if engine == "codex":
        return _default_codex_binary()
    if engine == "kimi":
        return "kimi"
    return "claude"


def _default_codex_binary() -> str:
    return "codex.cmd" if os.name == "nt" else "codex"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload
