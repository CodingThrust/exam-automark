import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .metrics import ScoreKey, load_score_table


def build_skillopt_split(
    benchmark_root: Path,
    dev_packet: Path,
    test_packet: Path,
    output_dir: Path,
    *,
    train_fraction: float = 0.5,
) -> dict[str, Any]:
    """Export physics text grading packets into SkillOpt train/val/test JSON."""
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")

    gold_scores, _ = load_score_table(benchmark_root / "gold" / "primary_scores.csv")
    dev_items = _load_packet_items(dev_packet, gold_scores, source_split="development")
    test_items = _load_packet_items(test_packet, gold_scores, source_split="held_out")
    train_items, val_items = _split_items(dev_items, train_fraction)

    _write_split(output_dir / "train" / "items.json", train_items)
    _write_split(output_dir / "val" / "items.json", val_items)
    _write_split(output_dir / "test" / "items.json", test_items)

    manifest = {
        "record_type": "physics_skillopt_split_export",
        "generated_at": _utc_now(),
        "benchmark_root": str(benchmark_root),
        "dev_packet": _packet_summary(dev_packet),
        "test_packet": _packet_summary(test_packet),
        "output_dir": str(output_dir),
        "split": {
            "method": "dev_sorted_student_ids_plus_heldout_test",
            "train_fraction": train_fraction,
            "train_student_ids": [item["student_id"] for item in train_items],
            "val_student_ids": [item["student_id"] for item in val_items],
            "test_student_ids": [item["student_id"] for item in test_items],
            "train_count": len(train_items),
            "val_count": len(val_items),
            "test_count": len(test_items),
        },
        "privacy_scope": {
            "contains_raw_student_answers": True,
            "contains_anonymous_student_ids": True,
            "contains_real_student_identities": False,
            "must_remain_under_data_dir": True,
        },
        "heldout_policy": (
            "Use train for SkillOpt reflection and val for candidate selection; "
            "use test only once for final evaluation of the selected skill."
        ),
        "skillopt_expected_layout": {
            "train": "train/items.json",
            "val": "val/items.json",
            "test": "test/items.json",
        },
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def validate_skillopt_split(split_dir: Path) -> dict[str, Any]:
    """Run a local no-model smoke check for a SkillOpt split directory."""
    checks = []
    split_counts: dict[str, int] = {}
    all_ids: list[str] = []
    item_summaries = []
    for split_name in ("train", "val", "test"):
        path = split_dir / split_name / "items.json"
        if not path.exists():
            checks.append(f"missing_{split_name}_items")
            split_counts[split_name] = 0
            continue
        try:
            items = _read_json(path)
        except json.JSONDecodeError:
            checks.append(f"invalid_{split_name}_json")
            split_counts[split_name] = 0
            continue
        if not isinstance(items, list) or not items:
            checks.append(f"empty_or_nonlist_{split_name}_items")
            split_counts[split_name] = 0
            continue
        split_counts[split_name] = len(items)
        for item in items:
            item_checks = _validate_item(item, split_name)
            checks.extend(item_checks)
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                all_ids.append(item["id"])
                item_summaries.append(
                    {
                        "id": item["id"],
                        "split": split_name,
                        "student_id": item.get("student_id"),
                        "source_split": item.get("source_split"),
                    }
                )
    duplicate_ids = sorted({item_id for item_id in all_ids if all_ids.count(item_id) > 1})
    if duplicate_ids:
        checks.append("duplicate_item_ids")

    manifest_path = split_dir / "manifest.json"
    if not manifest_path.exists():
        checks.append("missing_manifest")
    else:
        manifest = _read_json(manifest_path)
        if manifest.get("heldout_policy") is None:
            checks.append("missing_heldout_policy")
        privacy = manifest.get("privacy_scope", {})
        if privacy.get("contains_real_student_identities") is not False:
            checks.append("real_identity_policy_not_false")
        if privacy.get("must_remain_under_data_dir") is not True:
            checks.append("data_dir_policy_not_true")

    failed_checks = sorted(set(checks))
    return {
        "record_type": "physics_skillopt_split_smoke_check",
        "generated_at": _utc_now(),
        "split_dir": str(split_dir),
        "status": "ready" if not failed_checks else "not_ready",
        "failed_checks": failed_checks,
        "split_counts": split_counts,
        "item_count": len(all_ids),
        "item_summaries": sorted(item_summaries, key=lambda row: row["id"]),
    }


def _load_packet_items(
    packet: Path,
    gold_scores: dict[ScoreKey, float],
    *,
    source_split: str,
) -> list[dict[str, Any]]:
    manifest = _read_json(packet / "manifest.json")
    if manifest.get("task") != "grade":
        raise ValueError(f"SkillOpt export requires a grade packet: {packet}")
    if manifest.get("metadata", {}).get("input_mode") != "text-only":
        raise ValueError(f"SkillOpt export currently supports text-only packets: {packet}")

    course = _read_json(packet / "course.json")
    rubric = _read_json(packet / "rubric.json")
    output_schema = _read_json(packet / "output.schema.json")
    prompt_text = (packet / "prompt.txt").read_text(encoding="utf-8")
    question_ids = [question["id"] for question in course["questions"]]
    student_ids = list(manifest["student_ids"])
    items = []
    for student_id in student_ids:
        transcript_path = packet / "inputs" / student_id / "transcript.json"
        if not transcript_path.exists():
            raise FileNotFoundError(f"transcript missing for {student_id}: {transcript_path}")
        transcript = _read_json(transcript_path)
        gold_rows = _gold_rows_for_student(gold_scores, student_id, question_ids)
        items.append(
            {
                "id": f"{manifest['packet_id']}-{student_id}",
                "task_type": "physics_week9_text_grading",
                "course_id": course["course_id"],
                "assessment_id": course["assessment_id"],
                "source_split": source_split,
                "student_id": student_id,
                "input_mode": "text-only",
                "question": (
                    "Grade this anonymous physics week 9 transcript using the "
                    "provided course spec, rubric, and output schema."
                ),
                "prompt_text": prompt_text,
                "course": course,
                "rubric": rubric,
                "output_schema": output_schema,
                "transcript": transcript,
                "gold_scores": gold_rows,
                "gold_total": round(sum(row["score"] for row in gold_rows), 10),
                "prompt_packet": {
                    "packet_id": manifest["packet_id"],
                    "condition": manifest.get("condition"),
                    "prompt_hash": manifest.get("prompt_hash"),
                    "rubric_hash": manifest.get("rubric_hash"),
                    "output_schema_hash": manifest.get("output_schema_hash"),
                    "input_hash": manifest.get("input_hashes", {}).get(student_id),
                    "source_run_id": manifest.get("metadata", {}).get("source_run_id"),
                    "source_prompt_template_id": manifest.get("metadata", {}).get(
                        "prompt_template_id"
                    ),
                    "source_skill_version_id": manifest.get("metadata", {}).get(
                        "skill_version_id"
                    ),
                },
            }
        )
    return items


def _validate_item(item: Any, split_name: str) -> list[str]:
    if not isinstance(item, dict):
        return [f"{split_name}_item_not_object"]
    checks = []
    required_fields = (
        "id",
        "task_type",
        "student_id",
        "input_mode",
        "course",
        "rubric",
        "output_schema",
        "transcript",
        "gold_scores",
        "gold_total",
        "prompt_packet",
    )
    missing = [field for field in required_fields if field not in item]
    if missing:
        checks.append(f"{split_name}_item_missing_required_fields")
    if not _is_anonymous_student_id(item.get("student_id")):
        checks.append(f"{split_name}_nonanonymous_student_id")
    if item.get("input_mode") != "text-only":
        checks.append(f"{split_name}_not_text_only")
    if not isinstance(item.get("gold_scores"), list) or not item.get("gold_scores"):
        checks.append(f"{split_name}_missing_gold_scores")
    if not isinstance(item.get("transcript"), dict):
        checks.append(f"{split_name}_missing_transcript")
    if split_name == "test" and item.get("source_split") != "held_out":
        checks.append("test_source_split_not_held_out")
    if split_name in {"train", "val"} and item.get("source_split") != "development":
        checks.append(f"{split_name}_source_split_not_development")
    return checks


def _gold_rows_for_student(
    gold_scores: dict[ScoreKey, float],
    student_id: str,
    question_ids: list[str],
) -> list[dict[str, Any]]:
    rows = []
    missing = []
    for question_id in question_ids:
        key = (student_id, question_id)
        if key not in gold_scores:
            missing.append(question_id)
        else:
            rows.append({"question_id": question_id, "score": gold_scores[key]})
    if missing:
        raise ValueError(f"gold scores missing for {student_id}: {missing}")
    return rows


def _split_items(
    dev_items: list[dict[str, Any]],
    train_fraction: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(dev_items) < 2:
        raise ValueError("at least two development items are required")
    sorted_items = sorted(dev_items, key=lambda item: item["student_id"])
    train_count = round(len(sorted_items) * train_fraction)
    train_count = max(1, min(len(sorted_items) - 1, train_count))
    return sorted_items[:train_count], sorted_items[train_count:]


def _write_split(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, items)


def _packet_summary(packet: Path) -> dict[str, Any]:
    manifest = _read_json(packet / "manifest.json")
    return {
        "path": str(packet),
        "packet_id": manifest.get("packet_id"),
        "student_count": len(manifest.get("student_ids", [])),
        "packet_hash": _directory_hash(packet),
        "prompt_hash": manifest.get("prompt_hash"),
        "rubric_hash": manifest.get("rubric_hash"),
        "output_schema_hash": manifest.get("output_schema_hash"),
    }


def _is_anonymous_student_id(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 4 and value.startswith("S") and value[1:].isdigit()


def _directory_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
