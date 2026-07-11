import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


CONFIDENCE_LEVELS = {"high", "medium", "low"}
INPUT_MODES = {"image", "pdf", "transcript", "text"}
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class QuestionSpec:
    id: str
    max_score: float
    score_step: float = 0.25
    title: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_token(self.id, "question id")
        _require_positive_number(self.max_score, "max_score")
        _require_positive_number(self.score_step, "score_step")
        if not _is_multiple(self.max_score, self.score_step):
            raise ValueError(f"{self.id} max_score must be a multiple of score_step")
        object.__setattr__(self, "tags", tuple(self.tags))

    def allows_score(self, score: float) -> bool:
        return 0 <= score <= self.max_score and _is_multiple(score, self.score_step)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QuestionSpec":
        return cls(
            id=payload["id"],
            max_score=float(payload["max_score"]),
            score_step=float(payload.get("score_step", 0.25)),
            title=payload.get("title"),
            tags=tuple(payload.get("tags", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "max_score": self.max_score,
            "score_step": self.score_step,
        }
        if self.title is not None:
            result["title"] = self.title
        if self.tags:
            result["tags"] = list(self.tags)
        return result


@dataclass(frozen=True)
class CourseSpec:
    course_id: str
    assessment_id: str
    questions: tuple[QuestionSpec, ...]
    input_modes: tuple[str, ...] = ("image", "transcript")
    anonymous_id_pattern: str = r"^S[0-9]{3}$"
    score_unit: str = "points"

    def __post_init__(self) -> None:
        _require_token(self.course_id, "course_id")
        _require_token(self.assessment_id, "assessment_id")
        if not self.questions:
            raise ValueError("course spec must define at least one question")
        question_ids = [question.id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("question ids must be unique")
        if not self.input_modes:
            raise ValueError("input_modes must not be empty")
        unsupported = sorted(set(self.input_modes) - INPUT_MODES)
        if unsupported:
            raise ValueError(f"unsupported input modes: {unsupported}")
        try:
            re.compile(self.anonymous_id_pattern)
        except re.error as error:
            raise ValueError("anonymous_id_pattern must be a valid regex") from error
        object.__setattr__(self, "questions", tuple(self.questions))
        object.__setattr__(self, "input_modes", tuple(self.input_modes))

    @property
    def question_ids(self) -> tuple[str, ...]:
        return tuple(question.id for question in self.questions)

    @property
    def max_total(self) -> float:
        return round(sum(question.max_score for question in self.questions), 10)

    @property
    def question_map(self) -> dict[str, QuestionSpec]:
        return {question.id: question for question in self.questions}

    def validate_student_id(self, student_id: str) -> None:
        if re.fullmatch(self.anonymous_id_pattern, student_id) is None:
            raise ValueError(f"invalid anonymous student id: {student_id}")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CourseSpec":
        return cls(
            course_id=payload["course_id"],
            assessment_id=payload["assessment_id"],
            questions=tuple(
                QuestionSpec.from_dict(question)
                for question in payload["questions"]
            ),
            input_modes=tuple(payload.get("input_modes", ("image", "transcript"))),
            anonymous_id_pattern=payload.get(
                "anonymous_id_pattern", r"^S[0-9]{3}$"
            ),
            score_unit=payload.get("score_unit", "points"),
        )

    @classmethod
    def from_json_path(cls, path: Path) -> "CourseSpec":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"course spec must be a JSON object: {path}")
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "course_id": self.course_id,
            "assessment_id": self.assessment_id,
            "questions": [question.to_dict() for question in self.questions],
            "input_modes": list(self.input_modes),
            "anonymous_id_pattern": self.anonymous_id_pattern,
            "score_unit": self.score_unit,
        }


@dataclass(frozen=True)
class SplitPlan:
    development_student_ids: tuple[str, ...]
    heldout_student_ids: tuple[str, ...]
    transcript_development_student_ids: tuple[str, ...] = ()
    transcript_heldout_student_ids: tuple[str, ...] = ()
    seed: int | None = None
    status: str = "draft"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "development_student_ids", tuple(self.development_student_ids)
        )
        object.__setattr__(self, "heldout_student_ids", tuple(self.heldout_student_ids))
        object.__setattr__(
            self,
            "transcript_development_student_ids",
            tuple(self.transcript_development_student_ids),
        )
        object.__setattr__(
            self,
            "transcript_heldout_student_ids",
            tuple(self.transcript_heldout_student_ids),
        )
        _reject_duplicates(self.development_student_ids, "development split")
        _reject_duplicates(self.heldout_student_ids, "held-out split")
        overlap = set(self.development_student_ids) & set(self.heldout_student_ids)
        if overlap:
            raise ValueError(f"development and held-out splits overlap: {sorted(overlap)}")
        all_students = set(self.development_student_ids) | set(self.heldout_student_ids)
        transcript_students = set(self.transcript_development_student_ids) | set(
            self.transcript_heldout_student_ids
        )
        outside = transcript_students - all_students
        if outside:
            raise ValueError(f"transcript subset is outside split: {sorted(outside)}")

    @property
    def all_student_ids(self) -> tuple[str, ...]:
        return self.development_student_ids + self.heldout_student_ids

    def validate_against_course(self, course: CourseSpec) -> None:
        for student_id in self.all_student_ids:
            course.validate_student_id(student_id)


@dataclass(frozen=True)
class ScoreRecord:
    student_id: str
    question_id: str
    score: float
    confidence: str
    evidence: str
    flags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {self.confidence}")
        if not isinstance(self.evidence, str):
            raise ValueError("evidence must be text")
        object.__setattr__(self, "flags", tuple(self.flags))


def validate_score_records(records: list[ScoreRecord], course: CourseSpec) -> float:
    if len(records) != len(course.questions):
        raise ValueError(
            f"expected exactly {len(course.questions)} score records, got {len(records)}"
        )
    student_ids = {record.student_id for record in records}
    if len(student_ids) != 1:
        raise ValueError("records must belong to one student")
    student_id = next(iter(student_ids))
    course.validate_student_id(student_id)

    question_ids = [record.question_id for record in records]
    if set(question_ids) != set(course.question_ids) or len(question_ids) != len(
        set(question_ids)
    ):
        raise ValueError("each course question must appear exactly once")

    question_map = course.question_map
    for record in records:
        question = question_map[record.question_id]
        if not question.allows_score(record.score):
            raise ValueError(f"{record.question_id} score is out of range or off step")
    return round(sum(record.score for record in records), 10)


def _require_token(value: str, label: str) -> None:
    if not isinstance(value, str) or TOKEN.fullmatch(value) is None:
        raise ValueError(f"{label} must be a non-empty safe token")


def _require_positive_number(value: float, label: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be positive")


def _is_multiple(value: float, step: float) -> bool:
    try:
        value_decimal = Decimal(str(value))
        step_decimal = Decimal(str(step))
    except InvalidOperation:
        return False
    if step_decimal <= 0:
        return False
    return value_decimal.remainder_near(step_decimal) == 0


def _reject_duplicates(values: tuple[str, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} contains duplicate student ids")
