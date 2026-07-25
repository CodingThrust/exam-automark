# Physics SkillOpt DeepSeek R4 失败分析 / Failure Analysis

Date: 2026-07-25

## 中文版

### 直接结论

R4 candidate 未通过，是因为它的验证集得分低于 initial skill：

| 验证指标 | Initial skill | Candidate | 变化 |
| --- | ---: | ---: | ---: |
| Hard：整名学生所有小题完全一致 | 1 / 4 (0.2500) | 0 / 4 (0.0000) | -0.2500 |
| Soft：单个小题分数完全一致 | 38 / 48 (0.7917) | 23 / 48 (0.4792) | -0.3125 |

配置的 gate 指标是 `hard`。只有 candidate 的 gate 得分严格高于当前
skill，SkillOpt 才会接受它。Candidate 得分为 `0.0000`，低于当前 skill
的 `0.2500`，因此 gate 保留 initial skill。

根据本次运行中观察到的结果，这个拒绝决定是正确的。即使把 gate 改成
`soft`，candidate 也不会通过，因为它的 soft 得分同样下降了。

### Candidate 改了什么

Candidate 增加了一条全局规则：

> 当 rubric 的某项标准针对一个具体步骤给分时，只有学生明确写出该步骤
> 才能给分。不能只根据正确的最终答案推断学生完成了这个步骤。

这条规则来自两个训练集中的非完全正确案例，记录的
`support_count = 2`。

问题在于，这两个训练误差的方向相反：

| 匿名训练案例 | Gold | Initial prediction | 误差方向 |
| --- | ---: | ---: | --- |
| 半球扩散计算 | 3 | 2 | 少给 1 分 |
| 大粒子路径推理 | 2 | 3 | 多给 1 分 |

第一个答案给出了正确的面积关系和最终数值。虽然简化后的转录没有明确写出
每一步单位换算，但人工 gold label 仍给了满分。第二个答案写出了正确路径，
也说明重力增长得更快，却没有写出 rubric 要求的 `R^3` 与 `R^2` 的比较。

Optimizer 的失败摘要把两个案例都归因于“没有明确步骤却给了分”。这个诊断
适用于多给分的案例，却不适用于少给分的案例。一条更严格的全局规则不可能
同时修正两个相反方向的误差。

### Candidate 的问题在哪里

#### 1. 聚合证据时丢失了误差方向

Optimizer 把一个少给分和一个多给分案例归入同一个原因，并把它们作为一条
单方向修改的两个支持案例。因此，`support_count = 2` 夸大了这条修改真正
获得的支持。

Candidate 生成阶段至少需要保留：

- prediction 减去 gold 的分差；
- 受影响的 rubric criterion；
- 误差属于多给分还是少给分；
- 缺失证据来自学生作答，还是来自转录过程。

如果不同案例需要相反方向的修正，就不能将它们合并为同一项修改。

#### 2. 把局部修正过度推广成了全局规则

新规则是绝对化的，并被应用于所有 rubric criterion。它与 seed skill 中
更平衡的政策冲突：

- 最终答案正确且可见方法大体一致时，应给满分，除非 rubric 明确要求某个
  缺失步骤；
- 对缺少依据的答案，可以给结果分，但不能给未展示的过程分。

Candidate 丢失了这一区分。在双方都可解析的配对验证案例中，它改变了四道题
的分数；所有变化都是降分，而且每次变化都扩大了误差：

| 配对验证证据 | Initial skill | Candidate |
| --- | ---: | ---: |
| 小题分数完全一致 | 26 / 36 | 23 / 36 |
| 总绝对分数误差 | 8.50 | 11.75 |
| 分数发生变化的小题 | - | 4 道，全部降分 |

这个模式符合“系统性惩罚过重”的表现。由于 initial 和 candidate 的结果来自
两次独立模型调用，不能把差异完全归因于新增的那一句规则；若要得出因果结论，
还需要重复的配对调用。不过，这仍然是 candidate 在本次验证运行中没有泛化
成功的直接证据。

#### 3. 输出可靠性有所改善，但尚未解决

R4 生成了 48 条 item-level 结果，其中 47 条包含可解析的 prediction。一次
candidate validation 调用耗尽了 12,000 个 completion tokens，却返回空响应，
因此被记为：

- hard：`0`；
- soft：`0`；
- 总绝对误差哨兵值：`999`。

该失败样本恰好是 initial validation 中唯一 hard 完全正确的学生，因此也使
hard 得分从 `0.25` 降到 `0.00`。这部分属于技术可靠性问题，应与 candidate
的评分政策问题区分开。

即使排除这个失败样本，只比较两侧都有 prediction 的三个学生，candidate
仍更差：小题完全一致数从 26 降到 23，总绝对误差从 8.50 上升到 11.75。

#### 4. 验证设计过粗，噪声也过大

Hard accuracy 要求同一名学生的 12 道题分数全部完全一致。验证集只有四名
学生，因此分数每次最少跳动 `0.25`。这个指标太粗，难以识别较小的评分改进。

Baseline 和 candidate 都只评估了一次。记录的运行配置没有固定目标模型的
sampling temperature，也没有采用重复的配对评估。因此，实验把 skill 的
影响与目标模型的运行间波动混在了一起。

### 为什么 held-out hard 得分也下降了

Candidate 已被拒绝，从未成为 current skill 或 best skill。Baseline held-out
和 final held-out 都使用同一个 initial skill；18 个 held-out 样本的 system
prompt 和 user prompt 也完全相同。

尽管 prompt 相同：

- 两次调用中，只有 9 / 18 个完整分数向量完全一致；
- 216 个单题 prediction 中有 14 个发生变化；
- hard 整名学生完全一致率从 5 / 18 变为 4 / 18；
- soft 小题完全一致率从 181 / 216 变为 182 / 216；
- 总绝对分数误差从 37.75 改善到 35.25。

因此，报告中的 held-out hard delta `-0.0556` 不是 candidate skill 的效果，
而是同一 initial skill 重复评估时产生的差异。这也说明，只使用一个 hard
指标并不能提供稳定的优化信号。

### 根因分类

| 层级 | 观察到的原因 | 证据强度 |
| --- | --- | --- |
| Candidate generation | 把相反方向的误差合并成了一条更严格的修改 | artifact 直接证据 |
| Grading policy | 将“必须明确写出步骤”过度推广，丢失过程分与结果分的平衡 | 规则直接对比；验证模式支持 |
| Data/transcription | 简化转录可能遗漏或损坏影响人工 gold score 的证据 | development record 中观察到；未隔离精确贡献 |
| Target reliability | 一次 candidate validation 耗尽 12,000 tokens 后返回空响应 | artifact 直接证据 |
| Metric design | 四名学生的 hard gate 只能以 0.25 为单位变化 | 指标的确定性属性 |
| Evaluation design | 单次独立调用无法隔离 candidate 的效果 | protocol 直接证据 |

### R4 实际改善了什么

R4 仍然提供了有价值的工程结果：

- 完成了完整的 SkillOpt 流程；
- 48 条 target 记录中有 47 条可解析，相比 R3 的输出可靠性明显提高；
- validation gate 阻止了有害 candidate 成为选中 skill；
- 暴露了 error aggregation、metric choice 和 repeatability 的具体缺陷。

但它没有提高评分准确率，不能被描述为准确率改进。

### 改进选项

#### 选项 A：把 R4 结项为负结果

记录上述经验，不再重复运行相同配置，把精力转移到优先级更高的主线评分和
多模态比较。

- 收益：无需额外模型成本；科研表述诚实。
- 成本：无法得到正向的 SkillOpt 结果。
- 风险：优化管线中的弱点仍未解决。

#### 选项 B：在 R5 前修复测量和 candidate gate

如果 SkillOpt 仍是项目必需方向，推荐这个选项。

在下一次付费运行前实现以下离线检查：

1. 在 reflection input 中保留误差方向和 rubric criterion；
2. 当支持案例要求相反方向的修改时，拒绝 proposed edit；
3. 增加针对 seed skill 的 policy-conflict lint；
4. 使用重复的配对验证调用，并报告均值和波动；
5. 主要以 soft 小题准确率作为 gate，hard accuracy 和总绝对误差作为
   guardrail；
6. 把解析失败作为独立的可靠性 gate，在计算准确率前进行 retry/repair；
7. 制定全局规则前，要求同一误差方向至少有两个支持案例。

- 收益：直接处理 R4 中观察到的每一个失败层级。
- 成本：需要中等程度的工程工作和更多评估调用。
- 风险：四名学生的验证集可能仍然太小。

#### 选项 C：运行窄范围的 criterion-level proof of concept

选择一到两个高分歧 rubric criterion，在 criterion 层级构造更大的开发集，
只优化相应的决策规则，之后再回到整份试卷评分。

- 收益：反馈更密集、成本更低，也更容易获得有效的 SkillOpt 信号。
- 成本：结果只适用于所选择的 criteria。
- 风险：正向结果未必能推广到整份试卷评分。

### 建议

不要原样重跑 R4。现在应把它结项为负结果。如果项目仍要求得到正向 SkillOpt
实验，就把选项 B 的保护措施与选项 C 的窄范围结合，并确保 sealed held-out
set 不参与 candidate selection。

### 证据

公开记录：

- `RESULT-SUMMARY.md`
- `RUN-PROTOCOL.md`
- `../physics-skillopt-deepseek-training-run/R3-RUN-SUMMARY.md`
- `../physics-skillopt-target-reliability/RESULT-SUMMARY.md`

本分析使用的私有、已被 Git 忽略的运行 artifact：

- `summary.json`
- `history.json`
- `steps/step_0001/step_record.json`
- `steps/step_0001/trajectory_digest.json`
- `steps/step_0001/merged_patch.json`
- 配对的 item-level `result.json` 文件

本公开报告不包含原始学生转录、学生标识或 provider response。

---

## English version

### Direct answer

The R4 candidate was rejected because its validation score was worse than the
initial skill:

| Validation metric | Initial skill | Candidate | Change |
| --- | ---: | ---: | ---: |
| Hard exact-student accuracy | 1 / 4 (0.2500) | 0 / 4 (0.0000) | -0.2500 |
| Soft exact-subquestion accuracy | 38 / 48 (0.7917) | 23 / 48 (0.4792) | -0.3125 |

The configured gate metric was `hard`. SkillOpt accepts a candidate only when
its gate score is strictly greater than the current score. The candidate scored
`0.0000`, below the current `0.2500`, so the gate kept the initial skill.

This was the correct accept/reject decision for the observed run. Changing the
gate to `soft` would not have saved this candidate because its soft score also
decreased.

### What the candidate changed

The candidate appended one global rule:

> When a rubric criterion awards points for a specific step, award that point
> only if the step is explicitly shown. Do not infer the step from a correct
> final answer alone.

The rule was generated from two non-exact training cases and was recorded with
`support_count = 2`.

The problem is that the two training errors had opposite directions:

| Anonymous training case | Gold | Initial prediction | Error direction |
| --- | ---: | ---: | --- |
| Hemispherical-spreading calculation | 3 | 2 | under-scored by 1 |
| Large-particle path reasoning | 2 | 3 | over-scored by 1 |

The first answer showed the correct area relation and final value. Its gold
label awarded full credit even though the compact transcript did not explicitly
show every conversion step. The second answer named the correct path and said
gravity increases faster, but did not state the rubric's required
`R^3`-versus-`R^2` comparison.

The optimizer's failure summary treated both cases as the same
"missing explicit step but points were awarded" error. That diagnosis fits the
over-scored case, but it does not fit the under-scored case. A stricter global
rule cannot correct both directions.

### What was bad about the candidate

#### 1. Its evidence aggregation lost the error direction

The optimizer grouped an under-score and an over-score under one cause, then
reported two supporting cases for a one-directional edit. `support_count = 2`
therefore overstated the real support for the edit.

The candidate-generation stage needs to preserve at least:

- predicted minus gold score;
- rubric criterion affected;
- whether the error was an over-score or under-score;
- whether missing evidence came from the student or from transcription.

Edits should not merge cases whose required corrections point in opposite
directions.

#### 2. It over-generalized one local correction

The new rule was absolute and applied to every rubric criterion. It conflicted
with the seed skill's more balanced policy:

- award full credit when the final answer is correct and the visible method is
  broadly consistent, unless the rubric explicitly requires a missing step;
- award result credit but not omitted setup credit for unsupported answers.

The candidate removed that distinction. In the paired, parseable validation
cases, it changed four question scores; every change reduced a score and every
change increased error:

| Paired validation evidence | Initial skill | Candidate |
| --- | ---: | ---: |
| Exact subquestion scores | 26 / 36 | 23 / 36 |
| Total absolute score error | 8.50 | 11.75 |
| Changed question scores | - | 4, all reductions |

This pattern is consistent with systematic over-penalization. Because the
initial and candidate results came from separate model calls, it is not a clean
causal estimate of the appended sentence by itself; repeated paired calls would
be required for that claim. It is nevertheless direct evidence that the
candidate did not generalize on this validation run.

#### 3. Output reliability was improved, not solved

R4 produced 48 item-level result records. Forty-seven contained parseable
predictions. One candidate-validation call consumed the full 12,000 completion
tokens and returned an empty response, which was scored as:

- hard: `0`;
- soft: `0`;
- total absolute error sentinel: `999`.

That failed item was the only exact student under the initial validation run,
so it also made the hard score fall from `0.25` to `0.00`. This is partly a
technical reliability failure, separate from the candidate's scoring policy.

Even after excluding that failed item and comparing only the three cases with
predictions on both sides, the candidate was still worse: exact subquestions
fell from 26 to 23 and absolute error rose from 8.50 to 11.75.

#### 4. The validation design was too coarse and too noisy

Hard accuracy requires all 12 question scores for one student to match exactly.
With four validation students, the score moves only in increments of `0.25`.
This is too coarse for detecting small grading improvements.

The baseline and candidate were each evaluated once. The target sampling
temperature was not pinned in the recorded run configuration, and no repeated
paired evaluation was used. The experiment therefore mixed skill effects with
run-to-run target-model variation.

### Why the held-out hard score also decreased

The candidate was rejected and never became the current or best skill. Both
the baseline held-out evaluation and the final held-out evaluation used the
same initial skill, with identical system and user prompts for all 18 held-out
items.

Despite identical prompts:

- only 9 / 18 complete score vectors were identical across the two calls;
- 14 / 216 individual question predictions changed;
- hard exact-student accuracy changed from 5 / 18 to 4 / 18;
- soft exact-subquestion accuracy changed from 181 / 216 to 182 / 216;
- total absolute score error improved from 37.75 to 35.25.

Therefore the reported held-out hard delta of `-0.0556` is not a candidate-skill
effect. It is a repeat-evaluation difference for the same initial skill. It
also demonstrates why one hard metric alone is not a stable optimization
signal here.

### Root-cause classification

| Layer | Observed cause | Evidence strength |
| --- | --- | --- |
| Candidate generation | Opposite-direction errors were merged into one stricter edit | Direct artifact evidence |
| Grading policy | The edit over-generalized "explicit step" and lost balanced process/result credit | Direct rule comparison; validation pattern supports it |
| Data/transcription | Compact transcripts can omit or corrupt evidence that affected human gold scoring | Observed in development records; exact contribution not isolated |
| Target reliability | One empty 12,000-token candidate validation output | Direct artifact evidence |
| Metric design | Four-student hard gate changes in 0.25 increments | Deterministic metric property |
| Evaluation design | Single independent calls did not isolate candidate effects | Direct protocol evidence |

### What R4 did improve

R4 was still useful as an engineering result:

- it completed the full SkillOpt loop;
- 47 / 48 target records were parseable, a large reliability improvement over
  R3;
- the validation gate prevented a harmful candidate from becoming the selected
  skill;
- it exposed concrete weaknesses in error aggregation, metric choice, and
  repeatability.

It did not improve grading accuracy and must not be reported as doing so.

### Improvement options

#### Option A: close R4 as a negative result

Record the lessons above, do not rerun the same configuration, and move effort
to the higher-priority mainline grading and multimodal comparison work.

- Benefit: no further model cost; scientifically honest.
- Cost: does not produce a positive SkillOpt result.
- Risk: leaves the optimization pipeline weaknesses unresolved.

#### Option B: repair the measurement and candidate gates before R5

Recommended if SkillOpt remains a required project direction.

Implement these offline checks before another paid run:

1. preserve error direction and rubric criterion in reflection inputs;
2. reject a proposed edit when its supporting cases require opposite changes;
3. add a policy-conflict lint against the seed skill;
4. use paired repeated validation calls and report mean plus variation;
5. gate primarily on soft subquestion accuracy, with hard accuracy and total
   absolute error as guardrails;
6. make parse failure a separate reliability gate and retry/repair it before
   accuracy scoring;
7. require more than one supporting example per direction before making a
   global rule.

- Benefit: directly addresses every observed R4 failure layer.
- Cost: moderate engineering and additional evaluation calls.
- Risk: the four-student validation set may remain too small.

#### Option C: run a narrow criterion-level proof of concept

Choose one or two high-disagreement rubric criteria, construct a larger
development set at that criterion level, and optimize only the corresponding
decision rule before returning to whole-paper grading.

- Benefit: cheaper, denser feedback and a more attainable SkillOpt signal.
- Cost: result applies only to the selected criteria.
- Risk: a positive result may not generalize to full-paper grading.

### Recommendation

Do not rerun R4 unchanged. Close it as a negative result now. If a positive
SkillOpt experiment is still required, combine Option B's safeguards with
Option C's narrow scope, and keep the sealed held-out set out of candidate
selection.

### Evidence

Public records:

- `RESULT-SUMMARY.md`
- `RUN-PROTOCOL.md`
- `../physics-skillopt-deepseek-training-run/R3-RUN-SUMMARY.md`
- `../physics-skillopt-target-reliability/RESULT-SUMMARY.md`

Private, ignored run artifacts used for this analysis:

- `summary.json`
- `history.json`
- `steps/step_0001/step_record.json`
- `steps/step_0001/trajectory_digest.json`
- `steps/step_0001/merged_patch.json`
- paired item-level `result.json` files

No raw student transcript, student identifier, or provider response is included
in this public report.
