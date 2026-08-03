# DSAA3071 Week 6 Engine and Modality Matrix

Status / 状态: **design only; all rows below are blocked until the gates in
[`PRE-RUN-STATUS.json`](PRE-RUN-STATUS.json) are ready.**

## Why the engines are not treated identically / 为什么引擎不强行对称

Codex CLI, Kimi Code, and Claude Code are planned as image-capable engines:
each can have a direct image-grade route (M1), a fresh image-transcription route
(T1), and an own-transcript text-grade route (G1).

DeepSeek is available locally through the project's API-grade runner, but the
current integration does **not** implement a T1 transcription runner and has
not established that the eventual pinned model accepts image input. It therefore
must not be reported as a direct-multimodal versus text-first comparison unless
a separately authorized zero-data capability check and adapter validation pass.

## Development matrix / Development 实验矩阵

| Engine / 引擎 | M1 direct images | T1 images -> transcript | G1 own unchanged transcript | Where / 在哪里执行 |
| --- | --- | --- | --- | --- |
| Codex CLI | planned | planned | planned | local, after `codex.cmd` login and model pinning |
| Kimi Code | planned | planned | planned | advisor computer through `run-submit-grading-benchmark` skill |
| Claude Code | planned | planned | planned | advisor computer through the same skill |

After those three frozen T1 outputs exist, DeepSeek has three safe text-only
cross-source rows:

| Engine / 引擎 | Text input source / 文本来源 | Claim permitted / 可报告结论 |
| --- | --- | --- |
| DeepSeek | Codex T1 | same-transcript text-grading comparison |
| DeepSeek | Kimi T1 | transcript-source sensitivity and same-transcript comparison |
| DeepSeek | Claude T1 | transcript-source sensitivity and same-transcript comparison |

This is 12 planned development stages: 3 T1 + 6 M1/G1 + 3 DeepSeek text-only.
It deliberately does not label DeepSeek as multimodal without a validated
capability check.

Kimi and Claude are not removed from the plan: when their execution is needed,
the advisor runs the prior repository skill at
`.agents/skills/run-submit-grading-benchmark/SKILL.md` (or its compatible
Claude/Codex/OpenCode installation). The skill extracts the approved input,
records decision points, and submits results by a GitHub PR; it must consume a
new activation config rather than this blocked template.

## Mandatory order / 强制顺序

1. Complete only development gold first (7 students x 10 questions = 70 cells).
2. Pin engine/model identifiers using approved zero-data checks; do not reuse
   historical aliases as if they were current.
3. Record explicit development approval in a new activation configuration.
4. Run T1 for each image-capable engine and validate output/lineage.
5. Run M1 and each engine's G1 on the same development split.
6. Build and run DeepSeek text-only packets from each validated T1 source.
7. Compare only like-for-like data snapshots and inspect error cases.
8. Request a separate approval before any held-out packet is run.

No gold file may enter a model packet. All public reports must be aggregate-only
and exclude anonymous IDs, student work, individual scores, transcripts, and
private paths.
