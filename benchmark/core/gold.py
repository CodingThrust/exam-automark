import csv
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

from .schema import CourseSpec


REQUIRED_GOLD_COLUMNS = ("student_id", "question_id", "score")


def validate_gold_table(
    course: CourseSpec,
    gold_path: Path,
    student_ids: Sequence[str],
) -> dict[str, Any]:
    if not student_ids:
        raise ValueError("student_ids must not be empty")
    expected_students = tuple(student_ids)
    for student_id in expected_students:
        course.validate_student_id(student_id)

    rows, fieldnames = _read_csv(gold_path)
    missing_columns = [
        column for column in REQUIRED_GOLD_COLUMNS if column not in fieldnames
    ]
    expected_pairs = {
        (student_id, question_id)
        for student_id in expected_students
        for question_id in course.question_ids
    }
    actual_pairs = [
        (_cell(row, "student_id"), _cell(row, "question_id")) for row in rows
    ]
    pair_counts = Counter(actual_pairs)
    actual_unique = set(actual_pairs)
    duplicate_pairs = sorted(pair for pair, count in pair_counts.items() if count > 1)
    missing_pairs = sorted(expected_pairs - actual_unique)
    unexpected_pairs = sorted(actual_unique - expected_pairs)

    blank_pairs = []
    invalid_score_rows = []
    filled_score_rows = 0
    question_map = course.question_map
    for row_number, row in enumerate(rows, start=2):
        student_id = _cell(row, "student_id")
        question_id = _cell(row, "question_id")
        raw_score = _cell(row, "score")
        if not raw_score:
            blank_pairs.append((student_id, question_id))
            continue
        filled_score_rows += 1
        try:
            score = float(raw_score)
        except ValueError:
            invalid_score_rows.append(
                _invalid_row(row_number, student_id, question_id, raw_score, "not a number")
            )
            continue
        question = question_map.get(question_id)
        if question is None:
            invalid_score_rows.append(
                _invalid_row(row_number, student_id, question_id, raw_score, "unknown question_id")
            )
            continue
        if not question.allows_score(score):
            invalid_score_rows.append(
                _invalid_row(
                    row_number,
                    student_id,
                    question_id,
                    raw_score,
                    "score is out of range or off step",
                )
            )

    checks = [
        _check(
            "required_columns_present",
            not missing_columns,
            "all required columns are present"
            if not missing_columns
            else f"missing columns: {', '.join(missing_columns)}",
        ),
        _check(
            "all_expected_pairs_present_once",
            not missing_pairs and not duplicate_pairs and not unexpected_pairs,
            _pair_detail(missing_pairs, duplicate_pairs, unexpected_pairs),
        ),
        _check(
            "scores_complete",
            not blank_pairs,
            "no blank scores" if not blank_pairs else f"{len(blank_pairs)} blank scores",
        ),
        _check(
            "scores_within_course_steps",
            not invalid_score_rows,
            "all scores are within course ranges and score steps"
            if not invalid_score_rows
            else f"{len(invalid_score_rows)} invalid score rows",
        ),
    ]
    failed_checks = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "gold_readiness",
        "status": "not_ready" if failed_checks else "ready",
        "course_id": course.course_id,
        "assessment_id": course.assessment_id,
        "gold_path": gold_path.as_posix(),
        "expected_student_count": len(expected_students),
        "expected_question_count": len(course.question_ids),
        "expected_rows": len(expected_pairs),
        "rows_read": len(rows),
        "filled_score_rows": filled_score_rows,
        "blank_score_rows": len(blank_pairs),
        "missing_pairs": _pairs(missing_pairs),
        "duplicate_pairs": _pairs(duplicate_pairs),
        "unexpected_pairs": _pairs(unexpected_pairs),
        "invalid_score_rows": invalid_score_rows,
        "checks": checks,
        "failed_checks": failed_checks,
    }


def validate_gold_subset_table(
    course: CourseSpec,
    gold_path: Path,
    student_ids: Sequence[str],
) -> dict[str, Any]:
    """Strictly validate one selected cohort from a shared private gold table.

    The full table can intentionally contain unfinished held-out rows while a
    development cohort is ready for analysis.  This explicit helper copies
    only the requested anonymous rows into a temporary file below the private
    gold directory, then delegates to the unchanged strict validator.  It
    never represents the full cohort as ready.
    """

    expected_students = tuple(student_ids)
    if not expected_students:
        raise ValueError("student_ids must not be empty")
    source_path = Path(gold_path)
    with tempfile.TemporaryDirectory(
        prefix="exam-automark-selected-gold-",
        dir=source_path.parent,
    ) as tmp:
        selected_path = Path(tmp) / "selected-gold.csv"
        source_rows, selected_rows = _write_selected_gold(
            source_path,
            selected_path,
            expected_students,
        )
        report = validate_gold_table(course, selected_path, expected_students)

    report.update(
        {
            "report_type": "gold_subset_readiness",
            "validation_scope": "selected_students_only",
            "gold_path": source_path.as_posix(),
            "source_gold_path": source_path.as_posix(),
            "source_rows_read": source_rows,
            "selected_rows_read": selected_rows,
            "selected_student_count": len(expected_students),
        }
    )
    return report


def write_gold_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _read_csv(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), tuple(reader.fieldnames or ())


def _write_selected_gold(
    source_path: Path,
    selected_path: Path,
    student_ids: Sequence[str],
) -> tuple[int, int]:
    """Copy requested anonymous rows to an ephemeral private validation CSV."""

    selected_students = set(student_ids)
    source_rows = 0
    selected_rows = 0
    with source_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        fieldnames = list(reader.fieldnames or ())
        with selected_path.open("w", newline="", encoding="utf-8") as destination:
            writer = csv.DictWriter(destination, fieldnames=fieldnames)
            if fieldnames:
                writer.writeheader()
            for row in reader:
                source_rows += 1
                student_id = _cell(row, "student_id")
                if student_id in selected_students:
                    writer.writerow(row)
                    selected_rows += 1
    return source_rows, selected_rows


def _cell(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def _check(check_id: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "id": check_id,
        "status": "passed" if passed else "failed",
        "detail": detail,
    }


def _pairs(pairs: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    return [
        {"student_id": student_id, "question_id": question_id}
        for student_id, question_id in pairs
    ]


def _invalid_row(
    row_number: int,
    student_id: str,
    question_id: str,
    score: str,
    error: str,
) -> dict[str, Any]:
    return {
        "row_number": row_number,
        "student_id": student_id,
        "question_id": question_id,
        "score": score,
        "error": error,
    }


def _pair_detail(
    missing_pairs: list[tuple[str, str]],
    duplicate_pairs: list[tuple[str, str]],
    unexpected_pairs: list[tuple[str, str]],
) -> str:
    if not missing_pairs and not duplicate_pairs and not unexpected_pairs:
        return "every expected student/question pair appears exactly once"
    parts = []
    if missing_pairs:
        parts.append(f"missing={len(missing_pairs)}")
    if duplicate_pairs:
        parts.append(f"duplicates={len(duplicate_pairs)}")
    if unexpected_pairs:
        parts.append(f"unexpected={len(unexpected_pairs)}")
    return "; ".join(parts)
