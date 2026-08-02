# TASK9 Candidate-v3.3 Rule Precedence Experiment / TASK9 Candidate-v3.3 规则优先级实验

Status / 状态：**rejected by the pre-registered safety gate; active skill remains v3.2 / 未通过预注册安全门；active skill 保持 v3.2**

Human-adjudication update / 人工裁决更新：The four Q9 cases later selected for
the historical regression suite were not confirmed as model errors. This does
not reverse the candidate rejection: v3.3 still failed its pre-registered
global severe-error gate. It only withdraws the case-level claim that the
historical Q9 targets were confirmed defects.

后来进入历史回归套件的四个 Q9 案例均未被人工确认为模型错误。这不会推翻
v3.3 的 rejected 决定，因为它仍未通过预注册的全局严重错误门槛；被撤回的只是
“这些 Q9 案例已确认是模型缺陷”的逐例结论。

## 中文

本实验只修复一个已由开发集错题册确认的评分机制：
`rule_precedence_or_gate_error`。Candidate-v3.2 在开放式概念题上仍会把
rubric 中的示例性 evidence families 当成必须逐项满足的清单，并因答案简短而
自动降低 evidence level，即使题目的 `full_credit_rule` 已明确允许广泛、有效、
不矛盾的证据。

Candidate-v3.3 引入一个确定性的“规则优先级与整体充分性”决策：

1. 先读取题目要求、题目专属 `full_credit_rule` 和 material-error 条件。
2. 若 `full_credit_rule` 明确采用整体充分性，scoring elements 和示例族只用于
   组织证据与部分分；除非题目明确说“全部必需”，否则不得把它们变成清单。
3. 简短本身不是扣分依据。只有缺失被明确要求的行为、术语或逻辑关系，或出现
   可见矛盾时，才能降低 evidence level。
4. 最终理由必须指出具体缺失或矛盾，不能只写“太简短”或“缺少另一类示例”。

本次不修改 Q6、Q8、Q10 的规则。它们分别涉及 rubric/gold 合同冲突、文字表示
歧义或课程负责人风格裁决，不能混入本次单机制实验。测试集/held-out 数据不会
读取、运行或用于调参。

### 冻结比较

- 前版本：`skill_candidate_v3_2`
- 候选版本：`skill_candidate_v3_3`
- 模型：`deepseek-v4-pro`
- 输入：同一批 7 名开发集学生的人工复核 transcript
- 模式：`text-only`
- Rubric：`DSAA3071-week5-v2`，保持不变
- 重复次数：1
- 唯一允许的评分逻辑变化：规则优先级与整体充分性

### 预注册通过门槛

Candidate-v3.3 只有同时满足以下条件才接受：

1. Q9 MAE `< 9.000000`；
2. 全部 70 个学生-题目对的 question MAE `< 2.557143`；
3. 严重错误数 `<= 16`；
4. Q1-Q4 保持零回归；
5. 相对 v3.2 的 `resolved` 数量大于 `regression` 数量。

若未通过，保留负结果和候选快照，但 active skill 必须恢复并继续指向 v3.2。
一次运行完成后不根据同一输出继续改 prompt 再跑，避免顺着随机波动调参。

## English

This experiment changes exactly one grading mechanism confirmed by the
development error book: `rule_precedence_or_gate_error`. Candidate-v3.2 can
still turn illustrative rubric evidence families into a mandatory checklist
and downgrade concise answers even when the question-specific
`full_credit_rule` explicitly accepts broad, valid, non-contradictory evidence.

Candidate-v3.3 adds a deterministic rule-precedence and holistic-sufficiency
decision:

1. Read the task requirement, question-specific `full_credit_rule`, and
   material-error conditions first.
2. When the `full_credit_rule` defines holistic sufficiency, use scoring
   elements and example families to organize evidence and partial credit.
   Do not turn them into a checklist unless the question explicitly requires
   every item.
3. Brevity alone is not a deduction. Lower an evidence level only for a named
   missing required behavior, term, or relation, or for a visible contradiction.
4. The final rationale must name the missing requirement or contradiction; it
   may not rely only on “too brief” or “missing another example family.”

This run does not change the Q6, Q8, or Q10 policies. Those cases require
rubric/gold contract adjudication, direct-multimodal representation review, or
course-owner style calibration and must not be mixed into this single-mechanism
experiment. No held-out/test data is read, run, or used for tuning.

### Frozen comparison

- Predecessor: `skill_candidate_v3_2`
- Candidate: `skill_candidate_v3_3`
- Model: `deepseek-v4-pro`
- Input: the same seven-student human-reviewed development transcripts
- Mode: `text-only`
- Rubric: unchanged `DSAA3071-week5-v2`
- Repetitions: 1
- Only permitted grading-logic change: rule precedence and holistic sufficiency

### Pre-registered acceptance gate

Candidate-v3.3 is accepted only if all conditions pass:

1. Q9 MAE `< 9.000000`;
2. question MAE across all 70 student-question pairs `< 2.557143`;
3. severe-error count `<= 16`;
4. zero regressions on Q1-Q4;
5. `resolved` cases outnumber `regression` cases versus v3.2.

If the gate fails, retain the negative result and candidate snapshot, but
restore the active skill to v3.2. Do not edit the prompt and rerun after seeing
this output; that would tune to run noise.

Final artifacts / 最终产物：

- `public-summary.json`: privacy-safe all-70 score metrics
- `diagnosis-summary.json`: complete 31-case diagnosis aggregates
- `iteration-delta-v32-v33.json`: privacy-safe resolved/persistent/regression comparison
- `confidence-taxonomy-summary.json` and `CONFIDENCE-TAXONOMY.md`: confidence, flag, and mechanism audit
- `acceptance-decision.json`: machine-readable gate result
- `FAILURE-ANALYSIS.md`: fully bilingual interpretation and next-step recommendation
