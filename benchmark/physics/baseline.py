import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .gold import SCORE_FIELDS
from .runner import create_run_directory
from .schema import QUESTION_IDS, ScoreRecord, validate_score_records


def row_to_score_records(
    row: dict[str, str],
    student_id: str,
) -> list[ScoreRecord]:
    return [
        ScoreRecord(
            student_id=student_id,
            question_id=question_id,
            score=float(row[question_id]),
            confidence="medium",
            evidence="historical gpt_direct_v0 import",
            flags=("historical_single_run",),
        )
        for question_id in QUESTION_IDS
    ]


def import_baseline_run(physics_root: Path) -> Path:
    benchmark_root = physics_root / "benchmark"
    map_path = benchmark_root / "manifest" / "student_map.csv"
    grades_path = physics_root / "grades" / "grades.csv"
    map_rows = _read_csv_rows(map_path)
    source_to_id = {row["student"]: row["student_id"] for row in map_rows}
    if len(source_to_id) != len(map_rows):
        raise ValueError("student map contains duplicate source labels")
    grade_rows = _read_csv_rows(grades_path)
    grade_by_source = {row["student"]: row for row in grade_rows}
    if len(grade_by_source) != len(grade_rows):
        raise ValueError("historical grades contain duplicate students")
    if set(grade_by_source) != set(source_to_id):
        raise ValueError("historical grades do not match student map")

    records_by_id = {}
    for source_label, student_id in source_to_id.items():
        records = row_to_score_records(grade_by_source[source_label], student_id)
        validate_score_records(records)
        records_by_id[student_id] = records

    run_id = "G0-all-r1"
    run_dir = create_run_directory(
        benchmark_root / "runs",
        run_id,
        manifest={
            "condition": "G0",
            "split": "all",
            "repetition": 1,
            "provider": "historical",
            "model": "gpt_direct_v0",
            "student_ids": sorted(records_by_id),
            "input_hash": hashlib.sha256(grades_path.read_bytes()).hexdigest(),
            "parameters": {"historical_single_run": True},
        },
    )
    with (run_dir / "predictions.csv").open(
        "a", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
        for student_id in sorted(records_by_id):
            for record in records_by_id[student_id]:
                writer.writerow(
                    {
                        "student_id": record.student_id,
                        "question_id": record.question_id,
                        "score": record.score,
                        "confidence": record.confidence,
                        "evidence": record.evidence,
                        "ambiguity_code": ";".join(record.flags),
                    }
                )
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["end_time"] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run_dir


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        return _read_csv_rows_with_encoding(path, "utf-8-sig")
    except UnicodeDecodeError:
        return _read_csv_rows_with_encoding(path, "gb18030")


def _read_csv_rows_with_encoding(
    path: Path, encoding: str
) -> list[dict[str, str]]:
    with path.open(newline="", encoding=encoding) as handle:
        return list(csv.DictReader(handle))
