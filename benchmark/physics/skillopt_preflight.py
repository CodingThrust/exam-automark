from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .schema import ProviderResult


class TargetProvider(Protocol):
    model: str

    def complete_text(self, prompt: str) -> ProviderResult:
        ...


def run_target_preflight(
    *,
    split_dir: Path,
    output_dir: Path,
    split: str,
    provider: TargetProvider,
    limit: int = 0,
) -> dict[str, Any]:
    items = _load_items(split_dir, split)
    if limit > 0:
        items = items[:limit]
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    usage: Counter[str] = Counter()
    for item in items:
        rows.append(_run_one(item, output_dir, provider))
        usage.update(_numeric_usage(rows[-1].get("usage", {})))

    reason_counts = Counter(
        row["reason"] for row in rows if row.get("status") != "passed"
    )
    items_passed = sum(1 for row in rows if row.get("status") == "passed")
    summary = {
        "record_type": "physics_skillopt_target_preflight",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider": "deepseek",
        "model": provider.model,
        "split_dir": str(split_dir),
        "output_dir": str(output_dir),
        "split": split,
        "items_expected": len(items),
        "items_passed": items_passed,
        "items_failed": len(items) - items_passed,
        "status": "ready" if items and items_passed == len(items) else "failed",
        "hard_rate": _mean(row["hard"] for row in rows),
        "soft_avg": _mean(row["soft"] for row in rows),
        "total_abs_error": round(
            sum(float(row.get("total_abs_error", 0.0)) for row in rows), 6
        ),
        "reason_counts": dict(sorted(reason_counts.items())),
        "usage": dict(sorted(usage.items())),
        "rows": rows,
    }
    _write_json(output_dir / "summary.json", summary)
    return summary


def _load_items(split_dir: Path, split: str) -> list[dict[str, Any]]:
    if split not in {"train", "val", "test"}:
        raise ValueError(f"unsupported SkillOpt split: {split}")
    path = split_dir / split / "items.json"
    if not path.exists():
        raise FileNotFoundError(f"missing SkillOpt items file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"SkillOpt items file must contain a JSON array: {path}")
    return payload


def _run_one(
    item: dict[str, Any],
    output_dir: Path,
    provider: TargetProvider,
) -> dict[str, Any]:
    student_id = str(item["student_id"])
    item_dir = output_dir / "outputs" / student_id
    item_dir.mkdir(parents=True, exist_ok=True)

    system_prompt = _build_system_prompt(str(item.get("prompt_text", "")))
    user_prompt = _build_user_prompt(item)
    _write_text(item_dir / "target_system_prompt.txt", system_prompt)
    _write_text(item_dir / "target_user_prompt.txt", user_prompt)

    try:
        result = _complete(provider, system_prompt, user_prompt)
    except Exception as error:  # noqa: BLE001
        row = _failure_row(item, "target_call_error", str(error), {})
        _write_json(item_dir / "result.json", row)
        return row

    _write_text(item_dir / "raw_response.txt", result.raw_text)
    _write_json(
        item_dir / "conversation.json",
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": result.raw_text},
        ],
    )

    try:
        payload = _parse_json(result.raw_text)
    except Exception as error:  # noqa: BLE001
        row = _failure_row(item, "json_parse_error", str(error), result.usage)
        _write_json(item_dir / "result.json", row)
        return row

    try:
        hard, soft, total_abs_error = _score(payload, item)
    except Exception as error:  # noqa: BLE001
        row = _failure_row(item, "score_error", str(error), result.usage)
        row["prediction"] = payload
        _write_json(item_dir / "result.json", row)
        return row

    row = {
        "id": item.get("id"),
        "student_id": student_id,
        "status": "passed",
        "reason": "ok",
        "hard": hard,
        "soft": soft,
        "total_abs_error": total_abs_error,
        "prediction": payload,
        "gold_scores": item.get("gold_scores", []),
        "usage": result.usage,
    }
    _write_json(item_dir / "result.json", row)
    return row


def _complete(
    provider: TargetProvider,
    system_prompt: str,
    user_prompt: str,
) -> ProviderResult:
    complete_chat = getattr(provider, "complete_chat", None)
    if callable(complete_chat):
        return complete_chat(system_prompt, user_prompt)
    return provider.complete_text(system_prompt + "\n\n" + user_prompt)


def _build_system_prompt(skill_content: str) -> str:
    return (
        "You are the target grader inside a SkillOpt rollout.\n"
        "Use the dynamic grading skill below only as grading guidance. "
        "If the dynamic skill describes files, CSVs, feedback reports, or "
        "command-line workflows, treat those as background guidance, not as the "
        "required output format for this rollout.\n"
        "For this rollout, the user message defines the authoritative rubric, "
        "transcript, and output_schema. Return exactly one valid JSON object "
        "matching that schema.\n\n"
        "## Dynamic Grading Skill\n"
        f"{skill_content.strip()}\n"
    )


def _build_user_prompt(item: dict[str, Any]) -> str:
    question_ids = [row["question_id"] for row in item["gold_scores"]]
    compact_schema = {
        "type": "object",
        "required": ["student_id", "scores", "total"],
        "properties": {
            "student_id": {"const": item["student_id"]},
            "scores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["question_id", "score"],
                    "properties": {
                        "question_id": {"enum": question_ids},
                        "score": {"type": "number"},
                    },
                    "additionalProperties": False,
                },
                "minItems": len(question_ids),
                "maxItems": len(question_ids),
            },
            "total": {"type": "number"},
        },
        "additionalProperties": False,
    }
    payload = {
        "student_id": item["student_id"],
        "course": item["course"],
        "rubric": item["rubric"],
        "output_schema": compact_schema,
        "transcript": item["transcript"],
    }
    return (
        "Grade the anonymous physics work.\n"
        "Return one JSON object only. "
        "Do not include Markdown fences, prose, bullet points, explanations, "
        "or extra keys. The JSON must follow output_schema exactly and contain "
        "only student_id, scores, and total. Each scores item must contain only "
        "question_id and score.\n\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def _parse_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model response did not contain a JSON object")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("model response JSON must be an object")
    return payload


def _score(payload: dict[str, Any], item: dict[str, Any]) -> tuple[float, float, float]:
    if payload.get("student_id") != item["student_id"]:
        raise ValueError("student_id mismatch")
    scores = payload.get("scores")
    if not isinstance(scores, list):
        raise ValueError("scores must be a list")
    gold = {row["question_id"]: float(row["score"]) for row in item["gold_scores"]}
    predicted = {}
    for row in scores:
        if not isinstance(row, dict):
            raise ValueError("each score row must be an object")
        question_id = row.get("question_id")
        if question_id in predicted:
            raise ValueError(f"duplicate question_id: {question_id}")
        predicted[question_id] = float(row["score"])
    if set(predicted) != set(gold):
        raise ValueError("predicted question set does not match gold question set")
    abs_errors = [abs(predicted[question_id] - gold[question_id]) for question_id in gold]
    exact = sum(error == 0 for error in abs_errors)
    total_abs_error = round(sum(abs_errors), 6)
    hard = 1.0 if total_abs_error == 0 else 0.0
    soft = round(exact / len(abs_errors), 6) if abs_errors else 0.0
    return hard, soft, total_abs_error


def _failure_row(
    item: dict[str, Any],
    reason: str,
    detail: str,
    usage: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "student_id": item.get("student_id"),
        "status": "failed",
        "reason": reason,
        "detail": detail,
        "hard": 0.0,
        "soft": 0.0,
        "total_abs_error": 999.0,
        "gold_scores": item.get("gold_scores", []),
        "usage": usage,
    }


def _numeric_usage(usage: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in usage.items()
        if isinstance(value, int | float)
    }


def _mean(values: Any) -> float:
    numbers = [float(value) for value in values]
    if not numbers:
        return 0.0
    return round(sum(numbers) / len(numbers), 6)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
