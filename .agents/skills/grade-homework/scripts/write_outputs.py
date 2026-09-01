from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

from roster import (
    RosterEntry,
    RosterError,
    SAFE_SUBMISSION_ID,
    load_roster,
    require_private_path,
)


BASE_COLUMNS = ["student_id", "student_name", "student_number"]
TAIL_COLUMNS = ["total", "uncertainties", "flags"]
REVIEW_COLUMNS = [
    "student_id",
    "student_name",
    "student_number",
    "question_id",
    "score",
    "max_score",
    "confidence",
    "uncertainty",
    "flags",
]
ANNOTATION_KINDS = {"deduction", "praise", "review"}
DEDUCTION_TYPES = {
    "answer_only_cap",
    "blank_or_missing_answer",
    "contradiction",
    "incorrect_final_result",
    "insufficient_required_explanation",
    "local_arithmetic_or_notation_error",
    "material_method_error",
    "missing_required_evidence",
    "other_rubric_based",
    "unreadable_or_missing_evidence",
}
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?:^|\s)[A-Za-z]:[\\/]")
PRIVATE_DATA_PATH = re.compile(r"(?:^|[\\/])Data[\\/]", re.IGNORECASE)
FILE_URI = re.compile(r"\bfile://", re.IGNORECASE)
EMAIL_ADDRESS = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
IDENTITY_LABEL = re.compile(
    "\\b(?:student[ _-]?(?:id|number|name)|name)\\s*[:=]|(?:\\u59d3\\u540d|\\u5b66\\u53f7)\\s*[:\\uff1a]",
    re.IGNORECASE,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write private grading outputs.")
    parser.add_argument("grades_dir", type=Path)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--course-package", type=Path)
    parser.add_argument("--require-annotations", action="store_true")
    namespace = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    grades_dir = namespace.grades_dir

    try:
        require_private_path(grades_dir, label="grades directory")
        roster = load_roster(namespace.roster) if namespace.roster else None
        course_leaves = (
            _load_course_package(namespace.course_package)
            if namespace.course_package
            else None
        )
        record = json.loads(sys.stdin.read())
        normalized = _normalize_record(
            record,
            course_leaves=course_leaves,
            require_annotations=namespace.require_annotations,
        )
        roster_entry = _roster_entry(normalized["student_id"], roster)
    except Exception as error:
        print(f"invalid record: {error}", file=sys.stderr)
        return 2

    grades_dir.mkdir(parents=True, exist_ok=True)
    feedback_dir = grades_dir / "feedback"
    annotation_dir = grades_dir / "annotations"
    feedback_dir.mkdir(exist_ok=True)
    annotation_dir.mkdir(exist_ok=True)
    csv_path = grades_dir / "grades.csv"
    question_ids = (
        list(course_leaves)
        if course_leaves is not None
        else [item["question_id"] for item in normalized["scores"]]
    )
    header = BASE_COLUMNS + question_ids + TAIL_COLUMNS
    existing_rows = _read_existing_rows(csv_path)
    if existing_rows is not None:
        existing_header, rows = existing_rows
        if existing_header != header:
            print("CSV header mismatch; rubric changed mid-run", file=sys.stderr)
            return 4
        if any(row.get("student_id") == normalized["student_id"] for row in rows):
            print(json.dumps({"status": "skipped", "student_id": normalized["student_id"]}))
            return 0

    score_by_id = {item["question_id"]: item for item in normalized["scores"]}
    row = {
        "student_id": normalized["student_id"],
        "student_name": roster_entry.student_name if roster_entry else "",
        "student_number": roster_entry.student_number if roster_entry else "",
        "total": _format_score(normalized["total"]),
        "uncertainties": _uncertainty_cell(normalized),
        "flags": ";".join(normalized["flags"]),
    }
    for question_id in question_ids:
        row[question_id] = _format_score(score_by_id[question_id]["score"])

    _append_csv(csv_path, header, row)
    review_path = grades_dir / "review.csv"
    _append_review_rows(review_path, normalized, roster_entry)
    feedback_path = feedback_dir / f"{_safe_name(normalized['student_id'])}.md"
    feedback_path.write_text(_feedback_markdown(normalized), encoding="utf-8", newline="\n")
    annotation_path = annotation_dir / f"{_safe_name(normalized['student_id'])}.json"
    annotation_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "student_id": normalized["student_id"],
                "annotations": normalized["annotations"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": "written",
                "student_id": normalized["student_id"],
                "grades_csv": "grades.csv",
                "review_csv": "review.csv",
                "feedback": f"feedback/{feedback_path.name}",
                "annotations": f"annotations/{annotation_path.name}",
            },
            sort_keys=True,
        )
    )
    return 0


def _normalize_record(
    record: dict[str, Any],
    *,
    course_leaves: dict[str, dict[str, float]] | None,
    require_annotations: bool,
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")
    if "student_name" in record or "student_number" in record:
        raise ValueError("student names and numbers must come from the private roster")
    student_id = str(
        record.get("student_id") or record.get("submission_id") or record.get("student") or ""
    ).strip()
    if not student_id:
        raise ValueError("student_id is required")
    if not SAFE_SUBMISSION_ID.fullmatch(student_id):
        raise ValueError("student_id contains unsupported characters")
    scores = record.get("scores")
    if not isinstance(scores, list) or not scores:
        raise ValueError("scores must be a non-empty list")

    normalized_scores = []
    seen_question_ids: set[str] = set()
    flags = _normalized_flags(record.get("flags", []), label="record")
    for item in scores:
        if not isinstance(item, dict):
            raise ValueError("each score item must be an object")
        question_id = str(item.get("question_id", "")).strip()
        if not question_id:
            raise ValueError("question_id is required")
        if question_id in seen_question_ids:
            raise ValueError(f"duplicate question_id: {question_id}")
        seen_question_ids.add(question_id)
        score = float(item.get("score"))
        max_score = _positive_score(item.get("max_score"), "max_score", question_id)
        if score < 0 or score > max_score:
            raise ValueError(f"score is outside range for {question_id}")
        _validate_course_score(
            question_id=question_id,
            score=score,
            max_score=max_score,
            course_leaves=course_leaves,
        )
        confidence = str(item.get("confidence", "")).strip().lower()
        if confidence not in {"high", "medium", "low"}:
            raise ValueError(f"invalid confidence for {question_id}: {confidence}")
        item_flags = _normalized_flags(item.get("flags", []), label=question_id)
        deduction_trace = _normalize_deduction_trace(
            item.get("deduction_trace"),
            question_id=question_id,
            score=score,
            max_score=max_score,
            student_id=student_id,
        )
        attention_note = item.get("attention_note")
        if attention_note is not None:
            attention_note = _safe_trace_text(attention_note, "attention_note", student_id)
        if item_flags or confidence != "high":
            if attention_note is None:
                raise ValueError(
                    f"flags or non-high confidence require attention_note for {question_id}"
                )
        flags.extend(f"{question_id}:{flag}" for flag in item_flags)
        normalized_scores.append(
            {
                "question_id": question_id,
                "score": score,
                "max_score": max_score,
                "evidence": _safe_record_text(
                    item.get("evidence"), "evidence", student_id, required=True
                ),
                "feedback": _safe_record_text(
                    item.get("feedback", ""), "feedback", student_id, required=False
                ),
                "confidence": confidence,
                "flags": item_flags,
                "deduction_trace": deduction_trace,
                "attention_note": attention_note,
            }
        )
    if course_leaves is not None and set(seen_question_ids) != set(course_leaves):
        raise ValueError("record score leaves do not match the course package")
    expected_total = sum(item["score"] for item in normalized_scores)
    total = float(record.get("total", expected_total))
    if abs(total - expected_total) > 1e-9:
        raise ValueError("total must equal the sum of leaf scores")
    annotations = _normalize_annotations(
        record.get("annotations", []),
        student_id=student_id,
        question_ids=seen_question_ids,
        score_by_id={item["question_id"]: item for item in normalized_scores},
        require_annotations=require_annotations,
    )
    return {
        "student_id": student_id,
        "scores": normalized_scores,
        "annotations": annotations,
        "total": total,
        "flags": sorted(set(flags)),
    }


def _read_existing_rows(path: Path) -> tuple[list[str], list[dict[str, str]]] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _load_course_package(path: Path) -> dict[str, dict[str, float]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("course package could not be read") from error
    if not isinstance(payload, dict):
        raise ValueError("course package must be a JSON object")
    leaves = payload.get("score_leaves")
    if not isinstance(leaves, list) or not leaves:
        raise ValueError("course package requires non-empty score_leaves")

    result: dict[str, dict[str, float]] = {}
    for leaf in leaves:
        if not isinstance(leaf, dict):
            raise ValueError("course package score leaf must be an object")
        question_id = str(leaf.get("question_id", "")).strip()
        if not question_id:
            raise ValueError("course package score leaf requires question_id")
        if question_id in result:
            raise ValueError("course package has duplicate question_id")
        max_score = _positive_score(
            leaf.get("max_score"), "course-package max_score", question_id
        )
        increment = _positive_score(
            leaf.get("allowed_increment"),
            "course-package allowed_increment",
            question_id,
        )
        if not _on_increment(max_score, increment):
            raise ValueError(
                f"course-package max_score is not on its allowed increment for {question_id}"
            )
        result[question_id] = {
            "max_score": max_score,
            "allowed_increment": increment,
        }
    return result


def _validate_course_score(
    *,
    question_id: str,
    score: float,
    max_score: float,
    course_leaves: dict[str, dict[str, float]] | None,
) -> None:
    if course_leaves is None:
        return
    expected = course_leaves.get(question_id)
    if expected is None:
        raise ValueError(f"question_id is not declared by the course package: {question_id}")
    if abs(max_score - expected["max_score"]) > 1e-9:
        raise ValueError(f"max_score disagrees with the course package for {question_id}")
    if not _on_increment(score, expected["allowed_increment"]):
        raise ValueError(f"score is off the allowed increment for {question_id}")


def _on_increment(value: float, increment: float) -> bool:
    return abs(value / increment - round(value / increment)) <= 1e-9


def _roster_entry(
    student_id: str, roster: dict[str, RosterEntry] | None
) -> RosterEntry | None:
    if roster is None:
        return None
    entry = roster.get(student_id)
    if entry is None:
        raise ValueError("student_id is not present in the private roster")
    return entry


def _append_csv(path: Path, header: list[str], row: dict[str, str]) -> None:
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _append_review_rows(
    path: Path,
    record: dict[str, Any],
    roster_entry: RosterEntry | None,
) -> None:
    rows = []
    for item in record["scores"]:
        if item["confidence"] == "high" and not item["flags"]:
            continue
        rows.append(
            {
                "student_id": record["student_id"],
                "student_name": roster_entry.student_name if roster_entry else "",
                "student_number": roster_entry.student_number if roster_entry else "",
                "question_id": item["question_id"],
                "score": _format_score(item["score"]),
                "max_score": _format_score(item["max_score"]),
                "confidence": item["confidence"],
                "uncertainty": item["attention_note"] or "",
                "flags": ";".join(item["flags"]),
            }
        )
    if record["flags"]:
        rows.append(
            {
                "student_id": record["student_id"],
                "student_name": roster_entry.student_name if roster_entry else "",
                "student_number": roster_entry.student_number if roster_entry else "",
                "question_id": "",
                "score": "",
                "max_score": "",
                "confidence": "",
                "uncertainty": "Submission-level review required.",
                "flags": ";".join(record["flags"]),
            }
        )
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def _uncertainty_cell(record: dict[str, Any]) -> str:
    parts = [
        f"{item['question_id']}: {item['attention_note']}"
        for item in record["scores"]
        if item["confidence"] != "high" or item["flags"]
    ]
    if record["flags"]:
        parts.append("submission: " + ", ".join(record["flags"]))
    return " | ".join(parts)


def _normalize_annotations(
    value: Any,
    *,
    student_id: str,
    question_ids: set[str],
    score_by_id: dict[str, dict[str, Any]],
    require_annotations: bool,
) -> list[dict[str, Any]]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise ValueError("annotations must be a list")
    required = {"question_id", "page_id", "box", "kind", "label"}
    normalized = []
    for annotation in value:
        if not isinstance(annotation, dict) or set(annotation) != required:
            raise ValueError("annotations require exactly question_id,page_id,box,kind,label")
        question_id = str(annotation["question_id"]).strip()
        if question_id not in question_ids:
            raise ValueError("annotation question_id is not a scored leaf")
        page_id = str(annotation["page_id"]).strip()
        if not SAFE_SUBMISSION_ID.fullmatch(page_id):
            raise ValueError("annotation page_id contains unsupported characters")
        kind = annotation["kind"]
        if kind not in ANNOTATION_KINDS:
            raise ValueError("annotation kind is invalid")
        box = annotation["box"]
        if (
            not isinstance(box, list)
            or len(box) != 4
            or any(isinstance(part, bool) or not isinstance(part, (int, float)) for part in box)
        ):
            raise ValueError("annotation box must contain four numeric normalized values")
        x, y, width, height = (float(part) for part in box)
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            raise ValueError("annotation box must stay inside the normalized page")
        normalized.append(
            {
                "question_id": question_id,
                "page_id": page_id,
                "box": [x, y, width, height],
                "kind": kind,
                "label": _safe_trace_text(annotation["label"], "annotation label", student_id),
            }
        )

    if require_annotations:
        for question_id, item in score_by_id.items():
            matching = [entry for entry in normalized if entry["question_id"] == question_id]
            if item["score"] > 0 and not any(
                entry["kind"] == "praise" for entry in matching
            ):
                raise ValueError(f"score-bearing {question_id} requires a praise annotation")
            if item["score"] < item["max_score"] and not any(
                entry["kind"] == "deduction" for entry in matching
            ):
                raise ValueError(f"non-full {question_id} requires a deduction annotation")
            if (item["confidence"] != "high" or item["flags"]) and not any(
                entry["kind"] == "review" for entry in matching
            ):
                raise ValueError(f"review-needed {question_id} requires a review annotation")
    return normalized


def _normalized_flags(value: Any, *, label: str) -> list[str]:
    flags = _as_list(value)
    normalized = []
    for flag in flags:
        if not re.fullmatch(r"[a-z][a-z0-9_:-]{0,127}", flag):
            raise ValueError(f"invalid flag for {label}")
        normalized.append(flag)
    return normalized


def _require_private_output_directory(grades_dir: Path) -> None:
    """Backward-compatible private-output guard."""

    require_private_path(grades_dir, label="grades directory")


def _feedback_markdown(record: dict[str, Any]) -> str:
    lines = [
        f"# Feedback for {record['student_id']}",
        "",
        f"Total: {_format_score(record['total'])}",
        "",
    ]
    if record["flags"]:
        lines.extend(["Flags: " + ", ".join(record["flags"]), ""])
    for item in record["scores"]:
        max_score = "" if item["max_score"] is None else f" / {_format_score(float(item['max_score']))}"
        lines.extend(
            [
                f"## {item['question_id']}: {_format_score(item['score'])}{max_score}",
                "",
                f"Confidence: {item['confidence']}",
                "",
                f"Evidence: {item['evidence'] or 'No evidence recorded.'}",
                "",
                item["feedback"] or "No feedback recorded.",
                "",
            ]
        )
        if item["flags"]:
            lines.extend(["Flags: " + ", ".join(item["flags"]), ""])
        if item["deduction_trace"]:
            lines.extend(["Deduction trace:", ""])
            for trace in item["deduction_trace"]:
                lines.extend(
                    [
                        "- "
                        + f"{trace['rubric_criterion']}: "
                        + f"{trace['observed_evidence_or_missing_or_incorrect_part']} "
                        + f"(-{_format_score(trace['points_deducted'])}; "
                        + f"{trace['deduction_type']})",
                        "",
                    ]
                )
        if item["attention_note"]:
            lines.extend([f"Attention: {item['attention_note']}", ""])
    return "\n".join(lines)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _positive_score(value: Any, label: str, question_id: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} is required for {question_id}") from error
    if score <= 0:
        raise ValueError(f"{label} must be positive for {question_id}")
    return score


def _normalize_deduction_trace(
    value: Any,
    *,
    question_id: str,
    score: float,
    max_score: float,
    student_id: str,
) -> list[dict[str, Any]]:
    expected = round(max_score - score, 10)
    if expected == 0:
        if value not in (None, []):
            raise ValueError(f"full-credit {question_id} must not contain deduction_trace")
        return []
    if not isinstance(value, list) or not value:
        raise ValueError(f"non-full {question_id} requires deduction_trace")

    normalized = []
    required = {
        "rubric_criterion",
        "observed_evidence_or_missing_or_incorrect_part",
        "deduction_type",
        "points_deducted",
    }
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError(
                f"deduction_trace entries for {question_id} require exactly four fields"
            )
        deduction_type = entry["deduction_type"]
        if deduction_type not in DEDUCTION_TYPES:
            raise ValueError(f"invalid deduction_type for {question_id}")
        points_deducted = _positive_score(
            entry["points_deducted"], "points_deducted", question_id
        )
        normalized.append(
            {
                "rubric_criterion": _safe_trace_text(
                    entry["rubric_criterion"], "rubric_criterion", student_id
                ),
                "observed_evidence_or_missing_or_incorrect_part": _safe_trace_text(
                    entry["observed_evidence_or_missing_or_incorrect_part"],
                    "observed_evidence_or_missing_or_incorrect_part",
                    student_id,
                ),
                "deduction_type": deduction_type,
                "points_deducted": points_deducted,
            }
        )
    if abs(sum(entry["points_deducted"] for entry in normalized) - expected) > 1e-9:
        raise ValueError(
            f"deduction total must equal max_score - score for {question_id}"
        )
    return normalized


def _safe_trace_text(value: Any, label: str, student_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-blank text")
    if len(value) > 500:
        raise ValueError(f"{label} must be at most 500 characters")
    if (
        WINDOWS_ABSOLUTE_PATH.search(value)
        or PRIVATE_DATA_PATH.search(value)
        or FILE_URI.search(value)
    ):
        raise ValueError(f"{label} must not contain a private or absolute path")
    if EMAIL_ADDRESS.search(value) or IDENTITY_LABEL.search(value):
        raise ValueError(f"{label} must not contain identity-bearing text")
    if student_id.casefold() in value.casefold():
        raise ValueError(f"{label} must not repeat student_id")
    return value.strip()


def _safe_record_text(
    value: Any, label: str, student_id: str, *, required: bool
) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be plain text")
    if not value.strip():
        if required:
            raise ValueError(f"{label} must be non-blank text")
        return ""
    return _safe_trace_text(value, label, student_id)


def _format_score(value: float) -> str:
    return f"{value:g}"


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "_" for character in value)


if __name__ == "__main__":
    raise SystemExit(main())
