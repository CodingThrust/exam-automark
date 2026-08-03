# DSAA3071 Week 4 Full Benchmark: Pre-run Preparation Contract

Status / 状态: **corrected scope and rubric are frozen; this document does not
authorize a model run.**

## Scope, pages, and rubric / 范围、页面与量表

The benchmark contains Q1--Q10 for 130 points in one-point increments.

| Student packet page / 学生答卷包页面 | Question IDs / 题号 |
| --- | --- |
| `p01` | Q1, Q2, Q3, Q4 |
| `p02` | Q5, Q6, Q7, Q8 |
| `p03` | Q9, Q10 |

This mapping is user-confirmed for the approved anonymous student packets; it
is not inferred from the four-page official solution PDF. The rubric is derived
only from that official solution and contains no student examples.

## Matched conditions / 匹配条件

- **M1 / 直接多模态：** grade only approved anonymous page images.
- **T1 -> G1 / 先转录后评分：** an engine produces a fresh automatic transcript
  from the same images, then grades only its own unchanged transcript.

All compared runs must share the full course spec, rubric, prompt version,
snapshot, split, and private human gold. A later human-corrected transcript is
a separate versioned secondary route, never a silent replacement for T1.

## Answer-first policy / 先看答案的评分原则

Grade the student's actual claim first, then use reasoning to assign partial
credit, validate a claim, or detect technical contradictions. Accept semantic
equivalents and valid alternative proofs. Do not require official keywords,
exact state names, or exact case wording; do not duplicate evidence across
scoring elements.

## Gates / 模型调用前门槛

1. Exact final-approved snapshot, mapping, course, rubric, and split validate.
2. Development per-question human gold is complete and validated locally with
   `validate-gold-subset` against `students-development.txt`; this validates
   exactly 70 cells while the 15 held-out students remain blank and sealed.
3. Image M1/T1 packets pass privacy/scope/hash/split audit.
4. Exact models and supported image/transcription capabilities are pinned.
5. Each T1 is fresh; its G1 source is unchanged and passes lineage validation.
6. A separate explicit development-run approval is recorded.

Held-out packets remain sealed until a distinct approval. Passing anonymization
or packet audit alone never authorizes a model call.

## Result integration boundary / 结果整合边界

The advisor workflow can create a privacy-safe PR for Kimi/Claude run
artifacts. It does not yet compute aggregate direct-vs-text accuracy or merge
these results with prior DeepSeek/Codex runs. That generic multi-course
comparison is a separate post-run task and must not be inferred from the
presence of this preparation contract.
