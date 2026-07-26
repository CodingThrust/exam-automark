# TASK4 项目改进选项 / TASK4 Project Improvement Options

## 选择原则 / Decision rule

本文件把 sci-brain 调研建议映射到已有 TASK，避免：

- 把调研建议误报成已实现功能；
- 在 TASK4 重复实现 TASK6、TASK7 或 TASK8；
- 只因为某篇论文效果好，就未经本项目实验直接采用。

This document maps survey-derived recommendations to the existing TASK plan so that research suggestions are not mistaken for completed features or implemented twice.

## 当前事实 / Current facts

| 能力 / Capability | 当前状态 / Current status | 说明 / Evidence |
|---|---|---|
| Skill 版本化 | 已有 / Existing | `experiments/skill_versions/` |
| Plan、record、packet、hash | 已有 / Existing | `benchmark/core/` 与 `experiments/records/` |
| 严格评分 schema | 已有 / Existing | core 与 Physics schema validators |
| 隐私检查 | 已有 / Existing | `benchmark/physics/privacy.py` |
| 多项评分指标 | 部分已有 / Partly existing | exact、MAE、severe error、per-question 已有 |
| 统一错误阶段 taxonomy | 未完成 / Missing | 尚不能一致区分读取、转录、rubric、schema、feedback |
| Confidence calibration | 未完成 / Missing | 只有按 confidence 分档的 accuracy |
| 双路径多模态受控比较 | 未完成 / Missing | TASK7 |
| Candidate 多目标发布门槛 | 未完成 / Missing | TASK8 |
| 人工 review routing | 未统一 / Not unified | 尚未成为跨课程输出协议 |
| 调研工具版本固定 | 未完成 / Missing | manifest 未记录运行时 sci-brain commit |

## Option A：补齐调研来源与可复现性 / Harden survey provenance

实施内容：

- 在下一次调研运行中固定 sci-brain commit；
- 记录实际 query、候选来源、纳入/排除理由；
- 为每份报告记录 scoped cite keys；
- 将 literature surveys 纳入 research-record health audit；
- 检查 BibTeX 完整性和 dangling citations。

改善：

- 导师可以追问“这句话从哪篇论文来的”；
- 以后工具或文献更新时可以区分 source drift；
- 不会只剩 PDF 而失去生成依据。

局限：

- 提高的是调研可信度，不直接提高评分准确率；
- 旧运行缺失的 commit 不能事后百分之百恢复。

建议：**选择，现在作为 TASK4 的小型工程改进。**

Implementation: pin the sci-brain revision for future runs, record queries and inclusion decisions, preserve report-specific citation scopes, and audit literature-survey records. This improves research reproducibility, not grading accuracy.

## Option B：统一阶段级错误 taxonomy / Add a stage-level error taxonomy

建议最小分类：

1. `input_acquisition`：缺页、裁剪、旋转、图片质量；
2. `transcription`：手写、公式、符号、单位、图表识别；
3. `evidence_extraction`：没有找到学生实际写出的证据；
4. `rubric_application`：读对了，但 rubric 判断错；
5. `score_aggregation`：分项正确但加总、边界或步长错误；
6. `schema_or_tooling`：JSON、字段、解析、运行工具错误；
7. `feedback_grounding`：分数或证据与反馈不一致；
8. `rubric_ambiguity`：不是模型单方面错误，需要教师裁决。

改善：

- 能回答“direct multimodal 为什么比 transcript-first 差”；
- 能记录非主观、技术性错误；
- 能为 SkillOpt 生成同方向、同原因的 candidate 修改；
- 能把可自动修复和必须人工处理的情况分开。

建议：**选择，但归入 TASK6 实现。**

Implementation should live in TASK6 because it is the foundation for objective error analysis, confidence calibration, and the later multimodal comparison.

## Option C：做真正的 confidence calibration / Measure confidence calibration

不能只报告模型输出的 `high / medium / low`，至少要报告：

- 每档样本量；
- 每档 exact accuracy 与 severe-error rate；
- confidence 与错误类型的关系；
- high-confidence error 数量；
- 按题目、课程和 input mode 分层后的稳定性；
- 如果映射到概率，计算 Brier score 或 ECE。

要回答的导师问题是：

> 模型自称经常会错的地方，事实上是否更容易错？

建议：**选择，与 Option B 一起在 TASK6 实现。**

Confidence must be tested against observed correctness and error severity, not trusted as a self-description.

## Option D：同输入、双路径多模态比较 / Run a controlled dual-path multimodal comparison

同一批原始图片、同一 rubric、同一学生、同一模型版本分别运行：

```text
Path 1: image → direct multimodal grading
Path 2: image → fresh transcription → text grading
```

必须额外保存：

- fresh transcript；
- direct path 引用的视觉证据；
- 每个 stage 的错误类型；
- 每题 delta；
- 模型、CLI、prompt、skill 和 input hash。

改善：

- 不再把“先转录”当成唯一方案；
- 可以判断直接 vision 是否减少信息丢失；
- 可以判断 transcript-first 是否更可审计；
- 为 Codex CLI、Claude Code、Kimi 和 DeepSeek 的整合比较提供共同协议。

建议：**选择，归入 TASK7；这是本周明确要求，不应删减。**

Both paths are required. The experiment must hold the source images, students, rubric, and model settings constant.

## Option E：Candidate 多目标发布门槛 / Add a multi-objective candidate gate

candidate 不能因为一个总指标变好就通过。建议门槛至少包括：

- schema 和完整性检查全部通过；
- exact agreement 不得明显下降；
- severe-error rate 不得上升；
- 关键题目不得出现不可接受 regression；
- total-score 改善不能主要来自 error cancellation；
- high-confidence severe error 不得增加；
- 每项修改能追溯到具体错误和 rubric 条款；
- held-out 只在 dev gate 通过后运行。

改善：

- 直接解决 SkillOpt “candidate 看似有道理但实际更差”的问题；
- 防止只优化 accuracy；
- 让 accept / reject 决定可以自动生成证据。

建议：**选择，归入 TASK8 的 candidate-v3.2 缺陷审计与修改建议。**

The gate should combine integrity, item-level accuracy, severe errors, per-question regressions, cancellation analysis, confidence risk, and traceability.

## Option F：统一人工复核路由 / Add explicit human-review routing

建议触发条件：

- 低 confidence；
- 多次运行不一致；
- transcription 或 image-quality flag；
- rubric ambiguity；
- severe score impact；
- feedback 与 evidence 不一致；
- 影响 pass/fail 或等级边界。

改善：

- 把 human-in-the-loop 变成可执行协议；
- 教师只审核高价值 case，而不是重新检查全部答案。

局限：

- 触发阈值应由 TASK6、TASK7 的真实错误分布决定；
- 现在直接定死阈值会带来过多或过少人工复核。

建议：**原则上选择，但延后到 TASK9；先用 TASK6/7 数据定阈值。**

Human review should be routed by explicit evidence. Thresholds should be chosen after the error and calibration studies, not guessed now.

## 推荐选择 / Recommended selection

推荐选择 **A + B + C + D + E**，并接受 F 的原则但延后定阈值：

| 顺序 / Order | 选项 / Option | 放入 / Assigned TASK | 原因 / Reason |
|---:|---|---|---|
| 1 | A | TASK4 | 先补调研来源链，范围小且不与评分代码冲突 |
| 2 | B + C | TASK6 | 错误原因是 calibration 和多模态分析的共同基础 |
| 3 | D | TASK7 | 双路径比较依赖统一错误分类 |
| 4 | E | TASK8 | 用 TASK6/7 的证据定义 candidate gate |
| 5 | F | TASK9 | 用真实分布确定人工复核阈值 |

Recommended: select **A + B + C + D + E**, accept F as a design principle, and defer its thresholds until TASK9.

## 等待用户选择 / Awaiting user decision

TASK4 当前只完成知识讲解和方案设计。未在本文件中假装 B–F 已经实现。

TASK4 currently completes the explanation and decision design only. Options B–F are not represented as implemented.
