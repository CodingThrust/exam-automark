import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import CONFIDENCE_LEVELS, CourseSpec


SUPPORTED_TASKS = {"transcribe", "grade"}
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
FORBIDDEN_PACKET_TERMS = (
    "gold",
    "grades.csv",
    "primary_scores",
    "reviewer_scores",
    "predictions.csv",
    "metrics",
    "reports",
    "student_map",
)
FORBIDDEN_TEXT_TERMS = tuple(
    term for term in FORBIDDEN_PACKET_TERMS if term != "reports"
)


PACKET_INSTRUCTIONS = """# Blind Grading Experiment Packet

Work only with files inside this packet. Do not inspect parent directories or
any other workspace. Read `prompt.txt`, `manifest.json`, `course.json`, and the
files under `inputs/`.

Write exactly one JSON file per expected anonymous student under `outputs/`,
named `<student_id>.json`. Preserve every anonymous ID exactly. Return data that
matches `output.schema.json`.
"""


@dataclass(frozen=True)
class PromptPacketSpec:
    course: CourseSpec
    packet_id: str
    condition: str
    task: str
    prompt_text: str
    student_ids: tuple[str, ...]
    input_root: Path
    output_root: Path
    rubric: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for label, value in (
            ("packet_id", self.packet_id),
            ("condition", self.condition),
            ("task", self.task),
        ):
            if not isinstance(value, str) or SAFE_TOKEN.fullmatch(value) is None:
                raise ValueError(f"{label} must be a safe token")
        if self.task not in SUPPORTED_TASKS:
            raise ValueError(f"unsupported packet task: {self.task}")
        if not self.prompt_text.strip():
            raise ValueError("prompt_text must not be blank")
        if not self.student_ids:
            raise ValueError("student_ids must not be empty")
        for student_id in self.student_ids:
            self.course.validate_student_id(student_id)
        if len(self.student_ids) != len(set(self.student_ids)):
            raise ValueError("student_ids must be unique")
        if self.task == "grade" and self.rubric is None:
            raise ValueError("grade packets require a rubric")
        object.__setattr__(self, "student_ids", tuple(self.student_ids))
        object.__setattr__(self, "input_root", Path(self.input_root))
        object.__setattr__(self, "output_root", Path(self.output_root))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class PromptPacketResult:
    packet_path: Path
    packet_hash: str
    manifest: dict[str, Any]


@dataclass(frozen=True)
class TextGradingPacketSpec:
    course: CourseSpec
    packet_id: str
    condition: str
    prompt_text: str
    student_ids: tuple[str, ...]
    transcript_source: Path
    output_root: Path
    rubric: dict[str, Any]
    text_source_kind: str = "transcript"
    source_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for label, value in (
            ("packet_id", self.packet_id),
            ("condition", self.condition),
            ("text_source_kind", self.text_source_kind),
        ):
            if not isinstance(value, str) or SAFE_TOKEN.fullmatch(value) is None:
                raise ValueError(f"{label} must be a safe token")
        if not self.prompt_text.strip():
            raise ValueError("prompt_text must not be blank")
        if not self.student_ids:
            raise ValueError("student_ids must not be empty")
        for student_id in self.student_ids:
            self.course.validate_student_id(student_id)
        if len(self.student_ids) != len(set(self.student_ids)):
            raise ValueError("student_ids must be unique")
        if self.source_run_id is not None and not self.source_run_id.strip():
            raise ValueError("source_run_id must not be blank")
        object.__setattr__(self, "student_ids", tuple(self.student_ids))
        object.__setattr__(self, "transcript_source", Path(self.transcript_source))
        object.__setattr__(self, "output_root", Path(self.output_root))
        object.__setattr__(self, "metadata", dict(self.metadata))


def build_prompt_packet(spec: PromptPacketSpec) -> PromptPacketResult:
    packet_path = spec.output_root / spec.packet_id
    if packet_path.exists():
        raise FileExistsError(f"packet already exists: {packet_path}")
    (packet_path / "inputs").mkdir(parents=True)
    (packet_path / "outputs").mkdir()

    for student_id in spec.student_ids:
        source = spec.input_root / student_id
        if not source.is_dir():
            raise FileNotFoundError(f"input directory missing for: {student_id}")
        shutil.copytree(source, packet_path / "inputs" / student_id)

    _write_json(packet_path / "course.json", spec.course.to_dict())
    (packet_path / "prompt.txt").write_text(
        _normalize_text(spec.prompt_text),
        encoding="utf-8",
        newline="\n",
    )
    (packet_path / "INSTRUCTIONS.md").write_text(
        PACKET_INSTRUCTIONS,
        encoding="utf-8",
        newline="\n",
    )

    schema = (
        transcript_output_schema(spec.course)
        if spec.task == "transcribe"
        else grading_output_schema(spec.course)
    )
    _write_json(packet_path / "output.schema.json", schema)

    rubric_hash = None
    if spec.rubric is not None:
        _write_json(packet_path / "rubric.json", spec.rubric)
        rubric_hash = _file_hash(packet_path / "rubric.json")

    manifest = {
        "schema_version": 1,
        "packet_id": spec.packet_id,
        "course_id": spec.course.course_id,
        "assessment_id": spec.course.assessment_id,
        "condition": spec.condition,
        "task": spec.task,
        "student_ids": list(spec.student_ids),
        "prompt_hash": _file_hash(packet_path / "prompt.txt"),
        "course_hash": _file_hash(packet_path / "course.json"),
        "output_schema_hash": _file_hash(packet_path / "output.schema.json"),
        "rubric_hash": rubric_hash,
        "input_hashes": {
            student_id: directory_digest(packet_path / "inputs" / student_id)
            for student_id in spec.student_ids
        },
        "metadata": spec.metadata,
    }
    _write_json(packet_path / "manifest.json", manifest)

    findings = audit_prompt_packet(packet_path)
    if findings:
        raise ValueError("prompt packet audit failed: " + "; ".join(findings))
    return PromptPacketResult(
        packet_path=packet_path,
        packet_hash=directory_digest(packet_path),
        manifest=manifest,
    )


def build_text_grading_packet(spec: TextGradingPacketSpec) -> PromptPacketResult:
    packet_path = spec.output_root / spec.packet_id
    if packet_path.exists():
        raise FileExistsError(f"packet already exists: {packet_path}")
    if not spec.transcript_source.is_dir():
        raise FileNotFoundError(f"transcript source missing: {spec.transcript_source}")

    (packet_path / "inputs").mkdir(parents=True)
    (packet_path / "outputs").mkdir()

    source_hashes = {}
    for student_id in spec.student_ids:
        source = _find_transcript_source(spec.transcript_source, student_id)
        payload = _read_transcript_payload(source, student_id, spec.course)
        destination = packet_path / "inputs" / student_id / "transcript.json"
        destination.parent.mkdir()
        _write_json(destination, payload)
        source_hashes[student_id] = _file_hash(source)

    _write_json(packet_path / "course.json", spec.course.to_dict())
    (packet_path / "prompt.txt").write_text(
        _normalize_text(spec.prompt_text),
        encoding="utf-8",
        newline="\n",
    )
    (packet_path / "INSTRUCTIONS.md").write_text(
        PACKET_INSTRUCTIONS,
        encoding="utf-8",
        newline="\n",
    )
    _write_json(packet_path / "output.schema.json", grading_output_schema(spec.course))
    _write_json(packet_path / "rubric.json", spec.rubric)

    metadata = dict(spec.metadata)
    metadata.update(
        {
            "input_mode": "text-only",
            "source_run_id": spec.source_run_id,
            "text_source_hash": directory_digest(packet_path / "inputs"),
            "text_source_input_hashes": source_hashes,
            "text_source_kind": spec.text_source_kind,
            "text_source_path": spec.transcript_source.as_posix(),
        }
    )

    manifest = {
        "schema_version": 1,
        "packet_id": spec.packet_id,
        "course_id": spec.course.course_id,
        "assessment_id": spec.course.assessment_id,
        "condition": spec.condition,
        "task": "grade",
        "student_ids": list(spec.student_ids),
        "prompt_hash": _file_hash(packet_path / "prompt.txt"),
        "course_hash": _file_hash(packet_path / "course.json"),
        "output_schema_hash": _file_hash(packet_path / "output.schema.json"),
        "rubric_hash": _file_hash(packet_path / "rubric.json"),
        "input_hashes": {
            student_id: directory_digest(packet_path / "inputs" / student_id)
            for student_id in spec.student_ids
        },
        "metadata": metadata,
    }
    _write_json(packet_path / "manifest.json", manifest)

    findings = audit_prompt_packet(packet_path)
    if findings:
        raise ValueError("prompt packet audit failed: " + "; ".join(findings))
    return PromptPacketResult(
        packet_path=packet_path,
        packet_hash=directory_digest(packet_path),
        manifest=manifest,
    )


def transcript_output_schema(course: CourseSpec) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "student_id": {
                "type": "string",
                "pattern": course.anonymous_id_pattern,
            },
            "answers": {
                "type": "array",
                "minItems": len(course.questions),
                "maxItems": len(course.questions),
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {
                            "type": "string",
                            "enum": list(course.question_ids),
                        },
                        "text": {"type": "string"},
                        "unclear": {"type": "boolean"},
                    },
                    "required": ["question_id", "text", "unclear"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["student_id", "answers"],
        "additionalProperties": False,
    }


def grading_output_schema(course: CourseSpec) -> dict[str, Any]:
    max_question_score = max(question.max_score for question in course.questions)
    return {
        "type": "object",
        "properties": {
            "student_id": {
                "type": "string",
                "pattern": course.anonymous_id_pattern,
            },
            "scores": {
                "type": "array",
                "minItems": len(course.questions),
                "maxItems": len(course.questions),
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {
                            "type": "string",
                            "enum": list(course.question_ids),
                        },
                        "extracted_evidence": {"type": "string"},
                        "score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": max_question_score,
                        },
                        "evidence": {"type": "string"},
                        "confidence": {
                            "type": "string",
                            "enum": sorted(CONFIDENCE_LEVELS),
                        },
                        "flags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "question_id",
                        "extracted_evidence",
                        "score",
                        "evidence",
                        "confidence",
                        "flags",
                    ],
                    "additionalProperties": False,
                },
            },
            "total": {
                "type": "number",
                "minimum": 0,
                "maximum": course.max_total,
            },
        },
        "required": ["student_id", "scores", "total"],
        "additionalProperties": False,
    }


def audit_prompt_packet(packet: Path) -> list[str]:
    findings = []
    text_suffixes = {".json", ".md", ".txt", ".csv"}
    for path in packet.rglob("*"):
        relative = path.relative_to(packet).as_posix().lower()
        for term in FORBIDDEN_PACKET_TERMS:
            if term.lower() in relative:
                findings.append(f"forbidden path term {term}: {relative}")
        if path.is_file() and path.suffix.lower() in text_suffixes:
            text = path.read_text(encoding="utf-8").lower()
            for term in FORBIDDEN_TEXT_TERMS:
                if term.lower() in text:
                    findings.append(f"forbidden text term {term}: {relative}")
    return sorted(set(findings))


def directory_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_transcript_source(root: Path, student_id: str) -> Path:
    candidates = (
        root / f"{student_id}.json",
        root / student_id / "transcript.json",
        root / student_id / f"{student_id}.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"transcript missing for: {student_id}")


def _read_transcript_payload(
    path: Path,
    student_id: str,
    course: CourseSpec,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"transcript must be a JSON object: {path}")
    if payload.get("student_id") != student_id:
        raise ValueError(f"transcript student_id mismatch for: {student_id}")
    answers = payload.get("answers")
    if not isinstance(answers, list):
        raise ValueError(f"transcript answers must be a list: {path}")
    question_ids = []
    for answer in answers:
        if not isinstance(answer, dict):
            raise ValueError(f"transcript answer must be an object: {path}")
        question_id = answer.get("question_id")
        if not isinstance(question_id, str):
            raise ValueError(f"transcript answer question_id missing: {path}")
        if not isinstance(answer.get("text"), str):
            raise ValueError(f"transcript answer text must be a string: {path}")
        if not isinstance(answer.get("unclear"), bool):
            raise ValueError(f"transcript answer unclear must be boolean: {path}")
        question_ids.append(question_id)
    if set(question_ids) != set(course.question_ids) or len(question_ids) != len(
        set(question_ids)
    ):
        raise ValueError(f"transcript questions do not match course spec: {path}")
    return {
        "student_id": student_id,
        "answers": [
            {
                "question_id": answer["question_id"],
                "text": answer["text"],
                "unclear": answer["unclear"],
            }
            for answer in answers
        ],
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
