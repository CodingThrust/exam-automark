# TASK6 Zulip 结算草稿 / TASK6 Zulip Settlement Draft

> 状态 / Status: `ready_not_posted`

## 中文

### TASK6：Confidence 可信度与非主观错误类型

**做了什么**

- 使用 candidate-v3.2 现有 70 个 development 学生-题目对，自动核对 confidence、flags、33 个逐案诊断和 16 个严重错误。
- 建立 7 类固定错误机制，并把运行技术错误、输入表示、benchmark 合同、模型决策和主观分档分层。
- 新增 `audit-error-confidence`，从私有运行生成脱敏 JSON 和中英双语报告。
- 把 confidence/flag/taxonomy 审计加入错题生命周期和 CI；以后每次评分 skill 更新必须重新计算。

**得到了什么**

- high confidence 并不安全：47 对中有 13 个错误、5 个严重错误，错误率 27.66%。
- medium+low 复核 23/70 对，抓到 11/16 个严重错误，仍漏 5 个。
- 任意 flag 只抓到 6/16 个严重错误；`needs_manual_review` 只抓到 1/16。
- medium/low 或任意 flag 的组合需要复核 28/70 对，也只能抓到 12/16 个严重错误。
- 33 个差异可行动地拆为：11 例直接改 skill、11 例先人工裁决、1 例做多模态配对、10 例仅作分档校准。
- 当前运行技术失败为 0；没有把 API、schema 或文件错误混入评分认知失败。

**如何帮助项目**

- 回答了“模型自己说不确定时是否真的更容易错”：方向上是，但远不足以自动放行 high。
- 给 candidate-v3.3 提供 11 个高客观性直接目标：明确证据遗漏、无证据给分、规则优先级或 cap 执行错误。
- 给人工复核策略提供可量化的工作量、错误召回率和严重错误召回率。
- 固定 taxonomy 后，每次 skill 更新都能比较同类错误是否解决、持续或退步。

**限制**

- confidence 是顺序标签，不是概率，不能声称 high 等于 90% 正确。
- low 只有 1 个评分对，样本过小。
- 这是 7 人 development 审计，不是 held-out/test 结论。
- rubric-gold 与官方风格冲突仍需课程负责人裁决。

**证据**

- `experiments/records/DSAA3071-week5-confidence-taxonomy/README.md`
- `experiments/records/DSAA3071-week5-confidence-taxonomy/ANALYSIS.md`
- `experiments/records/DSAA3071-week5-confidence-taxonomy/confidence-taxonomy-summary.json`

**下一步**

先让课程负责人裁决 Q6/Q8/Q10 合同问题，再仅用 11 个高客观性模型错误设计 candidate-v3.3；新版本必须重新运行同一 confidence/flag/taxonomy 审计。

## English

### TASK6: Confidence reliability and non-subjective error taxonomy

**What was done**

- Audited confidence, flags, all 33 case diagnoses, and 16 severe errors across the existing 70 candidate-v3.2 development student-question pairs.
- Defined seven fixed mechanisms across technical runtime, input representation, benchmark contract, model decision, and subjective score-band layers.
- Added `audit-error-confidence` to generate a privacy-safe JSON result and bilingual report from the private run.
- Added confidence/flag/taxonomy auditing to the error-book lifecycle and CI so every later grading-skill update must recompute it.

**Findings**

High confidence is not safe: 13 of 47 pairs are wrong and five are severe. Reviewing medium plus low inspects 23/70 pairs and captures 11/16 severe errors, still missing five. Any flag captures only 6/16 severe errors, while explicit `needs_manual_review` captures only 1/16. Combining medium/low with any flag reviews 28/70 pairs and captures 12/16 severe errors.

The 33 discrepancies split into 11 direct skill candidates, 11 cases requiring human adjudication, one paired-multimodal case, and ten calibration anchors. Technical runtime failures are zero and remain separate from cognitive grading errors.

**Project value**

The result answers whether self-reported uncertainty predicts actual failure: directionally yes, but not well enough to auto-pass high confidence. It gives candidate-v3.3 eleven high-objectivity targets, quantifies review workload and recall, and makes mechanism-level resolved/persistent/regression tracking mandatory for future skill versions.

**Limits**

Confidence is ordinal rather than probabilistic; low has only one observation; this is a seven-student development audit rather than held-out evidence; and rubric-gold conflicts still require course-owner adjudication.

**Evidence and next step**

The three public evidence files are listed in the Chinese section. Next, adjudicate Q6/Q8/Q10 contract questions and build candidate-v3.3 only from the eleven high-objectivity model errors, then rerun this same audit.
