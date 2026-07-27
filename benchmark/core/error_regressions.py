"""Build and evaluate private, machine-checkable grading-error regressions."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .error_book import (
    SEVERE_ERROR_THRESHOLD,
    audit_public_error_summary,
    validate_private_output_path,
)


SUPPORTED_GATE_KINDS = {"exact_gold", "nonsevere_and_improved"}
SUPPORTED_REGRESSION_CLASSES = {"positive_credit", "negative_credit"}
COMPARABILITY_FIELDS = (
    "course_id",
    "assessment_id",
    "provider",
    "model",
    "input_mode",
    "data_snapshot_sha256",
    "gold_sha256",
    "text_source_sha256",
)


@dataclass(frozen=True)
class RegressionSuiteResult:
    private_suite: dict[str, Any]
    public_summary: dict[str, Any]


@dataclass(frozen=True)
class RegressionEvaluationResult:
    private_evaluation: dict[str, Any]
    public_summary: dict[str, Any]


def build_regression_suite(
    *,
    private_book_path: Path,
    diagnoses_path: Path,
    policy_path: Path,
) -> RegressionSuiteResult:
    """Select diagnosed development errors into an executable private suite."""

    private_book = _read_json(private_book_path)
    diagnoses = _read_json(diagnoses_path)
    policy = _read_json(policy_path)
    _validate_development_book(private_book, "source")
    suite_id, selectors = _validate_policy(policy)
    cases = _case_map(private_book)
    annotations = _annotation_map(diagnoses)

    if set(cases) != set(annotations):
        missing = sorted(set(cases) - set(annotations))
        extra = sorted(set(annotations) - set(cases))
        raise ValueError(
            "diagnoses must cover every source error exactly once; "
            f"missing={missing}, extra={extra}"
        )

    selected: list[dict[str, Any]] = []
    selected_source_ids: set[str] = set()
    selector_counts: Counter[str] = Counter()
    for selector in selectors:
        matches = [
            (case, annotations[case_id])
            for case_id, case in cases.items()
            if _matches_selector(case, annotations[case_id], selector)
        ]
        expected_count = selector["expected_case_count"]
        if len(matches) != expected_count:
            raise ValueError(
                f"selector {selector['selector_id']} expected "
                f"{expected_count} cases but matched {len(matches)}"
            )
        for case, annotation in sorted(
            matches,
            key=lambda pair: (
                _question_sort_key(pair[0]["question_id"]),
                pair[0]["anonymous_student_id"],
            ),
        ):
            source_case_id = case["case_id"]
            if source_case_id in selected_source_ids:
                raise ValueError(
                    f"source case selected more than once: {source_case_id}"
                )
            selected_source_ids.add(source_case_id)
            selector_counts[selector["selector_id"]] += 1
            selected.append(
                _private_suite_case(
                    index=len(selected) + 1,
                    case=case,
                    annotation=annotation,
                    selector=selector,
                )
            )

    if not selected:
        raise ValueError("regression policy selected no cases")

    source_provenance = private_book["provenance"]
    provenance = {
        field: source_provenance.get(field) for field in COMPARABILITY_FIELDS
    }
    provenance.update(
        {
            "source_skill_version_id": source_provenance.get(
                "skill_version_id"
            ),
            "source_run_id": source_provenance.get("run_id"),
            "source_private_book_sha256": _file_hash(private_book_path),
            "source_diagnoses_sha256": _file_hash(diagnoses_path),
            "policy_sha256": _file_hash(policy_path),
        }
    )
    acceptance = {
        "require_all_cases_pass": True,
        "necessary_not_sufficient": True,
        "severe_error_threshold": SEVERE_ERROR_THRESHOLD,
    }
    private_suite = {
        "record_type": "grading_error_regression_suite_private",
        "schema_version": 1,
        "suite_id": suite_id,
        "scope": {
            "split": "development",
            "comparison_key": "anonymous_student_id + question_id",
        },
        "provenance": provenance,
        "population": {
            "students": private_book["population"]["students"],
            "student_question_pairs": private_book["population"][
                "student_question_pairs"
            ],
            "target_cases": len(selected),
        },
        "acceptance": acceptance,
        "cases": selected,
    }
    public_summary = {
        "record_type": "grading_error_regression_suite_public",
        "schema_version": 1,
        "suite_id": suite_id,
        "scope": {
            "split": "development",
            "contains_student_level_records": False,
            "contains_answer_or_evidence_text": False,
        },
        "provenance": provenance,
        "acceptance": acceptance,
        "target_case_count": len(selected),
        "by_selector": [
            {
                "selector_id": selector["selector_id"],
                "question_id": selector["question_id"],
                "mechanism_code": selector["mechanism_code"],
                "regression_class": selector["regression_class"],
                "gate_kind": selector["gate"]["kind"],
                "target_cases": selector_counts[selector["selector_id"]],
            }
            for selector in selectors
        ],
        "by_question": _count_by(selected, "question_id", "target_cases"),
        "by_regression_class": _count_by(
            selected, "regression_class", "target_cases"
        ),
        "interpretation_limits": {
            "zh": [
                "该套件只包含开发集中的已知典型错误，不包含测试集。",
                "通过全部目标案例只是候选 skill 的必要条件；仍须检查全体样本的总体误差、严重错误和新 regression。",
                "公开摘要不包含学生编号、答案文字、逐例分数或私有路径。",
            ],
            "en": [
                "The suite contains known development errors only, never held-out data.",
                "Passing every target is necessary but not sufficient; aggregate error, severe errors, and new regressions must still be checked on the full development set.",
                "The public summary contains no student identifiers, answer text, case-level scores, or private paths.",
            ],
        },
    }
    _require_public_safe(public_summary, "regression suite summary")
    return RegressionSuiteResult(
        private_suite=private_suite,
        public_summary=public_summary,
    )


def write_regression_suite(
    *,
    private_book_path: Path,
    diagnoses_path: Path,
    policy_path: Path,
    private_output: Path,
    public_output: Path,
) -> RegressionSuiteResult:
    if private_output.resolve() == public_output.resolve():
        raise ValueError("private and public outputs must use different paths")
    validate_private_output_path(private_output)
    result = build_regression_suite(
        private_book_path=private_book_path,
        diagnoses_path=diagnoses_path,
        policy_path=policy_path,
    )
    _write_json(private_output, result.private_suite)
    _write_json(public_output, result.public_summary)
    return result


def evaluate_regression_suite(
    *,
    private_suite_path: Path,
    current_private_book_path: Path,
) -> RegressionEvaluationResult:
    """Evaluate a complete candidate error book against every frozen target."""

    suite = _read_json(private_suite_path)
    current = _read_json(current_private_book_path)
    _validate_private_suite(suite)
    _validate_development_book(current, "current")
    _validate_comparable(suite, current)
    current_cases = _private_case_key_map(current)

    rows = []
    for target in suite["cases"]:
        key = (
            target["anonymous_student_id"],
            target["question_id"],
        )
        current_case = current_cases.get(key)
        rows.append(_evaluate_case(target, current_case))

    passed_count = sum(row["passed"] for row in rows)
    status = "passed" if passed_count == len(rows) else "failed"
    evaluation_provenance = {
        "suite_id": suite["suite_id"],
        "suite_sha256": _file_hash(private_suite_path),
        "source_skill_version_id": suite["provenance"][
            "source_skill_version_id"
        ],
        "current_skill_version_id": current["provenance"].get(
            "skill_version_id"
        ),
        "current_run_id": current["provenance"].get("run_id"),
        "current_output_set_sha256": current["provenance"].get(
            "output_set_sha256"
        ),
    }
    private_evaluation = {
        "record_type": "grading_error_regression_evaluation_private",
        "schema_version": 1,
        "suite_id": suite["suite_id"],
        "status": status,
        "provenance": evaluation_provenance,
        "counts": {
            "target_cases": len(rows),
            "passed": passed_count,
            "failed": len(rows) - passed_count,
        },
        "cases": rows,
    }
    exact_gold_count = sum(row["exact_gold"] for row in rows)
    public_summary = {
        "record_type": "grading_error_regression_evaluation_public",
        "schema_version": 1,
        "suite_id": suite["suite_id"],
        "status": status,
        "scope": {
            "split": "development",
            "contains_student_level_records": False,
            "contains_answer_or_evidence_text": False,
        },
        "provenance": evaluation_provenance,
        "counts": private_evaluation["counts"],
        "observations": {
            "exact_gold": {
                "target_cases": len(rows),
                "exact_cases": exact_gold_count,
                "exact_rate": round(exact_gold_count / len(rows), 10),
                "hard_gate": False,
            }
        },
        "exact_gold_by_question": _exact_gold_counts_by_question(rows),
        "by_question": _evaluation_counts(rows, "question_id"),
        "by_regression_class": _evaluation_counts(
            rows, "regression_class"
        ),
        "by_gate_kind": _evaluation_counts(rows, "gate_kind"),
        "interpretation_limits": {
            "zh": [
                "failed 表示至少一个已知典型错误未满足冻结门禁。",
                "passed 也不能单独批准 candidate；必须再运行全开发集总体门禁。",
            ],
            "en": [
                "Failed means at least one known typical error missed its frozen gate.",
                "Passed does not approve a candidate by itself; the full-development global gate is still required.",
            ],
        },
    }
    _require_public_safe(public_summary, "regression evaluation summary")
    return RegressionEvaluationResult(
        private_evaluation=private_evaluation,
        public_summary=public_summary,
    )


def write_regression_evaluation(
    *,
    private_suite_path: Path,
    current_private_book_path: Path,
    private_output: Path,
    public_output: Path,
) -> RegressionEvaluationResult:
    if private_output.resolve() == public_output.resolve():
        raise ValueError("private and public outputs must use different paths")
    validate_private_output_path(private_output)
    result = evaluate_regression_suite(
        private_suite_path=private_suite_path,
        current_private_book_path=current_private_book_path,
    )
    _write_json(private_output, result.private_evaluation)
    _write_json(public_output, result.public_summary)
    return result


def _validate_policy(
    policy: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    if policy.get("schema_version") != 1:
        raise ValueError("regression policy schema_version must be 1")
    if policy.get("split") != "development":
        raise ValueError("regression policy must be development-only")
    suite_id = policy.get("suite_id")
    if not isinstance(suite_id, str) or not suite_id.strip():
        raise ValueError("regression policy requires a nonblank suite_id")
    selectors = policy.get("selectors")
    if not isinstance(selectors, list) or not selectors:
        raise ValueError("regression policy requires selectors")
    seen_ids: set[str] = set()
    normalized = []
    for selector in selectors:
        if not isinstance(selector, dict):
            raise ValueError("every selector must be an object")
        selector_id = selector.get("selector_id")
        if not isinstance(selector_id, str) or not selector_id:
            raise ValueError("every selector requires selector_id")
        if selector_id in seen_ids:
            raise ValueError(f"duplicate selector_id: {selector_id}")
        seen_ids.add(selector_id)
        for field in ("question_id", "mechanism_code"):
            if not isinstance(selector.get(field), str) or not selector[field]:
                raise ValueError(f"selector {selector_id} requires {field}")
        if selector.get("regression_class") not in SUPPORTED_REGRESSION_CLASSES:
            raise ValueError(
                f"selector {selector_id} has invalid regression_class"
            )
        expected = selector.get("expected_case_count")
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
            raise ValueError(
                f"selector {selector_id} requires positive expected_case_count"
            )
        severe_only = selector.get("severe_only")
        if not isinstance(severe_only, bool):
            raise ValueError(f"selector {selector_id} requires severe_only")
        gate = selector.get("gate")
        if not isinstance(gate, dict) or gate.get("kind") not in SUPPORTED_GATE_KINDS:
            raise ValueError(f"selector {selector_id} has invalid gate")
        normalized.append(selector)
    return suite_id, normalized


def _matches_selector(
    case: dict[str, Any],
    annotation: dict[str, Any],
    selector: dict[str, Any],
) -> bool:
    return (
        case.get("question_id") == selector["question_id"]
        and annotation.get("mechanism_code") == selector["mechanism_code"]
        and (not selector["severe_only"] or case.get("severe_error") is True)
    )


def _private_suite_case(
    *,
    index: int,
    case: dict[str, Any],
    annotation: dict[str, Any],
    selector: dict[str, Any],
) -> dict[str, Any]:
    return {
        "suite_case_id": f"REG-{index:03d}",
        "source_case_id": case["case_id"],
        "selector_id": selector["selector_id"],
        "anonymous_student_id": case["anonymous_student_id"],
        "question_id": case["question_id"],
        "regression_class": selector["regression_class"],
        "gate": selector["gate"],
        "mechanism_code": annotation["mechanism_code"],
        "review_confidence": annotation["review_confidence"],
        "recommended_action": annotation["recommended_action"],
        "gold_score": case["gold_score"],
        "baseline_predicted_score": case["predicted_score"],
        "baseline_absolute_error": case["absolute_error"],
        "baseline_severe_error": case["severe_error"],
    }


def _evaluate_case(
    target: dict[str, Any],
    current_case: dict[str, Any] | None,
) -> dict[str, Any]:
    gold = float(target["gold_score"])
    if current_case is None:
        current_predicted = gold
        current_absolute_error = 0.0
        current_severe = False
    else:
        current_gold = float(current_case["gold_score"])
        if current_gold != gold:
            raise ValueError(
                f"gold score drift for regression target {target['suite_case_id']}"
            )
        current_predicted = float(current_case["predicted_score"])
        current_absolute_error = float(current_case["absolute_error"])
        current_severe = bool(current_case["severe_error"])

    gate_kind = target["gate"]["kind"]
    if gate_kind == "exact_gold":
        passed = current_absolute_error == 0
        reason = "exact_gold" if passed else "still_disagrees_with_gold"
    elif gate_kind == "nonsevere_and_improved":
        improved = current_absolute_error < float(
            target["baseline_absolute_error"]
        )
        passed = not current_severe and improved
        if passed:
            reason = "nonsevere_and_strictly_improved"
        elif current_severe:
            reason = "severe_error_persists"
        else:
            reason = "not_strictly_improved"
    else:  # pragma: no cover - suite validation guards this branch.
        raise ValueError(f"unsupported gate kind: {gate_kind}")

    return {
        "suite_case_id": target["suite_case_id"],
        "source_case_id": target["source_case_id"],
        "selector_id": target["selector_id"],
        "anonymous_student_id": target["anonymous_student_id"],
        "question_id": target["question_id"],
        "regression_class": target["regression_class"],
        "gate_kind": gate_kind,
        "passed": passed,
        "reason": reason,
        "exact_gold": current_absolute_error == 0,
        "gold_score": gold,
        "baseline_predicted_score": target["baseline_predicted_score"],
        "baseline_absolute_error": target["baseline_absolute_error"],
        "current_predicted_score": current_predicted,
        "current_absolute_error": current_absolute_error,
        "current_severe_error": current_severe,
    }


def _validate_private_suite(suite: dict[str, Any]) -> None:
    if suite.get("record_type") != "grading_error_regression_suite_private":
        raise ValueError("invalid private regression suite record_type")
    if suite.get("schema_version") != 1:
        raise ValueError("private regression suite schema_version must be 1")
    if suite.get("scope", {}).get("split") != "development":
        raise ValueError("private regression suite must be development-only")
    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("private regression suite requires cases")
    seen_keys: set[tuple[str, str]] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("private regression suite case must be an object")
        key = (case.get("anonymous_student_id"), case.get("question_id"))
        if not all(isinstance(value, str) for value in key):
            raise ValueError("private regression suite case key is invalid")
        if key in seen_keys:
            raise ValueError(f"duplicate regression suite case key: {key}")
        seen_keys.add(key)
        if case.get("regression_class") not in SUPPORTED_REGRESSION_CLASSES:
            raise ValueError("private regression suite has invalid class")
        gate = case.get("gate")
        if not isinstance(gate, dict) or gate.get("kind") not in SUPPORTED_GATE_KINDS:
            raise ValueError("private regression suite has invalid gate")


def _validate_development_book(book: dict[str, Any], label: str) -> None:
    if book.get("record_type") != "grading_error_book_private":
        raise ValueError(f"{label} must be a private grading error book")
    if book.get("scope", {}).get("split") != "development":
        raise ValueError(f"{label} error book must be development-only")
    population = book.get("population")
    if not isinstance(population, dict):
        raise ValueError(f"{label} error book requires population")
    cases = book.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{label} error book cases must be a list")
    error_pairs = population.get("error_pairs")
    exact_pairs = population.get("exact_pairs")
    total_pairs = population.get("student_question_pairs")
    severe_pairs = population.get("severe_error_pairs")
    for field, value in (
        ("error_pairs", error_pairs),
        ("exact_pairs", exact_pairs),
        ("student_question_pairs", total_pairs),
        ("severe_error_pairs", severe_pairs),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{label} error book has invalid {field}")
    if len(cases) != error_pairs:
        raise ValueError(
            f"{label} error book case count does not match error_pairs"
        )
    if error_pairs + exact_pairs != total_pairs:
        raise ValueError(
            f"{label} error book exact/error counts do not cover population"
        )
    actual_severe = 0
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError(f"{label} error book case must be an object")
        absolute_error = case.get("absolute_error")
        severe = case.get("severe_error")
        if (
            not isinstance(absolute_error, (int, float))
            or isinstance(absolute_error, bool)
            or absolute_error <= 0
        ):
            raise ValueError(f"{label} error case has invalid absolute_error")
        if not isinstance(severe, bool):
            raise ValueError(f"{label} error case has invalid severe_error")
        expected_severe = absolute_error >= SEVERE_ERROR_THRESHOLD
        if severe != expected_severe:
            raise ValueError(
                f"{label} error case severe_error disagrees with threshold"
            )
        actual_severe += int(severe)
    if actual_severe != severe_pairs:
        raise ValueError(
            f"{label} error book severe case count does not match population"
        )


def _validate_comparable(
    suite: dict[str, Any],
    current: dict[str, Any],
) -> None:
    suite_provenance = suite["provenance"]
    current_provenance = current["provenance"]
    for field in COMPARABILITY_FIELDS:
        if suite_provenance.get(field) != current_provenance.get(field):
            raise ValueError(f"regression suite and current book disagree on {field}")
    for field in ("students", "student_question_pairs"):
        if suite["population"].get(field) != current["population"].get(field):
            raise ValueError(
                f"regression suite and current book disagree on population {field}"
            )


def _case_map(book: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    cases = book.get("cases")
    if not isinstance(cases, list):
        raise ValueError("private error book cases must be a list")
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            raise ValueError("every private error case requires case_id")
        case_id = case["case_id"]
        if case_id in result:
            raise ValueError(f"duplicate private error case_id: {case_id}")
        result[case_id] = case
    return result


def _annotation_map(diagnoses: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    annotations = diagnoses.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("diagnoses annotations must be a list")
    required = {
        "case_id",
        "mechanism_code",
        "review_confidence",
        "recommended_action",
    }
    for annotation in annotations:
        if not isinstance(annotation, dict) or not required.issubset(annotation):
            raise ValueError("every diagnosis requires regression fields")
        case_id = annotation["case_id"]
        if not isinstance(case_id, str):
            raise ValueError("diagnosis case_id must be text")
        if case_id in result:
            raise ValueError(f"duplicate diagnosis case_id: {case_id}")
        result[case_id] = annotation
    return result


def _private_case_key_map(
    book: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for case in book["cases"]:
        key = (case.get("anonymous_student_id"), case.get("question_id"))
        if not all(isinstance(value, str) for value in key):
            raise ValueError("private error case key is invalid")
        if key in result:
            raise ValueError(f"duplicate private error case key: {key}")
        result[key] = case
    return result


def _count_by(
    rows: list[dict[str, Any]],
    field: str,
    count_field: str,
) -> list[dict[str, Any]]:
    counts = Counter(row[field] for row in rows)
    return [
        {field: value, count_field: count}
        for value, count in sorted(counts.items())
    ]


def _evaluation_counts(
    rows: list[dict[str, Any]],
    field: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[row[field]]["passed" if row["passed"] else "failed"] += 1
    return [
        {
            field: value,
            "target_cases": counts["passed"] + counts["failed"],
            "passed": counts["passed"],
            "failed": counts["failed"],
        }
        for value, counts in sorted(grouped.items())
    ]


def _exact_gold_counts_by_question(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[row["question_id"]][
            "exact" if row["exact_gold"] else "not_exact"
        ] += 1
    return [
        {
            "question_id": question_id,
            "target_cases": counts["exact"] + counts["not_exact"],
            "exact_cases": counts["exact"],
            "not_exact_cases": counts["not_exact"],
        }
        for question_id, counts in sorted(
            grouped.items(), key=lambda item: _question_sort_key(item[0])
        )
    ]


def _require_public_safe(payload: dict[str, Any], label: str) -> None:
    findings = audit_public_error_summary(payload)
    if findings:
        raise ValueError(f"{label} failed privacy audit: {findings}")


def _question_sort_key(value: str) -> tuple[int, str]:
    suffix = value[1:] if value[:1].casefold() == "q" else ""
    return (int(suffix), value) if suffix.isdigit() else (10**9, value)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
