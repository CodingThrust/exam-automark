# Zulip 结算：TODO1 有意义的负结果 / Settlement: Meaningful Negative Results

## 中文版

```text
Topic: [exam-automark] TODO1 - 有意义的负结果复盘

状态：
completed

目标：
解释为什么已经完成的评分实验没有改善它们目标中的准确率信号。排除普通的
命令、认证、依赖、路径和暂时性网络错误。

完成内容：
- 审计 SkillOpt R4，以及 DSAA3071 candidate-v3、v3.1-r2 和 v3.2 的
  development 序列。
- 从私有运行输出重新计算题目层面、severe-error、总分和误差抵消指标。
- 区分已验证的指标驱动因素、行为诊断假设和未解决原因。

证据：
- experiments/records/physics-skillopt-deepseek-r4-run/FAILURE-ANALYSIS.md
- experiments/records/weekly-todo-integration-2026-07/TODO1-MEANINGFUL-NEGATIVE-RESULTS.md
- experiments/records/weekly-todo-integration-2026-07/TODO1-MEANINGFUL-NEGATIVE-RESULTS.json

关键结果：
SkillOpt R4 错误合并了相反方向的误差，生成了过于严格的 candidate，因此
validation accuracy 下降，gate 正确拒绝了它。

DSAA3071 candidate-v3 相比 R1 同样降低了题目层面准确率。Candidate-v3.1-r2
只有在学生总分 MAE 上看起来更好，原因是题目多给分和少给分之间的抵消变强。

Candidate-v3.2 在题目层面有小幅真实改善，但总分误差减少的 40 分中，只有
4 分来自题目层面绝对误差降低；其余 36 分，即 90%，来自新增的学生内部误差
抵消。C32 还增加了一个 severe-error 题目对，其中 Q6 增加了 19 个绝对
误差分。

负结果原因：
- SkillOpt 在聚合 candidate 证据时丢失误差方向。
- Candidate-v3 过度应用 proof-locality、cap 和 wording requirement。
- Candidate-v3.1 的总分指标隐藏了相互抵消的题目层面误差。
- Candidate-v3.2 的全局规则在 Q6 多给分，对 Q8 的处理仍不一致。
- Rubric/prompt/skill 联合修改和单次运行使因果归因无法成立。

实际改善：
- 现在能区分真实的题目层面改善和总分误差抵消。
- 负结果筛选已排除没有实验意义的运行事故。
- Candidate acceptance requirement 现在包括 severe-error guardrail 和
  cancellation diagnostic。

对项目的帮助：
避免因为 aggregate 总分看起来更好，就接受一个逐题评分反而更不可靠的
candidate；也让 candidate-v3.3 聚焦 Q6/Q8，而不是再次宽泛改写。

限制 / 禁止表述：
- C32 只有 development 证据，不是最终或 held-out 改善。
- 没有官方逐题评分理由。
- 行为解释属于诊断假设，不是已验证的人工评分理由。
- 每个 condition 只有一次运行，不能隔离模型波动。

决策：
把 C3 和 C31-r2 结项为有信息价值的负结果/混合结果。C32 只保留为
development candidate。在受控 Q6/Q8 审计和重复匹配 development comparison
通过前，不冻结它，也不运行 held-out。

下一步：
对选中的 Q6/Q8/Q9 development 案例启动 TODO3 的最新模型缺陷审计，然后用
single-factor ablation 和 severe-error 不增加 gate 提出 candidate-v3.3 修改。
```

---

## English version

```text
Topic: [exam-automark] TODO1 - meaningful negative-result retrospective

Status:
completed

Goal:
Explain why completed grading experiments did not improve their intended
accuracy signal. Exclude ordinary command, authentication, dependency, path,
and transient network errors.

What was done:
- Audited SkillOpt R4 and the DSAA3071 candidate-v3, v3.1-r2, and v3.2
  development sequence.
- Recomputed question-level, severe-error, total-score, and error-cancellation
  metrics from the private run outputs.
- Separated verified metric drivers from behavioral hypotheses and unresolved
  causes.

Evidence:
- experiments/records/physics-skillopt-deepseek-r4-run/FAILURE-ANALYSIS.md
- experiments/records/weekly-todo-integration-2026-07/TODO1-MEANINGFUL-NEGATIVE-RESULTS.md
- experiments/records/weekly-todo-integration-2026-07/TODO1-MEANINGFUL-NEGATIVE-RESULTS.json

Key result:
SkillOpt R4 generated an over-strict candidate from incorrectly merged
opposite-direction errors, so validation accuracy worsened and the gate
rejected it.

DSAA3071 candidate-v3 also worsened question-level accuracy versus R1.
Candidate-v3.1-r2 appeared better on student total MAE only because question
over-scores and under-scores cancelled more strongly.

Candidate-v3.2 is a small real question-level improvement, but only 4 of its 40
reduced total-error points came from lower question-level absolute error. The
other 36 points, or 90%, came from additional within-student cancellation.
C32 also added one severe-error pair, with Q6 contributing 19 additional
absolute-error points.

Failure causes:
- SkillOpt lost error direction while aggregating candidate evidence.
- Candidate-v3 over-applied proof-locality, cap, and wording requirements.
- Candidate-v3.1's total metric hid compensating item-level errors.
- Candidate-v3.2's global rules over-credited Q6 and did not solve Q8
  consistently.
- Joint rubric/prompt/skill changes and single runs prevent clean causal
  attribution.

What improved:
- We now distinguish true item-level improvement from total-score error
  cancellation.
- Negative-result selection excludes meaningless operational incidents.
- Candidate acceptance requirements now include a severe-error guardrail and a
  cancellation diagnostic.

How this helps the project:
It prevents a candidate from being accepted because aggregate totals look
better while individual question grading becomes less reliable. It also gives
candidate-v3.3 a focused Q6/Q8 target instead of another broad rewrite.

Limitations / prohibited claims:
- C32 has development evidence only and is not a final or held-out improvement.
- Official per-question rationales are unavailable.
- Behavioral explanations are diagnostic hypotheses, not verified human
  scoring rationales.
- One run per condition does not isolate model variation.

Decision:
Close C3 and C31-r2 as informative negative/mixed results. Keep C32 as a
development candidate only. Do not freeze it or run held-out until a controlled
Q6/Q8 audit and repeated matched development comparison pass.

Next action:
Start TODO3's latest-model defect audit on selected Q6/Q8/Q9 development cases,
then propose candidate-v3.3 changes with one-factor ablations and a
non-increasing severe-error gate.
```
