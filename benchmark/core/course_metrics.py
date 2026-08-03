"""Course-generic, aggregate-only comparison of completed grading runs.

Private gold and run outputs are read only locally.  Generated reports exclude
student identifiers, per-student scores, model evidence, raw answers, and paths
to private data so they can be placed in a public research record safely.
"""

from __future__ import annotations

import csv
import json
import math
import random
import re
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence

from .gold import validate_gold_table
from .schema import CONFIDENCE_LEVELS, CourseSpec


ScoreKey = tuple[str, str]

_HASH = re.compile(r"^[0-9a-f]{64}$")
_ANONYMOUS_STUDENT_ID = re.compile(r"\bS\d{3,}\b")
_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]{2}|/[A-Za-z])")
_COMPACT_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
_PRIVATE_PATH_SEGMENT = re.compile(
    r"(?i)(?:^|[\\/])(?:data|\.private-data|local)(?:[\\/]|$)"
)
_EMBEDDED_DRIVE_PATH = re.compile(r"(?i)[A-Za-z]:[\\/]")
_EPSILON = 1e-9
_METRIC_FIELDS = (
    "exact_agreement",
    "subquestion_mae",
    "mean_signed_error",
    "total_score_mae",
    "within_1_point_rate",
    "severe_error_rate",
    "macro_accuracy",
)


class CourseMetricsError(ValueError):
    """A local validation error that is safe to display before publication."""


def compare_course_runs(
    course: CourseSpec,
    gold_path: Path,
    student_ids: Sequence[str],
    baseline_run: Path,
    candidate_run: Path,
    *,
    bootstrap_seed: int = 20260701,
    bootstrap_samples: int = 10_000,
    require_same_data_snapshot: bool = False,
) -> dict[str, Any]:
    """Compare two complete runs against a ready question-level gold table.

    Each run may be a standard model-run directory, its ``outputs/`` directory,
    or a standalone predictions CSV.  Every requested anonymous student and
    every CourseSpec question must be present exactly once in both runs.
    """

    expected_students = _normalize_students(course, student_ids)
    gold_path = Path(gold_path).resolve()
    # Gold may intentionally cover the complete anonymous cohort while this
    # comparison evaluates only a frozen development or held-out split. Filter
    # before validation so out-of-split rows neither leak into a public report
    # nor make a valid split look incomplete. The selected rows still go
    # through the canonical strict validator unchanged.
    with tempfile.TemporaryDirectory(
        prefix="exam-automark-selected-gold-",
        dir=gold_path.parent,
    ) as tmp:
        selected_gold = Path(tmp) / "selected-gold.csv"
        _write_selected_gold(gold_path, selected_gold, expected_students)
        gold_report = validate_gold_table(course, selected_gold, expected_students)
        if gold_report["status"] != "ready":
            raise CourseMetricsError(
                "gold table is not ready: "
                + ", ".join(gold_report["failed_checks"])
            )
        gold = _load_gold_scores(selected_gold, expected_students)

    baseline_scores, baseline_confidence, baseline_summary = _load_run_scores(
        Path(baseline_run), course, expected_students
    )
    candidate_scores, candidate_confidence, candidate_summary = _load_run_scores(
        Path(candidate_run), course, expected_students
    )
    _require_matching_keys(gold, baseline_scores, label="baseline")
    _require_matching_keys(gold, candidate_scores, label="candidate")

    result = {
        "schema_version": 1,
        "record_type": "course_generic_run_metrics_comparison",
        "generated_at": _utc_now(),
        "course": {
            "course_id": _safe_identifier(course.course_id),
            "assessment_id": _safe_identifier(course.assessment_id),
            "score_unit": _safe_identifier(course.score_unit),
            "question_count": len(course.questions),
            "max_total": course.max_total,
        },
        "population": {
            "student_count": len(expected_students),
            "score_row_count": len(gold),
        },
        "metric_policy": {
            "exact_score_tolerance": _EPSILON,
            "within_total_points": 1.0,
            "severe_total_points": 2.0,
            "paired_bootstrap_unit": "student",
        },
        "comparison_provenance": _comparison_provenance(
            baseline_summary,
            candidate_summary,
            require_same_data_snapshot=require_same_data_snapshot,
        ),
        "baseline_run": baseline_summary,
        "candidate_run": candidate_summary,
        "baseline": evaluate_course_scores(
            gold, baseline_scores, baseline_confidence or None
        ),
        "candidate": evaluate_course_scores(
            gold, candidate_scores, candidate_confidence or None
        ),
    }
    result["candidate_minus_baseline"] = {
        metric: result["candidate"][metric] - result["baseline"][metric]
        for metric in _METRIC_FIELDS
    }
    result["bootstrap"] = {
        "seed": bootstrap_seed,
        "samples": bootstrap_samples,
        "exact_agreement_candidate_minus_baseline": paired_student_bootstrap(
            gold,
            baseline_scores,
            candidate_scores,
            seed=bootstrap_seed,
            samples=bootstrap_samples,
        ),
    }
    result["privacy"] = {
        "aggregate_only": True,
        "student_ids_included": False,
        "per_student_scores_included": False,
        "raw_answers_included": False,
        "model_evidence_included": False,
        "private_paths_included": False,
    }
    assert_privacy_safe_comparison(result)
    return result


def evaluate_course_scores(
    gold: dict[ScoreKey, float],
    predicted: dict[ScoreKey, float],
    confidence: dict[ScoreKey, str] | None = None,
) -> dict[str, Any]:
    """Calculate aggregate metrics without returning a row-level result."""

    _require_matching_keys(gold, predicted, label="prediction")
    errors = {key: predicted[key] - gold[key] for key in sorted(gold)}
    total_errors: dict[str, float] = defaultdict(float)
    question_errors: dict[str, list[float]] = defaultdict(list)
    for (student_id, question_id), error in errors.items():
        total_errors[student_id] += error
        question_errors[question_id].append(error)

    per_question = {
        question_id: {
            "score_row_count": len(values),
            "exact_agreement": fmean(_same_score(value, 0.0) for value in values),
            "mae": fmean(abs(value) for value in values),
            "mean_signed_error": fmean(values),
        }
        for question_id, values in sorted(question_errors.items())
    }
    result: dict[str, Any] = {
        "exact_agreement": fmean(_same_score(value, 0.0) for value in errors.values()),
        "subquestion_mae": fmean(abs(value) for value in errors.values()),
        "mean_signed_error": fmean(errors.values()),
        "total_score_mae": fmean(abs(value) for value in total_errors.values()),
        "within_1_point_rate": fmean(
            abs(value) <= 1.0 + _EPSILON for value in total_errors.values()
        ),
        "severe_error_rate": fmean(
            abs(value) > 2.0 + _EPSILON for value in total_errors.values()
        ),
        "macro_accuracy": fmean(
            values["exact_agreement"] for values in per_question.values()
        ),
        "per_question": per_question,
    }
    if confidence is None:
        result["confidence_accuracy"] = {
            "status": "not_available",
            "reason": "confidence labels were not supplied for every score row",
        }
        return result

    _require_matching_keys(gold, confidence, label="confidence")
    by_level: dict[str, list[bool]] = defaultdict(list)
    for key, error in errors.items():
        by_level[confidence[key]].append(_same_score(error, 0.0))
    result["confidence_accuracy"] = {
        "status": "available",
        "by_level": {
            level: {
                "score_row_count": len(matches),
                "exact_agreement": fmean(matches),
            }
            for level, matches in sorted(by_level.items())
        },
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
    """Paired bootstrap for candidate-minus-baseline exact agreement."""

    _require_matching_keys(gold, baseline, label="baseline")
    _require_matching_keys(gold, candidate, label="candidate")
    if samples <= 0:
        raise CourseMetricsError("bootstrap samples must be positive")
    student_keys: dict[str, list[ScoreKey]] = defaultdict(list)
    for key in sorted(gold):
        student_keys[key[0]].append(key)
    differences = []
    for keys in student_keys.values():
        left = fmean(_same_score(baseline[key], gold[key]) for key in keys)
        right = fmean(_same_score(candidate[key], gold[key]) for key in keys)
        differences.append(right - left)
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


def write_course_metrics_json(path: Path, report: dict[str, Any]) -> Path:
    """Write a privacy-checked aggregate JSON report."""

    assert_privacy_safe_comparison(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def write_course_metrics_markdown(path: Path, report: dict[str, Any]) -> Path:
    """Write a privacy-checked aggregate Markdown report."""

    assert_privacy_safe_comparison(report)
    markdown = render_course_metrics_markdown(report)
    if _ANONYMOUS_STUDENT_ID.search(markdown):
        raise CourseMetricsError("refusing to write Markdown containing a student ID")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8", newline="\n")
    return path


def render_course_metrics_markdown(report: dict[str, Any]) -> str:
    """Render an aggregate-only human-readable comparison."""

    assert_privacy_safe_comparison(report)
    course = report["course"]
    population = report["population"]
    baseline = report["baseline"]
    candidate = report["candidate"]
    deltas = report["candidate_minus_baseline"]
    provenance = report["comparison_provenance"]
    lines = [
        "# Course-generic grading comparison",
        "",
        "## Scope",
        "",
        f"- Course / assessment: `{_escape(course['course_id'])}` / "
        f"`{_escape(course['assessment_id'])}`",
        f"- Questions: `{course['question_count']}`; maximum total: "
        f"`{course['max_total']}` {course['score_unit']}",
        f"- Anonymous population: `{population['student_count']}` students; "
        f"`{population['score_row_count']}` question scores",
        "",
        "This report is aggregate-only. It excludes student IDs, individual scores, "
        "raw answers, evidence, prompts, model responses, and private paths.",
        "",
        "## Run provenance",
        "",
        "| Check | Status |",
        "| --- | --- |",
        f"| Run validation | `{_escape(provenance['run_validation'])}` |",
        f"| Course/assessment metadata | `{_escape(provenance['course_metadata'])}` |",
        f"| Anonymous population | `{_escape(provenance['population'])}` |",
        f"| Data-snapshot relation | `{_escape(provenance['data_snapshot'])}` |",
        "",
        "| Run | Provider / engine | Model | Input mode | Condition | Validation |",
        "| --- | --- | --- | --- | --- | --- |",
        _render_run_row("Baseline", report["baseline_run"]),
        _render_run_row("Candidate", report["candidate_run"]),
        "",
        "## Aggregate metrics",
        "",
        "| Metric | Baseline | Candidate | Candidate - baseline |",
        "| --- | ---: | ---: | ---: |",
    ]
    for metric in _METRIC_FIELDS:
        lines.append(
            f"| `{metric}` | {baseline[metric]:.4f} | {candidate[metric]:.4f} "
            f"| {deltas[metric]:.4f} |"
        )
    interval = report["bootstrap"]["exact_agreement_candidate_minus_baseline"]
    lines.extend(
        [
            "",
            "## Paired bootstrap",
            "",
            "- Unit: student; metric: exact-agreement candidate minus baseline.",
            f"- Seed / samples: `{report['bootstrap']['seed']}` / "
            f"`{report['bootstrap']['samples']}`",
            f"- Mean difference: `{interval['mean_difference']:.4f}`",
            f"- 95% interval: `[{interval['lower']:.4f}, {interval['upper']:.4f}]`",
            "",
            "## Per-question aggregate metrics",
            "",
            "Question identifiers are course metadata, not student identities.",
            "",
            "| Question | Rows | Baseline exact | Candidate exact | Delta exact | "
            "Baseline MAE | Candidate MAE | Delta MAE |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for question_id in sorted(baseline["per_question"]):
        left = baseline["per_question"][question_id]
        right = candidate["per_question"][question_id]
        lines.append(
            f"| `{_escape(question_id)}` | {left['score_row_count']} | "
            f"{left['exact_agreement']:.4f} | {right['exact_agreement']:.4f} | "
            f"{right['exact_agreement'] - left['exact_agreement']:.4f} | "
            f"{left['mae']:.4f} | {right['mae']:.4f} | "
            f"{right['mae'] - left['mae']:.4f} |"
        )
    lines.extend(_render_confidence_section("Baseline", baseline))
    lines.extend(_render_confidence_section("Candidate", candidate))
    lines.append("")
    return "\n".join(lines)


def assert_privacy_safe_comparison(report: dict[str, Any]) -> None:
    """Reject a report that carries individual or raw-answer information."""

    forbidden_keys = {
        "student_id",
        "student_ids",
        "raw_text",
        "answer",
        "answers",
        "evidence",
        "extracted_evidence",
        "feedback",
        "prompt",
        "input_images",
        "inputs",
        "gold_path",
        "baseline_path",
        "candidate_path",
        "packet",
        "command",
    }

    def visit(value: Any, location: str = "$") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                if key_text.lower() in forbidden_keys:
                    raise CourseMetricsError(
                        f"private key {key_text!r} detected at {location}"
                    )
                visit(child, f"{location}.{key_text}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{location}[{index}]")
        elif isinstance(value, str) and _ANONYMOUS_STUDENT_ID.search(value):
            raise CourseMetricsError(f"anonymous student ID detected at {location}")

    visit(report)


def _normalize_students(course: CourseSpec, student_ids: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(str(value).strip() for value in student_ids)
    if not normalized:
        raise CourseMetricsError("student_ids must not be empty")
    if len(normalized) != len(set(normalized)):
        raise CourseMetricsError("student_ids must be unique")
    for student_id in normalized:
        course.validate_student_id(student_id)
    return normalized


def _load_gold_scores(
    path: Path, student_ids: Sequence[str]
) -> dict[ScoreKey, float]:
    scores: dict[ScoreKey, float] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            student_id = str(row.get("student_id") or "").strip()
            if student_id not in student_ids:
                continue
            question_id = str(row.get("question_id") or "").strip()
            raw_score = str(row.get("score") or "").strip()
            if not raw_score:
                raise CourseMetricsError("validated gold unexpectedly contains a blank score")
            key = (student_id, question_id)
            if key in scores:
                raise CourseMetricsError("validated gold unexpectedly contains a duplicate")
            scores[key] = float(raw_score)
    return scores


def _write_selected_gold(
    source_path: Path,
    selected_path: Path,
    student_ids: Sequence[str],
) -> None:
    """Copy only the requested anonymous rows to an ephemeral validation CSV."""

    selected_students = set(student_ids)
    with source_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        fieldnames = list(reader.fieldnames or ())
        with selected_path.open("w", newline="", encoding="utf-8") as destination:
            writer = csv.DictWriter(destination, fieldnames=fieldnames)
            if fieldnames:
                writer.writeheader()
            for row in reader:
                student_id = str(row.get("student_id") or "").strip()
                if student_id in selected_students:
                    writer.writerow(row)


def _load_run_scores(
    path: Path,
    course: CourseSpec,
    student_ids: tuple[str, ...],
) -> tuple[dict[ScoreKey, float], dict[ScoreKey, str], dict[str, Any]]:
    if path.is_file():
        if path.suffix.lower() != ".csv":
            raise CourseMetricsError("a run file must be a predictions CSV")
        scores, confidence = _read_predictions_csv(path, course, student_ids)
        return scores, confidence, {
            "source_kind": "prediction_csv",
            "validation_status": "self_validated",
            "course_metadata": "not_recorded",
        }
    if not path.is_dir():
        raise FileNotFoundError(f"run path does not exist: {path}")

    if (path / "outputs").is_dir() or (path / "predictions.csv").is_file():
        run_root, output_dir, source_kind = path, path / "outputs", "run_directory"
    else:
        run_root, output_dir, source_kind = path.parent, path, "outputs_directory"
    metadata = _load_optional_json(run_root / "run-metadata.json")
    validation = _load_optional_json(run_root / "validation.json")
    validation_status = _validate_run_metadata(
        metadata, validation, course, student_ids
    )
    csv_path = run_root / "predictions.csv" if source_kind == "run_directory" else None
    json_paths = sorted(output_dir.glob("*.json"))
    if csv_path is not None and csv_path.is_file() and json_paths:
        raise CourseMetricsError(
            "run directory has both predictions.csv and outputs; choose one explicit source"
        )
    if csv_path is not None and csv_path.is_file():
        scores, confidence = _read_predictions_csv(csv_path, course, student_ids)
        source_kind = "run_directory_prediction_csv"
    else:
        scores, confidence = _read_output_jsons(output_dir, course, student_ids)
    return scores, confidence, _safe_run_summary(
        source_kind, metadata, validation, validation_status=validation_status
    )


def _validate_run_metadata(
    metadata: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    course: CourseSpec,
    student_ids: tuple[str, ...],
) -> str:
    if validation is not None and validation.get("status") != "passed":
        raise CourseMetricsError("run validation status must be passed")
    if metadata is None:
        return "passed" if validation is not None else "self_validated"
    if metadata.get("dry_run") is True:
        raise CourseMetricsError("dry-run outputs cannot be used for score comparison")
    task = metadata.get("task")
    if task is not None and task != "grade":
        raise CourseMetricsError("only completed grade runs can be compared")
    for field, expected in (
        ("course_id", course.course_id),
        ("assessment_id", course.assessment_id),
    ):
        actual = metadata.get(field)
        if actual is not None and actual != expected:
            raise CourseMetricsError(f"run metadata {field} does not match course")
    metadata_students = metadata.get("student_ids")
    if metadata_students is not None:
        if not isinstance(metadata_students, list) or any(
            not isinstance(value, str) for value in metadata_students
        ):
            raise CourseMetricsError("run metadata student_ids must be a string list")
        if len(metadata_students) != len(set(metadata_students)) or set(
            metadata_students
        ) != set(student_ids):
            raise CourseMetricsError("run metadata population does not match comparison")
    return "passed" if validation is not None else "self_validated"


def _read_output_jsons(
    output_dir: Path,
    course: CourseSpec,
    student_ids: tuple[str, ...],
) -> tuple[dict[ScoreKey, float], dict[ScoreKey, str]]:
    if not output_dir.is_dir():
        raise FileNotFoundError(f"run outputs directory missing: {output_dir}")
    paths = sorted(output_dir.glob("*.json"))
    actual_students = {path.stem for path in paths}
    expected_students = set(student_ids)
    if actual_students != expected_students:
        raise CourseMetricsError(
            "run outputs must contain exactly the expected student files "
            f"(missing={len(expected_students - actual_students)}, "
            f"unexpected={len(actual_students - expected_students)})"
        )
    scores: dict[ScoreKey, float] = {}
    confidence: dict[ScoreKey, str] = {}
    for path in paths:
        payload = _read_required_json(path)
        student_id = path.stem
        if payload.get("student_id") != student_id:
            raise CourseMetricsError("output student_id does not match its filename")
        rows = payload.get("scores")
        if not isinstance(rows, list):
            raise CourseMetricsError("output scores must be a list")
        seen_questions: set[str] = set()
        total = 0.0
        for row in rows:
            if not isinstance(row, dict):
                raise CourseMetricsError("each output score row must be an object")
            question_id = row.get("question_id")
            if not isinstance(question_id, str) or question_id not in course.question_map:
                raise CourseMetricsError("output has an unknown question_id")
            if question_id in seen_questions:
                raise CourseMetricsError("output has a duplicate question score")
            raw_score = row.get("score")
            if not _is_finite_number(raw_score):
                raise CourseMetricsError("output score must be a finite number")
            score = float(raw_score)
            if not course.question_map[question_id].allows_score(score):
                raise CourseMetricsError("output score is outside the course range or step")
            raw_confidence = row.get("confidence")
            if raw_confidence not in CONFIDENCE_LEVELS:
                raise CourseMetricsError("output confidence must be high, medium, or low")
            key = (student_id, question_id)
            scores[key] = score
            confidence[key] = str(raw_confidence)
            seen_questions.add(question_id)
            total += score
        if seen_questions != set(course.question_ids):
            raise CourseMetricsError("output questions do not match the course")
        if not _is_finite_number(payload.get("total")) or not _same_score(
            float(payload["total"]), total
        ):
            raise CourseMetricsError("output total must equal its question scores")
    _validate_prediction_pairs(scores, course, student_ids)
    return scores, confidence


def _read_predictions_csv(
    path: Path,
    course: CourseSpec,
    student_ids: tuple[str, ...],
) -> tuple[dict[ScoreKey, float], dict[ScoreKey, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = {"student_id", "question_id", "score"} - set(
            reader.fieldnames or ()
        )
        if missing:
            raise CourseMetricsError(
                "predictions CSV missing required columns: " + ", ".join(sorted(missing))
            )
        rows = list(reader)
    scores: dict[ScoreKey, float] = {}
    confidence: dict[ScoreKey, str] = {}
    for row in rows:
        student_id = str(row.get("student_id") or "").strip()
        question_id = str(row.get("question_id") or "").strip()
        if student_id not in student_ids:
            raise CourseMetricsError("predictions CSV has an unexpected student")
        if question_id not in course.question_map:
            raise CourseMetricsError("predictions CSV has an unknown question")
        key = (student_id, question_id)
        if key in scores:
            raise CourseMetricsError("predictions CSV has a duplicate score row")
        try:
            score = float(str(row.get("score") or "").strip())
        except ValueError as error:
            raise CourseMetricsError("predictions CSV score must be numeric") from error
        if not math.isfinite(score) or not course.question_map[question_id].allows_score(score):
            raise CourseMetricsError("predictions CSV score is outside the course range or step")
        scores[key] = score
        raw_confidence = str(row.get("confidence") or "").strip()
        if raw_confidence:
            if raw_confidence not in CONFIDENCE_LEVELS:
                raise CourseMetricsError(
                    "predictions CSV confidence must be high, medium, or low"
                )
            confidence[key] = raw_confidence
    _validate_prediction_pairs(scores, course, student_ids)
    if confidence and set(confidence) != set(scores):
        raise CourseMetricsError(
            "predictions CSV confidence must be supplied for every score row or none"
        )
    return scores, confidence


def _validate_prediction_pairs(
    scores: dict[ScoreKey, float],
    course: CourseSpec,
    student_ids: Sequence[str],
) -> None:
    expected = {
        (student_id, question_id)
        for student_id in student_ids
        for question_id in course.question_ids
    }
    actual = set(scores)
    if actual != expected:
        raise CourseMetricsError(
            "prediction scores do not cover the expected population/questions "
            f"(missing={len(expected - actual)}, unexpected={len(actual - expected)})"
        )


def _require_matching_keys(
    expected: dict[ScoreKey, Any], actual: dict[ScoreKey, Any], *, label: str
) -> None:
    if not expected:
        raise CourseMetricsError("score table must not be empty")
    if set(expected) != set(actual):
        raise CourseMetricsError(
            f"{label} score keys do not match the expected population "
            f"(missing={len(set(expected) - set(actual))}, "
            f"unexpected={len(set(actual) - set(expected))})"
        )


def _comparison_provenance(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    require_same_data_snapshot: bool,
) -> dict[str, str]:
    snapshots = (baseline.get("data_snapshot_hash"), candidate.get("data_snapshot_hash"))
    if all(isinstance(value, str) for value in snapshots):
        snapshot_status = "matched" if snapshots[0] == snapshots[1] else "different"
    else:
        snapshot_status = "not_recorded"
    if require_same_data_snapshot and snapshot_status != "matched":
        raise CourseMetricsError(
            "runs do not record the same data snapshot; cannot satisfy "
            "--require-same-data-snapshot"
        )
    metadata = (baseline.get("course_metadata"), candidate.get("course_metadata"))
    return {
        "run_validation": (
            "passed"
            if all(run.get("validation_status") == "passed" for run in (baseline, candidate))
            else "self_validated"
        ),
        "course_metadata": (
            "matched" if metadata == ("matched", "matched") else "partially_not_recorded"
        ),
        "population": "matched_by_exact_question_coverage",
        "data_snapshot": snapshot_status,
    }


def _safe_run_summary(
    source_kind: str,
    metadata: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    *,
    validation_status: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_kind": source_kind,
        "validation_status": validation_status,
        "course_metadata": "not_recorded",
    }
    if validation is not None:
        for field in ("students_expected", "students_passed", "students_failed"):
            value = validation.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                result[field] = value
    if metadata is None:
        return result
    result["course_metadata"] = (
        "matched"
        if metadata.get("course_id") is not None and metadata.get("assessment_id") is not None
        else "not_recorded"
    )
    for field in (
        "record_type",
        "provider",
        "engine",
        "model",
        "input_mode",
        "condition",
        "experiment_condition",
        "task",
    ):
        value = metadata.get(field)
        if isinstance(value, str) and value.strip():
            result[field] = _safe_identifier(value)
    for field in (
        "packet_hash",
        "prompt_hash",
        "rubric_hash",
        "data_snapshot_hash",
        "text_source_hash",
    ):
        value = metadata.get(field)
        if isinstance(value, str) and _HASH.fullmatch(value):
            result[field] = value
    return result


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    return _read_required_json(path) if path.is_file() else None


def _read_required_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CourseMetricsError(f"invalid JSON: {path.name}") from error
    if not isinstance(payload, dict):
        raise CourseMetricsError(f"JSON object required: {path.name}")
    return payload


def _same_score(left: float, right: float) -> bool:
    return abs(left - right) <= _EPSILON


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _render_run_row(label: str, summary: dict[str, Any]) -> str:
    provider = summary.get("provider") or summary.get("engine") or "not recorded"
    engine = summary.get("engine")
    if engine and engine != provider:
        provider = f"{provider} / {engine}"
    return (
        f"| {label} | `{_escape(str(provider))}` | "
        f"`{_escape(str(summary.get('model') or 'not recorded'))}` | "
        f"`{_escape(str(summary.get('input_mode') or 'not recorded'))}` | "
        f"`{_escape(str(summary.get('experiment_condition') or summary.get('condition') or 'not recorded'))}` | "
        f"`{_escape(str(summary.get('validation_status') or 'not recorded'))}` |"
    )


def _render_confidence_section(label: str, metrics: dict[str, Any]) -> list[str]:
    confidence = metrics["confidence_accuracy"]
    lines = ["", f"## {label} confidence accuracy", ""]
    if confidence["status"] != "available":
        return lines + [f"Not available: {confidence['reason']}"]
    lines.extend(
        [
            "| Confidence | Score rows | Exact agreement |",
            "| --- | ---: | ---: |",
        ]
    )
    for level, values in confidence["by_level"].items():
        lines.append(
            f"| `{_escape(level)}` | {values['score_row_count']} | "
            f"{values['exact_agreement']:.4f} |"
        )
    return lines


def _safe_identifier(value: str) -> str:
    """Accept only a compact metadata identifier safe for public reports."""

    if not isinstance(value, str):
        raise CourseMetricsError("run metadata contains an unsafe public identifier")
    compact = value
    if (
        _COMPACT_IDENTIFIER.fullmatch(compact) is None
        or _ANONYMOUS_STUDENT_ID.search(compact)
        or _ABSOLUTE_PATH.match(compact)
        or _EMBEDDED_DRIVE_PATH.search(compact)
        or _PRIVATE_PATH_SEGMENT.search(compact)
        or "://" in compact
        or "/../" in compact
        or "/./" in compact
    ):
        raise CourseMetricsError("run metadata contains an unsafe public identifier")
    return compact


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
