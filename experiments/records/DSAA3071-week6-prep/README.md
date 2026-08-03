# DSAA3071 Week 6 Full Benchmark Preparation

Status / 状态: **all pre-run inputs are prepared; no model has run and no model
run is authorized.**

This record prepares the complete 130-point Week 6 assessment (Q1--Q10) for a
privacy-safe comparison of direct multimodal grading and transcript-first
grading. It contains no raw student scan, identity map, human gold score, or
model output.

## Frozen scope / 冻结范围

| Item / 项目 | Contract / 约定 |
| --- | --- |
| Assessment / 考试 | DSAA3071 Week 6 -- Decidability & Undecidability |
| Questions / 题目 | Q1--Q10, all in scope |
| Total / 总分 | 130 points / 130 分 |
| Score step / 分数粒度 | 1 point / 1 分 |
| Course spec / 课程规范 | [`DSAA3071_week6_full_q1_q10.json`](../../course_specs/DSAA3071_week6_full_q1_q10.json) |
| Rubric / 评分量表 | [`rubric_v0.json`](rubric_v0.json), official-solution-only / 仅基于官方答案 |

## Approved input mapping / 已批准的输入页映射

| Anonymous student packet / 匿名学生答卷包 | Questions / 题号 |
| --- | --- |
| `p01` | Q1--Q5 |
| `p02` | Q6--Q8 |
| `p03` | Q9--Q10 |

The student packets have three pages, while the official question-plus-solution
reference has four. This mapping was declared and visually checked for the
approved anonymous student packets; it is **not** inferred from reference-PDF
pagination.

学生答卷包为三页，官方题目/答案参考为四页。上述映射是针对已批准匿名学生答卷
包声明并视觉核验的，**不是**由官方 PDF 页码推断。

## Prepared private inputs / 已准备的私有输入

- 21 anonymous students and 63 final-approved images (`p01`--`p03`); the
  snapshot is gitignored and bound by [`gold-reviewer-binding.json`](gold-reviewer-binding.json).
- A frozen 7-student development / 14-student held-out split in
  [`split.json`](split.json). Held-out remains sealed until a separate approval.
- A blank private 210-cell question-level gold template; it is deliberately
  not tracked and has no scores yet.
- Four audited private image packets: M1 direct-multimodal and T1 automatic
  transcription, each for development and held-out. Packet preparation is not
  a model invocation.

## What remains / 仍需完成

1. Enter and approve the seven development students' 70 private gold cells.
2. Pin actual engine/model identifiers through authorized zero-data capability
   checks. This includes `codex.cmd` login locally.
3. Create a new versioned activation configuration with explicit approval.
4. Run T1 first, validate unchanged transcript lineage, then run M1/G1.
5. Inspect development results before requesting a separate held-out run.

For the exact engine and modality plan, see
[`RUN-MATRIX-AND-PROTOCOL.md`](RUN-MATRIX-AND-PROTOCOL.md). For the hard gates,
see [`PRE-RUN-STATUS.json`](PRE-RUN-STATUS.json).

The advisor handoff can prepare, run, and submit Kimi/Claude result artifacts
through a future PR. It does not yet automatically aggregate direct-vs-text
accuracy or compare output with prior DeepSeek/Codex runs; that generic
multi-course metrics work is a separate post-run task.
