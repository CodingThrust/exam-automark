# Week 4 Full Engine and Modality Plan

Status / 状态: **planned only; no row below is authorized yet.**

The development split is the first and only planned target. Held-out remains
sealed until development results, error cases, and a separate approval exist.

| Engine / 引擎 | Direct M1 images | T1 image transcript | G1 own unchanged T1 | Execution route / 执行位置 |
| --- | --- | --- | --- | --- |
| Codex CLI | planned | planned | planned | local after `codex.cmd` login, capability check, and model pinning |
| Kimi Code | planned | planned | planned | advisor computer via `.agents/skills/run-submit-grading-benchmark/SKILL.md` |
| Claude Code | planned | planned | planned | advisor computer via the same compatible submission skill |

DeepSeek is not claimed as a symmetric multimodal arm: the current local API
integration can grade a text packet but does not implement automatic T1 and has
not yet validated vision input for the exact future model. Once Codex/Kimi/
Claude T1 outputs are frozen and lineage-valid, DeepSeek may grade each source
text separately; that supports same-transcript and transcript-source-sensitivity
comparisons, not a direct-multimodal claim.

Order / 顺序:

1. Complete the 70 development gold cells, then locally run
   `validate-gold-subset` with `students-development.txt`; this authorizes
   development analysis only, never the sealed held-out rows.
2. Pin actual models through approved zero-data checks.
3. Create a versioned activation configuration and record explicit approval.
4. Run image-capable engines' T1, validate unchanged lineage, then run M1/G1.
5. Build DeepSeek text-only packets from validated T1 outputs.
6. Analyze development errors; request separately before held-out execution.

The advisor skill remains available when Kimi/Claude are needed. It must receive
a new approved activation configuration and submit results through a GitHub PR;
it must never receive a gold table or bypass the frozen scope/split/lineage gates.
It does not yet aggregate those outputs with existing DeepSeek/Codex results;
that requires a separate generic multi-course metrics step after runs exist.
