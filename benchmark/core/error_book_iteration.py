"""Human-readable error cases and version-to-version error-book lifecycle."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .error_book import (
    audit_public_error_summary,
    validate_private_output_path,
)
from .skill_snapshots import SkillSnapshot, build_skill_snapshot


SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ErrorBookDeltaResult:
    private_delta: dict[str, Any]
    public_summary: dict[str, Any]


def render_private_typical_case_report(
    *,
    private_book_path: Path,
    diagnoses_path: Path,
    max_typical_cases: int = 12,
) -> str:
    if max_typical_cases <= 0:
        raise ValueError("max_typical_cases must be positive")
    book, cases = _load_reviewed_cases(private_book_path, diagnoses_path)
    selected = _select_typical_cases(cases, max_typical_cases)
    population = book.get("population", {})
    provenance = book.get("provenance", {})

    lines = [
        "# 典型错题册 / Typical Grading Error Book",
        "",
        "> **私有材料 / PRIVATE:** 包含匿名学生编号与答案证据。不得提交到公开 GitHub，"
        "不得粘贴到公开 Zulip。",
        "> Contains anonymous student IDs and answer evidence. Do not commit to "
        "public GitHub or paste into public Zulip.",
        "",
        "## 本版本 / This skill version",
        "",
        f"- Skill version: `{provenance.get('skill_version_id')}`",
        f"- Run: `{provenance.get('run_id')}`",
        f"- Input mode: `{provenance.get('input_mode')}`",
        f"- Split: `{book.get('scope', {}).get('split')}`",
        f"- All scored pairs: `{population.get('student_question_pairs')}`",
        f"- All error pairs: `{population.get('error_pairs')}`",
        f"- Severe error pairs: `{population.get('severe_error_pairs')}`",
        f"- Typical cases shown in full: `{len(selected)}`",
        "",
        "## 选择规则 / Selection rule",
        "",
        "典型案例先纳入逐案复核时人工标记的关键案例，再确定性补充：每道有错题的"
        "题目至少一个、每类根因至少一个、严重高估与严重低估各至少一个，最后按"
        "绝对分差补足。完整 33 例仍列在文末索引中。",
        "",
        "Selection starts with reviewer-nominated key cases, then deterministically "
        "adds at least one case per affected question, one per primary cause, "
        "one severe over-score and under-score when available, and the largest "
        "remaining absolute errors. The full case index remains at the end.",
        "",
        "## 典型案例 / Typical cases",
        "",
    ]
    for index, case in enumerate(selected, start=1):
        lines.extend(_render_case(index, case))

    lines.extend(
        [
            "## 全部错题索引 / Complete error index",
            "",
            "| Case | Student | Question | Gold | Predicted | Abs. error | "
            "Direction | Severe | Cause |",
            "|---|---|---|---:|---:|---:|---|---|---|",
        ]
    )
    for case in sorted(cases, key=_case_order):
        lines.append(
            "| {case_id} | {student} | {question} | {gold:g} | {predicted:g} | "
            "{absolute:g} | {direction} | {severe} | {cause} |".format(
                case_id=case["case_id"],
                student=case["anonymous_student_id"],
                question=case["question_id"],
                gold=case["gold_score"],
                predicted=case["predicted_score"],
                absolute=case["absolute_error"],
                direction=case["direction"],
                severe="yes" if case["severe_error"] else "no",
                cause=case["primary_cause"],
            )
        )

    lines.extend(
        [
            "",
            "## 每次 skill 更新时怎么更新 / Required update on every skill change",
            "",
            "1. 用新 skill version 在同一 development split 上运行。",
            "2. 重新执行 `build-error-book`，不能覆盖旧版本目录。",
            "3. 完成所有新错题的逐案诊断并重新生成本报告。",
            "4. 用 `compare-error-books` 生成 `persistent`、`resolved`、"
            "`regression` 三类差异。",
            "5. 更新公开 registry；如果当前 skill hash 没有完整错题产物，CI 应失败。",
            "",
            "1. Run the new skill version on the same development split.",
            "2. Run `build-error-book` again without overwriting the prior version.",
            "3. Diagnose every new error and regenerate this report.",
            "4. Run `compare-error-books` to classify persistent, resolved, and "
            "regression cases.",
            "5. Update the public registry; CI must fail when the current skill "
            "hash lacks complete error-book artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def write_private_typical_case_report(
    *,
    private_book_path: Path,
    diagnoses_path: Path,
    output_path: Path,
    max_typical_cases: int = 12,
) -> Path:
    validate_private_output_path(output_path)
    text = render_private_typical_case_report(
        private_book_path=private_book_path,
        diagnoses_path=diagnoses_path,
        max_typical_cases=max_typical_cases,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8", newline="\n")
    return output_path


def compare_error_books(
    *,
    previous_private_book_path: Path,
    current_private_book_path: Path,
) -> ErrorBookDeltaResult:
    previous = _read_json(previous_private_book_path)
    current = _read_json(current_private_book_path)
    _validate_comparable_books(previous, current)
    previous_cases = _case_map(previous)
    current_cases = _case_map(current)

    previous_keys = set(previous_cases)
    current_keys = set(current_cases)
    resolved_keys = previous_keys - current_keys
    regression_keys = current_keys - previous_keys
    persistent_keys = previous_keys & current_keys

    resolved = [
        _private_delta_row("resolved", previous_cases[key], None)
        for key in sorted(resolved_keys, key=_case_key_order)
    ]
    regressions = [
        _private_delta_row("regression", None, current_cases[key])
        for key in sorted(regression_keys, key=_case_key_order)
    ]
    persistent = [
        _private_delta_row(
            _persistent_status(previous_cases[key], current_cases[key]),
            previous_cases[key],
            current_cases[key],
        )
        for key in sorted(persistent_keys, key=_case_key_order)
    ]
    all_rows = resolved + regressions + persistent
    provenance = _delta_provenance(previous, current)
    private_delta = {
        "record_type": "grading_error_book_iteration_delta_private",
        "schema_version": 1,
        "scope": {
            "split": "development",
            "comparison_key": "anonymous_student_id + question_id",
        },
        "provenance": provenance,
        "counts": _delta_counts(all_rows),
        "cases": all_rows,
    }
    public_summary = {
        "record_type": "grading_error_book_iteration_delta_public",
        "schema_version": 1,
        "scope": {
            "split": "development",
            "contains_student_level_records": False,
            "contains_answer_or_evidence_text": False,
        },
        "provenance": provenance,
        "counts": _delta_counts(all_rows),
        "by_question": _public_delta_by_question(all_rows),
        "interpretation_limits": {
            "zh": [
                "resolved 表示旧版本错、新版本与 gold 一致；regression 表示旧版本一致、新版本出错。",
                "persistent 只说明同一学生-题目对仍有分差，不自动证明根因未改变。",
                "该比较只允许同一课程、测验和 development split。",
            ],
            "en": [
                "Resolved means the prior version disagreed and the new version matches gold; regression means the reverse.",
                "Persistent means the same student-question pair still disagrees and does not prove that its root cause is unchanged.",
                "Comparison is restricted to the same course, assessment, and development split.",
            ],
        },
    }
    findings = audit_public_error_summary(public_summary)
    if findings:
        raise ValueError(f"public iteration delta failed privacy audit: {findings}")
    return ErrorBookDeltaResult(
        private_delta=private_delta,
        public_summary=public_summary,
    )


def write_error_book_delta(
    *,
    previous_private_book_path: Path,
    current_private_book_path: Path,
    private_output: Path,
    public_output: Path,
) -> ErrorBookDeltaResult:
    if private_output.resolve() == public_output.resolve():
        raise ValueError("private and public outputs must use different paths")
    validate_private_output_path(private_output)
    result = compare_error_books(
        previous_private_book_path=previous_private_book_path,
        current_private_book_path=current_private_book_path,
    )
    _write_json(private_output, result.private_delta)
    _write_json(public_output, result.public_summary)
    return result


def validate_error_book_registry(
    *,
    repo_root: Path,
    registry_path: Path,
) -> list[str]:
    findings: list[str] = []
    try:
        registry = _read_json(registry_path)
    except (OSError, ValueError) as error:
        return [str(error)]
    policy = registry.get("policy")
    if not isinstance(policy, dict) or policy.get(
        "required_for_every_skill_update"
    ) is not True:
        findings.append("registry must require an error-book update for every skill update")
    if not isinstance(policy, dict) or policy.get(
        "required_regressions_for_future_skill_updates"
    ) is not True:
        findings.append(
            "registry must require regression evaluation for future skill updates"
        )

    required_suite_ids, suite_findings = _validate_regression_suites(
        repo_root=repo_root,
        registry=registry,
    )
    findings.extend(suite_findings)

    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        return findings + ["registry entries must be a non-empty list"]
    active_id = registry.get("active_skill_version_id")
    ids = [entry.get("skill_version_id") for entry in entries if isinstance(entry, dict)]
    if len(ids) != len(entries) or any(not isinstance(value, str) for value in ids):
        findings.append("every registry entry must have a skill_version_id")
        return findings
    if len(ids) != len(set(ids)):
        findings.append("registry skill_version_id values must be unique")
    if active_id != ids[-1]:
        findings.append("active_skill_version_id must be the final registry entry")

    for index, entry in enumerate(entries):
        findings.extend(
            _validate_registry_entry(
                repo_root=repo_root,
                entry=entry,
                expected_predecessor=(ids[index - 1] if index else None),
                is_active=entry.get("skill_version_id") == active_id,
                required_suite_ids=required_suite_ids,
            )
        )
    return sorted(set(findings))


def _validate_registry_entry(
    *,
    repo_root: Path,
    entry: dict[str, Any],
    expected_predecessor: str | None,
    is_active: bool,
    required_suite_ids: tuple[str, ...],
) -> list[str]:
    findings: list[str] = []
    skill_id = entry.get("skill_version_id")
    label = f"entry {skill_id}"
    if entry.get("predecessor_skill_version_id") != expected_predecessor:
        findings.append(f"{label}: predecessor does not match registry order")
    canonical_hash = entry.get("skill_canonical_hash")
    if not isinstance(canonical_hash, str) or SHA256.fullmatch(canonical_hash) is None:
        findings.append(f"{label}: invalid skill_canonical_hash")
    typical_hash = entry.get("private_typical_report_sha256")
    if not isinstance(typical_hash, str) or SHA256.fullmatch(typical_hash) is None:
        findings.append(f"{label}: invalid private_typical_report_sha256")
    typical_count = entry.get("private_typical_case_count")
    if not isinstance(typical_count, int) or isinstance(typical_count, bool):
        findings.append(f"{label}: invalid private_typical_case_count")
    elif typical_count <= 0:
        findings.append(f"{label}: private_typical_case_count must be positive")
    complete_index_count = entry.get("private_complete_error_index_count")
    if not isinstance(complete_index_count, int) or isinstance(
        complete_index_count, bool
    ):
        findings.append(f"{label}: invalid private_complete_error_index_count")

    snapshot_path = _repo_artifact(
        repo_root, entry.get("skill_snapshot"), label=f"{label} skill_snapshot"
    )
    error_summary_path = _repo_artifact(
        repo_root,
        entry.get("public_error_summary"),
        label=f"{label} public_error_summary",
    )
    diagnosis_path = _repo_artifact(
        repo_root,
        entry.get("public_diagnosis_summary"),
        label=f"{label} public_diagnosis_summary",
    )
    confidence_audit_path = _repo_artifact(
        repo_root,
        entry.get("public_confidence_taxonomy_audit"),
        label=f"{label} public_confidence_taxonomy_audit",
    )
    for path, artifact_label in (
        (snapshot_path, "skill snapshot"),
        (error_summary_path, "public error summary"),
        (diagnosis_path, "public diagnosis summary"),
        (confidence_audit_path, "public confidence taxonomy audit"),
    ):
        if path is None or not path.is_file():
            findings.append(f"{label}: missing {artifact_label}")
    if findings and (snapshot_path is None or not snapshot_path.is_file()):
        return findings

    try:
        snapshot = SkillSnapshot.from_json_path(snapshot_path)
    except (OSError, ValueError, KeyError) as error:
        findings.append(f"{label}: invalid skill snapshot: {error}")
        return findings
    if snapshot.skill_version_id != skill_id:
        findings.append(f"{label}: snapshot skill_version_id mismatch")
    if snapshot.canonical_hash != canonical_hash:
        findings.append(f"{label}: snapshot canonical hash mismatch")

    if is_active:
        rebuilt = build_skill_snapshot(
            skill_version_id=snapshot.skill_version_id,
            source_paths={
                source_label: repo_root / source_path
                for source_label, source_path in snapshot.skill_source_paths.items()
            },
        )
        if rebuilt.canonical_hash != canonical_hash:
            findings.append(
                f"{label}: current grading skill changed without an error-book update"
            )

    if error_summary_path is not None and error_summary_path.is_file():
        summary = _read_json(error_summary_path)
        findings.extend(
            f"{label}: unsafe public error summary: {finding}"
            for finding in audit_public_error_summary(summary)
        )
        if summary.get("provenance", {}).get("skill_version_id") != skill_id:
            findings.append(f"{label}: public error summary skill mismatch")
        expected_errors = summary.get("population", {}).get("error_pairs")
        if expected_errors != entry.get("error_pairs"):
            findings.append(f"{label}: error_pairs mismatch")
        if summary.get("population", {}).get("severe_error_pairs") != entry.get(
            "severe_error_pairs"
        ):
            findings.append(f"{label}: severe_error_pairs mismatch")
        if complete_index_count != expected_errors:
            findings.append(
                f"{label}: private complete index does not cover every error"
            )
    else:
        expected_errors = None
    if diagnosis_path is not None and diagnosis_path.is_file():
        diagnosis = _read_json(diagnosis_path)
        findings.extend(
            f"{label}: unsafe public diagnosis summary: {finding}"
            for finding in audit_public_error_summary(diagnosis)
        )
        if diagnosis.get("review", {}).get("case_count") != expected_errors:
            findings.append(f"{label}: diagnosis does not cover every error case")
        if diagnosis.get("review", {}).get("all_error_cases_reviewed") is not True:
            findings.append(f"{label}: diagnoses are incomplete")
    if confidence_audit_path is not None and confidence_audit_path.is_file():
        confidence_audit = _read_json(confidence_audit_path)
        findings.extend(
            f"{label}: unsafe public confidence audit: {finding}"
            for finding in audit_public_error_summary(confidence_audit)
        )
        if confidence_audit.get("provenance", {}).get(
            "skill_version_id"
        ) != skill_id:
            findings.append(f"{label}: confidence audit skill mismatch")
        if confidence_audit.get("population", {}).get(
            "error_pairs"
        ) != expected_errors:
            findings.append(f"{label}: confidence audit error_pairs mismatch")
        if confidence_audit.get("population", {}).get(
            "severe_error_pairs"
        ) != entry.get("severe_error_pairs"):
            findings.append(
                f"{label}: confidence audit severe_error_pairs mismatch"
            )

    delta_status = entry.get("iteration_delta_status")
    if expected_predecessor is None:
        if delta_status != "baseline_initialized":
            findings.append(f"{label}: first entry must initialize the baseline")
    else:
        if delta_status != "compared":
            findings.append(f"{label}: later entries must compare against predecessor")
        delta_path = _repo_artifact(
            repo_root,
            entry.get("public_iteration_delta"),
            label=f"{label} public_iteration_delta",
        )
        if delta_path is None or not delta_path.is_file():
            findings.append(f"{label}: missing public iteration delta")
        else:
            delta = _read_json(delta_path)
            provenance = delta.get("provenance", {})
            if provenance.get("previous_skill_version_id") != expected_predecessor:
                findings.append(f"{label}: delta predecessor mismatch")
            if provenance.get("current_skill_version_id") != skill_id:
                findings.append(f"{label}: delta current skill mismatch")
        evaluations = entry.get("public_regression_evaluations")
        if not isinstance(evaluations, dict):
            evaluations = {}
            findings.append(f"{label}: missing public regression evaluations")
        for suite_id in required_suite_ids:
            evaluation_path = _repo_artifact(
                repo_root,
                evaluations.get(suite_id),
                label=f"{label} regression evaluation {suite_id}",
            )
            if evaluation_path is None or not evaluation_path.is_file():
                findings.append(
                    f"{label}: missing regression evaluation for {suite_id}"
                )
                continue
            evaluation = _read_json(evaluation_path)
            findings.extend(
                f"{label}: unsafe regression evaluation: {finding}"
                for finding in audit_public_error_summary(evaluation)
            )
            if evaluation.get("suite_id") != suite_id:
                findings.append(f"{label}: regression suite_id mismatch")
            if evaluation.get("status") != "passed":
                findings.append(
                    f"{label}: regression evaluation must pass for {suite_id}"
                )
            if evaluation.get("provenance", {}).get(
                "current_skill_version_id"
            ) != skill_id:
                findings.append(
                    f"{label}: regression evaluation skill mismatch for {suite_id}"
                )
    return findings


def _validate_regression_suites(
    *,
    repo_root: Path,
    registry: dict[str, Any],
) -> tuple[tuple[str, ...], list[str]]:
    findings: list[str] = []
    raw_suites = registry.get("regression_suites")
    if not isinstance(raw_suites, list) or not raw_suites:
        return (), ["registry must define at least one regression suite"]

    suite_ids: list[str] = []
    for descriptor in raw_suites:
        if not isinstance(descriptor, dict):
            findings.append("regression suite descriptor must be an object")
            continue
        suite_id = descriptor.get("suite_id")
        if not isinstance(suite_id, str) or not suite_id:
            findings.append("regression suite descriptor requires suite_id")
            continue
        if suite_id in suite_ids:
            findings.append(f"duplicate regression suite_id: {suite_id}")
            continue
        suite_ids.append(suite_id)
        label = f"regression suite {suite_id}"

        private_hash = descriptor.get("private_suite_sha256")
        if not isinstance(private_hash, str) or SHA256.fullmatch(private_hash) is None:
            findings.append(f"{label}: invalid private_suite_sha256")
        target_count = descriptor.get("target_case_count")
        if (
            not isinstance(target_count, int)
            or isinstance(target_count, bool)
            or target_count <= 0
        ):
            findings.append(f"{label}: invalid target_case_count")

        policy_path = _repo_artifact(
            repo_root,
            descriptor.get("policy"),
            label=f"{label} policy",
        )
        summary_path = _repo_artifact(
            repo_root,
            descriptor.get("public_suite_summary"),
            label=f"{label} public suite summary",
        )
        negative_path = _repo_artifact(
            repo_root,
            descriptor.get("public_negative_control"),
            label=f"{label} public negative control",
        )
        for path, artifact_label in (
            (policy_path, "policy"),
            (summary_path, "public suite summary"),
            (negative_path, "public negative control"),
        ):
            if path is None or not path.is_file():
                findings.append(f"{label}: missing {artifact_label}")

        if policy_path is not None and policy_path.is_file():
            policy = _read_json(policy_path)
            if policy.get("suite_id") != suite_id:
                findings.append(f"{label}: policy suite_id mismatch")
            if policy.get("split") != "development":
                findings.append(f"{label}: policy must be development-only")
        if summary_path is not None and summary_path.is_file():
            summary = _read_json(summary_path)
            findings.extend(
                f"{label}: unsafe public suite summary: {finding}"
                for finding in audit_public_error_summary(summary)
            )
            if summary.get("suite_id") != suite_id:
                findings.append(f"{label}: public summary suite_id mismatch")
            if summary.get("target_case_count") != target_count:
                findings.append(f"{label}: target_case_count mismatch")
        if negative_path is not None and negative_path.is_file():
            negative = _read_json(negative_path)
            findings.extend(
                f"{label}: unsafe negative control: {finding}"
                for finding in audit_public_error_summary(negative)
            )
            if negative.get("suite_id") != suite_id:
                findings.append(f"{label}: negative control suite_id mismatch")
            counts = negative.get("counts", {})
            if (
                negative.get("status") != "failed"
                or counts.get("target_cases") != target_count
                or counts.get("passed") != 0
                or counts.get("failed") != target_count
            ):
                findings.append(
                    f"{label}: negative control must reject every target case"
                )
    return tuple(suite_ids), findings


def _load_reviewed_cases(
    private_book_path: Path,
    diagnoses_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    book = _read_json(private_book_path)
    diagnoses = _read_json(diagnoses_path)
    raw_cases = book.get("cases")
    annotations = diagnoses.get("annotations")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("private error book must contain cases")
    if not isinstance(annotations, list) or not annotations:
        raise ValueError("diagnoses must contain annotations")
    case_by_id = _unique_objects(raw_cases, "case_id", "private cases")
    diagnosis_by_id = _unique_objects(annotations, "case_id", "diagnoses")
    if set(case_by_id) != set(diagnosis_by_id):
        missing = sorted(set(case_by_id) - set(diagnosis_by_id))
        extra = sorted(set(diagnosis_by_id) - set(case_by_id))
        raise ValueError(
            "diagnoses must cover every private case; "
            f"missing={missing}, extra={extra}"
        )
    combined = []
    for case_id, case in case_by_id.items():
        annotation = diagnosis_by_id[case_id]
        required = (
            "primary_cause",
            "diagnosis_zh",
            "diagnosis_en",
            "recommended_action",
            "review_confidence",
        )
        if any(
            not isinstance(annotation.get(field), str)
            or not annotation[field].strip()
            for field in required
        ):
            raise ValueError(f"diagnosis fields are incomplete: {case_id}")
        combined.append({**case, **annotation})
    return book, combined


def _select_typical_cases(
    cases: list[dict[str, Any]],
    maximum: int,
) -> list[dict[str, Any]]:
    ranked = sorted(cases, key=_typical_rank)
    selected: dict[str, dict[str, Any]] = {}
    for case in ranked:
        if case.get("typical_case") is True:
            selected.setdefault(case["case_id"], case)
    if len(selected) > maximum:
        raise ValueError(
            "max_typical_cases is smaller than the reviewer-nominated case set"
        )

    target_categories = {
        ("question", case["question_id"])
        for case in ranked
    } | {
        ("cause", case["primary_cause"])
        for case in ranked
    } | {
        ("severe_direction", case["direction"])
        for case in ranked
        if case["severe_error"]
    }

    while len(selected) < maximum:
        covered = set()
        for case in selected.values():
            covered.update(_typical_categories(case))
        uncovered = target_categories - covered
        if not uncovered:
            break
        candidates = [
            case for case in ranked if case["case_id"] not in selected
        ]
        if not candidates:
            break
        best = min(
            candidates,
            key=lambda case: (
                -len(_typical_categories(case) & uncovered),
                _typical_rank(case),
            ),
        )
        if not (_typical_categories(best) & uncovered):
            break
        selected[best["case_id"]] = best

    covered = set()
    for case in selected.values():
        covered.update(_typical_categories(case))
    if not target_categories.issubset(covered):
        raise ValueError(
            "max_typical_cases is too small to cover every required category"
        )

    for case in ranked:
        if len(selected) >= maximum:
            break
        selected.setdefault(case["case_id"], case)
    return sorted(selected.values(), key=_case_order)


def _typical_categories(case: dict[str, Any]) -> set[tuple[str, str]]:
    categories = {
        ("question", case["question_id"]),
        ("cause", case["primary_cause"]),
    }
    if case["severe_error"]:
        categories.add(("severe_direction", case["direction"]))
    return categories


def _render_case(index: int, case: dict[str, Any]) -> list[str]:
    flags = ", ".join(case.get("flags", ())) or "none"
    lines = [
        f"### {index}. `{case['case_id']}` — "
        f"`{case['anonymous_student_id']}` / `{case['question_id']}`",
        "",
        "| Gold | Predicted | Signed error | Absolute error | Direction | "
        "Severe | Confidence | Flags |",
        "|---:|---:|---:|---:|---|---|---|---|",
        "| {gold:g} | {predicted:g} | {signed:+g} | {absolute:g} | "
        "{direction} | {severe} | {confidence} | {flags} |".format(
            gold=case["gold_score"],
            predicted=case["predicted_score"],
            signed=case["signed_error"],
            absolute=case["absolute_error"],
            direction=case["direction"],
            severe="yes" if case["severe_error"] else "no",
            confidence=case["confidence"],
            flags=flags,
        ),
        "",
        "**学生答案证据 / Student answer evidence**",
        "",
        "```text",
        _safe_fence(case.get("extracted_evidence", "")),
        "```",
        "",
        "**模型评分理由 / Model grading rationale**",
        "",
        "```text",
        _safe_fence(case.get("evidence", "")),
        "```",
        "",
        f"**主要根因 / Primary cause:** `{case['primary_cause']}` "
        f"(review confidence: `{case['review_confidence']}`)",
        "",
        f"- 中文诊断：{case['diagnosis_zh']}",
        f"- English diagnosis: {case['diagnosis_en']}",
        f"- 下一动作 / Next action: `{case['recommended_action']}`",
    ]
    if isinstance(case.get("mechanism_code"), str):
        lines.append(
            f"- 错误机制 / Error mechanism: `{case['mechanism_code']}`"
        )
    if case.get("typical_case") is True:
        lines.extend(
            [
                f"- 入选原因：{case.get('typical_reason_zh', '人工标记的关键案例')}",
                "- Selection reason: "
                f"{case.get('typical_reason_en', 'reviewer-nominated key case')}",
            ]
        )
    lines.append("")
    return lines


def _validate_comparable_books(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> None:
    for book, label in ((previous, "previous"), (current, "current")):
        if book.get("scope", {}).get("split") != "development":
            raise ValueError(f"{label} error book must be development-only")
    for field in (
        "course_id",
        "assessment_id",
        "provider",
        "model",
        "input_mode",
        "data_snapshot_sha256",
        "gold_sha256",
        "text_source_sha256",
    ):
        if previous.get("provenance", {}).get(field) != current.get(
            "provenance", {}
        ).get(field):
            raise ValueError(f"error books disagree on {field}")
    for field in ("students", "student_question_pairs"):
        if previous.get("population", {}).get(field) != current.get(
            "population", {}
        ).get(field):
            raise ValueError(f"error books disagree on population {field}")
    previous_skill = previous.get("provenance", {}).get("skill_version_id")
    current_skill = current.get("provenance", {}).get("skill_version_id")
    if not isinstance(previous_skill, str) or not isinstance(current_skill, str):
        raise ValueError("both error books require skill_version_id provenance")
    if previous_skill == current_skill:
        raise ValueError("error-book iteration comparison requires different skills")


def _case_map(book: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    cases = book.get("cases")
    if not isinstance(cases, list):
        raise ValueError("private error book cases must be a list")
    result = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("private error case must be an object")
        key = (case.get("anonymous_student_id"), case.get("question_id"))
        if not all(isinstance(value, str) for value in key):
            raise ValueError("private error case key is invalid")
        if key in result:
            raise ValueError(f"duplicate private error case: {key}")
        result[key] = case
    return result


def _private_delta_row(
    status: str,
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> dict[str, Any]:
    source = current or previous
    assert source is not None
    row = {
        "status": status,
        "anonymous_student_id": source["anonymous_student_id"],
        "question_id": source["question_id"],
        "previous": _case_score_view(previous),
        "current": _case_score_view(current),
    }
    if previous is not None and current is not None:
        row["absolute_error_change"] = round(
            current["absolute_error"] - previous["absolute_error"], 10
        )
    return row


def _case_score_view(case: dict[str, Any] | None) -> dict[str, Any] | None:
    if case is None:
        return None
    return {
        "gold_score": case["gold_score"],
        "predicted_score": case["predicted_score"],
        "absolute_error": case["absolute_error"],
        "severe_error": case["severe_error"],
        "confidence": case["confidence"],
        "flags": case["flags"],
    }


def _persistent_status(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> str:
    delta = current["absolute_error"] - previous["absolute_error"]
    if delta < 0:
        return "persistent_improved"
    if delta > 0:
        return "persistent_worsened"
    return "persistent_unchanged"


def _delta_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["status"] for row in rows)
    ordered = (
        "resolved",
        "regression",
        "persistent_improved",
        "persistent_unchanged",
        "persistent_worsened",
    )
    return {status: counts[status] for status in ordered}


def _public_delta_by_question(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[row["question_id"]][row["status"]] += 1
    return [
        {
            "question_id": question_id,
            **{
                status: counts[status]
                for status in (
                    "resolved",
                    "regression",
                    "persistent_improved",
                    "persistent_unchanged",
                    "persistent_worsened",
                )
            },
        }
        for question_id, counts in sorted(
            grouped.items(), key=lambda item: _question_sort_key(item[0])
        )
    ]


def _delta_provenance(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    previous_provenance = previous["provenance"]
    current_provenance = current["provenance"]
    return {
        "course_id": current_provenance["course_id"],
        "assessment_id": current_provenance["assessment_id"],
        "previous_skill_version_id": previous_provenance["skill_version_id"],
        "current_skill_version_id": current_provenance["skill_version_id"],
        "previous_run_id": previous_provenance.get("run_id"),
        "current_run_id": current_provenance.get("run_id"),
        "previous_output_set_sha256": previous_provenance.get("output_set_sha256"),
        "current_output_set_sha256": current_provenance.get("output_set_sha256"),
    }


def _repo_artifact(
    repo_root: Path,
    raw_path: Any,
    *,
    label: str,
) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return None
    resolved_root = repo_root.resolve()
    resolved = (resolved_root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved


def _unique_objects(
    rows: list[Any],
    key_name: str,
    label: str,
) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(key_name), str):
            raise ValueError(f"{label} require string {key_name}")
        key = row[key_name]
        if key in result:
            raise ValueError(f"duplicate {key_name} in {label}: {key}")
        result[key] = row
    return result


def _typical_rank(case: dict[str, Any]) -> tuple[Any, ...]:
    return (
        not bool(case["severe_error"]),
        -float(case["absolute_error"]),
        _question_sort_key(case["question_id"]),
        case["case_id"],
    )


def _case_order(case: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _question_sort_key(case["question_id"]),
        case["anonymous_student_id"].casefold(),
        case["case_id"],
    )


def _case_key_order(key: tuple[str, str]) -> tuple[Any, ...]:
    return (_question_sort_key(key[1]), key[0].casefold(), key[0])


def _question_sort_key(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"Q([0-9]+)(.*)", value, re.IGNORECASE)
    if match:
        return (int(match.group(1)), match.group(2))
    return (10_000, value)


def _safe_fence(value: Any) -> str:
    text = value if isinstance(value, str) else str(value)
    return text.replace("```", "` ` `").strip()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON object: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
