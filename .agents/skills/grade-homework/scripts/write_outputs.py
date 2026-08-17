from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


BASE_COLUMNS = ["student_id"]
TAIL_COLUMNS = ["total", "flags"]
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
    r"\b(?:student[ _-]?(?:id|number|name)|name)\s*[:=]|(?:姓名|学号)\s*[:：]",
    re.IGNORECASE,
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: write_outputs.py <grades_dir>", file=sys.stderr)
        return 2

    grades_dir = Path(args[0])

    try:
        _require_private_output_directory(grades_dir)
        grades_dir.mkdir(parents=True, exist_ok=True)
        feedback_dir = grades_dir / "feedback"
        feedback_dir.mkdir(exist_ok=True)
        record = json.loads(sys.stdin.read())
        normalized = _normalize_record(record)
    except Exception as error:
        print(f"invalid record: {error}", file=sys.stderr)
        return 2

    csv_path = grades_dir / "grades.csv"
    header = BASE_COLUMNS + [item["question_id"] for item in normalized["scores"]] + TAIL_COLUMNS
    existing_rows = _read_existing_rows(csv_path)
    if existing_rows is not None:
        existing_header, rows = existing_rows
        if existing_header != header:
            print("CSV header mismatch; rubric changed mid-run", file=sys.stderr)
            return 4
        if any(row.get("student_id") == normalized["student_id"] for row in rows):
            print(json.dumps({"status": "skipped", "student_id": normalized["student_id"]}))
            return 0

    row = {
        "student_id": normalized["student_id"],
        "total": _format_score(normalized["total"]),
        "flags": ";".join(normalized["flags"]),
    }
    for item in normalized["scores"]:
        row[item["question_id"]] = _format_score(item["score"])

    write_header = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    feedback_path = feedback_dir / f"{_safe_name(normalized['student_id'])}.md"
    feedback_path.write_text(_feedback_markdown(normalized), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": "written",
                "student_id": normalized["student_id"],
                "grades_csv": csv_path.as_posix(),
                "feedback": feedback_path.as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")
    student_id = str(record.get("student_id") or record.get("student") or "").strip()
    if not student_id:
        raise ValueError("student_id is required")
    scores = record.get("scores")
    if not isinstance(scores, list) or not scores:
        raise ValueError("scores must be a non-empty list")

    normalized_scores = []
    flags = list(_as_list(record.get("flags", [])))
    for item in scores:
        if not isinstance(item, dict):
            raise ValueError("each score item must be an object")
        question_id = str(item.get("question_id", "")).strip()
        if not question_id:
            raise ValueError("question_id is required")
        score = float(item.get("score"))
        max_score = _positive_score(item.get("max_score"), "max_score", question_id)
        if score < 0 or score > max_score:
            raise ValueError(f"score is outside range for {question_id}")
        confidence = str(item.get("confidence", "")).strip().lower()
        if confidence not in {"high", "medium", "low"}:
            raise ValueError(f"invalid confidence for {question_id}: {confidence}")
        item_flags = list(_as_list(item.get("flags", [])))
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
        if item_flags or confidence == "low":
            if attention_note is None:
                raise ValueError(
                    f"flags or low confidence require attention_note for {question_id}"
                )
        flags.extend(f"{question_id}:{flag}" for flag in item_flags)
        normalized_scores.append(
            {
                "question_id": question_id,
                "score": score,
                "max_score": max_score,
                "evidence": str(item.get("evidence", "")).strip(),
                "feedback": str(item.get("feedback", "")).strip(),
                "confidence": confidence,
                "flags": item_flags,
                "deduction_trace": deduction_trace,
                "attention_note": attention_note,
            }
        )
    total = float(record.get("total", sum(item["score"] for item in normalized_scores)))
    return {
        "student_id": student_id,
        "scores": normalized_scores,
        "total": total,
        "flags": sorted(set(str(flag) for flag in flags if str(flag).strip())),
    }


def _read_existing_rows(path: Path) -> tuple[list[str], list[dict[str, str]]] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _require_private_output_directory(grades_dir: Path) -> None:
    """Reject a new per-person grading record in an unignored Git location."""

    resolved = grades_dir.resolve()
    repository_root = next(
        (parent for parent in (resolved, *resolved.parents) if (parent / ".git").exists()),
        None,
    )
    if repository_root is None:
        return
    try:
        relative = resolved.relative_to(repository_root).as_posix()
    except ValueError:
        return
    check = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "check-ignore",
            "--quiet",
            "--no-index",
            "--",
            relative,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        return
    if check.returncode == 1:
        raise ValueError(
            "grades directory inside a Git worktree must be private and ignored"
        )
    raise ValueError("could not verify whether the grades directory is ignored")


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


def _format_score(value: float) -> str:
    return f"{value:g}"


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "_" for character in value)


if __name__ == "__main__":
    raise SystemExit(main())
