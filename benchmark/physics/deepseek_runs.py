import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .codex_import import (
    append_prediction_rows,
    parse_transcript_output,
    score_records_from_payload,
    validate_human_review_csv,
)
from .providers import DeepSeekProvider
from .runner import ValidationFailure, create_run_directory, run_student_with_retries
from .schema import ProviderResult, QUESTION_IDS, TranscriptAnswer


def run_deepseek_condition(
    benchmark_root: Path,
    condition: str,
    split: str,
    repetition: int,
    provider: DeepSeekProvider,
) -> Path:
    if condition not in {"D1", "D2"}:
        raise ValueError(f"unsupported DeepSeek condition: {condition}")
    if split not in {"dev", "test"}:
        raise ValueError(f"unsupported split: {split}")
    if repetition != 1:
        raise ValueError("revised benchmark permits one run per condition")
    if split == "test" and not (benchmark_root / "freeze.json").exists():
        raise ValueError("held-out split is sealed until freeze.json exists")

    config = _read_json(
        Path(__file__).with_name("configs") / "physics_week9.json"
    )
    if provider.model != config["deepseek_model"]:
        raise ValueError(
            f"DeepSeek model must be {config['deepseek_model']}, got {provider.model}"
        )
    transcripts = _load_condition_transcripts(benchmark_root, condition, split)
    rubric_path = benchmark_root / "rubric" / "rubric_v1.json"
    rubric = _read_json(rubric_path)
    prompt_path = Path(__file__).with_name("prompts") / "grade_structured.txt"
    prompt_template = prompt_path.read_text(encoding="utf-8")

    run_id = f"{condition}-{split}-r{repetition}"
    manifest = {
        "condition": condition,
        "split": split,
        "repetition": repetition,
        "provider": "deepseek",
        "model": provider.model,
        "student_ids": list(transcripts),
        "prompt_hash": _file_hash(prompt_path),
        "rubric_hash": _file_hash(rubric_path),
        "input_hashes": {
            student_id: _transcript_hash(answers)
            for student_id, answers in transcripts.items()
        },
        "parameters": {"response_format": "json_object"},
    }
    run_dir = create_run_directory(
        benchmark_root / "runs", run_id, manifest=manifest
    )
    usage: dict[str, int | float] = {}
    successes = 0
    for student_id, answers in transcripts.items():
        prompt = _compose_prompt(
            prompt_template, student_id, answers, rubric
        )

        def operation(attempt: int) -> ProviderResult:
            repair = ""
            if attempt > 1:
                repair = (
                    "\nThe previous response failed validation. Return one corrected "
                    "JSON object only, following the required schema exactly."
                )
            result = provider.complete_text(prompt + repair)
            try:
                score_records_from_payload(json.loads(result.raw_text), student_id)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                raise ValidationFailure(
                    f"invalid grading response: {error}", result=result
                ) from error
            return result

        result = run_student_with_retries(
            run_dir,
            student_id,
            operation,
            max_retries=config["max_retries"],
        )
        if result is None:
            continue
        records = score_records_from_payload(json.loads(result.raw_text), student_id)
        append_prediction_rows(run_dir / "predictions.csv", records)
        _merge_usage(usage, result.usage)
        successes += 1

    _finish_manifest(run_dir / "manifest.json", usage)
    if successes == 0:
        raise RuntimeError(
            f"{run_id} produced no predictions; see {run_dir / 'failures.jsonl'}"
        )
    return run_dir


def _load_condition_transcripts(
    benchmark_root: Path, condition: str, split: str
) -> dict[str, list[TranscriptAnswer]]:
    split_data = _read_json(benchmark_root / "manifest" / "split.json")
    key = "development_student_ids" if split == "dev" else "heldout_student_ids"
    if condition == "D1":
        student_ids = split_data[key]
        source = (
            benchmark_root / "transcripts" / "automatic" / f"T1-{split}-r1"
        )
        return {
            student_id: parse_transcript_output(
                source / f"{student_id}.json", student_id
            )
            for student_id in student_ids
        }

    student_ids = split_data["transcript_gold"][key]
    review_path = benchmark_root / "transcripts" / "human" / f"H1-{split}.csv"
    validate_human_review_csv(review_path, student_ids)
    with review_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    by_pair = {
        (row["student_id"], row["question_id"]): row["human_text"].strip()
        for row in rows
    }
    return {
        student_id: [
            TranscriptAnswer(
                question_id=question_id,
                text=by_pair[(student_id, question_id)],
                unclear="[UNCLEAR]" in by_pair[(student_id, question_id)],
            )
            for question_id in QUESTION_IDS
        ]
        for student_id in student_ids
    }


def _compose_prompt(
    template: str,
    student_id: str,
    answers: list[TranscriptAnswer],
    rubric: dict[str, Any],
) -> str:
    context = {
        "student_id": student_id,
        "transcript": [
            {
                "question_id": answer.question_id,
                "text": answer.text,
                "unclear": answer.unclear,
            }
            for answer in answers
        ],
        "rubric": rubric,
    }
    return (
        template
        + f"\n\nOutput student_id must be {student_id}."
        + "\nBenchmark context:\n"
        + json.dumps(context, ensure_ascii=True, sort_keys=True)
    )


def _transcript_hash(answers: list[TranscriptAnswer]) -> str:
    payload = [
        {
            "question_id": answer.question_id,
            "text": answer.text,
            "unclear": answer.unclear,
        }
        for answer in answers
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _merge_usage(total: dict[str, int | float], usage: dict[str, Any]) -> None:
    for key, value in usage.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total[key] = total.get(key, 0) + value


def _finish_manifest(path: Path, usage: dict[str, int | float]) -> None:
    manifest = _read_json(path)
    manifest["end_time"] = _utc_now()
    manifest["usage"] = usage
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
