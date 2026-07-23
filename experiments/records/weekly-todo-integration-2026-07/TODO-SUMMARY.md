# Weekly TODO Integration Summary

Date: 2026-07-21

Branch: `codex/weekly-todo-integration-2026-07`

This record consolidates the advisor TODOs that were developed across the main
`exam-automark` repository and several isolated worktrees. It is a navigation
and status document: it points to the durable artifacts, states what can be
claimed now, and separates completed work from follow-up experiments.

No raw student submissions, identity maps, API keys, raw model responses, or
files under `Data/` are committed in this integration record.

## Priority Update: 2026-07-23

The advisor-run automation is now the highest priority because it shortens the
feedback loop for every later Kimi/Claude experiment. The working order is:

1. **P0 — advisor run-and-submit skill:** configure the advisor environment,
   extract matched inputs, run Kimi Code and Claude Code in both text-only and
   multimodal modes, validate/package failures as well as successes, and open a
   GitHub PR automatically.
2. **P1 — failure retrospectives:** correct the SkillOpt R4 explanation,
   including why the candidate failed validation and which cases regressed;
   apply the same template to every failed experiment.
3. **P2 — automated Codex CLI versus Claude Code multimodal comparison:** use
   matched packets and the same reporting contract.
4. **P3 — mainline grading audit:** use the latest model to diagnose current
   candidate-v3.2 defects at private Sxxx/Qx level, aggregate objective error
   types, recommend changes, and measure confidence calibration.
5. **P4 — teach and choose:** explain the quantum.harness/beginner-training and
   sci-brain survey lessons in accessible detail, then present project changes
   for user selection.
6. **P5 — finish autoresearch:** complete the live dev-only loop after the
   metric, failure, and PR handoff pipeline is stable.

P0 implementation is on branch `feat/advisor-run-submit-skill`:

- `.agents/skills/run-submit-grading-benchmark/`
- `.claude/skills/run-submit-grading-benchmark/`
- `scripts/advisor_experiment.py`
- `benchmark/core/advisor_workflow.py`
- `experiments/records/advisor-run-submit-skill/README.md`

Current verification: both skill copies validate and match; the full
Kimi/Claude × text/multimodal × baseline/candidate development matrix completed
an offline 8-arm smoke run with `8/8` schema-valid outputs in every arm. No
external model was called. The current text packet provenance is explicitly
reported as `automatic-transcript`, while the direct-image packets are checked
against the page-level privacy review. Live advisor credentials and a real
result PR remain the acceptance test after merge.

## Executive Status

| Item | Status | Claim |
| --- | --- | --- |
| quantum.harness / beginner-training review | Done | Useful as a reproducibility-pattern reference, not as a dependency. |
| SkillOpt on Physics Week 9 | Run, negative result | Integrated and run with DeepSeek; R4 completed reliably but did not improve held-out hard accuracy. |
| Training/test-set oral explanation | Ready for oral report | We can explain why dev/train is used for iteration and held-out test is used only for final evaluation. |
| sci-brain survey reports | Done in this integration branch | Two PDF survey reports are committed. |
| Codex CLI headless and Claude headless reproduction | Done | Headless prompt, Python runner, and Claude Code reproduction guide are committed. |
| DSAA3071 W2/W3/W4/W6 source organization | Done as inventory | Source PDFs are organized and fingerprinted; anonymization/model runs are not started. |
| Physics multi-model benchmark | Partially done | DeepSeek and Codex CLI are reported; Kimi/Claude remain external/advisor-run or future runs. |
| autoresearch workflow design | MVP dry-run scaffold | A conservative one-prompt research-loop design and deterministic dry-run are committed; no model calls were made. |

## TODO 1: quantum.harness / beginner-training

Advisor request:

> Review `https://github.com/QuantumBFS/quantum.harness` and `/beginer-training`.

Artifact:

- `experiments/records/tooling-surveys/quantum-harness-beginner-training.md`

Current claim:

`quantum.harness` should not be treated as a direct dependency for
`exam-automark`. Its value is methodological: it shows how to organize
reproducible agentic experiments around a structured source of truth, pre-run
readiness gates, private raw-data isolation, and derived reports.

Reusable ideas for `exam-automark`:

- Use `experiment.json`, prompt packet manifests, run metadata, and metrics as
  the source of truth.
- Keep reusable knowledge, skills/prompts, raw run outputs, and reports in
  separate layers.
- Confirm drift-sensitive settings before model runs: course, assessment,
  split, rubric, skill/prompt version, provider/model, input mode, data snapshot
  hash, and schema.
- Treat reports as derived artifacts, not as manually edited sources of truth.

Limitation:

This was a tooling/reproducibility review only. We did not run the external
quantum project, migrate its toolchain, or depend on its quantum-physics code.

## TODO 2: SkillOpt On Physics Dataset

Advisor request:

> Try SkillOpt. Output: on physics dataset, show improvement in score accuracy.

Main artifacts:

- `experiments/records/physics-skillopt-pilot/`
- `experiments/records/physics-skillopt-adapter/`
- `experiments/records/physics-skillopt-deepseek-training-run/`
- `experiments/records/physics-skillopt-target-reliability/`
- `experiments/records/physics-skillopt-deepseek-r4-run/RUN-PROTOCOL.md`
- `experiments/records/physics-skillopt-deepseek-r4-run/RESULT-SUMMARY.md`

Relevant implementation:

- `benchmark/physics/skillopt.py`
- `benchmark/physics/skillopt_adapter.py`
- `benchmark/physics/skillopt_preflight.py`
- `benchmark/physics/skillopt_training.py`
- `tests/benchmark/physics/test_skillopt.py`
- `tests/benchmark/physics/test_skillopt_adapter.py`
- `tests/benchmark/physics/test_skillopt_preflight.py`
- `tests/benchmark/physics/test_skillopt_training.py`

What was done:

- Exported a Physics Week 9 text split for SkillOpt.
- Built a local SkillOpt `physics_grading` adapter and smoke validation.
- Prepared a no-secret DeepSeek training package.
- Ran R3 and diagnosed Windows UTF-8, JSON output, and target-reliability
  issues.
- Added a target preflight check.
- Ran R4 with target max tokens raised to 12,000 and target timeout raised to
  240 seconds.

R4 safe aggregate result:

- Baseline held-out hard score: 0.2778.
- Final held-out hard score: 0.2222.
- Held-out hard-score delta: -0.0556.
- Baseline held-out soft score: 0.8380.
- Final held-out soft score: 0.8426.
- Accepted edits: 0.
- Rejected edits: 1.
- Total tokens: 616,435.
- Wall time: about 70.3 minutes.

Current claim:

SkillOpt was integrated and run on the physics dataset, but the completed R4
run did not improve held-out hard score accuracy. This is a valid negative
experimental result, not a positive SkillOpt result.

Important terminology:

In SkillOpt records, "baseline" means the pre-optimization seed skill evaluated
inside SkillOpt. It does not necessarily mean the original Physics Week 9
baseline prompt from the earlier DeepSeek/Codex benchmark. Future SkillOpt runs
should pin the exact candidate prompt file and prompt hash as `skill_init` to
avoid ambiguity.

Recommended next step if the advisor still requires a positive SkillOpt result:

- Do not simply rerun R4.
- Design R5 around exact candidate prompt seeding, a softer primary metric
  such as MAE or severe-error rate, or a smaller high-disagreement question
  subset.
- Keep held-out test locked until the new development gate passes.

## Training Set And Test Set Oral Explanation

Short oral version:

Training/development data is where we are allowed to inspect errors, adjust the
rubric, revise the grading skill, and calibrate prompts. The held-out test set
is kept separate so we can measure whether the final method generalizes beyond
the examples used during iteration.

Why this matters:

- If we tune on the same students we use for the final result, the score can be
  overfit and not reproducible as a real conclusion.
- Development results are useful for debugging and design.
- Held-out test results are the evidence used for the final claim.
- A negative held-out result is still scientifically useful because it prevents
  us from overstating a prompt or skill improvement.

For this project:

- Physics Week 9 dev was used for prompt/skill iteration and SkillOpt train /
  validation splits.
- Physics Week 9 test was used as held-out evidence for DeepSeek/Codex
  benchmark reporting and SkillOpt final reporting.
- DSAA3071 Week 5 currently has development-style runs only; it should not be
  presented as final cross-course evidence yet.

## TODO 4: sci-brain Survey Reports

Advisor request:

> Use sci-brain survey skill to do a survey on optimizing skills and paper
> marking / LLM-based approaches. Output: two PDF files.

Artifacts:

- `experiments/records/literature-surveys/README.md`
- `experiments/records/literature-surveys/skill_optimization_survey.pdf`
- `experiments/records/literature-surveys/skill_optimization_survey.typ`
- `experiments/records/literature-surveys/llm_grading_survey.pdf`
- `experiments/records/literature-surveys/llm_grading_survey.typ`
- `experiments/records/literature-surveys/references.bib`
- `experiments/records/literature-surveys/sci_brain_run_manifest.json`
- `.knowledge/INDEX.md`
- `.knowledge/NOTES.md`
- `.knowledge/references.bib`

Current claim:

Two PDF survey reports are now committed. They are background research
artifacts, not grading experiment results. They contain no raw student data and
did not read or modify `Data/`.

Limitation:

The local Codex session did not have dedicated paper-search MCP tools available.
The sci-brain workflow therefore used WebSearch-style discovery and visible
arXiv/Semantic Scholar metadata, with unverified historical items marked as
needing verification.

## TODO 5: Codex CLI Headless Mode And Claude Headless Reproduction

Advisor request:

> Use codex cli mode in headless mode. Output: a headless mode prompt and
> reproducing python script for headless mode, better also support claude
> headless mode.

Artifacts:

- `experiments/records/Codex-CLI-headless-mode/headless-mode-prompt.md`
- `experiments/records/Codex-CLI-headless-mode/HEADLESS-RUN-PROTOCOL.md`
- `experiments/records/Codex-CLI-headless-mode/CLAUDE-CODE-REPRODUCTION.md`
- `scripts/run_headless_packet.py`
- `benchmark/core/headless_runner.py`
- `tests/benchmark/core/test_headless_runner.py`

Current claim:

Codex CLI headless mode is supported as a reproducible text-only grading
runner. Claude Code reproduction instructions are documented so an advisor can
repeat the packet-based workflow using Claude Code instead of Codex CLI.

Relation to earlier DeepSeek experiments:

DeepSeek API runs and Codex CLI headless runs can be compared because both use
the same audited prompt packets and schema. Codex CLI is effectively a
ChatGPT/Codex-family model path, while DeepSeek is the OpenAI-compatible API
path.

Limitation:

Claude Code support is documented as reproduction guidance. We have not run a
local Claude Code benchmark ourselves in this repository.

## TODO 6: DSAA3071 W2/W3/W4/W6 Source PDFs

Advisor request:

> DSAA3071, solutions, W2, W3, W4, W6: output PDFs in this stream.

Artifact:

- `experiments/records/DSAA3071-w2-w6-source-inventory/README.md`
- `experiments/records/DSAA3071-w2-w6-source-inventory/source-inventory.json`

Current claim:

The W2/W3/W4/W6 student-answer PDFs and matching question-plus-solution PDFs
have been organized and fingerprinted in a tracked inventory.

Data policy:

The actual PDFs remain under ignored `Data/DSAA3071/` and private data storage.
The tracked inventory contains only repo-relative paths, sizes, page counts,
and SHA-256 hashes.

Limitation:

This is source organization only. These weeks are not anonymized, transcribed,
rubric-scaffolded, or model-run-ready yet.

Recommended next step:

Choose one week, anonymize it, manually approve privacy, create rubric/gold
score files, build prompt packets, and only then run models.

## TODO 7: Scale Up Dataset And Benchmark Models

Advisor request:

> Scale up dataset, focus more on Codex. First, do a benchmark on different
> models, see which model meets the bar of "good enough". Output: a benchmark
> report.

Artifacts:

- `experiments/records/physics-codex-benchmark-report/MODEL-BENCHMARK-REPORT.md`
- `experiments/records/physics-codex-benchmark-report/model-benchmark-summary.json`
- `experiments/records/physics-codex-benchmark-report/note.typ`
- `experiments/records/physics-codex-benchmark-report/note.pdf`
- `docs/index.md`
- `docs/ai-grading-test-handoff.md`

Current claim:

Physics Week 9 has a benchmark report comparing completed DeepSeek API and
Codex CLI headless runs on baseline vs candidate-v2. The GitHub Pages handoff
page tells the advisor's AI how to recover private `Data/` from HKUST-GZ GitLab
and run Kimi/Claude-style tests without using YY's credentials.

Limitation:

This is not yet a full multi-model benchmark. Kimi and Claude results are not
included in the committed Typst/PDF report unless the advisor or a local runner
returns validated outputs. The Kimi API attempt did not become a completed
model result in this repository.

Recommended next step:

Collect advisor-run Kimi/Claude outputs or run them locally with valid
credentials, validate outputs against the schema, compute metrics, and update
the Typst/PDF benchmark report.

## TODO 8: autoresearch Workflow Design

Advisor request:

> autoresearch: `https://github.com/karpathy/autoresearch`. Output: an
> autoresearch repo, such that with a single prompt, we can run autoresearch
> experiment.

Artifacts:

- `experiments/records/autoresearch-design/README.md`
- `experiments/records/autoresearch-design/program.md`
- `experiments/records/autoresearch-design/run_experiment.py`
- `experiments/records/autoresearch-design/schema.json`

Current claim:

A conservative autoresearch design scaffold and minimal executable dry-run are
committed. It adapts the single-prompt autoresearch idea to grading-skill
experiments by keeping the editable surface narrow, evaluating candidates
against fixed dev metrics, and locking held-out tests behind a gate.

MVP dry-run artifacts:

- `experiments/records/autoresearch-design/single-prompt.md`
- `experiments/records/autoresearch-design/run-dry-run.ps1`
- `experiments/records/autoresearch-design/dry-run-result.json`

Limitation:

This is still not the full advisor-requested autoresearch system. It can run a
deterministic control-loop dry-run from one prompt, but it is not yet wired to
generate candidate skills with a live model, run full model experiments end to
end, or update reports automatically.

Recommended next step:

Use it after the core metric/report pipeline is stable. The first real loop
should operate only on dev packets and should not access gold scores or held-out
test outputs inside the candidate prompt.

## Related Mainline Progress: DSAA3071 Week 5

Although not one of the numbered advisor TODOs above, DSAA3071 Week 5 is the
current cross-course pilot.

Relevant artifacts:

- `experiments/records/DSAA3071-week5-prep/`
- `experiments/records/DSAA3071-week5-dev-model-run/`
- `experiments/records/DSAA3071-week5-candidate-v3-dev-plan/`
- `experiments/records/DSAA3071-week5-candidate-v31-dev-plan/`
- `experiments/skill_versions/skill_candidate_v3.json`
- `experiments/skill_versions/skill_candidate_v3_1.json`
- `experiments/skill_versions/skill_candidate_v3_1_r2.json`
- `experiments/skill_versions/skill_candidate_v3_2.json`

Current claim:

DSAA3071 Week 5 has anonymous/reviewed development packets, official
per-question gold scores, and candidate-v3.x concept-grading skill iterations.
This work helped clarify that concept/open-ended grading needs different rules
from physics calculation grading.

Limitation:

It is still a development pilot. It should not be presented as final
cross-course evidence until there is a locked held-out split and a final report.

## What Can Be Reported Now

Safe advisor-facing summary:

1. The reproducible experiment framework now has prompt packets, readiness
   gates, model runners, metrics, Typst/PDF reports, headless runner support,
   and data/privacy separation.
2. Physics Week 9 is the most complete benchmark: DeepSeek API and Codex CLI
   headless have completed text-only runs and a report.
3. SkillOpt has been integrated and run, but the R4 result is negative: no
   held-out hard accuracy improvement was observed.
4. DSAA3071 is being scaled up carefully: Week 5 has development experiments,
   while W2/W3/W4/W6 are currently source-inventory-ready only.
5. sci-brain and autoresearch outputs are now available as research-background
   and workflow-design/MVP dry-run artifacts, not as direct grading conclusions.

## What Remains Before A Strong Final Claim

- Add Kimi/Claude benchmark results or explicitly mark them as pending external
  runs.
- Decide the "good enough" threshold for grading: total-score MAE, severe error
  rate, per-question exact score, or full-paper exact match.
- Create at least one more course/assessment with locked held-out evaluation,
  not only development packets.
- For SkillOpt, run a redesigned R5 only if needed, using exact candidate prompt
  seeding and a metric less brittle than full-paper exact hard score.
- Keep private source PDFs and raw model outputs in `Data/` / HKUST-GZ GitLab,
  not in public GitHub.

## Chinese Briefing Notes

本周可以这样讲：

- 我们不是只在聊天里做实验，而是把实验拆成了可复现的记录、命令、
  prompt packet、schema、metrics 和 Typst/PDF 报告。
- Physics 是当前最完整的 benchmark：DeepSeek 和 Codex CLI 都有可复现
  结果，Codex CLI 可以作为 ChatGPT/Codex 路径与 DeepSeek 对照。
- SkillOpt 已经接入并跑通，但 R4 没有提升 held-out hard accuracy，所以
  应该诚实报告为负结果，而不是强行说 improved accuracy。
- DSAA3071 Week 5 用来推动概念题/open-ended 评分规则，W2/W3/W4/W6 目前
  只是整理和 fingerprint 完成，还没进入匿名化和模型评分。
- sci-brain survey 和 autoresearch 目前是研究背景和工作流设计产物，不是
  评分实验结论。
- 下一步要么补齐 Kimi/Claude 多模型结果并更新 benchmark report，要么选择
  一个 DSAA3071 新 week 继续匿名化、建 rubric/gold、跑模型。
