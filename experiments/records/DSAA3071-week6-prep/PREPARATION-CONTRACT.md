# DSAA3071 Week 6 Full Benchmark: Pre-run Preparation Contract

Status / 状态: **scope and rubric frozen; no model run is authorized by this
document.**

## 1. Scope and input pages / 范围与输入页

The benchmark includes Q1--Q10, worth 130 points in total, in one-point score
increments. Its semantic standard is
[`rubric_v0.json`](rubric_v0.json), extracted only from the official Week 6
solution; it has no student examples.

| Student packet page / 学生答卷包页面 | Question IDs / 题号 |
| --- | --- |
| `p01` | Q1, Q2, Q3, Q4, Q5 |
| `p02` | Q6, Q7, Q8 |
| `p03` | Q9, Q10 |

This is a student-packet mapping, not an inference from the four-page official
reference. Any scope, mapping, or rubric change requires a versioned artifact
and invalidates unmatched packets.

## 2. Matched modality conditions / 匹配的模态条件

Every comparison must keep the anonymous student set, frozen split, page scope,
course specification, rubric, prompt version, and private gold table identical.

1. **M1 direct multimodal / 直接多模态：** grade the approved anonymous page
   images directly.
2. **T1 then G1 / 先转录后评分：** an engine first produces a fresh automatic
   transcript from the same images (T1); that engine then grades only its own
   unchanged T1 transcript (G1).

Human transcription auditing may happen after the primary route, but it must
never silently edit or replace the primary automatic transcript. A corrected
transcript is a separately versioned secondary condition.

每次比较必须保持匿名学生集合、冻结划分、页面范围、课程规范、rubric、prompt
版本和私有 gold 表完全一致。人工转录复核只能在主自动路线之后进行，不能悄悄替换
引擎自己的 T1 输出。

## 3. Answer-first scoring / 先看答案的评分原则

Identify the student's actual answer or claim before checking reasoning.
Equivalent correct answers and valid alternative proofs receive credit. Do not
require official keywords or exact proof formatting. Do not duplicate points
for restated evidence. A technical contradiction affects only the associated
rubric elements rather than automatically zeroing an otherwise multi-part answer.

## 4. Gates before a model call / 模型调用前门槛

1. Final anonymization review and the exact private snapshot must validate.
2. Scope, page mapping, rubric, and development/held-out split must be frozen.
3. Development question-level gold must be human-entered and validated.
4. M1/T1 packets must pass scope, privacy, hash, and split-isolation audit.
5. T1 output must be fresh and structurally valid; G1 must preserve its exact
   source and pass the image-to-transcript lineage audit.
6. Exact model identifiers and permitted capabilities must be pinned.
7. A separate explicit run-readiness approval must be recorded.

Passing anonymization review or packet audit alone is not model authorization.
The tracked advisor configuration is deliberately blocked and rejects even a
dry-run until a copied versioned activation configuration sets
`model_run_allowed: true`; that switch is necessary but not sufficient.

## 5. Reporting / 汇报

Until the gates pass, call this **Week 6 benchmark preparation**, not a grading
result. Any later report must name the 130-point scope, split, engine, model,
input route, question-level outcomes, and modality-specific errors. It must not
report held-out findings until the separate held-out approval and run exist.
