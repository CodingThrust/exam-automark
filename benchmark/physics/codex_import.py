import csv
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gold import SCORE_FIELDS
from .runner import create_run_directory
from .schema import (
    QUESTION_IDS,
    ScoreRecord,
    TranscriptAnswer,
    validate_score_records,
)


HUMAN_REVIEW_FIELDS = (
    "student_id",
    "question_id",
    "automatic_text",
    "human_text",
    "reviewed",
)


def parse_transcript_output(
    path: Path, expected_student_id: str
) -> list[TranscriptAnswer]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid transcript JSON: {path.name}") from error
    if not isinstance(payload, dict):
        raise ValueError("transcript output must be a JSON object")
    if payload.get("student_id") != expected_student_id:
        raise ValueError("student_id does not match packet manifest")
    raw_answers = payload.get("answers")
    if not isinstance(raw_answers, list):
        raise ValueError("answers must be a list")
    if len(raw_answers) != len(QUESTION_IDS):
        raise ValueError("transcript must contain exactly 12 answers")

    answers = []
    for row in raw_answers:
        if not isinstance(row, dict):
            raise ValueError("each transcript answer must be an object")
        question_id = row.get("question_id")
        text = row.get("text")
        unclear = row.get("unclear")
        if not isinstance(question_id, str):
            raise ValueError("question_id must be text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"transcript text is blank for: {question_id}")
        if not isinstance(unclear, bool):
            raise ValueError(f"unclear must be boolean for: {question_id}")
        if unclear and "[UNCLEAR]" not in text:
            raise ValueError(f"unclear answer must contain [UNCLEAR]: {question_id}")
        answers.append(
            TranscriptAnswer(
                question_id=question_id,
                text=text.strip(),
                unclear=unclear,
            )
        )
    validate_transcript_answers(answers)
    by_question = {answer.question_id: answer for answer in answers}
    return [by_question[question_id] for question_id in QUESTION_IDS]


def validate_transcript_answers(answers: list[TranscriptAnswer]) -> None:
    if len(answers) != len(QUESTION_IDS):
        raise ValueError("transcript must contain exactly 12 answers")
    question_ids = [answer.question_id for answer in answers]
    if set(question_ids) != set(QUESTION_IDS) or len(question_ids) != len(
        set(question_ids)
    ):
        raise ValueError("each question must appear exactly once")


def create_human_review_csv(
    benchmark_root: Path, split: str, output: Path
) -> Path:
    if split not in {"dev", "test"}:
        raise ValueError(f"unsupported split: {split}")
    if output.exists():
        raise FileExistsError(f"human review file already exists: {output}")
    split_data = _read_json(benchmark_root / "manifest" / "split.json")
    key = "development_student_ids" if split == "dev" else "heldout_student_ids"
    student_ids = split_data["transcript_gold"][key]
    source_dir = (
        benchmark_root / "transcripts" / "automatic" / f"T1-{split}-r1"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=HUMAN_REVIEW_FIELDS)
        writer.writeheader()
        for student_id in student_ids:
            answers = parse_transcript_output(
                source_dir / f"{student_id}.json", student_id
            )
            for answer in answers:
                writer.writerow(
                    {
                        "student_id": student_id,
                        "question_id": answer.question_id,
                        "automatic_text": answer.text,
                        "human_text": "",
                        "reviewed": "",
                    }
                )
    return output


def validate_human_review_csv(
    path: Path, expected_student_ids: list[str]
) -> None:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != HUMAN_REVIEW_FIELDS:
            raise ValueError("human transcript columns do not match schema")
        rows = list(reader)

    expected_pairs = {
        (student_id, question_id)
        for student_id in expected_student_ids
        for question_id in QUESTION_IDS
    }
    actual_pairs = {(row["student_id"], row["question_id"]) for row in rows}
    if actual_pairs != expected_pairs or len(rows) != len(expected_pairs):
        raise ValueError("human transcript rows do not match frozen subset")
    if any(not row["automatic_text"].strip() for row in rows):
        raise ValueError("automatic transcript text is incomplete")
    if any(not row["human_text"].strip() for row in rows):
        raise ValueError("human transcript text is incomplete")
    if any(row["reviewed"].strip().lower() != "true" for row in rows):
        raise ValueError("human transcript review is incomplete")


def parse_grading_output(path: Path, expected_student_id: str) -> list[ScoreRecord]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid grading JSON: {path.name}") from error
    return score_records_from_payload(payload, expected_student_id)


def score_records_from_payload(
    payload: Any, expected_student_id: str
) -> list[ScoreRecord]:
    if not isinstance(payload, dict):
        raise ValueError("grading output must be a JSON object")
    if payload.get("student_id") != expected_student_id:
        raise ValueError("student_id does not match packet manifest")
    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, list):
        raise ValueError("scores must be a list")

    records = []
    for row in raw_scores:
        if not isinstance(row, dict):
            raise ValueError("each score must be an object")
        extracted = row.get("extracted_evidence")
        evidence = row.get("evidence")
        flags = row.get("flags")
        score = row.get("score")
        if not isinstance(extracted, str):
            raise ValueError("extracted_evidence must be text")
        if not isinstance(evidence, str):
            raise ValueError("evidence must be text")
        if not isinstance(flags, list) or not all(
            isinstance(flag, str) for flag in flags
        ):
            raise ValueError("flags must be a list of strings")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ValueError("score must be numeric")
        records.append(
            ScoreRecord(
                student_id=expected_student_id,
                question_id=row.get("question_id"),
                score=float(score),
                confidence=row.get("confidence"),
                evidence=evidence,
                flags=tuple(flags),
            )
        )
    calculated_total = validate_score_records(records)
    total = payload.get("total")
    if not isinstance(total, (int, float)) or isinstance(total, bool):
        raise ValueError("total must be numeric")
    if abs(float(total) - calculated_total) > 1e-9:
        raise ValueError("reported total does not match question scores")
    return records


def import_codex_packet(packet: Path, benchmark_root: Path) -> Path:
    manifest = _read_json(packet / "manifest.json")
    condition = manifest.get("condition")
    if condition not in {"T1", "G2", "G3"}:
        raise ValueError(f"unsupported Codex condition: {condition}")
    expected = manifest.get("student_ids")
    if not isinstance(expected, list) or not expected:
        raise ValueError("packet manifest has no student IDs")
    if len(expected) != len(set(expected)) or any(
        not isinstance(student_id, str)
        or re.fullmatch(r"S\d{3}", student_id) is None
        for student_id in expected
    ):
        raise ValueError("packet manifest contains invalid student IDs")

    output_paths = sorted((packet / "outputs").glob("*.json"))
    output_by_id = {path.stem: path for path in output_paths}
    if len(output_by_id) != len(output_paths) or set(output_by_id) != set(expected):
        raise ValueError("Codex outputs do not match packet student IDs")

    if condition == "T1":
        parsed = {
            student_id: parse_transcript_output(output_by_id[student_id], student_id)
            for student_id in expected
        }
    else:
        parsed = {
            student_id: parse_grading_output(output_by_id[student_id], student_id)
            for student_id in expected
        }

    run_id = manifest.get("run_id")
    expected_run_id = "{}-{}-r{}".format(
        condition, manifest.get("split"), manifest.get("repetition")
    )
    if not isinstance(run_id, str) or run_id != expected_run_id:
        raise ValueError("packet run_id is inconsistent")
    frozen_dir = benchmark_root / "transcripts" / "automatic" / run_id
    if condition == "T1" and frozen_dir.exists():
        raise FileExistsError(f"transcript directory already exists: {frozen_dir}")

    run_manifest = dict(manifest)
    run_manifest["provider"] = "codex-plus-interactive"
    run_manifest["model"] = manifest.get("display_model", "GPT-5.5")
    run_dir = create_run_directory(
        benchmark_root / "runs", run_id, manifest=run_manifest
    )
    raw_log = run_dir / "raw_responses.jsonl"

    if condition == "T1":
        frozen_dir.mkdir(parents=True, exist_ok=False)
        transcript_log = run_dir / "transcripts.jsonl"
        transcript_log.write_text("", encoding="utf-8")
        for student_id in expected:
            source = output_by_id[student_id]
            shutil.copy2(source, frozen_dir / f"{student_id}.json")
            _append_raw_codex_output(
                raw_log, student_id, run_manifest["model"], source
            )
            for answer in parsed[student_id]:
                _append_jsonl(
                    transcript_log,
                    {
                        "student_id": student_id,
                        "question_id": answer.question_id,
                        "text": answer.text,
                        "unclear": answer.unclear,
                    },
                )
    else:
        for student_id in expected:
            source = output_by_id[student_id]
            _append_raw_codex_output(
                raw_log, student_id, run_manifest["model"], source
            )
            append_prediction_rows(
                run_dir / "predictions.csv", parsed[student_id]
            )

    _finish_manifest(run_dir / "manifest.json")
    return run_dir


def _append_raw_codex_output(
    path: Path, student_id: str, model: str, source: Path
) -> None:
    _append_jsonl(
        path,
        {
            "student_id": student_id,
            "status": "imported",
            "model": model,
            "raw_text": source.read_text(encoding="utf-8"),
            "timestamp": _utc_now(),
        },
    )


def append_prediction_rows(path: Path, records: list[ScoreRecord]) -> None:
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
        for record in records:
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


def _finish_manifest(path: Path) -> None:
    manifest = _read_json(path)
    manifest["end_time"] = _utc_now()
    _write_json(path, manifest)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON file: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
