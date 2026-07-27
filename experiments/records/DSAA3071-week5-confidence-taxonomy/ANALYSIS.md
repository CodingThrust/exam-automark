# TASK6 Confidence 与错误类型审计 / Confidence and Error Taxonomy Audit

## 中文版

### 结论

本审计覆盖 `70` 个开发集学生-题目对：`33` 个评分差异、`16` 个严重差异、`0` 个技术运行失败。confidence 有方向信息，但不能作为正确性保证；flags 的漏报更严重。

### Confidence 实际是否可信

| Confidence | 对数 | 错误数 | 错误率 | 严重错误数 | 严重错误率 | 有 flag |
|---|---:|---:|---:|---:|---:|---:|
| `high` | 47 | 13 | 27.66% | 5 | 10.64% | 5 |
| `medium` | 22 | 19 | 86.36% | 10 | 45.45% | 13 |
| `low` | 1 | 1 | 100.00% | 1 | 100.00% | 1 |

`medium+low` 会复核 23/70 对（32.86% 工作量），抓到 11/16 个严重错误，但仍漏掉 5 个。因此 high 不能理解为“无需复核”。

### Flags 是否准确预警

任何 flag 只覆盖 14/33 个错误和 6/16 个严重错误。明确的 `needs_manual_review` 只标记 2 对，仅抓到 1 个严重错误。flag 词汇过于碎片化，19 种 flag 中有 16 种只出现一次。

把 `medium+low` 与任意 flag 合并，复核工作量升至 28/70（40.00%），严重错误召回率为 75.00%，仍不是安全的唯一门。

### 非主观错误 taxonomy

| Mechanism | 层级 | 客观性 | 案例 | 严重 | 无 flag | Skill 处置 |
|---|---|---|---:|---:|---:|---|
| `explicit_evidence_omission` | `model_decision` | `high` | 5 | 4 | 3 | `direct_skill_candidate` |
| `official_style_tolerance_mismatch` | `model_decision` | `medium` | 2 | 1 | 1 | `requires_human_adjudication` |
| `rubric_gold_contract_inconsistency` | `benchmark_contract` | `high` | 9 | 4 | 6 | `requires_human_adjudication` |
| `rule_precedence_or_gate_error` | `model_decision` | `high` | 4 | 3 | 1 | `direct_skill_candidate` |
| `score_band_boundary_disagreement` | `calibration_policy` | `low` | 10 | 2 | 5 | `calibration_anchor_only` |
| `text_representation_ambiguity` | `input_representation` | `high` | 1 | 1 | 1 | `paired_multimodal_required` |
| `unsupported_evidence_credit` | `model_decision` | `high` | 2 | 1 | 2 | `direct_skill_candidate` |

最有意义的下一步不是把 33 个差异全部写进 prompt：

- `11` 例高客观性模型错误可直接进入 candidate-v3.3 设计。
- `11` 例需先由课程负责人裁决 gold/rubric 或官方风格。
- `1` 例必须做 reviewed-transcript 与 direct-multimodal 配对。
- `10` 例只适合作为分档校准锚点，不应单独驱动规则重写。

### 建议

1. 不把 high confidence 当作自动放行条件；至少结合题目风险和错题回归集。
2. 将自由文本 flags 收敛为固定枚举，并单独保留 `needs_manual_review`。
3. candidate-v3.3 先处理明确证据遗漏、无证据给分和规则优先级错误。
4. 每次 skill 更新继续报告同一组 confidence、flag 和 taxonomy 指标。
5. 不使用 held-out/test 数据调参。

### 限制

- confidence 是 high/medium/low 顺序标签，不是数值概率，因此不能计算概率校准误差或声称 90% 可信。
- low confidence 只有 1 个评分对，不能据此估计稳定的低置信错误率。
- 根因与机制来自开发集逐案复核；rubric-gold 冲突仍需课程负责人裁决。
- 本审计未读取或运行 held-out/test 数据。

## English Version

### Conclusion

This audit covers 70 development student-question pairs: 33 score discrepancies, 16 severe discrepancies, and 0 technical runtime failures. Confidence is directionally useful but not a correctness guarantee; flags miss even more errors.

### Does confidence predict actual errors?

| Confidence | Pairs | Errors | Error rate | Severe | Severe rate | Flagged |
|---|---:|---:|---:|---:|---:|---:|
| `high` | 47 | 13 | 27.66% | 5 | 10.64% | 5 |
| `medium` | 22 | 19 | 86.36% | 10 | 45.45% | 13 |
| `low` | 1 | 1 | 100.00% | 1 | 100.00% | 1 |

Reviewing medium and low confidence inspects 23/70 pairs (32.86% workload) and captures 11/16 severe errors, but still misses 5. High confidence therefore does not mean safe to skip review.

### Do flags predict actual errors?

Any flag captures only 14/33 errors and 6/16 severe errors. Explicit `needs_manual_review` marks only 2 pairs and captures 1 severe error. The vocabulary is fragmented: 16 of 19 flags occur once.

Combining medium/low confidence with any flag raises workload to 28/70 (40.00%) and severe-error recall to 75.00%; it is still not a sufficient safety gate by itself.

### Non-subjective error taxonomy

| Mechanism | Layer | Objectivity | Cases | Severe | No flag | Skill disposition |
|---|---|---|---:|---:|---:|---|
| `explicit_evidence_omission` | `model_decision` | `high` | 5 | 4 | 3 | `direct_skill_candidate` |
| `official_style_tolerance_mismatch` | `model_decision` | `medium` | 2 | 1 | 1 | `requires_human_adjudication` |
| `rubric_gold_contract_inconsistency` | `benchmark_contract` | `high` | 9 | 4 | 6 | `requires_human_adjudication` |
| `rule_precedence_or_gate_error` | `model_decision` | `high` | 4 | 3 | 1 | `direct_skill_candidate` |
| `score_band_boundary_disagreement` | `calibration_policy` | `low` | 10 | 2 | 5 | `calibration_anchor_only` |
| `text_representation_ambiguity` | `input_representation` | `high` | 1 | 1 | 1 | `paired_multimodal_required` |
| `unsupported_evidence_credit` | `model_decision` | `high` | 2 | 1 | 2 | `direct_skill_candidate` |

The actionable split is:

- 11 high-objectivity model errors can directly inform candidate-v3.3.
- 11 cases require course-owner adjudication of gold/rubric or official style.
- 1 case requires a reviewed-transcript/direct-multimodal pair.
- 10 cases are calibration anchors and should not independently trigger rule rewrites.

### Recommendations

1. Do not auto-pass high-confidence output; combine confidence with question risk and the regression error book.
2. Replace free-form flags with a fixed enumeration and retain a distinct `needs_manual_review` signal.
3. Build candidate-v3.3 first from explicit evidence omissions, unsupported credit, and rule-precedence failures.
4. Recompute the same confidence, flag, and taxonomy metrics after every skill update.
5. Do not tune on held-out/test data.

### Limits

- Confidence is an ordinal high/medium/low label, not a numeric probability, so probability calibration error and claims such as 90% reliability are invalid.
- Low confidence contains only one pair and cannot estimate a stable low-confidence error rate.
- Causes and mechanisms come from development case review; rubric-gold conflicts still require course-owner adjudication.
- This audit did not read or run held-out/test data.
