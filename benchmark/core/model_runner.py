import base64
import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .model_policy import bind_model_release_policy
from .packets import directory_digest, validate_packet_output_contract
from .run_metadata import validate_run_metadata
from .rubrics import (
    execution_criterion_ids,
    execution_criterion_points,
    execution_scoring_gates,
)
from .schema import (
    CONFIDENCE_LEVELS,
    DEDUCTION_TYPES,
    GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1,
    GRADING_OUTPUT_CONTRACT_V1,
    CourseSpec,
    DeductionTrace,
    ScoreRecord,
    validate_score_records,
)


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
IMAGE_SUFFIXES = IMAGE_OR_DOCUMENT_SUFFIXES - {".pdf"}
IMAGE_MIME_TYPES = {
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}
INPUT_MODES = ("text-only", "multimodal")
TEXT_SUFFIXES = {".csv", ".json", ".md", ".text", ".txt"}
OPENAI_COMPATIBLE_PROVIDERS = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_endpoint": "https://api.deepseek.com",
        "display_name": "DeepSeek",
        "request_extra_body": {"thinking": {"type": "disabled"}},
    },
    "kimi": {
        "api_key_env": "MOONSHOT_API_KEY",
        "default_endpoint": "https://api.moonshot.ai/v1",
        "display_name": "Kimi",
    },
}


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
    endpoint: str | None = None
    max_retries: int = 0
    dry_run: bool = False
    command_argv: tuple[str, ...] = ()
    run_commit: str | None = None
    run_id: str | None = None
    model_release_policy: Path | None = None
    allow_provisional_model: bool = False


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
        task: str,
    ) -> ModelProviderResult:
        ...


class MultimodalModelProvider(Protocol):
    def complete_images(
        self,
        prompt: str,
        images: list[dict[str, Any]],
        *,
        student_id: str,
        course: CourseSpec,
        task: str,
    ) -> ModelProviderResult:
        ...


def run_model_packet(config: ModelPacketRunConfig) -> dict[str, Any]:
    packet = config.packet
    output = config.output
    if output.exists():
        raise FileExistsError(f"run output already exists: {output}")
    if config.provider not in OPENAI_COMPATIBLE_PROVIDERS:
        raise ValueError(f"unsupported provider: {config.provider}")
    if config.input_mode not in INPUT_MODES:
        raise ValueError(
            f"--input-mode must be one of {', '.join(INPUT_MODES)}"
        )
    if config.max_retries < 0:
        raise ValueError("--max-retries must be non-negative")
    model_policy_binding = (
        bind_model_release_policy(
            policy_path=config.model_release_policy,
            provider=config.provider,
            model=config.model,
            allow_provisional=config.allow_provisional_model,
        )
        if config.model_release_policy is not None
        else None
    )

    manifest = _read_json(packet / "manifest.json")
    task = manifest.get("task")
    if task not in {"grade", "transcribe"}:
        raise ValueError("packet task must be grade or transcribe")
    if task == "transcribe" and config.input_mode != "multimodal":
        raise ValueError("transcription packets require --input-mode multimodal")
    course = CourseSpec.from_dict(_read_json(packet / "course.json"))
    output_contract = validate_packet_output_contract(packet, manifest, course, task)
    prompt_text = (packet / "prompt.txt").read_text(encoding="utf-8")
    rubric = _read_json(packet / "rubric.json") if task == "grade" else None
    student_ids = tuple(manifest.get("student_ids", ()))
    if not student_ids:
        raise ValueError("packet manifest has no student_ids")

    text_inputs: dict[str, list[dict[str, str]]] = {}
    image_inputs: dict[str, list[dict[str, Any]]] = {}
    if config.input_mode == "multimodal":
        image_inputs = _load_image_inputs(packet, student_ids)
    else:
        text_inputs = _load_text_inputs(packet, student_ids)
    provider = _provider_from_config(config, output_contract=output_contract)
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

    metadata = _metadata(
        config,
        packet,
        manifest,
        command=command,
        model_policy_binding=model_policy_binding,
    )
    validate_run_metadata(metadata)
    metadata["started_at"] = _utc_now()
    _write_json(output / "run-metadata.json", metadata)

    for student_id in student_ids:
        images = None
        if config.input_mode == "multimodal":
            images = image_inputs[student_id]
            prompt = _compose_multimodal_prompt(
                prompt_text,
                student_id,
                course,
                rubric,
                images,
                task=task,
                submission_scope=_read_submission_scope(packet, student_id),
                output_contract=output_contract,
            )
        else:
            prompt = _compose_student_prompt(
                prompt_text,
                student_id,
                course,
                rubric,
                text_inputs[student_id],
                task=task,
                output_contract=output_contract,
            )
        success = _run_student(
            provider=provider,
            course=course,
            prompt=prompt,
            student_id=student_id,
            images=images,
            task=task,
            output=output,
            raw_responses=raw_responses,
            failures=failures,
            usage=usage,
            max_retries=config.max_retries,
            output_contract=output_contract,
            rubric=rubric,
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


def _provider_from_config(
    config: ModelPacketRunConfig,
    *,
    output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
) -> TextModelProvider | MultimodalModelProvider:
    if config.dry_run:
        return DryRunTextProvider(config.model, output_contract=output_contract)
    settings = _provider_settings(config.provider)
    return OpenAICompatibleTextProvider(
        model=config.model,
        endpoint=_provider_endpoint(config),
        api_key_env=settings["api_key_env"],
        display_name=settings["display_name"],
        temperature=config.temperature,
        top_p=config.top_p,
        max_tokens=config.max_tokens,
        response_format=config.response_format,
        request_extra_body=settings.get("request_extra_body"),
    )


class DryRunTextProvider:
    def __init__(
        self,
        model: str,
        *,
        output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
    ):
        self.model = model
        self.output_contract = output_contract

    def complete_text(
        self,
        prompt: str,
        *,
        student_id: str,
        course: CourseSpec,
        task: str,
    ) -> ModelProviderResult:
        if task == "transcribe":
            payload = {
                "student_id": student_id,
                "answers": [
                    {
                        "question_id": question.id,
                        "text": "dry-run placeholder",
                        "unclear": True,
                    }
                    for question in course.questions
                ],
            }
        else:
            traced = (
                self.output_contract
                == GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1
            )
            payload = {
                "student_id": student_id,
                "scores": [
                    _dry_run_score_row(question, traced=traced)
                    for question in course.questions
                ],
                "total": 0,
            }
        return ModelProviderResult(
            raw_text=json.dumps(payload, sort_keys=True),
            model=self.model,
            usage={"dry_run_prompt_chars": len(prompt)},
        )

    def complete_images(
        self,
        prompt: str,
        images: list[dict[str, Any]],
        *,
        student_id: str,
        course: CourseSpec,
        task: str,
    ) -> ModelProviderResult:
        result = self.complete_text(
            prompt, student_id=student_id, course=course, task=task
        )
        result.usage["dry_run_image_count"] = len(images)
        result.usage["dry_run_image_bytes"] = sum(len(image["data"]) for image in images)
        return result


def _dry_run_score_row(question: Any, *, traced: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "question_id": question.id,
        "extracted_evidence": "dry-run placeholder",
        "score": 0,
        "evidence": "Dry-run response; no model call was made.",
        "confidence": "low",
        "flags": ["dry_run"],
    }
    if traced:
        row["deduction_trace"] = [
            {
                "rubric_criterion": "synthetic dry-run contract check",
                "observed_evidence_or_missing_or_incorrect_part": (
                    "No student work is evaluated during a dry run."
                ),
                "deduction_type": "missing_required_evidence",
                "points_deducted": question.max_score,
            }
        ]
        row["attention_note"] = "Synthetic dry-run row; no model call was made."
    return row


class OpenAICompatibleTextProvider:
    def __init__(
        self,
        *,
        model: str,
        endpoint: str,
        api_key_env: str,
        display_name: str,
        temperature: float | None,
        top_p: float | None,
        max_tokens: int | None,
        response_format: str,
        request_extra_body: dict[str, Any] | None = None,
    ):
        self.model = model
        self.endpoint = endpoint
        self.api_key_env = api_key_env
        self.display_name = display_name
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.response_format = response_format
        self.request_extra_body = request_extra_body

    def complete_text(
        self,
        prompt: str,
        *,
        student_id: str,
        course: CourseSpec,
        task: str,
    ) -> ModelProviderResult:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise ValueError(
                f"{self.api_key_env} is required for non-dry {self.display_name} runs"
            )
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
        if self.request_extra_body is not None:
            request["extra_body"] = self.request_extra_body
        response = client.chat.completions.create(**request)
        message = response.choices[0].message.content
        return ModelProviderResult(
            raw_text=message or "",
            model=getattr(response, "model", self.model),
            usage=_usage_to_dict(getattr(response, "usage", None)),
        )

    def complete_images(
        self,
        prompt: str,
        images: list[dict[str, Any]],
        *,
        student_id: str,
        course: CourseSpec,
        task: str,
    ) -> ModelProviderResult:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise ValueError(
                f"{self.api_key_env} is required for non-dry {self.display_name} runs"
            )
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=self.endpoint)
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image in images:
            encoded = base64.b64encode(image["data"]).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image['mime']};base64,{encoded}"},
                }
            )
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "response_format": {"type": self.response_format},
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature
        if self.top_p is not None:
            request["top_p"] = self.top_p
        if self.max_tokens is not None:
            request["max_tokens"] = self.max_tokens
        if self.request_extra_body is not None:
            request["extra_body"] = self.request_extra_body
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


def _list_image_inputs(packet: Path, student_ids: tuple[str, ...]) -> dict[str, list[str]]:
    """Return packet-relative image paths per student, validating types.

    Snapshot-derived packets include a machine-readable ``submission.json`` that
    is not an image attachment.  When present, it is also the sole authority
    for page order; directory and filename sorting must not override it.
    """
    result: dict[str, list[str]] = {}
    for student_id in student_ids:
        input_dir = packet / "inputs" / student_id
        if not input_dir.is_dir():
            raise FileNotFoundError(f"input directory missing for: {student_id}")
        files = sorted(path for path in input_dir.rglob("*") if path.is_file())
        if not files:
            raise FileNotFoundError(f"no input files for: {student_id}")
        pdfs = [
            path.relative_to(input_dir).as_posix()
            for path in files
            if path.suffix.lower() == ".pdf"
        ]
        if pdfs:
            raise ValueError(
                "multimodal runner expects page images, not PDF, for "
                f"{student_id}: {', '.join(pdfs)}; convert each PDF page to an image first"
            )
        submission_metadata = input_dir / "submission.json"
        metadata_relative = "submission.json"
        if submission_metadata.is_file():
            ordered = _submission_page_order(submission_metadata, input_dir, student_id)
            actual_images = {
                path.relative_to(input_dir).as_posix()
                for path in files
                if path.suffix.lower() in IMAGE_SUFFIXES
            }
            if actual_images != set(ordered):
                raise ValueError(
                    "submission.json pages must match the packet image files for "
                    f"{student_id}"
                )
            unsupported = [
                path.relative_to(input_dir).as_posix()
                for path in files
                if path.relative_to(input_dir).as_posix() != metadata_relative
                and path.suffix.lower() not in IMAGE_SUFFIXES
            ]
        else:
            ordered = [
                path.relative_to(input_dir).as_posix()
                for path in files
                if path.suffix.lower() in IMAGE_SUFFIXES
            ]
            unsupported = [
                path.relative_to(input_dir).as_posix()
                for path in files
                if path.suffix.lower() not in IMAGE_SUFFIXES
            ]
        if unsupported:
            raise ValueError(
                "multimodal runner found non-image input files for "
                f"{student_id}: {', '.join(unsupported)}"
            )
        result[student_id] = ordered
    return result


def _submission_page_order(metadata_path: Path, input_dir: Path, student_id: str) -> list[str]:
    # ``candidate`` below is resolved before its confinement check.  Resolve the
    # root at the same boundary: on Windows a private Data directory can be
    # reached through a junction, and comparing a physical candidate with the
    # logical junction path otherwise rejects every valid page.
    input_dir = input_dir.resolve()
    try:
        payload = _read_json(metadata_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"submission.json is invalid for {student_id}") from error
    if payload.get("student_id") != student_id:
        raise ValueError(f"submission.json student_id mismatch for {student_id}")
    if payload.get("grading_unit") != "anonymous_submission":
        raise ValueError("submission.json must use anonymous_submission grading")
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("submission.json must contain ordered pages")
    prior_page = 0
    paths: list[str] = []
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("submission.json page must be an object")
        if "question_id" in page or "question_ids" in page:
            raise ValueError(
                "submission.json page must not assign question IDs; "
                "page order is not a question mapping"
            )
        source_page = page.get("source_page")
        relative = page.get("file")
        if type(source_page) is not int or source_page <= prior_page:
            raise ValueError("submission.json source pages must be positive and ordered")
        if not isinstance(relative, str) or not relative or "\\" in relative:
            raise ValueError("submission.json page file must be a POSIX relative path")
        candidate = (input_dir / relative).resolve()
        if not _is_within(candidate, input_dir) or candidate.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError("submission.json page file must name a packet image")
        normalized = candidate.relative_to(input_dir).as_posix()
        if normalized != relative or normalized in paths:
            raise ValueError("submission.json page file is invalid or duplicated")
        prior_page = source_page
        paths.append(normalized)
    return paths


def _read_submission_scope(packet: Path, student_id: str) -> dict[str, Any] | None:
    metadata_path = packet / "inputs" / student_id / "submission.json"
    if not metadata_path.is_file():
        return None
    input_dir = metadata_path.parent
    paths = _submission_page_order(metadata_path, input_dir, student_id)
    payload = _read_json(metadata_path)
    missing = payload.get("missing_question_ids", [])
    if not isinstance(missing, list) or not all(isinstance(item, str) for item in missing):
        raise ValueError("submission.json missing_question_ids must be text")
    return {
        "grading_unit": "anonymous_submission",
        "missing_question_ids": missing,
        "ordered_page_files": paths,
    }


def _load_image_inputs(
    packet: Path, student_ids: tuple[str, ...]
) -> dict[str, list[dict[str, Any]]]:
    image_paths = _list_image_inputs(packet, student_ids)
    result: dict[str, list[dict[str, Any]]] = {}
    for student_id, paths in image_paths.items():
        input_dir = packet / "inputs" / student_id
        result[student_id] = [
            {
                "path": relative,
                "mime": IMAGE_MIME_TYPES[(input_dir / relative).suffix.lower()],
                "data": (input_dir / relative).read_bytes(),
            }
            for relative in paths
        ]
    return result


def _compose_multimodal_prompt(
    prompt_text: str,
    student_id: str,
    course: CourseSpec,
    rubric: dict[str, Any] | None,
    images: list[dict[str, Any]],
    *,
    task: str,
    submission_scope: dict[str, Any] | None,
    output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
) -> str:
    context = {
        "student_id": student_id,
        "course": course.to_dict(),
        "input_images": [image["path"] for image in images],
    }
    if rubric is not None:
        context["rubric"] = rubric
    if submission_scope is not None:
        context["submission_scope"] = submission_scope
    task_instruction = (
        "Transcribe only visible work from these images; do not assign scores."
        if task == "transcribe"
        else "Grade from these images directly."
    )
    return (
        prompt_text.rstrip()
        + f"\n\nOutput student_id must be {student_id}."
        + "\nThe student's scanned paper pages are attached as images in the "
        "order listed under input_images. "
        + "Page-position rule: attachment order, input index, source-page number, "
        "and image filename are locators only, not question identifiers. Never "
        "infer a question_id from them. Question order may vary by submission; "
        "locate each question from visible labels, stems, and answer content "
        "across all supplied pages. "
        + task_instruction
        + "\nRequired response contract:\n"
        + _structured_output_contract(
            course, student_id, task, output_contract=output_contract
        )
        + _execution_contract_prompt_note(rubric)
        + "\nPacket context:\n"
        + json.dumps(context, ensure_ascii=True, sort_keys=True)
    )


def _compose_student_prompt(
    prompt_text: str,
    student_id: str,
    course: CourseSpec,
    rubric: dict[str, Any] | None,
    inputs: list[dict[str, str]],
    *,
    task: str = "grade",
    output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
) -> str:
    context = {
        "student_id": student_id,
        "course": course.to_dict(),
        "inputs": inputs,
    }
    if rubric is not None:
        context["rubric"] = rubric
    if task == "transcribe":
        context["task_instruction"] = "Transcribe only visible work; do not assign scores."
    return (
        prompt_text.rstrip()
        + f"\n\nOutput student_id must be {student_id}."
        + "\nPage-position rule: listed input pages are ordered evidence, not "
        "question identifiers. Never infer a question_id from an input index, "
        "source-page number, or image filename. Question order may vary by "
        "submission; locate each question from visible labels, stems, and answer "
        "content across all supplied pages."
        + "\nRequired response contract:\n"
        + _structured_output_contract(
            course, student_id, task, output_contract=output_contract
        )
        + _execution_contract_prompt_note(rubric)
        + "\nPacket context:\n"
        + json.dumps(context, ensure_ascii=True, sort_keys=True)
    )


def _structured_output_contract(
    course: CourseSpec,
    student_id: str,
    task: str,
    *,
    output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
) -> str:
    """Return an explicit cross-provider JSON field contract for one response."""
    if task == "transcribe":
        example: dict[str, Any] = {
            "student_id": student_id,
            "answers": [
                {"question_id": question_id, "text": "visible text", "unclear": False}
                for question_id in course.question_ids
            ],
        }
    else:
        traced = output_contract == GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1
        example = {
            "student_id": student_id,
            "scores": [
                _contract_score_row(question, traced=traced)
                for question in course.questions
            ],
            "total": 0,
        }
    trace_instruction = ""
    if task == "grade" and output_contract == GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1:
        trace_instruction = (
            " Every leaf row must include deduction_trace and attention_note. "
            "Use null for either field when it is not applicable. Every non-full-"
            "credit leaf must instead provide deduction_trace with one or more "
            "four-field entries; their points_deducted must sum exactly to that "
            "leaf's max_score minus score. Any row with flags or low confidence "
            "must instead provide a concise non-null attention_note. Deduction "
            "traces are audit statements, not hidden reasoning or chain-of-thought. "
            "Use deduction_type exactly as one of: "
            + ", ".join(sorted(DEDUCTION_TYPES))
            + ". Do not invent aliases."
        )
    return (
        "Return exactly one JSON object and no Markdown. Follow this structural "
        "example exactly: "
        + json.dumps(example, ensure_ascii=True, separators=(",", ":"))
        + ". Replace example values with the actual response. Use every listed "
        "question_id exactly once. Each listed question_id is one independently "
        "scored or transcribed leaf item; do not aggregate declared subparts. "
        "For grading, `total` must equal the sum of score rows after applying "
        "course.final_score_cap when that field is present. Do not rename `scores` "
        "to `items` or add alternative top-level fields."
        + trace_instruction
    )


def _contract_score_row(question: Any, *, traced: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "question_id": question.id,
        "extracted_evidence": "visible evidence",
        "score": 0,
        "evidence": "scoring rationale",
        "confidence": "medium",
        "flags": [],
    }
    if traced:
        row["deduction_trace"] = [
            {
                "rubric_criterion": "criterion label from the frozen rubric",
                "observed_evidence_or_missing_or_incorrect_part": (
                    "concise visible evidence or missing/incorrect part"
                ),
                "deduction_type": "missing_required_evidence",
                "points_deducted": question.max_score,
            }
        ]
    return row


def _execution_contract_prompt_note(rubric: dict[str, Any] | None) -> str:
    if not isinstance(rubric, dict) or rubric.get("rubric_format") != "execution_contract_v1":
        return ""
    return (
        "\nExecution-contract rule: score only the declared criteria. Ignore "
        "unrelated extra content unless it directly contradicts a declared "
        "criterion. For every deduction_trace, rubric_criterion must be the "
        "exact applicable criterion ID from this rubric."
    )


def _run_student(
    *,
    provider: TextModelProvider | MultimodalModelProvider,
    course: CourseSpec,
    prompt: str,
    student_id: str,
    images: list[dict[str, Any]] | None,
    task: str,
    output: Path,
    raw_responses: Path,
    failures: Path,
    usage: dict[str, int | float],
    max_retries: int,
    output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
    rubric: dict[str, Any] | None = None,
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
            if images is None:
                result = provider.complete_text(
                    attempt_prompt,
                    student_id=student_id,
                    course=course,
                    task=task,
                )
            else:
                result = provider.complete_images(
                    attempt_prompt,
                    images,
                    student_id=student_id,
                    course=course,
                    task=task,
                )
            payload = _parse_json_result(result.raw_text)
            if task == "grade":
                _validate_grade_payload(
                    payload,
                    student_id,
                    course,
                    output_contract=output_contract,
                    rubric=rubric,
                )
            else:
                _validate_transcript_payload(payload, student_id, course)
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


def _validate_grade_payload(
    payload: dict[str, Any],
    student_id: str,
    course: CourseSpec,
    *,
    output_contract: str = GRADING_OUTPUT_CONTRACT_V1,
    rubric: dict[str, Any] | None = None,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("grade output must be a JSON object")
    if output_contract == GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1:
        if set(payload) != {"student_id", "scores", "total"}:
            raise ValueError(
                "deduction-trace grade output requires only student_id, scores, and total"
            )
    if payload.get("student_id") != student_id:
        raise ValueError(f"student_id mismatch: expected {student_id}")
    scores = payload.get("scores")
    if not isinstance(scores, list):
        raise ValueError("scores must be a list")
    _normalize_full_credit_empty_deduction_traces(
        scores, course, output_contract=output_contract
    )
    records = []
    required_row_fields = {
        "question_id",
        "extracted_evidence",
        "score",
        "evidence",
        "confidence",
        "flags",
    }
    trace_optional_fields = {"deduction_trace", "attention_note"}
    for row in scores:
        if not isinstance(row, dict):
            raise ValueError("each score row must be an object")
        if output_contract == GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1:
            if not required_row_fields <= set(row):
                missing = sorted(required_row_fields - set(row))
                raise ValueError(
                    "deduction-trace score row missing field(s): " + ", ".join(missing)
                )
            unexpected = set(row) - required_row_fields - trace_optional_fields
            if unexpected:
                raise ValueError(
                    "deduction-trace score row has unexpected field(s): "
                    + ", ".join(sorted(unexpected))
                )
        if not isinstance(row.get("extracted_evidence"), str):
            raise ValueError("extracted_evidence must be text")
        if output_contract == GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1:
            if not row["extracted_evidence"].strip():
                raise ValueError("extracted_evidence must not be blank")
            if not isinstance(row.get("evidence"), str) or not row["evidence"].strip():
                raise ValueError("evidence must be non-blank text")
        flags = row.get("flags")
        if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
            raise ValueError("flags must be a list of strings")
        deduction_trace: list[DeductionTrace] = []
        raw_trace = row.get("deduction_trace")
        if raw_trace is not None:
            if not isinstance(raw_trace, list) or not raw_trace:
                raise ValueError("deduction_trace must be a non-empty list when present")
            for entry in raw_trace:
                if not isinstance(entry, dict) or set(entry) != {
                    "rubric_criterion",
                    "observed_evidence_or_missing_or_incorrect_part",
                    "deduction_type",
                    "points_deducted",
                }:
                    raise ValueError(
                        "each deduction_trace entry requires exactly the four contract fields"
                    )
                deduction_trace.append(
                    DeductionTrace(
                        rubric_criterion=entry["rubric_criterion"],
                        observed_evidence_or_missing_or_incorrect_part=entry[
                            "observed_evidence_or_missing_or_incorrect_part"
                        ],
                        deduction_type=entry["deduction_type"],
                        points_deducted=entry["points_deducted"],
                    )
                )
        attention_note = row.get("attention_note")
        if attention_note is not None and not isinstance(attention_note, str):
            raise ValueError("attention_note must be text")
        records.append(
            ScoreRecord(
                student_id=student_id,
                question_id=row["question_id"],
                score=float(row["score"]),
                confidence=row["confidence"],
                evidence=row["evidence"],
                flags=tuple(flags),
                deduction_trace=tuple(deduction_trace),
                attention_note=attention_note,
            )
        )
    total = validate_score_records(
        records,
        course,
        grading_output_contract=output_contract,
    )
    if rubric is not None and output_contract == GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1:
        for record in records:
            permitted_criteria = execution_criterion_ids(rubric, record.question_id)
            criterion_points = execution_criterion_points(rubric, record.question_id)
            scoring_gates = execution_scoring_gates(rubric, record.question_id)
            if permitted_criteria is None:
                continue
            traced_criteria: set[str] = set()
            for trace in record.deduction_trace:
                if trace.rubric_criterion not in permitted_criteria:
                    raise ValueError(
                        f"{record.question_id} deduction_trace rubric_criterion must be a declared criterion ID"
                    )
                if trace.rubric_criterion in traced_criteria:
                    raise ValueError(
                        f"{record.question_id} deduction_trace may not repeat a rubric criterion"
                    )
                traced_criteria.add(trace.rubric_criterion)
                if criterion_points is not None and abs(
                    float(trace.points_deducted)
                    - criterion_points[trace.rubric_criterion]
                ) > 1e-9:
                    raise ValueError(
                        f"{record.question_id} deduction_trace points_deducted must equal the declared criterion points"
                    )
            declared_gate_ids = set(scoring_gates or {})
            used_gate_ids = declared_gate_ids & traced_criteria
            if used_gate_ids:
                if len(used_gate_ids) != 1 or len(traced_criteria) != 1:
                    raise ValueError(
                        f"{record.question_id} scoring-gate deduction must be the only deduction_trace entry"
                    )
                gate_id = next(iter(used_gate_ids))
                gate = scoring_gates[gate_id]
                if abs(float(record.score) - float(gate["score_cap"])) > 1e-9:
                    raise ValueError(
                        f"{record.question_id} scoring-gate deduction requires score_cap"
                    )
                gate_trace = next(
                    trace
                    for trace in record.deduction_trace
                    if trace.rubric_criterion == gate_id
                )
                if gate_trace.deduction_type != gate["deduction_type"]:
                    raise ValueError(
                        f"{record.question_id} scoring-gate deduction_type must match the declared gate"
                    )
    if "total" not in payload:
        raise ValueError("total is required")
    # Leaf score rows have already passed the course-specific coverage, range,
    # step, evidence, confidence, and flags checks above.  The model-reported
    # total is therefore redundant: replace it with the deterministic course
    # total so final-score caps and bonus rules are applied consistently across
    # models.
    payload["total"] = total
    for row in payload["scores"]:
        if row["confidence"] not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {row['confidence']}")


def _normalize_full_credit_empty_deduction_traces(
    scores: list[Any],
    course: CourseSpec,
    *,
    output_contract: str,
) -> None:
    """Normalize a provider's empty-list spelling of a nullable full-credit trace.

    The strict v5.3 schema represents an inapplicable trace as ``null``. Some
    JSON-object providers still emit ``[]`` for a full-credit leaf. Converting
    that one syntactic variant before validation preserves the score and cannot
    hide a missing deduction: non-full leaves keep ``[]`` and are rejected.
    """

    if output_contract != GRADING_OUTPUT_CONTRACT_DEDUCTION_TRACE_V1:
        return
    question_map = course.question_map
    for row in scores:
        if not isinstance(row, dict) or row.get("deduction_trace") != []:
            continue
        question = question_map.get(row.get("question_id"))
        score = row.get("score")
        if (
            question is not None
            and isinstance(score, (int, float))
            and not isinstance(score, bool)
            and abs(float(score) - float(question.max_score)) <= 1e-9
        ):
            row["deduction_trace"] = None


def _validate_transcript_payload(
    payload: dict[str, Any], student_id: str, course: CourseSpec
) -> None:
    if payload.get("student_id") != student_id:
        raise ValueError(f"student_id mismatch: expected {student_id}")
    answers = payload.get("answers")
    if not isinstance(answers, list):
        raise ValueError("transcript answers must be a list")
    question_ids: list[str] = []
    for answer in answers:
        if not isinstance(answer, dict):
            raise ValueError("transcript answer must be an object")
        question_id = answer.get("question_id")
        if not isinstance(question_id, str):
            raise ValueError("transcript answer question_id must be text")
        if not isinstance(answer.get("text"), str):
            raise ValueError("transcript answer text must be text")
        if not isinstance(answer.get("unclear"), bool):
            raise ValueError("transcript answer unclear must be boolean")
        question_ids.append(question_id)
    if set(question_ids) != set(course.question_ids) or len(question_ids) != len(
        set(question_ids)
    ):
        raise ValueError("transcript question_ids must match the course exactly once")


def _metadata(
    config: ModelPacketRunConfig,
    packet: Path,
    manifest: dict[str, Any],
    *,
    command: str,
    model_policy_binding: dict[str, str] | None = None,
) -> dict[str, Any]:
    manifest_metadata = manifest.get("metadata", {})
    if not isinstance(manifest_metadata, dict):
        manifest_metadata = {}
    data_snapshot_hash = (
        manifest_metadata.get("data_snapshot_hash")
        or manifest_metadata.get("input_snapshot_manifest_sha256")
    )
    metadata = {
        "schema_version": 1,
        "record_type": "model_packet_run",
        "provider": config.provider,
        "model": config.model,
        "dry_run": config.dry_run,
        "input_mode": config.input_mode,
        "endpoint": _provider_endpoint(config),
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
        "data_snapshot_hash": data_snapshot_hash,
        "source_run_id": manifest_metadata.get("source_run_id"),
        "text_source_kind": manifest_metadata.get("text_source_kind"),
        "source_transcription_packet_hash": manifest_metadata.get(
            "source_transcription_packet_hash"
        ),
        "packet": packet.as_posix(),
        "packet_hash": directory_digest(packet),
        "output_contract": manifest.get(
            "output_contract",
            "transcript_v1"
            if manifest.get("task") == "transcribe"
            else GRADING_OUTPUT_CONTRACT_V1,
        ),
        "output_schema_hash": manifest.get("output_schema_hash"),
        "prompt_hash": manifest["prompt_hash"],
        "rubric_hash": manifest.get("rubric_hash"),
        "text_source_hash": directory_digest(packet / "inputs"),
        "student_ids": list(manifest.get("student_ids", ())),
        "run_commit": config.run_commit or _git_commit(),
        "run_id": config.run_id,
        "api_key_source": (
            f"{_provider_settings(config.provider)['api_key_env']} environment variable"
        ),
        "cost_estimate": {
            "estimated": True,
            "currency": "USD",
            "input_tokens": None,
            "output_tokens": None,
            "total_cost": None,
        },
    }
    if model_policy_binding is not None:
        metadata.update(model_policy_binding)
    return metadata


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
        if config.run_id is not None:
            argv.extend(["--run-id", config.run_id])
        if config.model_release_policy is not None:
            argv.extend(["--model-release-policy", str(config.model_release_policy)])
        if config.allow_provisional_model:
            argv.append("--allow-provisional-model")
    command = "python -m benchmark.core.cli " + shlex.join(argv)
    _write_json(output / "command.argv.json", argv)
    (output / "command.txt").write_text(command + "\n", encoding="utf-8", newline="\n")
    return command


def _provider_settings(provider: str) -> dict[str, str]:
    try:
        return OPENAI_COMPATIBLE_PROVIDERS[provider]
    except KeyError as error:
        raise ValueError(f"unsupported provider: {provider}") from error


def _provider_endpoint(config: ModelPacketRunConfig) -> str:
    if config.endpoint:
        return config.endpoint
    return _provider_settings(config.provider)["default_endpoint"]


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


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
