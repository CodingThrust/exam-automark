import csv
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any

from .codex_import import parse_grading_output


ScoreKey = tuple[str, str]


def _validate_predictions(
    gold: dict[ScoreKey, float],
    predicted: dict[ScoreKey, float],
) -> None:
    if not gold:
        raise ValueError("gold scores must not be empty")
    missing = sorted(set(gold) - set(predicted))
    if missing:
        raise ValueError(f"missing predictions: {missing}")


def evaluate_scores(
    gold: dict[ScoreKey, float],
    predicted: dict[ScoreKey, float],
    confidence: dict[ScoreKey, str] | None = None,
) -> dict[str, Any]:
    _validate_predictions(gold, predicted)
    keys = sorted(gold)
    errors = {key: predicted[key] - gold[key] for key in keys}

    total_errors: dict[str, float] = defaultdict(float)
    question_matches: dict[str, list[bool]] = defaultdict(list)
    for (student_id, question_id), error in errors.items():
        total_errors[student_id] += error
        question_matches[question_id].append(error == 0)

    per_question_accuracy = {
        question_id: fmean(matches)
        for question_id, matches in sorted(question_matches.items())
    }
    result: dict[str, Any] = {
        "exact_agreement": fmean(error == 0 for error in errors.values()),
        "subquestion_mae": fmean(abs(error) for error in errors.values()),
        "mean_signed_error": fmean(errors.values()),
        "total_score_mae": fmean(abs(error) for error in total_errors.values()),
        "within_1_point_rate": fmean(
            abs(error) <= 1.0 for error in total_errors.values()
        ),
        "severe_error_rate": fmean(
            abs(error) > 2.0 for error in total_errors.values()
        ),
        "per_question_accuracy": per_question_accuracy,
        "macro_accuracy": fmean(per_question_accuracy.values()),
    }

    if confidence is not None:
        missing_confidence = sorted(set(gold) - set(confidence))
        if missing_confidence:
            raise ValueError(f"missing confidence labels: {missing_confidence}")
        confidence_matches: dict[str, list[bool]] = defaultdict(list)
        for key, error in errors.items():
            confidence_matches[confidence[key]].append(error == 0)
        result["confidence_accuracy"] = {
            level: fmean(matches)
            for level, matches in sorted(confidence_matches.items())
        }

    return result


def paired_student_bootstrap(
    gold: dict[ScoreKey, float],
    baseline: dict[ScoreKey, float],
    candidate: dict[ScoreKey, float],
    *,
    seed: int = 20260701,
    samples: int = 10_000,
) -> dict[str, float]:
    _validate_predictions(gold, baseline)
    _validate_predictions(gold, candidate)
    if samples <= 0:
        raise ValueError("samples must be positive")

    student_keys: dict[str, list[ScoreKey]] = defaultdict(list)
    for key in sorted(gold):
        student_keys[key[0]].append(key)

    differences = []
    for keys in student_keys.values():
        baseline_accuracy = fmean(baseline[key] == gold[key] for key in keys)
        candidate_accuracy = fmean(candidate[key] == gold[key] for key in keys)
        differences.append(candidate_accuracy - baseline_accuracy)

    rng = random.Random(seed)
    sample_means = sorted(
        fmean(rng.choice(differences) for _ in differences) for _ in range(samples)
    )
    lower_index = min(samples - 1, math.floor(0.025 * samples))
    upper_index = min(samples - 1, math.ceil(0.975 * samples) - 1)
    return {
        "mean_difference": fmean(differences),
        "lower": sample_means[lower_index],
        "upper": sample_means[upper_index],
    }


def compare_run_directories(
    benchmark_root: Path,
    baseline_run: Path,
    candidate_run: Path,
    *,
    bootstrap_seed: int = 20260701,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    baseline_scores, baseline_confidence = load_run_scores(baseline_run)
    candidate_scores, candidate_confidence = load_run_scores(candidate_run)
    if set(baseline_scores) != set(candidate_scores):
        missing_candidate = sorted(set(baseline_scores) - set(candidate_scores))
        missing_baseline = sorted(set(candidate_scores) - set(baseline_scores))
        raise ValueError(
            "run prediction keys do not match; "
            f"missing_candidate={missing_candidate}, missing_baseline={missing_baseline}"
        )

    student_ids = {student_id for student_id, _ in baseline_scores}
    gold_scores, _ = load_score_table(
        benchmark_root / "gold" / "primary_scores.csv",
        student_ids=student_ids,
    )
    if set(gold_scores) != set(baseline_scores):
        missing_gold = sorted(set(baseline_scores) - set(gold_scores))
        missing_predictions = sorted(set(gold_scores) - set(baseline_scores))
        raise ValueError(
            "gold keys do not match run predictions; "
            f"missing_gold={missing_gold}, missing_predictions={missing_predictions}"
        )

    baseline_metrics = evaluate_scores(
        gold_scores,
        baseline_scores,
        baseline_confidence if baseline_confidence else None,
    )
    candidate_metrics = evaluate_scores(
        gold_scores,
        candidate_scores,
        candidate_confidence if candidate_confidence else None,
    )
    paired = paired_student_bootstrap(
        gold_scores,
        baseline_scores,
        candidate_scores,
        seed=bootstrap_seed,
        samples=bootstrap_samples,
    )
    metric_deltas = {
        metric: candidate_metrics[metric] - baseline_metrics[metric]
        for metric in (
            "exact_agreement",
            "subquestion_mae",
            "mean_signed_error",
            "total_score_mae",
            "within_1_point_rate",
            "severe_error_rate",
            "macro_accuracy",
        )
    }
    return {
        "record_type": "physics_run_metrics_comparison",
        "generated_at": _utc_now(),
        "benchmark_root": str(benchmark_root),
        "baseline_run": _run_summary(baseline_run),
        "candidate_run": _run_summary(candidate_run),
        "student_count": len(student_ids),
        "score_count": len(gold_scores),
        "bootstrap": {
            "seed": bootstrap_seed,
            "samples": bootstrap_samples,
            "exact_agreement_candidate_minus_baseline": paired,
        },
        "baseline": baseline_metrics,
        "candidate": candidate_metrics,
        "candidate_minus_baseline": metric_deltas,
    }


def load_run_scores(run_dir: Path) -> tuple[dict[ScoreKey, float], dict[ScoreKey, str]]:
    predictions = run_dir / "predictions.csv"
    if predictions.exists():
        return load_score_table(predictions)

    outputs = run_dir / "outputs"
    if not outputs.is_dir():
        raise ValueError(f"run has neither predictions.csv nor outputs/: {run_dir}")

    scores: dict[ScoreKey, float] = {}
    confidence: dict[ScoreKey, str] = {}
    output_paths = sorted(outputs.glob("*.json"))
    if not output_paths:
        raise ValueError(f"run outputs are empty: {outputs}")
    for path in output_paths:
        for record in parse_grading_output(path, path.stem):
            key = (record.student_id, record.question_id)
            if key in scores:
                raise ValueError(f"duplicate score row in {path}: {key}")
            scores[key] = record.score
            confidence[key] = record.confidence
    return scores, confidence


def load_score_table(
    path: Path,
    *,
    student_ids: set[str] | None = None,
) -> tuple[dict[ScoreKey, float], dict[ScoreKey, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    scores: dict[ScoreKey, float] = {}
    confidence: dict[ScoreKey, str] = {}
    for row in rows:
        student_id = row["student_id"]
        if student_ids is not None and student_id not in student_ids:
            continue
        key = (student_id, row["question_id"])
        if key in scores:
            raise ValueError(f"duplicate score row in {path}: {key}")
        raw_score = row["score"].strip()
        if not raw_score:
            raise ValueError(f"blank score in {path}: {key}")
        scores[key] = float(raw_score)
        raw_confidence = row.get("confidence", "").strip()
        if raw_confidence:
            confidence[key] = raw_confidence
    return scores, confidence


def write_metrics_json(path: Path, result: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_metrics_markdown(path: Path, result: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Physics Metrics Comparison",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Benchmark root: `{result['benchmark_root']}`",
        f"- Baseline run: `{result['baseline_run']['path']}`",
        f"- Candidate run: `{result['candidate_run']['path']}`",
        f"- Students: `{result['student_count']}`",
        f"- Score rows: `{result['score_count']}`",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Baseline | Candidate | Candidate - Baseline |",
        "|---|---:|---:|---:|",
    ]
    for metric in (
        "exact_agreement",
        "total_score_mae",
        "within_1_point_rate",
        "severe_error_rate",
        "subquestion_mae",
        "mean_signed_error",
        "macro_accuracy",
    ):
        lines.append(
            "| {metric} | {baseline:.4f} | {candidate:.4f} | {delta:.4f} |".format(
                metric=metric,
                baseline=result["baseline"][metric],
                candidate=result["candidate"][metric],
                delta=result["candidate_minus_baseline"][metric],
            )
        )

    interval = result["bootstrap"]["exact_agreement_candidate_minus_baseline"]
    lines.extend(
        [
            "",
            "## Paired Bootstrap",
            "",
            "- Metric: exact agreement, candidate minus baseline",
            f"- Seed: `{result['bootstrap']['seed']}`",
            f"- Samples: `{result['bootstrap']['samples']}`",
            f"- Mean difference: `{interval['mean_difference']:.4f}`",
            f"- 95% interval: `[{interval['lower']:.4f}, {interval['upper']:.4f}]`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _run_summary(run_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {"path": str(run_dir)}
    for name in ("run-metadata.json", "manifest.json"):
        path = run_dir / name
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            for key in (
                "provider",
                "model",
                "input_mode",
                "validation_status",
                "packet_hash",
                "prompt_hash",
                "rubric_hash",
                "run_commit",
            ):
                if key in payload:
                    summary[key] = payload[key]
            break
    validation = run_dir / "validation.json"
    if validation.exists():
        payload = json.loads(validation.read_text(encoding="utf-8"))
        summary["validation"] = {
            key: payload[key]
            for key in (
                "status",
                "students_expected",
                "students_passed",
                "students_failed",
            )
            if key in payload
        }
    return summary


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
