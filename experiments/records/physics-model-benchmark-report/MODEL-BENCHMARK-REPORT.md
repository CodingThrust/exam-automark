# Physics Week 9 Model Benchmark Report v1

Status: Codex CLI held-out evidence added. This report summarizes completed
text-only Physics Week 9 model benchmark runs and does not contain raw student
transcripts or raw model responses.

## Question

For the Physics Week 9 text-only pilot, which model/skill condition currently
meets the bar of "good enough" for continued experimentation?

## Current Answer

Among completed held-out text-only runs, the best-supported condition is:

```text
Codex CLI + candidate-v2 prompt/skill
```

Codex CLI candidate-v2 reaches held-out exact agreement `0.8981`, improves over
the Codex baseline by `+0.0324`, and has lower total-score MAE than the Codex
baseline (`1.0833` vs `1.3194`). It also outperforms the completed DeepSeek
candidate-v2 held-out run on the aggregate metrics used in this report.

This is still a pilot-level result, not a production-grade grading claim. The
Codex CLI severe-error rate remains `0.3333`, and the paired bootstrap interval
for Codex candidate-v2 minus Codex baseline exact agreement includes zero
(`[-0.0046, 0.0833]`). Claude Code is not evaluated yet.

## Provisional Good-Enough Bar

The bar used in this v0 report is intentionally modest and should be reviewed
with the advisor before being treated as final:

- all expected students pass schema validation;
- held-out exact agreement is at least `0.84`;
- held-out exact agreement improves over the baseline under the same
  provider/model;
- held-out total-score MAE is at most `2.10` and improves over the baseline;
- held-out within-1-point rate is at least `0.50`;
- severe-error rate is reported and does not worsen.

Production use would need a stricter severe-error bar.

## Evidence Matrix

| Provider | Model | Split | Baseline validation | Candidate validation | Current status |
| --- | --- | --- | --- | --- | --- |
| DeepSeek public API | `deepseek-v4-pro` | development | passed, 8/8 | passed, 8/8 | candidate-v2 improves baseline |
| DeepSeek public API | `deepseek-v4-pro` | held-out test | passed, 18/18 | passed, 18/18 | candidate-v2 meets provisional pilot bar |
| Codex CLI | `gpt-5.5` | development | passed, 8/8 | passed, 8/8 | candidate-v2 improves exact agreement; total-score MAE worsens |
| Codex CLI | `gpt-5.5` | held-out test | passed, 18/18 | passed, 18/18 | candidate-v2 is best-supported completed condition |
| Claude Code | `claude-sonnet-4-20250514` | not run | not run | not run | reproducible path only |

## Metric Summary

| Evidence | Exact agreement baseline | Exact agreement candidate | Delta | Total-score MAE baseline | Total-score MAE candidate | Severe-error delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek dev | 0.7917 | 0.8542 | +0.0625 | 2.1563 | 0.7500 | -0.2500 |
| DeepSeek held-out | 0.8102 | 0.8426 | +0.0324 | 2.2639 | 2.0833 | +0.0000 |
| Codex CLI dev | 0.8750 | 0.8958 | +0.0208 | 0.4375 | 0.5938 | +0.0000 |
| Codex CLI held-out | 0.8657 | 0.8981 | +0.0324 | 1.3194 | 1.0833 | +0.0000 |

## Held-Out Provider Comparison

Both completed providers were evaluated on the same held-out split size
(`G1-test-r1`, 18 students, 216 subquestion score rows). The comparison below is
not a causal provider claim because Codex CLI and DeepSeek use different model
serving stacks and hidden system behavior, but it is the current practical
benchmark for deciding the next experiment.

| Held-out candidate-v2 metric | DeepSeek public API | Codex CLI | Codex minus DeepSeek |
| --- | ---: | ---: | ---: |
| exact agreement | 0.8426 | 0.8981 | +0.0556 |
| macro accuracy | 0.8426 | 0.8981 | +0.0556 |
| subquestion MAE | 0.1852 | 0.0995 | -0.0856 |
| total-score MAE | 2.0833 | 1.0833 | -1.0000 |
| within-1-point rate | 0.5000 | 0.6667 | +0.1667 |
| severe-error rate | 0.4444 | 0.3333 | -0.1111 |

Interpretation: Codex CLI candidate-v2 is the strongest completed held-out
condition by this report's aggregate metrics. The remaining blocker is still
severe errors, not schema validity or basic exact agreement.

## DeepSeek Held-Out Result

DeepSeek candidate-v2 improves over DeepSeek baseline on held-out exact
agreement, macro accuracy, subquestion MAE, total-score MAE, within-1-point
rate, and signed bias.

| Metric | Baseline | Candidate-v2 | Direction |
| --- | ---: | ---: | --- |
| exact agreement | 0.8102 | 0.8426 | candidate better |
| macro accuracy | 0.8102 | 0.8426 | candidate better |
| subquestion MAE | 0.2002 | 0.1852 | candidate better |
| total-score MAE | 2.2639 | 2.0833 | candidate better |
| within-1-point rate | 0.3333 | 0.5000 | candidate better |
| severe-error rate | 0.4444 | 0.4444 | no improvement |

Paired bootstrap for candidate minus baseline exact agreement:

```text
mean difference = 0.0324
95% interval = [0.0046, 0.0602]
```

Interpretation: candidate-v2 is the current best-supported pilot condition, but
severe errors remain the key blocker.

## Codex CLI Development Result

Codex CLI candidate-v2 improved exact agreement and subquestion MAE on the
development split:

| Metric | Baseline | Candidate-v2 | Direction |
| --- | ---: | ---: | --- |
| exact agreement | 0.8750 | 0.8958 | candidate better |
| macro accuracy | 0.8750 | 0.8958 | candidate better |
| subquestion MAE | 0.0990 | 0.0807 | candidate better |
| total-score MAE | 0.4375 | 0.5938 | candidate worse |
| within-1-point rate | 0.8750 | 0.8750 | unchanged |
| severe-error rate | 0.1250 | 0.1250 | unchanged |

Interpretation: the dev split was useful as a sanity check before spending the
held-out run. It should not be treated as the final model comparison because it
was part of the experiment development loop.

## Codex CLI Held-Out Result

Codex CLI candidate-v2 improves over Codex CLI baseline on held-out exact
agreement, macro accuracy, subquestion MAE, total-score MAE, and signed bias.
Within-1-point rate and severe-error rate are unchanged.

| Metric | Baseline | Candidate-v2 | Direction |
| --- | ---: | ---: | --- |
| exact agreement | 0.8657 | 0.8981 | candidate better |
| macro accuracy | 0.8657 | 0.8981 | candidate better |
| subquestion MAE | 0.1262 | 0.0995 | candidate better |
| total-score MAE | 1.3194 | 1.0833 | candidate better |
| within-1-point rate | 0.6667 | 0.6667 | unchanged |
| severe-error rate | 0.3333 | 0.3333 | unchanged |

Paired bootstrap for candidate minus baseline exact agreement:

```text
mean difference = 0.0324
95% interval = [-0.0046, 0.0833]
```

Interpretation: Codex CLI candidate-v2 meets the provisional pilot bar, but the
uncertainty interval says the observed exact-agreement improvement over the
Codex baseline is not yet robust enough to claim a stable model/prompt effect.

## Claude Code Status

Claude Code is not evaluated yet. The repository now contains a reproducible
Claude Code headless path:

- `experiments/records/Codex-CLI-headless-mode/CLAUDE-CODE-REPRODUCTION.md`
- `experiments/records/Codex-CLI-headless-mode/HEADLESS-RUN-PROTOCOL.md`

The expected internal command shape is:

```text
claude -p --output-format json --max-turns 1 --model claude-sonnet-4-20250514
```

Claude should not be included in model accuracy comparisons until real baseline
and candidate outputs pass validation.

## Source Artifacts

Committed summary records:

- `experiments/records/physics-week9-baseline-candidate-v2-run/DEV-METRICS-STRICT-SCHEMA.md`
- `experiments/records/physics-week9-baseline-candidate-v2-run/HELD-OUT-METRICS-STRICT-SCHEMA.md`
- `experiments/records/physics-week9-codex-headless-run/DEV-METRICS-CODEX-ARGFIX.md`
- `experiments/records/Codex-CLI-headless-mode/CLAUDE-CODE-REPRODUCTION.md`

Local ignored metrics artifacts:

- `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/dev-metrics-strict-schema.json`
- `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/held-out-metrics-strict-schema.json`
- `Data/physics/benchmark/runs/physics-week9-codex-headless/codex-dev-G1-baseline-vs-candidate-argfix.metrics.json`
- `Data/physics/benchmark/runs/physics-week9-codex-headless/codex-baseline-text-G1-test-r1`
- `Data/physics/benchmark/runs/physics-week9-codex-headless/codex-candidate-text-G1-test-r1`
- `Data/physics/benchmark/runs/physics-week9-codex-headless/codex-heldout-G1-baseline-vs-candidate.metrics.json`

## Reproducibility Notes

This report is reproducible only when the reviewer has:

- the same private `Data/` tree;
- the committed code and records from `780e75a` or later;
- the same prompt packet directories;
- the same model/provider setup;
- no prompt/rubric/transcript edits between compared arms.

`Data/` is intentionally ignored by Git. Raw student transcripts, raw model
responses, per-student output JSON, and raw prompts are not committed.

## Next Required Runs

1. Run Claude Code baseline and candidate-v2 on `G1-dev-r1`.
2. If Claude dev validation passes, run Claude Code on `G1-test-r1`.
3. Investigate severe-error cases before making an operational grading claim.
4. Regenerate this report with matched held-out evidence for DeepSeek, Codex
   CLI, and Claude Code.
