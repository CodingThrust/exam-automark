import csv
from pathlib import Path

from .schema import QUESTION_IDS


SCORE_FIELDS = (
    "student_id",
    "question_id",
    "score",
    "confidence",
    "evidence",
    "ambiguity_code",
)


def create_score_template(student_ids: list[str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
        writer.writeheader()
        for student_id in student_ids:
            for question_id in QUESTION_IDS:
                writer.writerow({"student_id": student_id, "question_id": question_id})


def validate_adjudication(row: dict[str, str]) -> None:
    primary = row["primary_score"].strip()
    reviewer = row["reviewer_score"].strip()
    if primary != reviewer:
        if not row["adjudicated_score"].strip() or not row["reason"].strip():
            raise ValueError("score disagreement requires adjudication and reason")
