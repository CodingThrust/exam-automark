# DSAA3071 Week 4 Full Benchmark Preparation

Status / 状态: **corrected full scope is prepared; no model has run and no
model run is authorized.**

This is the authoritative replacement for the former unrun W4 partial setup.
It prepares Q1--Q10 (130 points) for matched direct-multimodal and
transcript-first grading, with no raw student scan, identity map, human score,
or model output tracked here.

| Item / 项目 | Contract / 约定 |
| --- | --- |
| Scope / 范围 | Q1--Q10, 130 points / 130 分 |
| Page map / 页面映射 | `p01: Q1-Q4`; `p02: Q5-Q8`; `p03: Q9-Q10` |
| Rubric / 评分量表 | [`rubric_v0.json`](rubric_v0.json), official-solution-only / 仅官方答案 |
| Development / 开发集 | 7 anonymous students, inherited pre-output membership |
| Held-out / 保留集 | 15 anonymous students, sealed / 封存 |

The full anonymous source is 22 students x 3 approved pages = 66 images. A
fresh private 220-row gold template and four audited M1/T1 packets have been
created under `Data/DSAA3071/week4/benchmark/v2-full-q1-q10/`; this is not a
model invocation.

Before any model call: enter 70 development gold cells, pin actual engine and
capability IDs through approved zero-data checks, run/validate T1 lineage, and
record a separate development approval. See
[`PRE-RUN-STATUS.json`](PRE-RUN-STATUS.json) and
[`PREPARATION-CONTRACT.md`](PREPARATION-CONTRACT.md).

Development gold is checked locally against only the frozen seven-student
development split; the 15 held-out rows remain blank and sealed. Use the
explicit `validate-gold-subset` command recorded in the contract—ordinary
`validate-gold` remains the stricter full-cohort check.
For efficient development-only entry, the local reviewer must include its
separately proposed `--students-file` filter; until that generic reviewer
support is merged locally, do not use the former six-question W4 reviewer or
silently score the held-out cohort.

When Kimi Code or Claude Code is needed, the compatible advisor handoff is
already frozen as
[`advisor-workflow-development.blocked.json`](advisor-workflow-development.blocked.json).
It is deliberately blocked: it provides a repeatable future PR route, but it
cannot be activated until the gates above are complete.
When activated, it writes aggregate-only public results to a new immutable
record directory rather than overwriting this preparation record.

Current limitation / 当前限制：the handoff can prepare, run, and submit
Kimi/Claude result artifacts, but this prep record deliberately contains no
cross-model aggregate comparison yet. Direct-vs-text accuracy and comparison
with prior DeepSeek/Codex results require a separate generic multi-course
metrics/aggregation step after development gold and run outputs are ready.
