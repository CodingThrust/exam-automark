# TODO1 有意义的负结果复盘 / Meaningful Negative-Result Retrospective

Date: 2026-07-25

## 中文版

### 技术摘要

TODO1 不应该罗列每一次命令运行失败，而应该解释那些已经完成、且其结果会
改变项目决策的实验。

两条实验线符合这一标准：

1. Physics SkillOpt R4 成功生成了 candidate，但 candidate 使验证准确率下降，
   因而被正确拒绝。
2. DSAA3071 candidate-v3 和 candidate-v3.1 都生成了有效输出，但前者没有带来
   改善，后者的表面改善来自题目层面的多给分和少给分在学生总分中相互抵消。
   Candidate-v3.2 在 aggregate 层面有小幅真实改善，但它的总分误差改善仍有
   90% 来自误差抵消，而且 severe-error 数量增加。

普通的命令、认证、依赖、路径及暂时性网络错误不纳入本报告。它们应该进入
runbook，而不是实验复盘。

### 哪些结果属于 TODO1

| 结果 | 是否纳入 | 原因 |
| --- | --- | --- |
| SkillOpt R4 candidate rejection | 是 | 优化实验已完成；candidate 准确率下降 |
| DSAA3071 C3 vs R1 | 是 | 受控开发集比较已完成；candidate 表现变差 |
| DSAA3071 C31-r2 vs R1 | 是 | 总分改善掩盖了更差的题目层面准确率 |
| DSAA3071 C32 vs R1 | 作为仍有未解决权衡的修正结果 | aggregate 小幅改善，但 severe error 和 cancellation 仍存在 |
| 一次性的 CLI、认证、路径、依赖、provider 或网络错误 | 否 | 属于运行事故，不是评分质量证据 |
| Physics candidate-v2 | 不作为负结果纳入 | held-out 有改善；severe-error rate 未变属于错误分类 TODO |
| Kimi/Claude 导师实验结果 | 暂不纳入 | 外部真实结果尚未返回 |
| Autoresearch MVP | 暂不纳入 | 真实循环尚未完成，没有可解释的完整负实验 |

### Candidate-v3 在目标指标上反而变差

权威比较使用 DSAA3071 development set 的 7 名学生、每名学生 10 道题，共
70 个学生-题目分数对。

| 指标 | R1 baseline | C3 candidate-v3 | C3 减 R1 |
| --- | ---: | ---: | ---: |
| 题目 MAE | 2.614 | 2.814 | +0.200，变差 |
| 分数完全一致的题目对 | 36 / 70 | 35 / 70 | -1 |
| Severe-error 题目对 | 15 / 70 | 17 / 70 | +2，变差 |
| 题目层面绝对误差分数 | 183 | 197 | +14，变差 |
| 学生总分绝对误差分数 | 141 | 141 | 不变 |

按题目分解可以解释净增加的 14 个误差分：

| 题目 | C3 减 R1 的绝对误差分数 | 解释 |
| --- | ---: | --- |
| Q5 | +7 | 变差 |
| Q6 | +1 | 略微变差 |
| Q7 | +14 | 最大退步 |
| Q8 | -6 | 改善 |
| Q9 | 0 | aggregate 无变化 |
| Q10 | -2 | 改善 |

仅 Q7 就增加了 14 个绝对误差分。Q8 和 Q10 的改善抵消了 Q5 和 Q6 的新增
误差，最后得到同样为 14 分的净退步。

现有案例复核支持、但不能证明三个行为层面的解释：

- candidate-v3 有时会因为局部证明瑕疵，抹去本来正确的整体构造方向所得分；
- material-error cap 的触发范围过宽；
- required evidence label 有时被当作必须逐字出现的关键词，未接受语义等价表达。

这些只能称为诊断假设，因为 gold data 有官方分数，却没有官方评分理由。

### Candidate-v3.1 的总分改善来自误差抵消

如果只看学生总分 MAE，C31-r2 似乎有所改善：

| 指标 | R1 baseline | C31-r2 | 变化 |
| --- | ---: | ---: | ---: |
| 题目 MAE | 2.614 | 2.929 | +0.314，变差 |
| 分数完全一致的题目对 | 36 / 70 | 37 / 70 | +1 |
| Severe-error 题目对 | 15 / 70 | 18 / 70 | +3，变差 |
| 题目层面绝对误差分数 | 183 | 205 | +22，变差 |
| 学生总分绝对误差分数 | 141 | 129 | -12，改善 |
| 学生内部误差抵消差值 | 42 | 76 | +34 |

恒等关系是：

```text
学生总分绝对误差
= 题目层面绝对误差 - 学生内部误差抵消
```

C31-r2 增加了 22 个题目层面误差分，同时增加了 34 个多给分/少给分相互
抵消的分数。因此，最后 12 分的总分“改善”不能证明逐题评分变得更好。

主要观察到的驱动因素是 Q7 的证明给分不稳定和 Q9 的系统性少给分。
Open-ended adequacy 规则没能克服严格的逐项满分要求。

### Candidate-v3.2 在题目层面只有小幅改善

C32 不是失败实验。它是这个 development 序列中第一个同时降低题目 MAE 和
总分 MAE 的 candidate。但是，两种改善的幅度和来源差异很大：

| 指标 | R1 baseline | C32 | 变化 |
| --- | ---: | ---: | ---: |
| 题目 MAE | 2.614 | 2.557 | -0.057，改善 |
| 分数完全一致的题目对 | 36 / 70 | 37 / 70 | +1 |
| Severe-error 题目对 | 15 / 70 | 16 / 70 | +1，变差 |
| 题目层面绝对误差分数 | 183 | 179 | -4，改善 |
| 学生总分绝对误差分数 | 141 | 101 | -40，改善 |
| 学生内部误差抵消差值 | 42 | 78 | +36 |

总分误差减少了 40 分，其中只有 4 分来自题目层面绝对误差降低。其余 36 分，
即 90%，来自更强的学生内部误差抵消。

这不会抹去真实存在的 4 分题目层面改善，但它意味着总分 MAE 严重夸大了改善
的强度。

### Q6 抵消了 C32 的大部分收益

下表中负值表示改善，正值表示退步。

| 题目 | C32 减 R1 的绝对误差分数 | Severe-error 题目对变化 |
| --- | ---: | ---: |
| Q5 | -15 | -2 |
| Q6 | +19 | +2 |
| Q7 | 0 | 0 |
| Q8 | -1 | +1 |
| Q9 | -5 | 0 |
| Q10 | -2 | 0 |

最大改善来自 Q5，但 Q5 的 rubric 在 v1 和 v2 间没有变化。最大退步来自 Q6，
而 Q6 的 rubric 同样没有变化。定向修改的 rubric 是 Q7-Q9。

因此，Q5/Q6 的变化不能归因于针对 Q7-Q9 的 rubric calibration。它可能来自
全局 candidate prompt/skill、改变后的顶层评分政策、目标模型波动，或这些
因素的组合。

配对案例复核提供了三个不暴露学生身份的例子：

- Q6 官方分 `8`：R1 给 `9`，而 C32 给 `20`，因为 C32 从 tree、BFS 和
  acceptance state 推断所有关键 simulation element 都已展示；
- Q8 官方分 `9`：R1 给 `8`，而 C32 应用 invalid-extra-output cap，把分数
  降到 `5`；
- Q9 官方分 `25`：R1 给 `22`，而 C32 给 `12`，原因是它认为有效证据过于
  简短，尽管设计中的 official-style-adequacy 规则本应允许这种答案。

这些案例说明，全局规则的应用还不够一致，不能把 C32 冻结为最终 skill。

### 范围、来源和指标验证

- 总体：7 名匿名 DSAA3071 Week 5 development 学生。
- 粒度：70 个学生-题目对和 7 个学生总分。
- Gold 来源：官方逐题分数。
- 比较条件：R1、C3、C31-r2 和 C32。
- 从被 Git 忽略的本地输出重新计算后，R1、C3、C31-r2 和 C32 的指标与已
  commit 的记录在小数点后六位完全一致。
- C32 同时改变 rubric、prompt 和 skill；这是 package comparison，不是
  single-factor ablation。
- Rubric v2 修改 Q7、Q8、Q9 和顶层评分政策。Q5、Q6、Q10 的题目 rubric
  未改变。

### 已验证、较可能和未解决的结论

#### 已验证

- 与 R1 相比，C3 的题目 MAE、exact agreement 和 severe-error rate 都变差。
- C31-r2 的总分改善来自更多误差抵消，同时题目层面误差变差。
- C32 的题目层面改善只有 4 个误差分，增加了 1 个 severe error，并且总分
  改善的 90% 来自误差抵消。
- C32 下 Q6 增加了 19 个绝对误差分。

#### 较可能但尚无因果证明

- Candidate-v3 的 proof 和 cap 规则相对于观察到的官方评分方式过于激进。
- C32 的全局 open-ended-adequacy 和 semantic-equivalence 规则可能把相关
  术语误当作关系已经得到证明，从而在 Q6 多给分。
- Q8 invalid-output cap 对某些有官方分数的答案过于粗暴。

#### 未解决

- 没有官方逐题评分理由，无法确认每个分数背后教师的确切判断。
- 每个 condition 只运行一次，记录的 temperature 为 `null`，未测量目标模型
  波动。
- C32 没有 held-out 证据。

### Candidate-v3.3 前建议的项目改进

1. 把题目层面 MAE 和 exact agreement 作为主要 acceptance metrics，把总分
   MAE 作为 guardrail，而不是主要目标。
2. 每次评分比较都增加 cancellation diagnostic：题目层面绝对误差、学生总分
   绝对误差以及两者差值。
3. 接受 candidate 前，要求 severe-error 数量不增加。
4. 在合并测试前，分别用 development arm 隔离 rubric、prompt 和 skill 的
   修改。
5. 对 Q6，区分“提到一个术语”和“证明一个必要关系”。不能仅根据 tree/BFS
   字样推断 branch addressing 或 accept-if-any 行为。
6. 对 Q8，根据已复核的官方案例校准 invalid-output deduction，而不是从单一
   文本信号应用宽泛 cap。
7. 修改下一个 candidate 前，让最新模型作为 defect critic，检查最大的
   Q6/Q8/Q9 分歧。
8. 进入 held-out 前重复匹配的 development comparison，以测量运行间波动。

### 决策

把 candidate-v3 和 C31-r2 结项为有信息价值的负结果/混合结果。C32 只保留为
development candidate，不作为冻结后的最终 skill。下一项有价值的行动是执行
受控的 Q6/Q8 缺陷审计并设计 candidate-v3.3，而不是再次进行宽泛 prompt 改写。

### 后续问题

- 能否为选中的 Q6/Q8/Q9 分歧取得官方评分理由或教师复核？
- C32 的 4 分题目层面改善能否在重复匹配运行中保持？
- 导致 Q6 多给分的具体因素是什么：semantic equivalence、open-ended
  adequacy、official-style adequacy，还是模型波动？

---

## English version

### Technical summary

TODO1 should not catalogue every failed command. It should explain completed
experiments whose result changes a project decision.

Two experiment lines meet that standard:

1. Physics SkillOpt R4 produced a candidate, but the candidate made validation
   accuracy worse and was correctly rejected.
2. DSAA3071 candidate-v3 and candidate-v3.1 produced valid outputs, but their
   apparent gains were absent or driven by question-level errors cancelling in
   the student total. Candidate-v3.2 is a small real aggregate improvement, but
   its large total-score gain is still 90% error cancellation and it increases
   the severe-error count.

Ordinary command, authentication, dependency, path, and transient network
errors are excluded. They belong in runbooks, not an experiment retrospective.

### Which results belong in TODO1

| Result | Include? | Reason |
| --- | --- | --- |
| SkillOpt R4 candidate rejection | Yes | Completed optimization result; candidate accuracy worsened |
| DSAA3071 C3 versus R1 | Yes | Completed controlled development comparison; candidate worsened |
| DSAA3071 C31-r2 versus R1 | Yes | Total-score improvement hid worse question-level accuracy |
| DSAA3071 C32 versus R1 | As remediation with unresolved tradeoffs | Small aggregate improvement, but severe errors and cancellation remain |
| One-off CLI, auth, path, dependency, provider, or network errors | No | Operational incident, not evidence about grading quality |
| Physics candidate-v2 | No negative-result entry | Held-out results improved; unchanged severe-error rate belongs in the error-taxonomy TODO |
| Kimi/Claude advisor results | Not yet | Real external results have not returned |
| Autoresearch MVP | Not yet | The real loop is incomplete, so there is no completed negative experiment to explain |

### Candidate-v3 worsened the metric it was meant to improve

The authoritative comparison is seven DSAA3071 development students and ten
questions per student, for 70 student-question score pairs.

| Metric | R1 baseline | C3 candidate-v3 | C3 minus R1 |
| --- | ---: | ---: | ---: |
| Question MAE | 2.614 | 2.814 | +0.200 worse |
| Exact score pairs | 36 / 70 | 35 / 70 | -1 |
| Severe-error pairs | 15 / 70 | 17 / 70 | +2 worse |
| Item-level absolute error points | 183 | 197 | +14 worse |
| Student-total absolute error points | 141 | 141 | unchanged |

Question-level decomposition explains the net 14-point regression:

| Question | C3 minus R1 absolute-error points | Interpretation |
| --- | ---: | --- |
| Q5 | +7 | Worse |
| Q6 | +1 | Slightly worse |
| Q7 | +14 | Largest regression |
| Q8 | -6 | Improvement |
| Q9 | 0 | No aggregate change |
| Q10 | -2 | Improvement |

Q7 alone adds 14 absolute error points. Improvements on Q8 and Q10 offset the
additional errors on Q5 and Q6, leaving the same 14-point net regression.

The existing case review supports, but does not prove, three behavioral
explanations:

- candidate-v3 sometimes let a local proof flaw erase credit for an otherwise
  valid construction direction;
- material-error caps were triggered too broadly;
- required evidence labels could be treated as mandatory wording instead of
  accepting a valid semantic equivalent.

These are diagnostic hypotheses because the gold data contains official scores
but not official scoring rationales.

### Candidate-v3.1's total-score gain was error cancellation

C31-r2 looked better if only student total-score MAE was inspected:

| Metric | R1 baseline | C31-r2 | Change |
| --- | ---: | ---: | ---: |
| Question MAE | 2.614 | 2.929 | +0.314 worse |
| Exact score pairs | 36 / 70 | 37 / 70 | +1 |
| Severe-error pairs | 15 / 70 | 18 / 70 | +3 worse |
| Item-level absolute error points | 183 | 205 | +22 worse |
| Student-total absolute error points | 141 | 129 | -12 better |
| Within-student cancellation gap | 42 | 76 | +34 |

The identity is:

```text
student-total absolute error
= item-level absolute error - within-student cancellation
```

C31-r2 added 22 points of question-level error but added 34 points of
over-score/under-score cancellation. The resulting 12-point total-score
"improvement" is therefore not evidence of better per-question grading.

The main observed drivers were Q7 proof-credit instability and systematic Q9
under-scoring. The open-ended adequacy rule did not overcome the strict
element-by-element full-credit requirement.

### Candidate-v3.2 improved only slightly at question level

C32 is not a failed experiment. It is the first candidate in this development
sequence to reduce both question MAE and total-score MAE versus R1. However, the
size and source of those two improvements are very different:

| Metric | R1 baseline | C32 | Change |
| --- | ---: | ---: | ---: |
| Question MAE | 2.614 | 2.557 | -0.057 better |
| Exact score pairs | 36 / 70 | 37 / 70 | +1 |
| Severe-error pairs | 15 / 70 | 16 / 70 | +1 worse |
| Item-level absolute error points | 183 | 179 | -4 better |
| Student-total absolute error points | 141 | 101 | -40 better |
| Within-student cancellation gap | 42 | 78 | +36 |

Only 4 of the 40 reduced student-total error points come from lower
question-level absolute error. The other 36 points, or 90%, come from additional
within-student cancellation.

This does not erase the 4-point question-level improvement. It means total-score
MAE substantially overstates the strength of the improvement.

### Q6 offsets most of C32's gains

Negative values below are improvements; positive values are regressions.

| Question | C32 minus R1 absolute-error points | Severe-error pair change |
| --- | ---: | ---: |
| Q5 | -15 | -2 |
| Q6 | +19 | +2 |
| Q7 | 0 | 0 |
| Q8 | -1 | +1 |
| Q9 | -5 | 0 |
| Q10 | -2 | 0 |

The largest improvement is Q5, whose rubric did not change between v1 and v2.
The largest regression is Q6, whose rubric also did not change. The targeted
rubric changes were Q7-Q9.

Therefore the observed Q5/Q6 movement cannot be attributed to the targeted
Q7-Q9 rubric calibration. It can come from the global candidate prompt/skill,
the changed top-level grading policy, target-model variation, or a combination
of those factors.

The paired case review gives three useful examples without exposing student
identity:

- Q6 official score `8`: R1 scored `9`, while C32 scored `20` after inferring
  that tree, BFS, and an acceptance state demonstrated every essential
  simulation element.
- Q8 official score `9`: R1 scored `8`, while C32 applied the invalid-extra-
  output cap and reduced the score to `5`.
- Q9 official score `25`: R1 scored `22`, while C32 scored `12` because the
  valid evidence was considered too brief, despite the intended
  official-style-adequacy rule.

These cases show that the global rules are not applied consistently enough to
freeze C32 as the final skill.

### Scope, source, and metric validation

- Population: seven anonymous DSAA3071 Week 5 development students.
- Grain: 70 student-question pairs and seven student totals.
- Gold source: official per-question scores.
- Compared conditions: R1, C3, C31-r2, and C32.
- Fresh recomputation from the ignored local outputs reproduced the committed
  R1, C3, C31-r2, and C32 metrics exactly to six decimal places.
- C32 changes rubric, prompt, and skill together; it is a package comparison,
  not a single-factor ablation.
- Rubric v2 changes Q7, Q8, Q9 and the top-level grading policy. Q5, Q6, and Q10
  question rubrics are unchanged.

### What is verified, likely, and unresolved

#### Verified

- C3 worsened question MAE, exact agreement, and severe-error rate versus R1.
- C31-r2's total-score improvement was caused by additional cancellation while
  question-level error worsened.
- C32 made a small four-point question-level improvement, added one severe
  error, and obtained 90% of its total-score improvement from cancellation.
- Q6 contributed 19 additional absolute-error points under C32.

#### Likely but not causally proven

- Candidate-v3's proof and cap rules were too aggressive for the observed
  official scoring style.
- C32's global open-ended-adequacy and semantic-equivalence rules encouraged
  over-credit on Q6 by treating related terms as demonstrated relations.
- The Q8 invalid-output cap is too blunt for some official-scored answers.

#### Unresolved

- Official per-question rationales are unavailable, so the exact human reason
  for each score cannot be confirmed.
- Each condition was run once and the recorded temperature is `null`; target
  variation was not measured.
- C32 has no held-out evidence.

### Project changes recommended before candidate-v3.3

1. Make question-level MAE and exact agreement the primary acceptance metrics.
   Treat total-score MAE as a guardrail, not the main objective.
2. Add a cancellation diagnostic to every grading comparison:
   item-level absolute error, student-total absolute error, and their gap.
3. Require severe-error count not to increase before accepting a candidate.
4. Isolate rubric, prompt, and skill changes in separate development arms before
   testing a combined package.
5. For Q6, distinguish a term being mentioned from a required relation being
   demonstrated. Do not infer branch addressing or accept-if-any behavior from
   tree/BFS wording alone.
6. For Q8, calibrate invalid-output deductions against reviewed official cases
   instead of applying a broad cap from one textual signal.
7. Run the latest model as a defect critic on the largest Q6/Q8/Q9 disagreements
   before editing the next candidate.
8. Repeat the matched development comparison before held-out testing so
   run-to-run variation is measured.

### Decision

Close candidate-v3 and C31-r2 as informative negative/mixed results. Keep C32
as a development candidate, not a frozen final skill. The next useful action is
a controlled Q6/Q8 defect audit and candidate-v3.3 design, not another broad
prompt rewrite.

### Further questions

- Can official rationales or instructor review be obtained for the selected
  Q6/Q8/Q9 disagreements?
- Does C32's four-point item-level improvement survive a repeated matched run?
- Which individual rule causes the Q6 over-credit: semantic equivalence,
  open-ended adequacy, official-style adequacy, or model variation?
