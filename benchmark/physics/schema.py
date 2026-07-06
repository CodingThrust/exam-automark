from dataclasses import dataclass, field
from typing import Any


QUESTION_MAX = {
    "Q1a": 2.0,
    "Q1b": 2.0,
    "Q1c": 3.0,
    "Q1d": 3.0,
    "Q2a": 7.0,
    "Q2b": 3.0,
    "Q3a": 1.5,
    "Q3b": 1.5,
    "Q3c": 1.5,
    "Q3d": 1.5,
    "Q3e": 2.0,
    "Q3f": 2.0,
}
QUESTION_IDS = tuple(QUESTION_MAX)
CONFIDENCE_LEVELS = {"high", "medium", "low"}


@dataclass(frozen=True)
class ScoreRecord:
    student_id: str
    question_id: str
    score: float
    confidence: str
    evidence: str
    flags: tuple[str, ...] = ()

    def __post_init__(self):
        if self.question_id not in QUESTION_MAX:
            raise ValueError(f"unknown question: {self.question_id}")
        if not 0 <= self.score <= QUESTION_MAX[self.question_id]:
            raise ValueError(f"{self.question_id} score is out of range")
        if round(self.score * 4) != self.score * 4:
            raise ValueError("score must use a quarter-point increment")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {self.confidence}")


@dataclass(frozen=True)
class TranscriptAnswer:
    question_id: str
    text: str
    unclear: bool = False


@dataclass(frozen=True)
class ProviderResult:
    raw_text: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    system_fingerprint: str | None = None


def validate_score_records(records: list[ScoreRecord]) -> float:
    if len(records) != len(QUESTION_IDS):
        raise ValueError("expected exactly 12 score records")
    question_ids = [record.question_id for record in records]
    if set(question_ids) != set(QUESTION_IDS) or len(question_ids) != len(
        set(question_ids)
    ):
        raise ValueError("each question must appear exactly once")
    student_ids = {record.student_id for record in records}
    if len(student_ids) != 1:
        raise ValueError("records must belong to one student")
    return round(sum(record.score for record in records), 2)
