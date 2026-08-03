# W4 Development Run R1: Controlled Model Comparison / W4 开发集 R1：受控模型比较

## Scope and safety boundary / 范围与安全边界

This is a development-only diagnostic run over 7 approved anonymous students
and 70 question-level score rows (W4 Q1--Q10). Held-out students, human-gold
content, raw scans, transcripts, model outputs, and private error books remain
local and are not part of this record.

这是一次仅限开发集的诊断运行，覆盖 7 位已批准的匿名学生、70 个题目级评分
单元（W4 Q1--Q10）。留出集学生、人工 gold 内容、原始扫描件、转录文本、模型
输出及私有错题集均保留在本地，不属于本记录。

| Condition / 条件 | Engine and route / 引擎与路线 |
| --- | --- |
| Codex M1 | `gpt-5.6-sol`, direct anonymous-image grading / 直接读取匿名图像评分 |
| Codex G1 | `gpt-5.6-sol`, grading the frozen Codex T1 transcript / 对冻结的 Codex T1 转录评分 |
| DeepSeek G1 | `deepseek-v4-pro`, grading the exact same frozen Codex T1 transcript / 对完全相同的冻结 Codex T1 转录评分 |

All three runs completed 7/7 students with no model-run failures. The
development gold gate, packet audit, transcript validation, and M1--T1--G1
lineage gate passed. M1 and Codex G1 share the same source snapshot, prompt,
and rubric; the two G1 conditions additionally share the same transcript hash,
T1 source run, prompt, and rubric. The outer terminal monitor reached its
12-minute observation window for two long calls, but their existing child
processes completed naturally and their final run validations passed; no call
was retried or duplicated.

三条运行均为 7/7 完成且没有模型运行失败。开发集 gold 门槛、包审计、转录
校验和 M1--T1--G1 谱系门槛均已通过。M1 与 Codex G1 使用相同的源快照、prompt
和 rubric；两条 G1 还使用相同的转录哈希、T1 来源运行、prompt 和 rubric。两次
较长调用曾超过终端监控的 12 分钟观察窗口，但其已有子进程自然完成且最终运行
校验通过；没有重试或重复调用。

## Headline result / 核心结果

`Exact agreement` is question-level exact agreement with human gold. `Cell
MAE` is mean absolute error per question-level score. `Total MAE` is mean
absolute error in each student's Q1--Q10 total. `Signed error` is predicted
minus gold, so a negative value means systematic underscoring.

`Exact agreement` 是与人工 gold 完全一致的题目级比例；`Cell MAE` 是每个题目
评分单元的平均绝对误差；`Total MAE` 是每位学生 Q1--Q10 总分的平均绝对误差；
`Signed error` 为预测分减 gold 分，负值表示系统性少给分。

| Condition / 条件 | Exact agreement | Cell MAE | Total MAE | Signed error |
| --- | ---: | ---: | ---: | ---: |
| Codex M1 direct image / 直接读图 | 42.9% | 2.20 | 11.71 | -1.17 |
| Codex G1 transcript-first / 先转录 | 45.7% | 2.39 | 14.14 | -1.41 |
| DeepSeek G1 same transcript / 同一转录 | 41.4% | 3.46 | 28.29 | -2.83 |

No route is ready for unattended production grading: every development-student
total differed from gold by more than one point, and every run had at least a
five-point error on every student's total under the current strict aggregate
definition. These are diagnostic findings, not a claim that the gold is an
absolute ground truth.

目前没有任何路线适合无人值守的正式评分：按照当前严格的汇总定义，每位开发集
学生的总分与 gold 都相差超过 1 分，并且每条路线都在每位学生的总分上出现至少
5 分误差。这些是诊断性发现，并不把 gold 宣称为绝对真值。

## What the controlled comparisons say / 受控比较说明了什么

### 1. Direct image versus transcript-first: Codex M1 vs Codex G1

- M1 changes exact agreement by **-2.9 percentage points** relative to G1
  (bootstrap interval **-8.6 to 0.0 pp**), so this 7-student development set
  does not establish an exact-agreement advantage for direct image grading.
- M1 has a slightly lower cell MAE (**-0.19**) and lower total MAE (**-2.43**).
  In other words, direct image grading made some more scores non-exact while
  reducing the average size of score errors.
- Therefore the evidence is a trade-off, not a winner declaration. Both M1 and
  G1 must remain available and be tested on further, separately prepared data.

- 与 G1 相比，M1 的完全一致率变化为 **-2.9 个百分点**（bootstrap 区间
  **-8.6 到 0.0 pp**），所以这个 7 人开发集不能证明直接读图在完全一致率上更好。
- M1 的题目级 MAE 略低（**-0.19**），总分 MAE 也更低（**-2.43**）。也就是说，
  直接读图使部分分数不再完全一致，但降低了平均误差幅度。
- 因此结论是权衡，而不是宣布胜者。M1 和 G1 都应保留，并在另外准备的数据上继续
  测试。

### 2. Model effect on the same transcript: Codex G1 vs DeepSeek G1

- On the identical Codex T1 text, Codex G1 has **+4.3 pp** exact agreement
  relative to DeepSeek G1; its bootstrap interval (**-2.9 to +11.4 pp**) still
  crosses zero because the development sample is small.
- Codex G1 nevertheless has lower cell MAE (**-1.07**) and lower total MAE
  (**-14.14**), while DeepSeek G1 shows the larger underscoring bias.
- This is a useful signal for the next diagnostic round, not a defensible
  provider ranking. It must be repeated on additional prepared development
  cohorts and later on a sealed held-out evaluation.

- 在完全相同的 Codex T1 文本上，Codex G1 比 DeepSeek G1 高 **4.3 个百分点**的
  完全一致率；但 bootstrap 区间（**-2.9 到 +11.4 pp**）仍跨过零，因为开发样本很小。
- Codex G1 的题目级 MAE（**-1.07**）和总分 MAE（**-14.14**）均更低，而 DeepSeek
  G1 的少给分偏差更大。
- 这是下一轮诊断的有用信号，不是可以辩护的供应商排名。它需要在更多已准备的开发
  cohort 上重复，并最终在密封的留出集上评估。

## Where to investigate first / 应优先调查哪里

The public aggregate statistics identify a stable triage order without exposing
any student answer:

公开汇总统计在不暴露任何学生作答的前提下，给出了稳定的排查优先级：

1. **Q7--Q10 first / 首先 Q7--Q10.** Q7 and Q9 have zero exact agreement for
   all three conditions; Q8 and Q10 are also poor across routes. Q9 has the
   largest persistent per-question error magnitude among the shared failures.
2. **Q5--Q6 second / 其次 Q5--Q6.** These show meaningful route/provider
   differences, especially a much larger DeepSeek-G1 under-score on Q5 and
   weaker DeepSeek-G1 exact agreement on Q6.
3. **Q1--Q4 are not the first tuning target / Q1--Q4 暂不是首要调优目标.** Q1
   is exact for all conditions; Q2--Q4 are mostly stable. Q4 nevertheless has
   a shared positive scoring bias, so it remains a small calibration check.

This points to scoring/rubric interpretation before OCR as the likely first
place to investigate, but it is deliberately not a root-cause conclusion.
Private case review must distinguish rubric ambiguity, missing evidence,
transcription ambiguity, and model reasoning before a skill change is made.

这首先指向评分或 rubric 理解，而非 OCR，应作为首要调查方向；但这不是根因结论。
在修改 skill 前，必须通过私有案例复核区分 rubric 歧义、证据遗漏、转录歧义和模型
推理问题。

## Confidence is informative but not an acceptance gate / 置信度有信息量，但不能作为放行门槛

High-confidence predictions are more often exact than medium/low-confidence
predictions, but they are still far from reliable enough for automatic
acceptance: high-confidence exact agreement is 66.7% for Codex G1, 51.7% for
Codex M1, and 61.4% for DeepSeek G1. Medium-confidence exact agreement is 0%
for Codex M1 and DeepSeek G1 and 10.5% for Codex G1 on this sample.

高置信度预测确实比中低置信度更常与 gold 一致，但仍远不足以自动放行：Codex G1、
Codex M1 和 DeepSeek G1 的高置信度完全一致率分别只有 66.7%、51.7% 和 61.4%。
在本样本中，Codex M1 和 DeepSeek G1 的中置信度完全一致率为 0%，Codex G1 为 10.5%。

Use confidence as a human-review priority signal, not as a score-acceptance
rule. This result is preliminary because it has only 70 question-level rows.

应把置信度作为人工复核优先级信号，而不是接受分数的规则。由于这里只有 70 个题目级
评分单元，这一结论仍是初步的。

## Error-book status and next action / 错题集状态与下一步

Three private development error books were built: Codex M1 has 40 mismatched
score pairs (12 severe), Codex G1 has 38 (15 severe), and DeepSeek G1 has 41
(23 severe). Their public, privacy-audited summaries are stored alongside this
report.

已构建三份私有开发集错题集：Codex M1 有 40 个不一致评分对（12 个严重），Codex G1
有 38 个（15 个严重），DeepSeek G1 有 41 个（23 个严重）。对应的公开、隐私审计
汇总与本报告放在一起。

The error-book iteration tool intentionally refuses to label M1-to-G1 changes
as "resolved" or "regressed", because their input modes differ. That safeguard
is correct: a modality change is a controlled route comparison, not a skill
update. Its evidence should be interpreted through the two aggregate metrics
files below.

错题集迭代工具会有意拒绝把 M1 到 G1 的变化标为“修复”或“回归”，因为两者输入模式
不同。这个保护是正确的：模态改变是受控路线比较，不是 skill 更新。相关证据应通过下面
两份聚合指标文件解释。

Before any scoring-skill edit, review representative private cases from Q7--Q10
and record one concrete mechanism per case. Only then should a candidate skill
be drafted, rerun on the same development protocol, compared against this
baseline, and finally evaluated on a sealed held-out cohort.

在任何评分 skill 修改之前，应复核 Q7--Q10 的代表性私有案例，并为每个案例记录一个
具体机制。之后才能起草 candidate skill，按同一开发协议重跑，与此基线比较，最后在密封
留出 cohort 上评估。

## Public artifacts / 公开产物

- `metrics-codex-m1-vs-g1.{json,md}`: controlled route comparison / 受控路线比较。
- `metrics-codex-g1-vs-deepseek-g1.{json,md}`: same-transcript model comparison /
  同转录模型比较。
- `error-summary-codex-m1.json`, `error-summary-codex-g1.json`, and
  `error-summary-deepseek-g1.json`: privacy-audited aggregate error summaries /
  通过隐私审计的聚合错题统计。

