import csv
import json
from pathlib import Path
from typing import Any

from .codex_import import validate_human_review_csv
from .schema import QUESTION_IDS


DEV_RUNS = {
    "G2-dev-r1": 8,
    "D1-dev-r1": 8,
    "G3-dev-r1": 4,
    "D2-dev-r1": 4,
}
TEST_RUNS = {
    "G2-test-r1": 18,
    "D1-test-r1": 18,
    "G3-test-r1": 6,
    "D2-test-r1": 6,
}


def validate_benchmark_workspace(root: Path) -> dict[str, Any]:
    freeze_path = root / "freeze.json"
    if not freeze_path.exists():
        return {"stage": "privacy_approved"}

    split_path = _require_file(root / "manifest" / "split.json")
    rubric_path = _require_file(root / "rubric" / "rubric_v1.json")
    split = _read_json(split_path)
    rubric = _read_json(rubric_path)
    if split.get("status") != "frozen":
        raise ValueError("split.json is not frozen")
    if rubric.get("status") != "frozen":
        raise ValueError("rubric_v1.json is not frozen")

    dev_ids = list(split["development_student_ids"])
    test_ids = list(split["heldout_student_ids"])
    transcript_dev = list(split["transcript_gold"]["development_student_ids"])
    transcript_test = list(split["transcript_gold"]["heldout_student_ids"])
    if len(dev_ids) != 8 or len(test_ids) != 18 or set(dev_ids) & set(test_ids):
        raise ValueError("split.json must contain disjoint 8-person dev and 18-person test")
    if len(transcript_dev) != 4 or len(transcript_test) != 6:
        raise ValueError("split.json must contain 4 dev and 6 test transcript students")
    all_ids = dev_ids + test_ids
    _validate_gold(root / "gold" / "primary_scores.csv", all_ids)

    freeze = _read_json(freeze_path)
    if freeze.get("excluded_run_ids") != ["G1-dev-r1"]:
        raise ValueError("freeze.json must explicitly exclude G1-dev-r1")
    _validate_score_run(root, "G0-all-r1", all_ids)
    for run_id, count in DEV_RUNS.items():
        student_ids = dev_ids if count == 8 else transcript_dev
        _validate_score_run(root, run_id, student_ids)
    _validate_transcript_run(root, "dev", dev_ids)
    validate_human_review_csv(
        _require_file(root / "transcripts" / "human" / "H1-dev.csv"),
        transcript_dev,
    )
    _require_file(root / "metrics-dev.json")

    final_stage = any((root / "runs" / run_id).exists() for run_id in TEST_RUNS)
    if not final_stage:
        return {
            "stage": "development_frozen",
            "students": len(all_ids),
            "reference_scores": len(all_ids) * len(QUESTION_IDS),
            "development_students": len(dev_ids),
            "heldout_students": len(test_ids),
            "reviewed_transcript_students": len(transcript_dev),
        }

    for run_id, count in TEST_RUNS.items():
        student_ids = test_ids if count == 18 else transcript_test
        _validate_score_run(root, run_id, student_ids)
    _validate_transcript_run(root, "test", test_ids)
    validate_human_review_csv(
        _require_file(root / "transcripts" / "human" / "H1-test.csv"),
        transcript_test,
    )
    for name in ("metrics-test.json", "metrics-all.json"):
        _require_file(root / name)
    _require_file(root / "reports" / "physics_week9_benchmark.md")
    _validate_anonymous_pages(root, all_ids)
    return {
        "stage": "final",
        "students": len(all_ids),
        "reference_scores": len(all_ids) * len(QUESTION_IDS),
        "development_students": len(dev_ids),
        "heldout_students": len(test_ids),
        "reviewed_transcript_students": len(transcript_dev) + len(transcript_test),
        "excluded_runs": freeze["excluded_run_ids"],
    }


def _validate_gold(path: Path, student_ids: list[str]) -> None:
    rows = _read_csv(_require_file(path))
    expected = {
        (student_id, question_id)
        for student_id in student_ids
        for question_id in QUESTION_IDS
    }
    actual = {(row["student_id"], row["question_id"]) for row in rows}
    if len(rows) != len(expected) or actual != expected:
        raise ValueError("primary gold must contain 312 unique reference scores")
    if any(not row["score"].strip() for row in rows):
        raise ValueError("primary gold contains blank scores")


def _validate_score_run(root: Path, run_id: str, student_ids: list[str]) -> None:
    run_dir = root / "runs" / run_id
    manifest = _read_json(_require_file(run_dir / "manifest.json"))
    if not manifest.get("end_time"):
        raise ValueError(f"run is incomplete: {run_id}")
    rows = _read_csv(_require_file(run_dir / "predictions.csv"))
    expected = {
        (student_id, question_id)
        for student_id in student_ids
        for question_id in QUESTION_IDS
    }
    actual = {(row["student_id"], row["question_id"]) for row in rows}
    if len(rows) != len(expected) or actual != expected:
        raise ValueError(f"run predictions are incomplete: {run_id}")
    failures = run_dir / "failures.jsonl"
    if failures.exists() and failures.read_text(encoding="utf-8").strip():
        raise ValueError(f"run contains terminal failures: {run_id}")


def _validate_transcript_run(root: Path, split: str, student_ids: list[str]) -> None:
    frozen = root / "transcripts" / "automatic" / f"T1-{split}-r1"
    files = sorted(frozen.glob("S*.json"))
    if len(files) != len(student_ids) or {path.stem for path in files} != set(
        student_ids
    ):
        raise ValueError(f"T1-{split}-r1 transcripts are incomplete")
    run_dir = root / "runs" / f"T1-{split}-r1"
    manifest = _read_json(_require_file(run_dir / "manifest.json"))
    if not manifest.get("end_time"):
        raise ValueError(f"T1-{split}-r1 import is incomplete")
    rows = (run_dir / "transcripts.jsonl").read_text(encoding="utf-8").splitlines()
    if len(rows) != len(student_ids) * len(QUESTION_IDS):
        raise ValueError(f"T1-{split}-r1 normalized transcripts are incomplete")


def _validate_anonymous_pages(root: Path, student_ids: list[str]) -> None:
    page_ids = {
        path.parent.name for path in (root / "anonymized").glob("S*/*.jpg")
    }
    if page_ids != set(student_ids):
        raise ValueError("anonymous page folders do not match the 26-student manifest")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise ValueError(f"required benchmark file is missing: {path}")
    return path
