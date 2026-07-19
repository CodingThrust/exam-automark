# Physics Week 9 Model Benchmark Report v0

Status: first evidence-based model benchmark summary. This report does not run
new model calls.

## Question

For the Physics Week 9 text-only pilot, which model/skill condition currently
meets the bar of "good enough" for continued experimentation?

## Current Answer

The only condition with held-out test evidence that meets the provisional pilot
bar is:

```text
DeepSeek public API + candidate-v2 prompt/skill
```

This is not a production-grade conclusion. The severe-error rate remains high
on held-out test (`0.4444`), so the result should be reported as pilot-level
evidence only.

Codex CLI has encouraging development-split evidence, but no held-out test run
yet. Claude Code has a documented reproduction path, but no real Claude model
run yet.

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
| Codex CLI | `gpt-5.5` | development | passed, 8/8 | passed, 8/8 | directional only; held-out missing |
| Claude Code | `claude-sonnet-4-20250514` | not run | not run | not run | reproducible path only |

## Metric Summary

| Evidence | Exact agreement baseline | Exact agreement candidate | Delta | Total-score MAE baseline | Total-score MAE candidate | Severe-error delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek dev | 0.7917 | 0.8542 | +0.0625 | 2.1563 | 0.7500 | -0.2500 |
| DeepSeek held-out | 0.8102 | 0.8426 | +0.0324 | 2.2639 | 2.0833 | +0.0000 |
| Codex CLI dev | 0.8750 | 0.8958 | +0.0208 | 0.4375 | 0.5938 | +0.0000 |

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

Codex CLI candidate-v2 also improves exact agreement and subquestion MAE on the
development split:

| Metric | Baseline | Candidate-v2 | Direction |
| --- | ---: | ---: | --- |
| exact agreement | 0.8750 | 0.8958 | candidate better |
| macro accuracy | 0.8750 | 0.8958 | candidate better |
| subquestion MAE | 0.0990 | 0.0807 | candidate better |
| total-score MAE | 0.4375 | 0.5938 | candidate worse |
| within-1-point rate | 0.8750 | 0.8750 | unchanged |
| severe-error rate | 0.1250 | 0.1250 | unchanged |

Interpretation: Codex CLI is promising on dev, but cannot yet be compared as a
held-out benchmark because `G1-test-r1` has not been run.

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

## Reproducibility Notes

This report is reproducible only when the reviewer has:

- the same private `Data/` tree;
- the committed code and records from `89737fe` or later;
- the same prompt packet directories;
- the same model/provider setup;
- no prompt/rubric/transcript edits between compared arms.

`Data/` is intentionally ignored by Git. Raw student transcripts, raw model
responses, per-student output JSON, and raw prompts are not committed.

## Next Required Runs

1. Run Codex CLI baseline and candidate-v2 on `G1-test-r1`.
2. Run Claude Code baseline and candidate-v2 on `G1-dev-r1`.
3. If Claude dev validation passes, run Claude Code on `G1-test-r1`.
4. Regenerate this report with matched held-out evidence for DeepSeek, Codex
   CLI, and Claude Code.

## Next Codex Held-Out Commands

Run these only after deciding to spend the additional Codex usage. Use new
output directories if any of these paths already exist.

```powershell
$runCommit = git rev-parse --short HEAD
$model = "gpt-5.5"

python scripts\run_headless_packet.py `
  --engine codex `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-test-r1 `
  --output Data\physics\benchmark\runs\physics-week9-codex-headless\codex-baseline-text-G1-test-r1 `
  --max-retries 2 `
  --run-commit $runCommit

$baseline = $LASTEXITCODE

python scripts\run_headless_packet.py `
  --engine codex `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-candidate-v2-text-strict-schema\G1-test-r1 `
  --output Data\physics\benchmark\runs\physics-week9-codex-headless\codex-candidate-text-G1-test-r1 `
  --max-retries 2 `
  --run-commit $runCommit

$candidate = $LASTEXITCODE

"baseline exit=$baseline; candidate exit=$candidate"
```

After both arms pass validation:

```powershell
python -m benchmark.physics.cli metrics `
  --root Data\physics\benchmark `
  --baseline-run Data\physics\benchmark\runs\physics-week9-codex-headless\codex-baseline-text-G1-test-r1 `
  --candidate-run Data\physics\benchmark\runs\physics-week9-codex-headless\codex-candidate-text-G1-test-r1 `
  --output-json Data\physics\benchmark\runs\physics-week9-codex-headless\codex-heldout-G1-baseline-vs-candidate.metrics.json `
  --output-md Data\physics\benchmark\runs\physics-week9-codex-headless\codex-heldout-G1-baseline-vs-candidate.metrics.md
```
