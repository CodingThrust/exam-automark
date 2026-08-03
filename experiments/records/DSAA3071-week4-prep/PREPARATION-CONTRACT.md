# DSAA3071 Week 4 Partial Benchmark: Pre-run Preparation Contract

Status / 状态: **scope and rubric frozen; no model run is authorized by this
document.**

This contract binds the W4 partial benchmark to one question scope, one rubric,
and matched input conditions before model output is observed. It is deliberately
privacy-safe: it contains no raw scan, student answer, identity map, gold score,
or model output.

## 1. Frozen scope / 冻结范围

| Item / 项目 | Contract / 约定 |
| --- | --- |
| Assessment / 考试 | DSAA3071 Week 4 |
| Benchmark total / benchmark 总分 | 60 points / 60 分 |
| In scope / 纳入范围 | Q1-Q4 (5 each), Q9 (25), Q10 (15) |
| Excluded / 排除范围 | Q5-Q8; they must not enter gold, transcripts, packets, predictions, or metrics. / Q5-Q8 不得进入 gold、转录、packet、预测或指标。 |
| Score increment / 分数粒度 | 1 point / 1 分 |
| Rubric / 评分量表 | [`rubric_v0.json`](rubric_v0.json), derived from the official Week 4 solution without student examples. / 基于官方 Week 4 答案整理，且不含学生示例。 |

Any scope or rubric change must create a new versioned artifact and invalidate
unmatched packets. It must not silently alter a later comparison.

任何范围或 rubric 改动都必须新建版本化文件，并使未匹配的 packet 失效；不得
悄悄改写后续比较的含义。

## 2. Input-page contract / 输入页约定

The course owner expressly declared this mapping for the **anonymized
student-submission packets**:

| Student-packet page / 学生答卷包页面 | Question IDs / 题号 |
| --- | --- |
| `p01` | Q1, Q2, Q3, Q4 |
| `p03` | Q9, Q10 |

This mapping is **not inferred** from the official question-plus-solution PDF
pagination. The reference PDF is used only to extract questions and rubric
semantics. In particular, its layout may place a question on a different page
than the declared student-packet page.

上述映射由课程负责人针对**匿名学生答卷包**直接指定，**不是**由官方题目/答案
PDF 的页码推断而来。官方 PDF 只用于抽取题目与 rubric 语义；其排版可能与学生
答卷包中的页面位置不同。

## 3. Matched experimental conditions / 两种匹配实验条件

Both conditions below must use the same anonymous student set, frozen split,
question scope, rubric version, and gold table:

1. **Direct multimodal / 直接多模态：** grade the approved anonymous `p01`
   and `p03` image/PDF evidence for the scoped questions.
2. **Transcript-first / 先转录后评分：** each engine creates a fresh automatic
   transcript from the same approved anonymous pages, then grades only its own
   **unchanged** transcript output.

The comparison is about input modality and transcription effects, not about
different students, different questions, or different gold labels.

An optional human transcription-quality audit may be performed after the
primary automatic runs, but it must not silently edit or replace the transcript
used by the primary transcript-first condition. A human-corrected transcript is
a separately versioned secondary condition, not a substitute for the engine's
automatic route.

两种条件必须使用同一批匿名学生、同一冻结划分、同一题目范围、同一 rubric 版本和
同一 gold 表。比较的对象是输入模态与转录过程的影响，而不是学生、题目或 gold
标签的差异。

每个 engine 都必须从同一批已批准的页面生成新的自动转录，再只对**未改写的、自己
生成的转录**评分。主自动路线运行后可选择性进行人工转录质量审计，但不得悄悄编辑或
替换主路线所用转录；人工修订的转录是一个单独版本化的次级条件，而非自动路线的替身。

## 4. Answer-first scoring policy / 先看答案的评分政策

For each question, first identify the answer or claim the student actually
makes. Then use the reasoning only to verify the claim, assign partial credit
for independently correct relevant work, and detect material contradictions.
Equivalent wording, a valid alternative recognizer example, or a different
correct palindrome construction must receive credit; the official phrasing is
not a required string match. Do not award duplicate points when one piece of
evidence supports the same scoring element in several wordings.

每题先识别学生实际给出的答案或主张，再用推理去验证该主张、识别独立正确的相关
步骤并发现实质矛盾。等价表述、有效的其他 recognizer 示例、或不同但正确的回文
机描述都应得到相应分数；不得把官方措辞当作字符串匹配要求。同一评分要素的同一
证据即使换了多种说法，也不得重复给分。

## 5. Required gates before any model call / 模型调用前的必要门槛

1. Confirm the approved anonymized W4 input version and page-to-question
   extraction against the declared mapping. / 确认已通过匿名化审核的 W4 输入版本，
   并按声明的映射提取页面和题目。
2. Freeze the anonymous development/held-out split before seeing model output.
   / 在看到模型输出前冻结匿名 development/held-out 划分。
3. Create and manually review a private per-question gold table for exactly
   these six questions. / 仅针对这六题创建并人工复核私有的逐题 gold 表。
4. Produce structurally validated fresh automatic transcript evidence with
   provenance, and construct matched direct-multimodal and transcript-first
   prompt packets. / 产出结构校验通过、可追溯的新鲜自动转录证据，并构造两类匹配的
   prompt packet。
5. Audit every packet for scope, privacy, rubric hash, and student/split
   isolation. / 审计每个 packet 的范围、隐私、rubric 哈希和学生/划分隔离。
6. Record an explicit run-readiness approval. / 记录明确的 run-readiness 批准。

Passing an anonymization review alone is not a model-run authorization.
仅通过匿名化审核并不等于获准运行模型。

The tracked blocked configuration is also technically enforced: every model
probe or run, including a dry run, is rejected until a copied, versioned
activation configuration explicitly sets
`future_run_contract.model_run_allowed: true`. That switch remains necessary
but not sufficient; all of the other gates above still apply.
The local doctor and plan commands display this gate as not ready/blocked rather
than presenting the frozen configuration as runnable.

被追踪的阻断配置也有技术强制：在复制出的、版本化的 activation 配置明确设置
`future_run_contract.model_run_allowed: true` 之前，任何模型 probe 或 run（包括
dry run）都会被拒绝。该开关仍只是必要条件，不能替代上列其余所有门槛。
本地 doctor 和 plan 也会把这一门槛显示为 not ready/blocked，而不会把冻结配置呈现为可运行。

## 6. Reporting rule / 汇报规则

Until all gates pass, refer to this work as **W4 partial benchmark
preparation**, not as a grading result. Once runs exist, report question-level
results, modality-specific failures, and the 60-point scope explicitly; do not
generalize the result to the full 130-point Week 4 assessment.

在全部门槛通过前，本工作只能称为 **W4 部分 benchmark 准备**，不能称为评分结果。
产生运行结果后，也必须明确逐题结果、模态相关失败和 60 分范围；不得把结论泛化为
完整 130 分的 Week 4 考试。
