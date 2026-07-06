import math
import random
from collections import defaultdict
from statistics import fmean
from typing import Any


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
