---
title: Course-generic Aggregate Grading Metrics
---

# Course-generic aggregate grading metrics / 课程通用汇总评分指标

`compare-course-runs` compares two completed grading runs against a
question-level human gold table described by a `CourseSpec`. It makes no model
call. It is intended for a new course such as DSAA3071 Week 4 after the human
gold table and the direct-multimodal and transcription-then-grading runs exist.

该命令在本地把两个已完成的模型评分结果与按题人工 gold 对比，不会调用模型。它适用于
DSAA3071 Week 4 这类新课程：先有人工 gold，再有直接多模态和“先转录再评分”的结果，
最后才进行对比。

## Required gates / 必要前置条件

- A valid `CourseSpec`, including the actual question IDs, score ranges, and
  score steps.
- A complete gold CSV that passes `validate-gold` for the exact anonymous
  student list being compared. Blank or incomplete gold is a readiness block,
  not a model failure.
- Gold validation is subset-scoped, not development-only: the command selects
  the requested anonymous rows before validating them. Therefore a development
  comparison may proceed while held-out rows remain blank; a held-out
  comparison, in turn, requires its own held-out rows to be complete.
- Two completed grade-run outputs. Each must contain exactly one score for each
  requested anonymous student/question pair. Standard run directories must
  have `validation.json` with `status: passed`; dry-run outputs are refused.
- When the experiment requires it, use `--require-same-data-snapshot` to make
  the command reject runs whose metadata does not bind to the same input
  snapshot.

- 必须提供有效的 `CourseSpec`，其中包含真实题号、分值范围与分数步长。
- gold CSV 必须针对本次比较的匿名学生名单完整通过 `validate-gold`；未填 gold 是就绪性
  阻塞，不是模型实验失败。
- gold 校验按本次选择的匿名子集进行，而不只限定 development：命令先筛选所请求的行再校验。
  因此 development 比较可在 held-out 行仍为空时进行；但 held-out 比较时，其自身的 held-out
  行必须完整。
- 两个评分运行都必须完整：每个匿名学生、每道题恰好一个分数。标准运行目录的
  `validation.json` 必须为 `passed`；dry-run 结果会被拒绝。
- 如果实验要求两个臂来自同一输入快照，加入 `--require-same-data-snapshot`；缺失或不同的
  快照绑定会阻止比较。

## Command / 命令

All `Data/` paths remain local and ignored by Git. The result files may be
written under `experiments/records/` because they are checked to be
aggregate-only.

```powershell
python -m benchmark.core.cli compare-course-runs `
  --course <tracked-course-spec.json> `
  --gold <private-gold.csv> `
  --students-file <tracked-or-private-anonymous-student-list.txt> `
  --baseline-run <private-baseline-run-or-outputs-dir> `
  --candidate-run <private-candidate-run-or-outputs-dir> `
  --output-json <tracked-aggregate-comparison.json> `
  --output-md <tracked-aggregate-comparison.md> `
  --require-same-data-snapshot
```

可接受的运行输入是标准运行目录、其 `outputs/` 目录，或一个独立的 `predictions.csv`。命令会
写出 JSON 与 Markdown 两种聚合报告。

## What is safe to share / 可公开的内容

The generated artifacts contain only course/assessment metadata, aggregate
population counts, aggregate and per-question metrics, a paired bootstrap
interval, safe run metadata, and confidence-versus-exact-agreement aggregates.
They explicitly reject student IDs, individual scores, raw answers, model
evidence, prompts, responses, and private paths.

生成的文件只包含课程/考试元数据、总体人数、总体与按题指标、配对 bootstrap 区间、安全的
运行元数据，以及 confidence 与实际准确率的汇总关系。它会拒绝学生 ID、个人分数、原始作答、
模型证据、提示词、模型响应和私有路径。

## Advisor-workflow integration limit / 与导师工作流的边界

The current `advisor_workflow` keeps its existing physics-specific metrics
command unchanged. For Week 4, invoke this standalone command after both
grading arms and validated gold are present. A future workflow-level selector
should explicitly provide `course_spec`, `gold`, and `students_file` before it
replaces the physics backend; silently reusing the physics schema would make a
new-course comparison ambiguous.

当前 `advisor_workflow` 保持原有的 physics 专用指标命令不变。Week 4 在两条评分臂和完整
gold 都准备好后调用此独立命令即可。未来若要把它接入自动工作流，必须显式配置
`course_spec`、`gold` 和 `students_file`；不能悄悄复用 physics 的 schema，否则新课程的
比较范围会变得不明确。
