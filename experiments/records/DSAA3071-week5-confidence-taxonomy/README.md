# TASK6 Confidence 与错误类型审计 / Confidence and Error Taxonomy Audit

## 中文

### 目的

本记录回答两个问题：

1. 模型给出的 `high`、`medium`、`low` confidence 是否真的对应不同错误风险？
2. 模型自己标记的 flags 和 `needs_manual_review` 是否能抓住它实际容易犯的错误？

同时把 33 个 candidate-v3.2 开发集错题细分为固定、可跨 skill 版本比较的机制，优先保留非主观、可验证的错误，而不是把所有分数差异都当作 prompt 问题。

### 数据和边界

- 来源：DSAA3071 Week 5 candidate-v3.2、DeepSeek `deepseek-v4-pro`、reviewed text、development split。
- 人数与粒度：7 名匿名学生、70 个学生-题目对。
- 评分差异：33；严重差异（单题绝对分差至少 5）：16。
- 技术运行失败：0；运行失败与评分错误严格分开。
- 未读取或运行 held-out/test 数据，也没有调用新模型。

私有输入包含匿名学生编号、答案证据、原始模型输出与逐案诊断，只保存在 gitignored `Data/`。公开输出只有汇总、哈希、taxonomy 定义和中英双语解释。

### 核心结论

- Confidence **有方向性但不可靠**：high 的错误率为 27.66%，仍含 5 个严重错误；medium+low 能抓住 11/16 个严重错误，但会漏掉 5 个。
- Flags **不能作为唯一复核门**：任意 flag 只抓到 6/16 个严重错误；明确的 `needs_manual_review` 只抓到 1/16。
- 合并 medium/low 与任意 flag 后，需要复核 28/70（40%）个评分对，也只能抓到 12/16（75%）个严重错误。
- 33 个差异中，11 例为高客观性、可直接驱动 candidate-v3.3 的模型错误；11 例需课程负责人先裁决；1 例需 transcript/direct-multimodal 配对；10 例只适合作为分档校准锚点。

### 固定机制

| Mechanism | 含义 | 下一动作 |
|---|---|---|
| `explicit_evidence_omission` | 明确或可验证的答案证据被漏识别 | 直接改进 skill |
| `unsupported_evidence_credit` | 关键词、暗示或未展示步骤被当作证据 | 直接改进 skill |
| `rule_precedence_or_gate_error` | 明示规则优先级、override、上下文检查或 cap 执行错误 | 直接改进 skill |
| `official_style_tolerance_mismatch` | 简洁、局部省略或官方风格容忍度不一致 | 先人工裁决 |
| `rubric_gold_contract_inconsistency` | rubric 无法复现 gold | 先修 benchmark 合同 |
| `text_representation_ambiguity` | text-only 无法可靠保留原图信息 | 做多模态配对 |
| `score_band_boundary_disagreement` | 部分理解对应分数档位不同 | 仅作校准锚点 |

### 自动复现

```powershell
python -m benchmark.core.cli audit-error-confidence `
  --run-dir Data/DSAA3071/week5-benchmark-redaction-v3/runs/deepseek-C32-text-dev-reviewed-r1 `
  --private-book Data/DSAA3071/week5-benchmark-redaction-v3/error_book/C32-dev-reviewed-r1/error-book.private.json `
  --diagnoses Data/DSAA3071/week5-benchmark-redaction-v3/error_book/C32-dev-reviewed-r1/case-diagnoses.private.json `
  --public-error-summary experiments/records/DSAA3071-week5-candidate-v32-error-book/public-summary.json `
  --public-output experiments/records/DSAA3071-week5-confidence-taxonomy/confidence-taxonomy-summary.json `
  --markdown-output experiments/records/DSAA3071-week5-confidence-taxonomy/ANALYSIS.md
```

命令会验证 development split、非 dry-run、通过结构校验、运行与错题册 provenance、原始输出集合哈希、70 对完整覆盖、33 个诊断完整覆盖以及公开结果隐私。

### 输出

- `confidence-taxonomy-summary.json`：唯一结构化结果源。
- `ANALYSIS.md`：由结构化结果确定性生成的完整中英双语报告。
- 私有 `TYPICAL-ERROR-CASES.private.md`：加入 `mechanism_code` 后的 12 个完整案例和 33 例索引。

以后每次主评分 skill 更新都必须重新生成 confidence/flag/taxonomy 审计；该要求已加入 error-book registry 与 CI。

## English

### Purpose

This record tests whether ordinal `high`, `medium`, and `low` confidence actually correspond to different error risk, and whether model-produced flags—especially `needs_manual_review`—identify the errors the grader truly makes. It also assigns all 33 candidate-v3.2 development discrepancies to a fixed mechanism taxonomy so future skill versions can be compared without treating every score difference as a prompt defect.

### Data and scope

The source is the DSAA3071 Week 5 candidate-v3.2 DeepSeek `deepseek-v4-pro` reviewed-text development run: seven anonymous students, 70 student-question pairs, 33 score discrepancies, 16 severe discrepancies, and zero technical runtime failures. No held-out/test data was read or run, and no new model call was made.

Private identifiers, answer evidence, raw outputs, and diagnoses remain in gitignored `Data/`. Public artifacts contain only aggregates, hashes, taxonomy definitions, and bilingual interpretation.

### Main findings

- Confidence is **directionally useful but unsafe**. High confidence still has a 27.66% error rate and five severe errors. Medium plus low captures 11/16 severe errors but misses five.
- Flags are **not a sufficient review gate**. Any flag captures only 6/16 severe errors; explicit `needs_manual_review` captures 1/16.
- Combining medium/low confidence with any flag reviews 28/70 pairs (40%) and still captures only 12/16 severe errors (75%).
- Of 33 discrepancies, 11 high-objectivity model errors can directly inform candidate-v3.3, 11 require course-owner adjudication, one requires a transcript/direct-multimodal pair, and ten are calibration anchors only.

The fixed mechanism definitions and reproduction command are shown in the Chinese section. `confidence-taxonomy-summary.json` is the structured source of truth and `ANALYSIS.md` is generated from it. Every future main grading-skill update must regenerate this audit; the requirement is enforced through the error-book registry and CI.
