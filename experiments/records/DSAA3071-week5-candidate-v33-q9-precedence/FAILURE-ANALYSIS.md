# Candidate-v3.3 未通过分析 / Candidate-v3.3 Failure Analysis

## 2026-08-02 人工裁决更正 / Human-adjudication correction

v3.3 的拒绝结论保持不变：它确实未通过预注册的全局严重错误门槛。但后来人工
复核表明，进入历史回归套件的四个 Q9 案例均不能确认为模型错误。因此下文关于
Q9 机制错误数量和“高客观性模型错误”的逐例归因是历史 provisional 诊断，
不能继续作为硬门禁或新一轮调参目标。

The v3.3 rejection remains valid because it failed the pre-registered global
severe-error gate. Later human review, however, did not confirm any of the four
Q9 cases selected for the historical regression suite as model errors.
Case-level claims below about Q9 mechanism failures or highly objective model
errors are therefore historical provisional diagnoses, not active gates or
tuning targets.

## 中文版

### 结论

Candidate-v3.3 **没有通过预注册安全门，因此不替换 active v3.2**。这不是运行报错：
7/7 名开发集学生均通过 schema validation，技术失败为 0。失败的有意义原因是
严重评分差异从 `16` 增至 `17`，违反了“不得增加”的硬门槛。

与此同时，这次实验并非毫无改善：

| 指标 | v3.2 | v3.3 | 变化 | 门槛结果 |
|---|---:|---:|---:|---|
| Q9 MAE | 9.000000 | 7.000000 | -2.000000 | 通过 |
| 全体 question MAE | 2.557143 | 2.185714 | -0.371429 | 通过 |
| Student-total MAE | 14.428571 | 10.428571 | -4.000000 | 仅描述 |
| Exact agreement | 0.528571 | 0.557143 | +0.028572 | 仅描述 |
| 错误对数 | 33 | 31 | -2 | 仅描述 |
| 严重错误数 | 16 | 17 | +1 | **失败** |
| Q1-Q4 错误数 | 0 | 0 | 0 | 通过 |
| Resolved / regression | — | 3 / 1 | 净 +2 | 通过 |

### 为什么没有通过

本次只允许修改 `rule_precedence_or_gate_error`，目标是让题目专属
`full_credit_rule` 在采用整体充分性时优先于示例 evidence-family 加和，并禁止
仅因答案简短而降档。Q9 MAE 确实从 9 降到 7，但该机制没有被稳定执行：
当前 31 个错误中仍有 4 个规则优先级错误，其中 3 个是严重错误，而且全部没有
flag。模型仍会在某些答案上机械做 element sum，没有真正执行 full-credit
override。

严重错误净增 1 的来源不是 Q9 严重错误数增加，而是：

- Q5 严重错误 `1→2`；
- Q6 严重错误 `2→3`；
- Q10 严重错误 `1→0`；
- Q7、Q8、Q9 的严重错误数不变。

这说明单次生成存在跨题波动。虽然全体 MAE 和 Q9 改善，但不能把所有改善都因果
归功于新增规则，也不能忽视高影响错误尾部变差。一次运行、7 名开发集学生不足以
证明稳定提升。

### 错题增量告诉了我们什么

相对 v3.2：

- 3 个旧错题 resolved；
- 1 个新 regression，位于 Q7，分差为 2，不是严重错误；
- 12 个持续错误改善；
- 10 个持续错误不变；
- 8 个持续错误恶化。

逐案复核覆盖 31/31 个错误。按可执行性分层：

- 9 个高客观性模型错误可直接用于下一次 candidate；
- 11 个必须先由课程负责人裁决 rubric/gold 或官方风格；
- 2 个必须做 reviewed-transcript 与 direct-multimodal 配对；
- 9 个只适合作为分档锚点。

这比“把全部差异写进 prompt”更重要，因为它阻止我们把 Q6/Q8/Q10 的合同冲突
误当成模型学习目标。

### Confidence 与 flags 的不足

High confidence 仍有 14/49 个错误和 6 个严重错误。任意 flag 只抓到 6/17 个
严重错误；`medium/low OR any flag` 复核 22/70 对，也只抓到 12/17 个严重错误。
所以 confidence 和 flag 不能作为唯一发布门，典型错题回归仍然必要。

### 处置

1. Codex 与 Claude 的 active `grade-homework` skill 已恢复为 v3.2。
2. v3.3 prompt、skill hash、冻结门槛、run commit、输出、31 例错题册和增量全部保留。
3. 不根据本次输出修改 prompt 后重跑，避免对一次随机生成调参。
4. 不读取或运行 held-out/test 数据。

### 下一步建议

不要立刻做 v3.3-r2。先处理导师最关心的可解释典型错题：

1. 把 Q9 的 4 个规则优先级错误作为“full-credit override 未执行”的回归组；
2. 把 Q6 的 2 个 unsupported-credit 严重案例加入负向回归，防止整体宽松导致高估；
3. 请课程负责人裁决 Q6/Q8/Q10 的 11 个合同/风格案例；
4. 对 Q8 的 2 个表示歧义案例做 transcript 与 direct-multimodal 配对；
5. 只有在这些约束可机器检查后，再设计下一次 project-owned skill optimization loop。

### 限制

- 只有一次模型运行，不能分离 prompt 效果与生成波动。
- 只有 7 名开发集学生、70 个学生-题目对。
- Gold 没有逐题官方理由，合同冲突只能定位，不能由模型最终裁决。
- 本报告是开发集证据，不是测试集准确率结论。

## English Version

### Conclusion

Candidate-v3.3 **fails the pre-registered safety gate and does not replace
active v3.2**. This is not a runtime failure: all seven development students
pass schema validation and technical failures are zero. The meaningful failure
is that severe score discrepancies increase from `16` to `17`, violating the
hard non-increase gate.

The run still improves several descriptive metrics:

| Metric | v3.2 | v3.3 | Change | Gate result |
|---|---:|---:|---:|---|
| Q9 MAE | 9.000000 | 7.000000 | -2.000000 | Pass |
| All-pair question MAE | 2.557143 | 2.185714 | -0.371429 | Pass |
| Student-total MAE | 14.428571 | 10.428571 | -4.000000 | Descriptive |
| Exact agreement | 0.528571 | 0.557143 | +0.028572 | Descriptive |
| Error pairs | 33 | 31 | -2 | Descriptive |
| Severe errors | 16 | 17 | +1 | **Fail** |
| Q1-Q4 errors | 0 | 0 | 0 | Pass |
| Resolved / regression | — | 3 / 1 | Net +2 | Pass |

Four gates pass; the severe-error gate fails.

### Why it fails

The only permitted change targets `rule_precedence_or_gate_error`: a
question-specific holistic `full_credit_rule` should override illustrative
evidence-family addition, and brevity alone should not downgrade evidence.
Q9 MAE improves, but execution is not stable. Four rule-precedence errors remain
among the 31 current errors, three are severe, and none has a flag. The model
still mechanically sums elements in some answers instead of executing the
full-credit override.

The net severe-error increase does not come from more severe Q9 errors. Severe
counts change from one to two on Q5, two to three on Q6, and one to zero on Q10;
Q7, Q8, and Q9 are unchanged. This cross-question movement shows single-run
generation variance. Better aggregate and Q9 MAE cannot all be causally
attributed to the new rule, and the worse high-impact tail cannot be ignored.

### What the error-book delta teaches us

Versus v3.2, three errors resolve, one non-severe Q7 regression appears, twelve
persistent errors improve, ten are unchanged, and eight worsen. Review covers
all 31 current errors.

The actionable partition is nine high-objectivity model errors for a future
candidate, eleven cases requiring course-owner rubric/gold or official-style
adjudication, two cases requiring paired transcript/direct-multimodal review,
and nine calibration anchors. This prevents Q6/Q8/Q10 contract conflicts from
being injected blindly into the prompt.

### Confidence and flag limits

High confidence still contains 14/49 errors and six severe errors. Any flag
captures only 6/17 severe errors. Reviewing medium/low confidence or any flag
inspects 22/70 pairs and captures only 12/17 severe errors. Confidence and flags
cannot be the sole release gate; typical-error regression remains necessary.

### Disposition

1. Restore both Codex and Claude active `grade-homework` skills to v3.2.
2. Retain the v3.3 prompt, skill hash, frozen gate, run commit, outputs,
   complete 31-case error book, and iteration delta.
3. Do not edit the prompt and rerun after observing this result.
4. Do not read or run held-out/test data.

### Recommended next step

Do not immediately create v3.3-r2. First turn the four Q9 precedence failures
into a full-credit-override regression group, add the two severe Q6
unsupported-credit cases as negative constraints, obtain course-owner
adjudication for the eleven Q6/Q8/Q10 contract/style cases, and run paired
transcript/direct-multimodal review on the two Q8 representation cases. Only
then should the project design the next machine-checkable skill-optimization
loop.

### Limits

- One model run cannot separate prompt effect from generation variance.
- The development set has seven students and 70 student-question pairs.
- Gold has no official per-question rationales, so contract conflicts can be
  located but not finally adjudicated by the model.
- This is development evidence, not held-out accuracy.
