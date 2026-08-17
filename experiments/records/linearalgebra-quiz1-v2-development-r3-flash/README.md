# Linear Algebra Quiz 1 — V5.2 DeepSeek V4 Flash extension / V5.2 DeepSeek V4 Flash 补跑

This record adds the stable `deepseek-v4-flash` G1 scoring route to the frozen
V5.2 Linear Algebra Quiz 1 development experiment. It is an aggregate-only
development record: 30 anonymized submissions and 300 minimal score items. It
does not contain student identifiers, answers, transcripts, individual marks,
raw model responses, or private paths.

本记录只在冻结的 V5.2 Linear Algebra Quiz 1 开发集上补充稳定版
`deepseek-v4-flash` 的 G1 评分路线。公开内容仅含 30 份匿名作答、300 个最小
评分格的汇总信息；不含学生标识、作答、转录、逐人分数、原始模型响应或私有路径。

## Controlled scope / 受控范围

- G1-Codex and G1-DeepSeek Flash used the same frozen G1 packet, validated T1
  transcription commitment, development roster, and data snapshot.
- The V5.2 skill, V5.2 r2 grading prompt, course contract, and rubric were not
  changed. T1 was not rerun.
- The DeepSeek V4 Flash route is marked stable by the public model-release
  policy. The older V4 Pro observation remains provisional and is not replaced
  by this record.
- No held-out submission, production score, or new V5.3 packet was used.

## Structural completion / 结构完成情况

The initial Flash run produced 25 structurally valid outputs. Five outputs
failed JSON parsing only; they were rerun once with the same frozen packet and
model route. The 25 initial outputs and 5 successful JSON-only repairs were
checked for non-overlap and combined into a private canonical 30 / 30 run. Raw
responses were not copied into that canonical record. Only the complete,
validated canonical run was eligible for metrics.

首次 Flash 运行有 25 份结构有效输出；另有 5 份仅因 JSON 解析失败而未通过。
这 5 份在相同冻结 packet 和模型路线下进行一次 JSON 修复重试。首批 25 份与修复
5 份经无重叠核验后合成为私有的 30 / 30 规范运行；规范记录不复制原始响应，且只有
该完整、验证通过的记录用于指标计算。

## Aggregate result / 聚合结果

| Route | Leaf exact agreement | Leaf MAE | Total-score MAE | Within 1 point | Severe total error | Mean signed error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| G1-Codex | 87.3% | 0.54 | 3.03 | 50.0% | 40.0% | +0.00 |
| G1-DeepSeek V4 Flash | 86.3% | 0.82 | 4.77 | 46.7% | 53.3% | +0.01 |

The Flash route is materially better than the prior provisional V4 Pro result
on this development set, but it remains below the matched G1-Codex route on
total-score MAE and severe-error rate. The paired exact-agreement difference
(Flash minus Codex) is -1.0 percentage point, with a 95% paired-bootstrap
interval of [-4.3, +2.0] percentage points. This small development sample does
not support a general model ranking or a production-readiness claim.

Flash 在该开发集上显著好于此前的暂定版 V4 Pro 观察结果，但总分 MAE 和严重误差率
仍低于同输入的 G1-Codex。Flash 相对 Codex 的叶子精确一致率差为 -1.0 个百分点，
配对 bootstrap 95% 区间为 [-4.3, +2.0] 个百分点。样本很小，不能据此做泛化模型
排序或生产可用性主张。

## Rubric-analysis signal / rubric 分析信号

The three same-input G1 routes (Codex, Flash, and the prior provisional Pro)
agree exactly on 80.0% of leaf scores. Codex–Flash agreement is 84.7% at the
leaf level, with total-score MAE 4.13 between the two routes. This is a
repeatability diagnostic, not a replacement for human gold.

The priority leaves for V5.3 rubric refinement are:

| Leaf | Why it is a priority |
| --- | --- |
| Q4 | Lowest same-input agreement: 46.7% Codex–Flash and 30.0% three-model exact agreement; Flash also has the weakest human-alignment result on this leaf. |
| Q2a | 56.7% Codex–Flash and 50.0% three-model exact agreement; first-substantive-error and downstream-consequence treatment need an executable boundary. |
| Q2b | Symbolic-equivalence recognition and simplification checks remain less stable than objective items, even though route-level human alignment is higher than Q2a. |

The objective leaves Q1b–Q1e were exact for all routes. Those leaves do not
need additional explanatory requirements. The V5.3 course rubric should instead
make the following distinctions executable for calculation leaves: valid
algebraic equivalence; answer-only cap; the first substantive error; no
downstream double deduction; and whether an error is local arithmetic versus a
material formula or method defect. Unrelated extra work must not reduce a
correctly demonstrated required part.

同输入的三条 G1 路线（Codex、Flash、此前暂定版 Pro）在 80.0% 的叶子项上完全一致；
Codex–Flash 叶子一致率为 84.7%，两路线总分 MAE 为 4.13。这是可重复性诊断，不替代
人工 gold。V5.3 应优先为 Q4、Q2a、Q2b 给出可执行的计算题边界；而 Q1b–Q1e 不应因为
“更细致”而被错误地增加解释要求。

## Limitations and next gate / 限制与下一关

This record contains no V5.3 model result. Its purpose is to use V5.2 evidence
to draft a more detailed V5.3 rubric, not to compare V5.2 and V5.3 performance.
Before any V5.3 development run, the course owner must calibrate the detailed
score bands for representative calculation-error categories, especially the
Q2a sign/arithmetic boundary, Q2b algebraic equivalence, and Q4 tetrahedron
formula-factor error. The resulting V5.3 rubric and prompt will then be frozen,
validated, and tested before any explicitly authorized development rerun. The
held-out set remains untouched until a later authorization.

本记录不含任何 V5.3 模型结果。它的用途是根据 V5.2 证据起草更细的 V5.3 rubric，
而不是把不同版本的性能作伪比较。任何 V5.3 开发集运行前，课程负责人仍需校准 Q2a
符号／算术边界、Q2b 代数等价和 Q4 四面体公式系数错误等代表性分档；随后才冻结、
验证和测试 V5.3 rubric 与 prompt。留出集继续保持未使用状态。
