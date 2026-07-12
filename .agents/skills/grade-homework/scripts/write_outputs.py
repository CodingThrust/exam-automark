from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any


BASE_COLUMNS = ["student_id"]
TAIL_COLUMNS = ["total", "flags"]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: write_outputs.py <grades_dir>", file=sys.stderr)
        return 2

    grades_dir = Path(args[0])
    grades_dir.mkdir(parents=True, exist_ok=True)
    feedback_dir = grades_dir / "feedback"
    feedback_dir.mkdir(exist_ok=True)

    try:
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
        confidence = str(item.get("confidence", "")).strip().lower()
        if confidence not in {"high", "medium", "low"}:
            raise ValueError(f"invalid confidence for {question_id}: {confidence}")
        item_flags = list(_as_list(item.get("flags", [])))
        flags.extend(f"{question_id}:{flag}" for flag in item_flags)
        normalized_scores.append(
            {
                "question_id": question_id,
                "score": score,
                "max_score": item.get("max_score"),
                "evidence": str(item.get("evidence", "")).strip(),
                "feedback": str(item.get("feedback", "")).strip(),
                "confidence": confidence,
                "flags": item_flags,
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
    return "\n".join(lines)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _format_score(value: float) -> str:
    return f"{value:g}"


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "_" for character in value)


if __name__ == "__main__":
    raise SystemExit(main())
