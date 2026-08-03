"""Confidence, flag, and non-subjective error taxonomy audit."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from .error_book import audit_public_error_summary


CONFIDENCE_ORDER = ("high", "medium", "low")
PRIMARY_CAUSE_MECHANISMS = {
    "model_grading_error": {
        "explicit_evidence_omission",
        "official_style_tolerance_mismatch",
        "rule_precedence_or_gate_error",
        "unsupported_evidence_credit",
    },
    "score_band_calibration": {"score_band_boundary_disagreement"},
    "rubric_gold_misalignment": {"rubric_gold_contract_inconsistency"},
    "input_representation_ambiguity": {"text_representation_ambiguity"},
}
MECHANISM_DEFINITIONS = {
    "explicit_evidence_omission": {
        "error_layer": "model_decision",
        "objectivity_level": "high",
        "skill_update_disposition": "direct_skill_candidate",
        "zh": "答案中已有明确或可验证的语义证据，但模型未识别或错误降档。",
        "en": "Explicit or verifiable semantic evidence is present, but the model misses or downgrades it.",
    },
    "unsupported_evidence_credit": {
        "error_layer": "model_decision",
        "objectivity_level": "high",
        "skill_update_disposition": "direct_skill_candidate",
        "zh": "模型把关键词、暗示或未展示步骤当作已经证明的评分要素。",
        "en": "The model credits a keyword, implication, or unstated step as demonstrated evidence.",
    },
    "rule_precedence_or_gate_error": {
        "error_layer": "model_decision",
        "objectivity_level": "high",
        "skill_update_disposition": "direct_skill_candidate",
        "zh": "模型没有执行明示的规则优先级、满分覆盖规则、上下文检查或分数上限条件。",
        "en": "The model violates an explicit precedence, full-credit override, context check, or score-cap rule.",
    },
    "official_style_tolerance_mismatch": {
        "error_layer": "model_decision",
        "objectivity_level": "medium",
        "skill_update_disposition": "requires_human_adjudication",
        "zh": "模型对省略、简洁程度或官方评分风格的容忍度与 gold 不一致。",
        "en": "The model's tolerance for omissions, brevity, or official grading style differs from gold.",
    },
    "score_band_boundary_disagreement": {
        "error_layer": "calibration_policy",
        "objectivity_level": "low",
        "skill_update_disposition": "calibration_anchor_only",
        "zh": "概念方向大体一致，但部分理解或证明完整度对应的分数档位不同。",
        "en": "The conceptual direction broadly agrees, but the score band for partial understanding or completeness differs.",
    },
    "rubric_gold_contract_inconsistency": {
        "error_layer": "benchmark_contract",
        "objectivity_level": "high",
        "skill_update_disposition": "requires_human_adjudication",
        "zh": "明示 rubric 的要素、门槛或算术无法复现官方 gold。",
        "en": "Explicit rubric elements, gates, or arithmetic cannot reproduce official gold.",
    },
    "text_representation_ambiguity": {
        "error_layer": "input_representation",
        "objectivity_level": "high",
        "skill_update_disposition": "paired_multimodal_required",
        "zh": "文字输入丢失或混淆了需要原图裁决的记号、布局或状态。",
        "en": "Text input loses or confounds notation, layout, or state that requires the source image.",
    },
}
LAYER_DEFINITIONS = {
    "pipeline_technical": {
        "zh": "API、鉴权、超时、schema、缺失输出等运行失败；不作为评分认知错误。",
        "en": "API, authentication, timeout, schema, or missing-output failures; excluded from cognitive grading errors.",
    },
    "input_representation": {
        "zh": "转录或 text-only 表示不足。",
        "en": "Transcription or text-only representation is insufficient.",
    },
    "benchmark_contract": {
        "zh": "rubric 与官方 gold 的评分合同不一致。",
        "en": "The rubric and official gold define inconsistent grading contracts.",
    },
    "model_decision": {
        "zh": "在输入和合同足够时，模型的证据识别或规则执行错误。",
        "en": "Evidence-recognition or rule-execution errors when input and contract are sufficient.",
    },
    "calibration_policy": {
        "zh": "部分分档位或容忍政策差异。",
        "en": "Partial-credit band or tolerance-policy differences.",
    },
}


def build_error_confidence_audit(
    *,
    run_dir: Path,
    private_book_path: Path,
    diagnoses_path: Path,
    public_error_summary_path: Path,
) -> dict[str, Any]:
    book = _read_json(private_book_path)
    diagnoses = _read_json(diagnoses_path)
    source_summary = _read_json(public_error_summary_path)
    _validate_source_records(book, diagnoses, source_summary)
    pairs = _load_pairs(run_dir, book, diagnoses)

    population = book["population"]
    error_pairs = int(population["error_pairs"])
    severe_pairs = int(population["severe_error_pairs"])
    technical_failures = int(book["technical_failures"]["count"])
    confidence_rows = [
        _confidence_row(level, pairs)
        for level in CONFIDENCE_ORDER
        if any(pair["confidence"] == level for pair in pairs)
    ]
    confidence_by_level = {
        row["confidence"]: row for row in confidence_rows
    }
    signal = {
        "classification": "directionally_informative_not_probability_calibrated",
        "error_rate_monotonic_high_to_low": _nondecreasing(
            confidence_by_level[level]["error_rate"]
            for level in CONFIDENCE_ORDER
            if level in confidence_by_level
        ),
        "severe_error_rate_monotonic_high_to_low": _nondecreasing(
            confidence_by_level[level]["severe_error_rate"]
            for level in CONFIDENCE_ORDER
            if level in confidence_by_level
        ),
        "labels_are_numeric_probabilities": False,
        "low_confidence_sample_size": confidence_by_level.get(
            "low", {}
        ).get("pairs", 0),
    }
    review_policies = [
        _review_policy(
            "low_only",
            pairs,
            lambda pair: pair["confidence"] == "low",
            error_pairs,
            severe_pairs,
        ),
        _review_policy(
            "medium_or_low",
            pairs,
            lambda pair: pair["confidence"] in {"medium", "low"},
            error_pairs,
            severe_pairs,
        ),
        _review_policy(
            "any_flag",
            pairs,
            lambda pair: bool(pair["flags"]),
            error_pairs,
            severe_pairs,
        ),
        _review_policy(
            "medium_or_low_or_any_flag",
            pairs,
            lambda pair: (
                pair["confidence"] in {"medium", "low"}
                or bool(pair["flags"])
            ),
            error_pairs,
            severe_pairs,
        ),
        _review_policy(
            "explicit_needs_manual_review",
            pairs,
            lambda pair: "needs_manual_review" in pair["flags"],
            error_pairs,
            severe_pairs,
        ),
    ]
    flag_rows = _flag_rows(pairs, error_pairs, severe_pairs)
    mechanism_rows = _taxonomy_rows(
        pairs,
        group_field="mechanism_code",
        definitions=MECHANISM_DEFINITIONS,
    )
    layer_rows = _taxonomy_rows(
        pairs,
        group_field="error_layer",
        definitions=LAYER_DEFINITIONS,
    )
    if technical_failures:
        layer_rows.insert(
            0,
            {
                "error_layer": "pipeline_technical",
                "cases": technical_failures,
                "severe_error_pairs": 0,
                "mean_absolute_error": None,
                "flagged_pairs": 0,
                "no_flag_pairs": 0,
                "confidence_counts": {},
                "direction_counts": {},
                **LAYER_DEFINITIONS["pipeline_technical"],
            },
        )

    disposition_rows = _simple_taxonomy_counts(
        pairs, "skill_update_disposition"
    )
    objectivity_rows = _simple_taxonomy_counts(pairs, "objectivity_level")
    provenance = book["provenance"]
    low_confidence_pairs = next(
        (
            row["pairs"]
            for row in confidence_rows
            if row["confidence"] == "low"
        ),
        0,
    )
    low_confidence_pair_label = (
        "pair" if low_confidence_pairs == 1 else "pairs"
    )
    result = {
        "record_type": "grading_error_confidence_taxonomy_audit_public",
        "schema_version": 1,
        "scope": {
            "split": "development",
            "contains_heldout_or_test_data": False,
            "contains_student_level_records": False,
            "contains_answer_or_evidence_text": False,
            "technical_failures_are_separate": True,
        },
        "provenance": {
            key: provenance.get(key)
            for key in (
                "course_id",
                "assessment_id",
                "condition",
                "provider",
                "model",
                "input_mode",
                "skill_version_id",
                "run_commit",
                "run_id",
                "packet_id",
                "packet_sha256",
                "output_set_sha256",
                "gold_sha256",
                "prompt_sha256",
                "rubric_sha256",
                "data_snapshot_sha256",
                "text_source_sha256",
            )
        }
        | {
            "private_error_book_sha256": _file_hash(private_book_path),
            "private_diagnoses_sha256": _file_hash(diagnoses_path),
            "source_public_summary_sha256": _file_hash(
                public_error_summary_path
            ),
        },
        "population": {
            "students": population["students"],
            "student_question_pairs": population["student_question_pairs"],
            "exact_pairs": population["exact_pairs"],
            "error_pairs": error_pairs,
            "severe_error_pairs": severe_pairs,
            "technical_failure_count": technical_failures,
        },
        "confidence_audit": {
            "levels": confidence_rows,
            "signal_assessment": signal,
            "review_policies": review_policies,
        },
        "flag_audit": {
            "any_flag": next(
                policy
                for policy in review_policies
                if policy["policy"] == "any_flag"
            ),
            "explicit_needs_manual_review": next(
                policy
                for policy in review_policies
                if policy["policy"] == "explicit_needs_manual_review"
            ),
            "flag_vocabulary_size": len(flag_rows),
            "single_observation_flags": sum(
                row["pairs"] == 1 for row in flag_rows
            ),
            "model_flag_text_published": False,
        },
        "error_taxonomy": {
            "technical_failure_count": technical_failures,
            "layers": layer_rows,
            "mechanisms": mechanism_rows,
            "objectivity_groups": objectivity_rows,
            "skill_update_dispositions": disposition_rows,
        },
        "interpretation_limits": {
            "zh": [
                "confidence 是 high/medium/low 顺序标签，不是数值概率，因此不能计算概率校准误差或声称 90% 可信。",
                f"low confidence 有 {low_confidence_pairs} 个评分对，"
                "样本仍不足以估计稳定的低置信错误率。",
                "根因与机制来自开发集逐案复核；rubric-gold 冲突仍需课程负责人裁决。",
                "本审计未读取或运行 held-out/test 数据。",
            ],
            "en": [
                "Confidence is an ordinal high/medium/low label, not a numeric probability, so probability calibration error and claims such as 90% reliability are invalid.",
                f"Low confidence contains {low_confidence_pairs} "
                f"{low_confidence_pair_label}, which "
                "is still insufficient to estimate a stable low-confidence error rate.",
                "Causes and mechanisms come from development case review; rubric-gold conflicts still require course-owner adjudication.",
                "This audit did not read or run held-out/test data.",
            ],
        },
    }
    findings = audit_public_error_summary(result)
    if findings:
        raise ValueError(f"public confidence audit failed privacy scan: {findings}")
    return result


def write_error_confidence_audit(
    *,
    run_dir: Path,
    private_book_path: Path,
    diagnoses_path: Path,
    public_error_summary_path: Path,
    public_output: Path,
    markdown_output: Path,
) -> dict[str, Any]:
    result = build_error_confidence_audit(
        run_dir=run_dir,
        private_book_path=private_book_path,
        diagnoses_path=diagnoses_path,
        public_error_summary_path=public_error_summary_path,
    )
    _write_json(public_output, result)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(
        render_error_confidence_markdown(result),
        encoding="utf-8",
        newline="\n",
    )
    return result


def render_error_confidence_markdown(audit: dict[str, Any]) -> str:
    population = audit["population"]
    confidence = audit["confidence_audit"]
    policies = {
        row["policy"]: row for row in confidence["review_policies"]
    }
    flags = audit["flag_audit"]
    taxonomy = audit["error_taxonomy"]
    lines = [
        "# Confidence 与错误类型审计 / Confidence and Error Taxonomy Audit",
        "",
        "## 中文版",
        "",
        "### 结论",
        "",
        f"本审计覆盖 `{population['student_question_pairs']}` 个开发集学生-题目对："
        f"`{population['error_pairs']}` 个评分差异、"
        f"`{population['severe_error_pairs']}` 个严重差异、"
        f"`{population['technical_failure_count']}` 个技术运行失败。"
        "confidence 有方向信息，但不能作为正确性保证；flags 的漏报更严重。",
        "",
        "### Confidence 实际是否可信",
        "",
        "| Confidence | 对数 | 错误数 | 错误率 | 严重错误数 | 严重错误率 | 有 flag |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in confidence["levels"]:
        lines.append(
            f"| `{row['confidence']}` | {row['pairs']} | "
            f"{row['error_pairs']} | {_percent(row['error_rate'])} | "
            f"{row['severe_error_pairs']} | "
            f"{_percent(row['severe_error_rate'])} | "
            f"{row['flagged_pairs']} |"
        )
    medium_low = policies["medium_or_low"]
    combined = policies["medium_or_low_or_any_flag"]
    lines.extend(
        [
            "",
            f"`medium+low` 会复核 {medium_low['review_pairs']}/"
            f"{population['student_question_pairs']} 对（"
            f"{_percent(medium_low['review_workload_rate'])} 工作量），"
            f"抓到 {medium_low['severe_error_pairs_captured']}/"
            f"{population['severe_error_pairs']} 个严重错误，但仍漏掉 "
            f"{medium_low['missed_severe_error_pairs']} 个。"
            "因此 high 不能理解为“无需复核”。",
            "",
            "### Flags 是否准确预警",
            "",
            f"任何 flag 只覆盖 {flags['any_flag']['error_pairs_captured']}/"
            f"{population['error_pairs']} 个错误和 "
            f"{flags['any_flag']['severe_error_pairs_captured']}/"
            f"{population['severe_error_pairs']} 个严重错误。明确的 "
            f"`needs_manual_review` 只标记 "
            f"{flags['explicit_needs_manual_review']['review_pairs']} 对，"
            f"仅抓到 {flags['explicit_needs_manual_review']['severe_error_pairs_captured']} "
            "个严重错误。flag 词汇过于碎片化，"
            f"{flags['flag_vocabulary_size']} 种 flag 中有 "
            f"{flags['single_observation_flags']} 种只出现一次。",
            "",
            f"把 `medium+low` 与任意 flag 合并，复核工作量升至 "
            f"{combined['review_pairs']}/"
            f"{population['student_question_pairs']}（"
            f"{_percent(combined['review_workload_rate'])}），"
            f"严重错误召回率为 "
            f"{_percent(combined['severe_error_recall'])}，仍不是安全的唯一门。",
            "",
            "### 非主观错误 taxonomy",
            "",
            "| Mechanism | 层级 | 客观性 | 案例 | 严重 | 无 flag | Skill 处置 |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in taxonomy["mechanisms"]:
        lines.append(
            f"| `{row['mechanism_code']}` | `{row['error_layer']}` | "
            f"`{row['objectivity_level']}` | {row['cases']} | "
            f"{row['severe_error_pairs']} | {row['no_flag_pairs']} | "
            f"`{row['skill_update_disposition']}` |"
        )
    dispositions = {
        row["skill_update_disposition"]: row["cases"]
        for row in taxonomy["skill_update_dispositions"]
    }
    lines.extend(
        [
            "",
            f"最有意义的下一步不是把 {population['error_pairs']} 个差异全部写进 prompt：",
            "",
            f"- `{dispositions.get('direct_skill_candidate', 0)}` 例高客观性模型错误可直接进入下一次 candidate 设计。",
            f"- `{dispositions.get('requires_human_adjudication', 0)}` 例需先由课程负责人裁决 gold/rubric 或官方风格。",
            f"- `{dispositions.get('paired_multimodal_required', 0)}` 例必须做 reviewed-transcript 与 direct-multimodal 配对。",
            f"- `{dispositions.get('calibration_anchor_only', 0)}` 例只适合作为分档校准锚点，不应单独驱动规则重写。",
            "",
            "### 建议",
            "",
            "1. 不把 high confidence 当作自动放行条件；至少结合题目风险和错题回归集。",
            "2. 将自由文本 flags 收敛为固定枚举，并单独保留 `needs_manual_review`。",
            "3. 下一次 candidate 只处理明确证据遗漏、无证据给分和规则优先级错误。",
            "4. 每次 skill 更新继续报告同一组 confidence、flag 和 taxonomy 指标。",
            "5. 不使用 held-out/test 数据调参。",
            "",
            "### 限制",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in audit["interpretation_limits"]["zh"])
    lines.extend(
        [
            "",
            "## English Version",
            "",
            "### Conclusion",
            "",
            f"This audit covers {population['student_question_pairs']} development "
            f"student-question pairs: {population['error_pairs']} score "
            f"discrepancies, {population['severe_error_pairs']} severe "
            f"discrepancies, and {population['technical_failure_count']} "
            "technical runtime failures. Confidence is directionally useful but "
            "not a correctness guarantee; flags miss even more errors.",
            "",
            "### Does confidence predict actual errors?",
            "",
            "| Confidence | Pairs | Errors | Error rate | Severe | Severe rate | Flagged |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in confidence["levels"]:
        lines.append(
            f"| `{row['confidence']}` | {row['pairs']} | "
            f"{row['error_pairs']} | {_percent(row['error_rate'])} | "
            f"{row['severe_error_pairs']} | "
            f"{_percent(row['severe_error_rate'])} | "
            f"{row['flagged_pairs']} |"
        )
    lines.extend(
        [
            "",
            f"Reviewing medium and low confidence inspects "
            f"{medium_low['review_pairs']}/"
            f"{population['student_question_pairs']} pairs "
            f"({_percent(medium_low['review_workload_rate'])} workload) and "
            f"captures {medium_low['severe_error_pairs_captured']}/"
            f"{population['severe_error_pairs']} severe errors, but still misses "
            f"{medium_low['missed_severe_error_pairs']}. High confidence therefore "
            "does not mean safe to skip review.",
            "",
            "### Do flags predict actual errors?",
            "",
            f"Any flag captures only {flags['any_flag']['error_pairs_captured']}/"
            f"{population['error_pairs']} errors and "
            f"{flags['any_flag']['severe_error_pairs_captured']}/"
            f"{population['severe_error_pairs']} severe errors. Explicit "
            f"`needs_manual_review` marks only "
            f"{flags['explicit_needs_manual_review']['review_pairs']} pairs and "
            f"captures {flags['explicit_needs_manual_review']['severe_error_pairs_captured']} "
            "severe error(s). The vocabulary is fragmented: "
            f"{flags['single_observation_flags']} of "
            f"{flags['flag_vocabulary_size']} flags occur once.",
            "",
            f"Combining medium/low confidence with any flag raises workload to "
            f"{combined['review_pairs']}/"
            f"{population['student_question_pairs']} "
            f"({_percent(combined['review_workload_rate'])}) and severe-error "
            f"recall to {_percent(combined['severe_error_recall'])}; it is still "
            "not a sufficient safety gate by itself.",
            "",
            "### Non-subjective error taxonomy",
            "",
            "| Mechanism | Layer | Objectivity | Cases | Severe | No flag | Skill disposition |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in taxonomy["mechanisms"]:
        lines.append(
            f"| `{row['mechanism_code']}` | `{row['error_layer']}` | "
            f"`{row['objectivity_level']}` | {row['cases']} | "
            f"{row['severe_error_pairs']} | {row['no_flag_pairs']} | "
            f"`{row['skill_update_disposition']}` |"
        )
    lines.extend(
        [
            "",
            "The actionable split is:",
            "",
            f"- {dispositions.get('direct_skill_candidate', 0)} high-objectivity model errors can directly inform the next candidate design.",
            f"- {dispositions.get('requires_human_adjudication', 0)} cases require course-owner adjudication of gold/rubric or official style.",
            f"- {dispositions.get('paired_multimodal_required', 0)} case(s) require a reviewed-transcript/direct-multimodal pair.",
            f"- {dispositions.get('calibration_anchor_only', 0)} cases are calibration anchors and should not independently trigger rule rewrites.",
            "",
            "### Recommendations",
            "",
            "1. Do not auto-pass high-confidence output; combine confidence with question risk and the regression error book.",
            "2. Replace free-form flags with a fixed enumeration and retain a distinct `needs_manual_review` signal.",
            "3. Build the next candidate only from explicit evidence omissions, unsupported credit, and rule-precedence failures.",
            "4. Recompute the same confidence, flag, and taxonomy metrics after every skill update.",
            "5. Do not tune on held-out/test data.",
            "",
            "### Limits",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in audit["interpretation_limits"]["en"])
    lines.append("")
    return "\n".join(lines)


def _validate_source_records(
    book: dict[str, Any],
    diagnoses: dict[str, Any],
    source_summary: dict[str, Any],
) -> None:
    if book.get("scope", {}).get("split") != "development":
        raise ValueError("private error book must be development-only")
    if source_summary.get("scope", {}).get("split") != "development":
        raise ValueError("public error summary must be development-only")
    public_findings = audit_public_error_summary(source_summary)
    if public_findings:
        raise ValueError(
            f"source public error summary failed privacy scan: {public_findings}"
        )
    if book.get("technical_failures", {}).get(
        "included_as_grading_cases"
    ) is not False:
        raise ValueError("technical failures must remain separate")
    for field in (
        "course_id",
        "assessment_id",
        "provider",
        "model",
        "input_mode",
        "skill_version_id",
        "run_id",
        "packet_sha256",
        "output_set_sha256",
        "gold_sha256",
    ):
        if book.get("provenance", {}).get(field) != source_summary.get(
            "provenance", {}
        ).get(field):
            raise ValueError(f"private and public error records disagree on {field}")
    for field in (
        "students",
        "student_question_pairs",
        "exact_pairs",
        "error_pairs",
        "severe_error_pairs",
    ):
        if book.get("population", {}).get(field) != source_summary.get(
            "population", {}
        ).get(field):
            raise ValueError(f"private and public populations disagree on {field}")
    annotations = diagnoses.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("diagnoses annotations must be a list")
    cases = book.get("cases")
    if not isinstance(cases, list):
        raise ValueError("private error cases must be a list")
    case_ids = _unique_values(cases, "case_id", "private cases")
    diagnosis_ids = _unique_values(annotations, "case_id", "diagnoses")
    if case_ids != diagnosis_ids:
        raise ValueError("diagnoses must cover every private error case")
    for annotation in annotations:
        primary_cause = annotation.get("primary_cause")
        mechanism = annotation.get("mechanism_code")
        if primary_cause not in PRIMARY_CAUSE_MECHANISMS:
            raise ValueError(f"unsupported primary_cause: {primary_cause}")
        if mechanism not in PRIMARY_CAUSE_MECHANISMS[primary_cause]:
            raise ValueError(
                f"mechanism_code does not match primary_cause: "
                f"{annotation.get('case_id')}"
            )


def _load_pairs(
    run_dir: Path,
    book: dict[str, Any],
    diagnoses: dict[str, Any],
) -> list[dict[str, Any]]:
    metadata = _read_json(run_dir / "run-metadata.json")
    if metadata.get("split") != "development":
        raise ValueError("confidence audit requires a development run")
    if metadata.get("dry_run") is not False:
        raise ValueError("confidence audit rejects dry runs")
    if metadata.get("validation_status") != "passed":
        raise ValueError("confidence audit requires a validation-passed run")
    for field in (
        "course_id",
        "assessment_id",
        "provider",
        "model",
        "input_mode",
        "skill_version_id",
        "packet_hash",
    ):
        provenance_field = (
            "packet_sha256" if field == "packet_hash" else field
        )
        if metadata.get(field) != book.get("provenance", {}).get(
            provenance_field
        ):
            raise ValueError(f"run and error book disagree on {field}")
    output_dir = run_dir / "outputs"
    if _directory_hash(output_dir) != book["provenance"]["output_set_sha256"]:
        raise ValueError("run output hash does not match the private error book")

    cases = {
        (case["anonymous_student_id"], case["question_id"]): case
        for case in book["cases"]
    }
    if len(cases) != len(book["cases"]):
        raise ValueError("duplicate student-question key in private error book")
    annotations = {
        annotation["case_id"]: annotation
        for annotation in diagnoses["annotations"]
    }
    output_paths = sorted(
        output_dir.glob("*.json"), key=lambda path: path.name.casefold()
    )
    expected_students = metadata.get("student_ids")
    if (
        not isinstance(expected_students, list)
        or not all(isinstance(value, str) for value in expected_students)
        or len(expected_students) != len(set(expected_students))
    ):
        raise ValueError(
            "run metadata student_ids must be a unique string list"
        )
    if {path.stem for path in output_paths} != set(expected_students):
        raise ValueError("run outputs do not match metadata student_ids")

    pairs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in output_paths:
        payload = _read_json(path)
        student_id = payload.get("student_id")
        if student_id != path.stem:
            raise ValueError(f"output student_id mismatch: {path.name}")
        scores = payload.get("scores")
        if not isinstance(scores, list):
            raise ValueError(f"output scores must be a list: {path.name}")
        for score in scores:
            if not isinstance(score, dict):
                raise ValueError(f"output score must be an object: {path.name}")
            question_id = score.get("question_id")
            confidence = score.get("confidence")
            flags = score.get("flags")
            if not isinstance(question_id, str):
                raise ValueError(f"invalid question_id: {path.name}")
            if confidence not in CONFIDENCE_ORDER:
                raise ValueError(f"invalid confidence: {path.name}:{question_id}")
            if (
                not isinstance(flags, list)
                or not all(isinstance(flag, str) and flag for flag in flags)
                or len(flags) != len(set(flags))
            ):
                raise ValueError(f"invalid flags: {path.name}:{question_id}")
            key = (student_id, question_id)
            if key in seen:
                raise ValueError(f"duplicate output pair: {key}")
            seen.add(key)
            case = cases.get(key)
            annotation = annotations[case["case_id"]] if case else None
            if case is not None:
                if confidence != case.get("confidence"):
                    raise ValueError(f"confidence drift for {case['case_id']}")
                if flags != case.get("flags"):
                    raise ValueError(f"flag drift for {case['case_id']}")
                mechanism = annotation["mechanism_code"]
                definition = MECHANISM_DEFINITIONS[mechanism]
            else:
                mechanism = None
                definition = {}
            pairs.append(
                {
                    "student_question_key": key,
                    "question_id": question_id,
                    "confidence": confidence,
                    "flags": tuple(flags),
                    "is_error": case is not None,
                    "is_severe": bool(case and case["severe_error"]),
                    "absolute_error": (
                        float(case["absolute_error"]) if case else 0.0
                    ),
                    "direction": case.get("direction") if case else None,
                    "primary_cause": (
                        annotation.get("primary_cause") if annotation else None
                    ),
                    "mechanism_code": mechanism,
                    "error_layer": definition.get("error_layer"),
                    "objectivity_level": definition.get("objectivity_level"),
                    "skill_update_disposition": definition.get(
                        "skill_update_disposition"
                    ),
                }
            )
    population = book["population"]
    if len(pairs) != population["student_question_pairs"]:
        raise ValueError("output pair count does not match error-book population")
    if len(cases) != population["error_pairs"]:
        raise ValueError("error case count does not match error-book population")
    if sum(pair["is_severe"] for pair in pairs) != population[
        "severe_error_pairs"
    ]:
        raise ValueError("severe case count does not match error-book population")
    return pairs


def _confidence_row(
    confidence: str,
    pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = [pair for pair in pairs if pair["confidence"] == confidence]
    errors = sum(pair["is_error"] for pair in selected)
    severe = sum(pair["is_severe"] for pair in selected)
    return {
        "confidence": confidence,
        "pairs": len(selected),
        "exact_pairs": len(selected) - errors,
        "error_pairs": errors,
        "error_rate": _ratio(errors, len(selected)),
        "exact_agreement": _ratio(len(selected) - errors, len(selected)),
        "severe_error_pairs": severe,
        "severe_error_rate": _ratio(severe, len(selected)),
        "flagged_pairs": sum(bool(pair["flags"]) for pair in selected),
    }


def _review_policy(
    name: str,
    pairs: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
    total_errors: int,
    total_severe: int,
) -> dict[str, Any]:
    selected = [pair for pair in pairs if predicate(pair)]
    errors = sum(pair["is_error"] for pair in selected)
    severe = sum(pair["is_severe"] for pair in selected)
    return {
        "policy": name,
        "review_pairs": len(selected),
        "review_workload_rate": _ratio(len(selected), len(pairs)),
        "exact_pairs_reviewed": len(selected) - errors,
        "error_pairs_captured": errors,
        "error_precision": _ratio(errors, len(selected)),
        "error_recall": _ratio(errors, total_errors),
        "missed_error_pairs": total_errors - errors,
        "severe_error_pairs_captured": severe,
        "severe_error_yield": _ratio(severe, len(selected)),
        "severe_error_recall": _ratio(severe, total_severe),
        "missed_severe_error_pairs": total_severe - severe,
    }


def _flag_rows(
    pairs: list[dict[str, Any]],
    total_errors: int,
    total_severe: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        for flag in pair["flags"]:
            grouped[flag].append(pair)
    rows = []
    for flag, selected in sorted(grouped.items()):
        errors = sum(pair["is_error"] for pair in selected)
        severe = sum(pair["is_severe"] for pair in selected)
        rows.append(
            {
                "flag": flag,
                "pairs": len(selected),
                "error_pairs": errors,
                "error_precision": _ratio(errors, len(selected)),
                "error_recall": _ratio(errors, total_errors),
                "severe_error_pairs": severe,
                "severe_error_recall": _ratio(severe, total_severe),
            }
        )
    return rows


def _taxonomy_rows(
    pairs: list[dict[str, Any]],
    *,
    group_field: str,
    definitions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        value = pair.get(group_field)
        if pair["is_error"] and isinstance(value, str):
            grouped[value].append(pair)
    rows = []
    for value, selected in sorted(grouped.items()):
        definition = definitions[value]
        row = {
            group_field: value,
            "cases": len(selected),
            "severe_error_pairs": sum(
                pair["is_severe"] for pair in selected
            ),
            "mean_absolute_error": _mean(
                pair["absolute_error"] for pair in selected
            ),
            "flagged_pairs": sum(bool(pair["flags"]) for pair in selected),
            "no_flag_pairs": sum(not pair["flags"] for pair in selected),
            "confidence_counts": dict(
                sorted(Counter(pair["confidence"] for pair in selected).items())
            ),
            "direction_counts": dict(
                sorted(Counter(pair["direction"] for pair in selected).items())
            ),
            **definition,
        }
        rows.append(row)
    return rows


def _simple_taxonomy_counts(
    pairs: list[dict[str, Any]],
    field: str,
) -> list[dict[str, Any]]:
    grouped = Counter(
        pair[field] for pair in pairs if pair["is_error"] and pair[field]
    )
    return [
        {field: value, "cases": count}
        for value, count in sorted(grouped.items())
    ]


def _unique_values(
    rows: list[Any],
    key: str,
    label: str,
) -> set[str]:
    values = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(key), str):
            raise ValueError(f"{label} require string {key}")
        values.append(row[key])
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {key} in {label}")
    return set(values)


def _nondecreasing(values: Any) -> bool:
    sequence = list(values)
    return all(left <= right for left, right in zip(sequence, sequence[1:]))


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _mean(values: Any) -> float:
    sequence = list(values)
    return round(sum(sequence) / len(sequence), 6) if sequence else 0.0


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


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
