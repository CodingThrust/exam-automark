"""Build a private grading-error book and a privacy-safe public summary."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

from .packets import directory_digest
from .schema import (
    CONFIDENCE_LEVELS,
    CourseSpec,
    ScoreRecord,
    validate_score_records,
)


DEVELOPMENT_SPLITS = {"dev", "development"}
SEVERE_ERROR_THRESHOLD = 5.0
ANONYMOUS_STUDENT_ID = re.compile(r"\bS[0-9]{3,}\b", re.IGNORECASE)
WINDOWS_ABSOLUTE_PATH = re.compile(r"\b[A-Za-z]:[\\/]")
FORBIDDEN_PUBLIC_KEYS = {
    "anonymous_student_id",
    "student_id",
    "student_ids",
    "evidence",
    "extracted_evidence",
    "gold_score",
    "predicted_score",
    "signed_error",
    "output_file",
    "output_path",
    "notes",
    "flag",
    "flags",
    "flags_on_error_cases",
}


@dataclass(frozen=True)
class ErrorBookResult:
    private_book: dict[str, Any]
    public_summary: dict[str, Any]


@dataclass(frozen=True)
class _ScoredItem:
    student_id: str
    question_id: str
    gold_score: float
    predicted_score: float
    confidence: str
    flags: tuple[str, ...]
    evidence: str
    extracted_evidence: str
    output_file: str
    output_sha256: str

    @property
    def signed_error(self) -> float:
        return _clean_number(self.predicted_score - self.gold_score)

    @property
    def absolute_error(self) -> float:
        return _clean_number(abs(self.signed_error))

    @property
    def is_exact(self) -> bool:
        return self.signed_error == 0

    @property
    def is_severe(self) -> bool:
        return self.absolute_error >= SEVERE_ERROR_THRESHOLD

    @property
    def direction(self) -> str:
        return "over_score" if self.signed_error > 0 else "under_score"


def build_error_book(
    *,
    run_dir: Path,
    gold_path: Path,
    packet_dir: Path,
) -> ErrorBookResult:
    """Build records without writing them.

    Only development runs are accepted. Student-level details stay exclusively
    in ``private_book``; ``public_summary`` contains aggregate statistics.
    """

    metadata = _read_json_object(run_dir / "run-metadata.json")
    manifest = _read_json_object(packet_dir / "manifest.json")
    course = CourseSpec.from_json_path(packet_dir / "course.json")
    _validate_provenance(metadata, manifest, course, packet_dir)

    expected_student_ids = _expected_student_ids(metadata, manifest, course)
    outputs = _load_outputs(run_dir, expected_student_ids, course)
    gold_scores = _load_gold(gold_path, expected_student_ids, course)

    predicted_keys = set(outputs)
    if set(gold_scores) != predicted_keys:
        missing_gold = sorted(predicted_keys - set(gold_scores))
        missing_predictions = sorted(set(gold_scores) - predicted_keys)
        raise ValueError(
            "gold keys do not match run predictions; "
            f"missing_gold={missing_gold}, missing_predictions={missing_predictions}"
        )

    items = [
        _ScoredItem(
            student_id=student_id,
            question_id=question_id,
            gold_score=gold_scores[(student_id, question_id)],
            predicted_score=output["score"],
            confidence=output["confidence"],
            flags=output["flags"],
            evidence=output["evidence"],
            extracted_evidence=output["extracted_evidence"],
            output_file=output["output_file"],
            output_sha256=output["output_sha256"],
        )
        for (student_id, question_id), output in sorted(
            outputs.items(),
            key=lambda pair: (
                _question_sort_key(pair[0][1]),
                pair[0][0].casefold(),
                pair[0][0],
            ),
        )
    ]
    error_items = [item for item in items if not item.is_exact]
    technical_failure_count = _nonempty_line_count(run_dir / "failures.jsonl")
    provenance = _provenance(
        metadata=metadata,
        manifest=manifest,
        run_dir=run_dir,
        gold_path=gold_path,
        packet_dir=packet_dir,
        outputs_dir=run_dir / "outputs",
    )

    private_book = {
        "record_type": "grading_error_book_private",
        "schema_version": 1,
        "scope": {
            "split": "development",
            "selection_rule": (
                "all student-question pairs with predicted_score != gold_score"
            ),
            "selection_rule_zh": "纳入开发集中所有预测分数不等于人工金标准分数的学生-题目对",
            "severe_error_definition": (
                f"absolute score error >= {SEVERE_ERROR_THRESHOLD:g} points"
            ),
            "severe_error_definition_zh": (
                f"单道题绝对分差大于等于 {SEVERE_ERROR_THRESHOLD:g} 分"
            ),
        },
        "provenance": provenance,
        "population": _population_summary(items, expected_student_ids),
        "technical_failures": {
            "count": technical_failure_count,
            "included_as_grading_cases": False,
        },
        "cases": [
            _private_case(index, item)
            for index, item in enumerate(error_items, start=1)
        ],
    }
    public_summary = _public_summary(
        items=items,
        expected_student_ids=expected_student_ids,
        technical_failure_count=technical_failure_count,
        provenance=provenance,
    )
    findings = audit_public_error_summary(public_summary)
    if findings:
        raise ValueError(f"public error summary failed privacy audit: {findings}")
    return ErrorBookResult(
        private_book=private_book,
        public_summary=public_summary,
    )


def write_error_book(
    *,
    run_dir: Path,
    gold_path: Path,
    packet_dir: Path,
    private_output: Path,
    public_output: Path,
) -> ErrorBookResult:
    if private_output.resolve() == public_output.resolve():
        raise ValueError("private and public outputs must use different paths")
    validate_private_output_path(private_output)
    result = build_error_book(
        run_dir=run_dir,
        gold_path=gold_path,
        packet_dir=packet_dir,
    )
    _write_json(private_output, result.private_book)
    _write_json(public_output, result.public_summary)
    return result


def audit_public_error_summary(payload: Any) -> list[str]:
    """Return privacy findings for a proposed public summary."""

    findings: list[str] = []

    def visit(value: Any, location: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized = str(key).casefold()
                if normalized in FORBIDDEN_PUBLIC_KEYS:
                    findings.append(f"forbidden key at {location}: {key}")
                visit(child, f"{location}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{location}[{index}]")
        elif isinstance(value, str):
            if ANONYMOUS_STUDENT_ID.search(value):
                findings.append(f"anonymous student id at {location}")
            if WINDOWS_ABSOLUTE_PATH.search(value) or value.startswith(("/", "\\")):
                findings.append(f"absolute path at {location}")
            if "Data/" in value or "Data\\" in value:
                findings.append(f"private Data path at {location}")

    visit(payload, "$")
    return sorted(set(findings))


def build_public_diagnosis_summary(
    *,
    private_book_path: Path,
    diagnoses_path: Path,
) -> dict[str, Any]:
    private_book = _read_json_object(private_book_path)
    diagnoses = _read_json_object(diagnoses_path)
    cases = private_book.get("cases")
    annotations = diagnoses.get("annotations")
    if not isinstance(cases, list) or not cases:
        raise ValueError("private error book must contain cases")
    if not isinstance(annotations, list) or not annotations:
        raise ValueError("diagnosis file must contain annotations")

    case_by_id: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            raise ValueError("every private error case must have a case_id")
        case_id = case["case_id"]
        if case_id in case_by_id:
            raise ValueError(f"duplicate private case_id: {case_id}")
        case_by_id[case_id] = case

    annotation_by_id: dict[str, dict[str, Any]] = {}
    required = {
        "case_id",
        "primary_cause",
        "review_confidence",
        "diagnosis_zh",
        "diagnosis_en",
        "recommended_action",
    }
    for annotation in annotations:
        if not isinstance(annotation, dict) or not required.issubset(annotation):
            raise ValueError("every diagnosis annotation must contain required fields")
        case_id = annotation["case_id"]
        if not isinstance(case_id, str):
            raise ValueError("diagnosis case_id must be text")
        if case_id in annotation_by_id:
            raise ValueError(f"duplicate diagnosis case_id: {case_id}")
        for field in required - {"case_id"}:
            if not isinstance(annotation[field], str) or not annotation[field].strip():
                raise ValueError(f"diagnosis field must be nonblank: {case_id}:{field}")
        annotation_by_id[case_id] = annotation

    if set(annotation_by_id) != set(case_by_id):
        missing = sorted(set(case_by_id) - set(annotation_by_id))
        extra = sorted(set(annotation_by_id) - set(case_by_id))
        raise ValueError(
            "diagnoses must cover every private error case exactly once; "
            f"missing={missing}, extra={extra}"
        )

    review_scope = diagnoses.get("review_scope")
    if not isinstance(review_scope, dict):
        review_scope = {}
    cause_counts = Counter(
        annotation["primary_cause"] for annotation in annotation_by_id.values()
    )
    confidence_counts = Counter(
        annotation["review_confidence"]
        for annotation in annotation_by_id.values()
    )
    action_counts = Counter(
        annotation["recommended_action"]
        for annotation in annotation_by_id.values()
    )
    by_question: dict[str, Counter[str]] = defaultdict(Counter)
    for case_id, annotation in annotation_by_id.items():
        question_id = case_by_id[case_id].get("question_id")
        if not isinstance(question_id, str):
            raise ValueError(f"private case has invalid question_id: {case_id}")
        by_question[question_id][annotation["primary_cause"]] += 1

    summary = {
        "record_type": "grading_error_diagnosis_public_summary",
        "schema_version": 1,
        "scope": {
            "split": "development",
            "contains_student_level_records": False,
            "contains_answer_or_evidence_text": False,
            "taxonomy_status": review_scope.get("taxonomy_status", "provisional"),
        },
        "review": {
            "case_count": len(case_by_id),
            "review_date": diagnoses.get("review_date"),
            "reviewer": review_scope.get("reviewer"),
            "reviewer_model_id": review_scope.get("reviewer_model_id"),
            "all_error_cases_reviewed": True,
            "private_error_book_sha256": _file_hash(private_book_path),
            "private_diagnoses_sha256": _file_hash(diagnoses_path),
        },
        "primary_cause_counts": [
            {"primary_cause": cause, "error_pairs": count}
            for cause, count in sorted(cause_counts.items())
        ],
        "review_confidence_counts": [
            {"review_confidence": level, "error_pairs": count}
            for level, count in sorted(confidence_counts.items())
        ],
        "recommended_action_counts": [
            {"recommended_action": action, "error_pairs": count}
            for action, count in sorted(
                action_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
        "by_question": [
            {
                "question_id": question_id,
                "error_pairs_reviewed": sum(counts.values()),
                "primary_cause_counts": [
                    {"primary_cause": cause, "error_pairs": count}
                    for cause, count in sorted(counts.items())
                ],
            }
            for question_id, counts in sorted(
                by_question.items(), key=lambda item: _question_sort_key(item[0])
            )
        ],
        "interpretation_limits": {
            "zh": [
                "根因标签是当前模型基于开发集证据给出的可审计判断，不是最终人工裁决。",
                "rubric-gold 不一致的案例必须先由课程负责人裁决，不能直接用于优化 skill。",
                "该汇总不包含测试集、学生编号、答案文字或逐案分数。",
            ],
            "en": [
                "Root-cause labels are auditable development-split judgments "
                "by the current model, not final human adjudications.",
                "Rubric-gold mismatch cases require course-owner adjudication "
                "before skill optimization.",
                "This summary contains no held-out data, student identifiers, "
                "answer text, or case-level scores.",
            ],
        },
    }
    findings = audit_public_error_summary(summary)
    if findings:
        raise ValueError(f"public diagnosis summary failed privacy audit: {findings}")
    return summary


def write_public_diagnosis_summary(
    *,
    private_book_path: Path,
    diagnoses_path: Path,
    public_output: Path,
) -> dict[str, Any]:
    summary = build_public_diagnosis_summary(
        private_book_path=private_book_path,
        diagnoses_path=diagnoses_path,
    )
    _write_json(public_output, summary)
    return summary


def _validate_provenance(
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    course: CourseSpec,
    packet_dir: Path,
) -> None:
    split = metadata.get("split")
    packet_split = manifest.get("metadata", {}).get("split")
    if split not in DEVELOPMENT_SPLITS or packet_split not in DEVELOPMENT_SPLITS:
        raise ValueError(
            "error books may only be built from an explicitly labelled "
            "development run and development packet"
        )
    if metadata.get("dry_run") is not False:
        raise ValueError("error book requires a non-dry-run model result")
    validation_status = metadata.get("validation_status")
    if not isinstance(validation_status, str) or not validation_status.startswith(
        "passed"
    ):
        raise ValueError("error book requires a validation-passed run")
    if manifest.get("task") != "grade":
        raise ValueError("error book requires a grading packet")
    for field, expected in (
        ("course_id", course.course_id),
        ("assessment_id", course.assessment_id),
        ("packet_id", manifest.get("packet_id")),
        ("condition", manifest.get("condition")),
    ):
        if metadata.get(field) != expected:
            raise ValueError(f"run metadata and packet disagree on {field}")
    actual_packet_hash = directory_digest(packet_dir)
    if metadata.get("packet_hash") != actual_packet_hash:
        raise ValueError("run packet hash does not match the supplied packet")
    for field in ("prompt_hash", "rubric_hash"):
        if metadata.get(field) != manifest.get(field):
            raise ValueError(f"run metadata and packet disagree on {field}")


def _expected_student_ids(
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    course: CourseSpec,
) -> tuple[str, ...]:
    packet_ids = manifest.get("student_ids")
    run_ids = metadata.get("student_ids")
    if (
        not isinstance(packet_ids, list)
        or not packet_ids
        or not all(isinstance(item, str) for item in packet_ids)
    ):
        raise ValueError("packet manifest must contain student_ids")
    if len(packet_ids) != len(set(packet_ids)):
        raise ValueError("packet manifest contains duplicate student_ids")
    if run_ids != packet_ids:
        raise ValueError("run metadata student_ids do not match packet student_ids")
    for student_id in packet_ids:
        course.validate_student_id(student_id)
    return tuple(packet_ids)


def _load_outputs(
    run_dir: Path,
    expected_student_ids: tuple[str, ...],
    course: CourseSpec,
) -> dict[tuple[str, str], dict[str, Any]]:
    output_dir = run_dir / "outputs"
    paths = sorted(output_dir.glob("*.json"), key=lambda path: path.name.casefold())
    output_by_id = {path.stem: path for path in paths}
    if len(output_by_id) != len(paths) or set(output_by_id) != set(
        expected_student_ids
    ):
        raise ValueError("run outputs do not exactly match packet student_ids")

    result: dict[tuple[str, str], dict[str, Any]] = {}
    for student_id in expected_student_ids:
        path = output_by_id[student_id]
        payload = _read_json_object(path)
        if payload.get("student_id") != student_id:
            raise ValueError(f"output student_id mismatch: {path.name}")
        raw_scores = payload.get("scores")
        if not isinstance(raw_scores, list):
            raise ValueError(f"output scores must be a list: {path.name}")
        records: list[ScoreRecord] = []
        extracted_by_question: dict[str, str] = {}
        for row in raw_scores:
            if not isinstance(row, dict):
                raise ValueError(f"score row must be an object: {path.name}")
            question_id = row.get("question_id")
            score = row.get("score")
            confidence = row.get("confidence")
            evidence = row.get("evidence")
            extracted_evidence = row.get("extracted_evidence")
            flags = row.get("flags")
            if not isinstance(question_id, str):
                raise ValueError(f"question_id must be text: {path.name}")
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                raise ValueError(f"score must be numeric: {path.name}")
            if confidence not in CONFIDENCE_LEVELS:
                raise ValueError(f"invalid confidence: {path.name}:{question_id}")
            if not isinstance(evidence, str):
                raise ValueError(f"evidence must be text: {path.name}:{question_id}")
            if not isinstance(extracted_evidence, str):
                raise ValueError(
                    f"extracted_evidence must be text: {path.name}:{question_id}"
                )
            if not isinstance(flags, list) or not all(
                isinstance(flag, str) for flag in flags
            ):
                raise ValueError(
                    f"flags must be a list of strings: {path.name}:{question_id}"
                )
            records.append(
                ScoreRecord(
                    student_id=student_id,
                    question_id=question_id,
                    score=float(score),
                    confidence=confidence,
                    evidence=evidence,
                    flags=tuple(flags),
                )
            )
            if question_id in extracted_by_question:
                raise ValueError(f"duplicate question_id: {path.name}:{question_id}")
            extracted_by_question[question_id] = extracted_evidence

        calculated_total = validate_score_records(records, course)
        total = payload.get("total")
        if not isinstance(total, (int, float)) or isinstance(total, bool):
            raise ValueError(f"total must be numeric: {path.name}")
        if abs(float(total) - calculated_total) > 1e-9:
            raise ValueError(f"reported total does not match course score total: {path.name}")
        output_sha256 = _file_hash(path)
        for record in records:
            key = (student_id, record.question_id)
            if key in result:
                raise ValueError(f"duplicate output score: {key}")
            result[key] = {
                "score": record.score,
                "confidence": record.confidence,
                "flags": record.flags,
                "evidence": record.evidence,
                "extracted_evidence": extracted_by_question[record.question_id],
                "output_file": path.name,
                "output_sha256": output_sha256,
            }
    return result


def _load_gold(
    path: Path,
    expected_student_ids: tuple[str, ...],
    course: CourseSpec,
) -> dict[tuple[str, str], float]:
    expected = set(expected_student_ids)
    scores: dict[tuple[str, str], float] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"student_id", "question_id", "score"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"gold score columns are incomplete: {path}")
        for row in reader:
            student_id = row["student_id"]
            if student_id not in expected:
                continue
            question_id = row["question_id"]
            if question_id not in course.question_map:
                raise ValueError(
                    f"unexpected gold question for development student: "
                    f"{student_id}:{question_id}"
                )
            key = (student_id, question_id)
            if key in scores:
                raise ValueError(f"duplicate gold score: {key}")
            raw_score = row["score"].strip()
            if not raw_score:
                raise ValueError(f"blank gold score: {key}")
            try:
                score = float(raw_score)
            except ValueError as error:
                raise ValueError(f"invalid gold score: {key}") from error
            if not course.question_map[question_id].allows_score(score):
                raise ValueError(f"gold score is out of range or off step: {key}")
            scores[key] = score

    expected_keys = {
        (student_id, question_id)
        for student_id in expected_student_ids
        for question_id in course.question_ids
    }
    if set(scores) != expected_keys:
        missing = sorted(expected_keys - set(scores))
        raise ValueError(
            f"gold scores are incomplete for development outputs: {missing}"
        )
    return scores


def _provenance(
    *,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    run_dir: Path,
    gold_path: Path,
    packet_dir: Path,
    outputs_dir: Path,
) -> dict[str, Any]:
    return {
        "course_id": metadata["course_id"],
        "assessment_id": metadata["assessment_id"],
        "condition": metadata["condition"],
        "run_id": run_dir.name,
        "provider": metadata.get("provider"),
        "model": metadata.get("model"),
        "input_mode": metadata.get("input_mode"),
        "skill_version_id": metadata.get("skill_version_id"),
        "run_commit": metadata.get("run_commit"),
        "packet_id": metadata.get("packet_id"),
        "packet_sha256": directory_digest(packet_dir),
        "output_set_sha256": _directory_hash(outputs_dir),
        "gold_sha256": _file_hash(gold_path),
        "prompt_sha256": manifest.get("prompt_hash"),
        "rubric_sha256": manifest.get("rubric_hash"),
        "data_snapshot_sha256": metadata.get("data_snapshot_hash"),
        "text_source_sha256": metadata.get("text_source_hash"),
    }


def _private_case(index: int, item: _ScoredItem) -> dict[str, Any]:
    return {
        "case_id": f"DEV-ERR-{index:03d}",
        "case_type": "scoring_disagreement",
        "anonymous_student_id": item.student_id,
        "question_id": item.question_id,
        "gold_score": item.gold_score,
        "predicted_score": item.predicted_score,
        "signed_error": item.signed_error,
        "absolute_error": item.absolute_error,
        "direction": item.direction,
        "severe_error": item.is_severe,
        "confidence": item.confidence,
        "flags": list(item.flags),
        "evidence": item.evidence,
        "extracted_evidence": item.extracted_evidence,
        "output_file": item.output_file,
        "output_sha256": item.output_sha256,
        "diagnosis_status": "pending_latest_model_review",
        "cause_type": None,
        "cause_explanation_zh": None,
        "cause_explanation_en": None,
        "proposed_change_zh": None,
        "proposed_change_en": None,
        "human_review_status": "pending",
    }


def _public_summary(
    *,
    items: list[_ScoredItem],
    expected_student_ids: tuple[str, ...],
    technical_failure_count: int,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    safe_provenance_keys = (
        "course_id",
        "assessment_id",
        "condition",
        "run_id",
        "provider",
        "model",
        "input_mode",
        "skill_version_id",
        "run_commit",
        "packet_id",
        "packet_sha256",
        "output_set_sha256",
        "gold_sha256",
        "prompt_sha256",
        "rubric_sha256",
        "data_snapshot_sha256",
        "text_source_sha256",
    )
    error_items = [item for item in items if not item.is_exact]
    severe_items = [item for item in items if item.is_severe]
    student_total_errors: dict[str, float] = defaultdict(float)
    for item in items:
        student_total_errors[item.student_id] += item.signed_error

    return {
        "record_type": "grading_error_book_public_summary",
        "schema_version": 1,
        "scope": {
            "split": "development",
            "contains_heldout_or_test_data": False,
            "contains_student_level_records": False,
            "contains_answer_or_evidence_text": False,
            "selection_rule": "all score disagreements, aggregated for public release",
            "selection_rule_zh": "完整统计全部评分分歧，仅以聚合形式公开",
            "severe_error_threshold_points": SEVERE_ERROR_THRESHOLD,
        },
        "provenance": {key: provenance.get(key) for key in safe_provenance_keys},
        "population": {
            "students": len(expected_student_ids),
            "student_question_pairs": len(items),
            "exact_pairs": len(items) - len(error_items),
            "error_pairs": len(error_items),
            "severe_error_pairs": len(severe_items),
            "technical_failure_count": technical_failure_count,
            "technical_failures_included_as_grading_cases": False,
        },
        "metrics": {
            "question_exact_agreement": _ratio(
                len(items) - len(error_items), len(items)
            ),
            "question_score_mae": _mean(item.absolute_error for item in items),
            "question_signed_error_mean": _mean(
                item.signed_error for item in items
            ),
            "severe_error_rate_abs_ge_5": _ratio(
                len(severe_items), len(items)
            ),
            "student_total_score_mae": _mean(
                abs(value) for value in student_total_errors.values()
            ),
            "student_total_signed_error_mean": _mean(
                student_total_errors.values()
            ),
        },
        "error_directions": _direction_summary(error_items),
        "error_magnitude_bands": _magnitude_summary(error_items),
        "by_question": _group_summary(
            items,
            key=lambda item: item.question_id,
            key_name="question_id",
            sort_key=_question_sort_key,
        ),
        "by_confidence": _group_summary(
            items,
            key=lambda item: item.confidence,
            key_name="confidence",
        ),
        "model_flag_coverage": {
            "error_pairs_with_model_flags": sum(
                bool(item.flags) for item in error_items
            ),
            "error_pairs_without_model_flags": sum(
                not item.flags for item in error_items
            ),
            "model_flag_text_published": False,
        },
        "interpretation_limits": {
            "zh": [
                "这里只报告开发集上的描述性统计，不能当作测试集准确率。",
                "逐个学生、逐道题的证据与诊断只保存在 git 忽略的私有错题集中。",
                "标签只描述模型输出；在人工或最新模型复核前，不等同于已确认的根因。",
            ],
            "en": [
                "These are descriptive development-split statistics, not "
                "held-out accuracy.",
                "Student-question evidence and diagnoses remain only in the "
                "gitignored private error book.",
                "Free-form model flags remain private and are not confirmed "
                "root causes before review.",
            ],
        },
    }


def _population_summary(
    items: list[_ScoredItem],
    expected_student_ids: tuple[str, ...],
) -> dict[str, Any]:
    errors = [item for item in items if not item.is_exact]
    return {
        "students": len(expected_student_ids),
        "student_question_pairs": len(items),
        "exact_pairs": len(items) - len(errors),
        "error_pairs": len(errors),
        "severe_error_pairs": sum(item.is_severe for item in errors),
    }


def _group_summary(
    items: list[_ScoredItem],
    *,
    key: Any,
    key_name: str,
    sort_key: Any | None = None,
) -> list[dict[str, Any]]:
    groups: dict[str, list[_ScoredItem]] = defaultdict(list)
    for item in items:
        groups[key(item)].append(item)
    ordered_keys = sorted(groups, key=sort_key)
    rows = []
    for group_key in ordered_keys:
        group = groups[group_key]
        errors = [item for item in group if not item.is_exact]
        severe = [item for item in group if item.is_severe]
        rows.append(
            {
                key_name: group_key,
                "pairs": len(group),
                "exact_pairs": len(group) - len(errors),
                "error_pairs": len(errors),
                "severe_error_pairs": len(severe),
                "exact_agreement": _ratio(len(group) - len(errors), len(group)),
                "mae": _mean(item.absolute_error for item in group),
                "signed_error_mean": _mean(item.signed_error for item in group),
                "severe_error_rate_abs_ge_5": _ratio(len(severe), len(group)),
            }
        )
    return rows


def _direction_summary(items: list[_ScoredItem]) -> dict[str, int]:
    counts = Counter(item.direction for item in items)
    return {
        "over_score": counts["over_score"],
        "under_score": counts["under_score"],
    }


def _magnitude_summary(items: list[_ScoredItem]) -> list[dict[str, Any]]:
    bands = (
        ("gt_0_lt_1", lambda value: 0 < value < 1),
        ("ge_1_lt_5", lambda value: 1 <= value < 5),
        ("ge_5", lambda value: value >= 5),
    )
    return [
        {
            "band": label,
            "error_pairs": sum(predicate(item.absolute_error) for item in items),
        }
        for label, predicate in bands
    ]


def _question_sort_key(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"Q([0-9]+)(.*)", value, re.IGNORECASE)
    if match:
        return (int(match.group(1)), match.group(2))
    return (10_000, value)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _mean(values: Any) -> float:
    materialized = list(values)
    return round(fmean(materialized), 6) if materialized else 0.0


def _clean_number(value: float) -> float:
    rounded = round(float(value), 10)
    return 0.0 if rounded == 0 else rounded


def _nonempty_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    return sum(bool(line.strip()) for line in lines)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON object: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _directory_hash(path: Path) -> str:
    digest = hashlib.sha256()
    files = (item for item in path.rglob("*") if item.is_file())
    for file_path in sorted(
        files,
        key=lambda item: (
            item.relative_to(path).as_posix().casefold(),
            item.relative_to(path).as_posix(),
        ),
    ):
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def validate_private_output_path(private_output: Path) -> None:
    """Reject a private output inside Git unless Git explicitly ignores it."""

    private_resolved = private_output.resolve()
    git_root = _find_git_root(private_resolved.parent)
    if git_root is None:
        return
    relative = private_resolved.relative_to(git_root)
    check = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={git_root.as_posix()}",
            "check-ignore",
            "--quiet",
            "--",
            relative.as_posix(),
        ],
        cwd=git_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        raise ValueError(
            "private output is inside a Git repository but is not ignored: "
            f"{relative.as_posix()}"
        )


def _find_git_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None
