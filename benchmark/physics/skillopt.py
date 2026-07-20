import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any

from .metrics import ScoreKey, evaluate_scores, load_run_scores, load_score_table


SUMMARY_METRICS = (
    "exact_agreement",
    "macro_accuracy",
    "subquestion_mae",
    "total_score_mae",
    "within_1_point_rate",
    "severe_error_rate",
)


def build_skillopt_pilot_summary(
    benchmark_root: Path,
    baseline_run: Path,
    candidate_run: Path,
    *,
    train_fraction: float = 0.5,
) -> dict[str, Any]:
    """Build a privacy-safe SkillOpt pilot anchor from existing physics runs."""
    baseline_scores, baseline_confidence = load_run_scores(baseline_run)
    candidate_scores, candidate_confidence = load_run_scores(candidate_run)
    _validate_matching_predictions(baseline_scores, candidate_scores)

    student_ids = sorted({student_id for student_id, _ in baseline_scores})
    train_ids, validation_ids = _split_student_ids(student_ids, train_fraction)
    gold_scores, _ = load_score_table(
        benchmark_root / "gold" / "primary_scores.csv",
        student_ids=set(student_ids),
    )
    _validate_matching_predictions(gold_scores, baseline_scores, label="gold")

    train = _subset_comparison(
        gold_scores,
        baseline_scores,
        candidate_scores,
        train_ids,
        baseline_confidence,
        candidate_confidence,
    )
    validation = _subset_comparison(
        gold_scores,
        baseline_scores,
        candidate_scores,
        validation_ids,
        baseline_confidence,
        candidate_confidence,
    )
    gate = _acceptance_gate(validation)
    return {
        "record_type": "physics_skillopt_pilot_summary",
        "generated_at": _utc_now(),
        "benchmark_root": str(benchmark_root),
        "baseline_run": str(baseline_run),
        "candidate_run": str(candidate_run),
        "privacy_scope": {
            "contains_raw_student_answers": False,
            "contains_model_transcripts": False,
            "contains_anonymous_student_ids": True,
            "contains_scores": True,
        },
        "skillopt_scope": {
            "status": "pre_adapter_anchor",
            "purpose": (
                "Summarize existing development-split grading failures before "
                "building the official SkillOpt benchmark adapter."
            ),
            "official_adapter_requirements": [
                "SplitDataLoader subclass",
                "rollout helper that persists conversations for reflection",
                "EnvAdapter subclass",
                "YAML config",
            ],
            "heldout_policy": (
                "Do not use the physics held-out test split for SkillOpt candidate "
                "selection; reserve it for final evaluation only."
            ),
        },
        "split": {
            "method": "sorted_student_ids",
            "train_fraction": train_fraction,
            "train_student_ids": train_ids,
            "validation_student_ids": validation_ids,
        },
        "train": train,
        "validation": validation,
        "acceptance_gate": gate,
    }


def write_skillopt_pilot_json(path: Path, summary: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_skillopt_pilot_markdown(path: Path, summary: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Physics SkillOpt Pilot Anchor",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Baseline run: `{summary['baseline_run']}`",
        f"- Candidate run: `{summary['candidate_run']}`",
        f"- Status: `{summary['skillopt_scope']['status']}`",
        "- Private content: no raw student answers or model transcripts",
        "",
        "## Split",
        "",
        f"- Method: `{summary['split']['method']}`",
        f"- Train students: `{', '.join(summary['split']['train_student_ids'])}`",
        f"- Validation students: `{', '.join(summary['split']['validation_student_ids'])}`",
        "",
        "## Validation Metrics",
        "",
        "| Metric | Baseline | Candidate | Candidate - Baseline |",
        "|---|---:|---:|---:|",
    ]
    validation = summary["validation"]
    for metric in SUMMARY_METRICS:
        lines.append(
            "| {metric} | {baseline:.4f} | {candidate:.4f} | {delta:.4f} |".format(
                metric=metric,
                baseline=validation["baseline"][metric],
                candidate=validation["candidate"][metric],
                delta=validation["candidate_minus_baseline"][metric],
            )
        )

    gate = summary["acceptance_gate"]
    lines.extend(
        [
            "",
            "## Acceptance Gate",
            "",
            f"- Candidate passes pilot gate: `{gate['candidate_passes_gate']}`",
            f"- Exact agreement improves: `{gate['checks']['exact_agreement_improves']}`",
            f"- Macro accuracy improves: `{gate['checks']['macro_accuracy_improves']}`",
            f"- Total score MAE does not worsen: `{gate['checks']['total_score_mae_not_worse']}`",
            f"- Severe error rate does not worsen: `{gate['checks']['severe_error_rate_not_worse']}`",
            "",
            "## Weak Validation Questions",
            "",
            "| Question | Candidate accuracy | Baseline accuracy | Delta | Candidate MAE |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in validation["weak_questions"]:
        lines.append(
            "| {question_id} | {candidate_accuracy:.4f} | {baseline_accuracy:.4f} | "
            "{accuracy_delta:.4f} | {candidate_mae:.4f} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## SkillOpt Integration Notes",
            "",
            "- This file is an anchor for building a SkillOpt adapter, not a final accuracy claim.",
            "- Official SkillOpt training still requires an environment adapter that stores per-item conversations for reflection.",
            "- Keep held-out physics test data untouched until the skill candidate has been selected on development validation data.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _subset_comparison(
    gold: dict[ScoreKey, float],
    baseline: dict[ScoreKey, float],
    candidate: dict[ScoreKey, float],
    student_ids: list[str],
    baseline_confidence: dict[ScoreKey, str],
    candidate_confidence: dict[ScoreKey, str],
) -> dict[str, Any]:
    student_set = set(student_ids)
    subset_gold = _filter_scores(gold, student_set)
    subset_baseline = _filter_scores(baseline, student_set)
    subset_candidate = _filter_scores(candidate, student_set)
    baseline_metrics = evaluate_scores(
        subset_gold,
        subset_baseline,
        _filter_confidence(baseline_confidence, student_set) or None,
    )
    candidate_metrics = evaluate_scores(
        subset_gold,
        subset_candidate,
        _filter_confidence(candidate_confidence, student_set) or None,
    )
    deltas = {
        metric: candidate_metrics[metric] - baseline_metrics[metric]
        for metric in SUMMARY_METRICS
    }
    return {
        "student_count": len(student_ids),
        "score_count": len(subset_gold),
        "baseline": baseline_metrics,
        "candidate": candidate_metrics,
        "candidate_minus_baseline": deltas,
        "weak_questions": _weak_questions(
            subset_gold,
            subset_baseline,
            subset_candidate,
        ),
        "score_feedback": _score_feedback(
            subset_gold,
            subset_baseline,
            subset_candidate,
        ),
    }


def _weak_questions(
    gold: dict[ScoreKey, float],
    baseline: dict[ScoreKey, float],
    candidate: dict[ScoreKey, float],
) -> list[dict[str, Any]]:
    by_question: dict[str, list[ScoreKey]] = defaultdict(list)
    for key in sorted(gold):
        by_question[key[1]].append(key)

    rows = []
    for question_id, keys in sorted(by_question.items()):
        baseline_accuracy = fmean(baseline[key] == gold[key] for key in keys)
        candidate_accuracy = fmean(candidate[key] == gold[key] for key in keys)
        candidate_mae = fmean(abs(candidate[key] - gold[key]) for key in keys)
        rows.append(
            {
                "question_id": question_id,
                "baseline_accuracy": baseline_accuracy,
                "candidate_accuracy": candidate_accuracy,
                "accuracy_delta": candidate_accuracy - baseline_accuracy,
                "candidate_mae": candidate_mae,
                "score_count": len(keys),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["candidate_accuracy"],
            -row["candidate_mae"],
            row["question_id"],
        ),
    )


def _score_feedback(
    gold: dict[ScoreKey, float],
    baseline: dict[ScoreKey, float],
    candidate: dict[ScoreKey, float],
) -> list[dict[str, Any]]:
    feedback = []
    for key in sorted(gold):
        baseline_error = baseline[key] - gold[key]
        candidate_error = candidate[key] - gold[key]
        feedback.append(
            {
                "student_id": key[0],
                "question_id": key[1],
                "gold_score": gold[key],
                "baseline_score": baseline[key],
                "candidate_score": candidate[key],
                "baseline_error": baseline_error,
                "candidate_error": candidate_error,
                "change": _classify_change(abs(baseline_error), abs(candidate_error)),
            }
        )
    return feedback


def _acceptance_gate(validation: dict[str, Any]) -> dict[str, Any]:
    deltas = validation["candidate_minus_baseline"]
    checks = {
        "exact_agreement_improves": deltas["exact_agreement"] > 0,
        "macro_accuracy_improves": deltas["macro_accuracy"] > 0,
        "total_score_mae_not_worse": deltas["total_score_mae"] <= 0,
        "severe_error_rate_not_worse": deltas["severe_error_rate"] <= 0,
    }
    return {
        "rule": (
            "Accept a candidate only if validation exact agreement and macro "
            "accuracy improve, while total score MAE and severe error rate do not worsen."
        ),
        "checks": checks,
        "candidate_passes_gate": all(checks.values()),
    }


def _split_student_ids(
    student_ids: list[str],
    train_fraction: float,
) -> tuple[list[str], list[str]]:
    if len(student_ids) < 2:
        raise ValueError("at least two students are required for a train/validation split")
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    train_count = round(len(student_ids) * train_fraction)
    train_count = max(1, min(len(student_ids) - 1, train_count))
    return student_ids[:train_count], student_ids[train_count:]


def _filter_scores(
    scores: dict[ScoreKey, float],
    student_ids: set[str],
) -> dict[ScoreKey, float]:
    return {key: value for key, value in scores.items() if key[0] in student_ids}


def _filter_confidence(
    confidence: dict[ScoreKey, str],
    student_ids: set[str],
) -> dict[ScoreKey, str]:
    return {key: value for key, value in confidence.items() if key[0] in student_ids}


def _validate_matching_predictions(
    reference: dict[ScoreKey, float],
    other: dict[ScoreKey, float],
    *,
    label: str = "candidate",
) -> None:
    if set(reference) != set(other):
        missing_other = sorted(set(reference) - set(other))
        missing_reference = sorted(set(other) - set(reference))
        raise ValueError(
            f"{label} score keys do not match; "
            f"missing_other={missing_other}, missing_reference={missing_reference}"
        )


def _classify_change(baseline_error: float, candidate_error: float) -> str:
    if candidate_error < baseline_error:
        return "improved"
    if candidate_error > baseline_error:
        return "regressed"
    return "unchanged"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
