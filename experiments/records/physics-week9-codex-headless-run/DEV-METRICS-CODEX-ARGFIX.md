# Physics Week 9 Codex Headless Dev Metrics

Status: development run completed after the Codex CLI argument fix. This is not
a held-out test result.

## Run Scope

| Field | Value |
| --- | --- |
| Course | `physics` |
| Assessment | `week9` |
| Split | `development` |
| Students | `8` |
| Score rows | `96` |
| Provider | `codex_cli` |
| Engine | `codex` |
| Model | `gpt-5.5` |
| Codex CLI version | `codex-cli 0.133.0` |
| Git commit | `0b38ebd` |

## Reproducing Commands

Baseline:

```powershell
python -m benchmark.core.cli run-headless-packet `
  --engine codex `
  --model gpt-5.5 `
  --input-mode text-only `
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1 `
  --output Data/physics/benchmark/runs/physics-week9-codex-headless/codex-baseline-text-G1-dev-r1-argfix `
  --max-retries 2 `
  --run-commit 0b38ebd
```

Candidate-v2:

```powershell
python -m benchmark.core.cli run-headless-packet `
  --engine codex `
  --model gpt-5.5 `
  --input-mode text-only `
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1 `
  --output Data/physics/benchmark/runs/physics-week9-codex-headless/codex-candidate-text-G1-dev-r1-argfix `
  --max-retries 2 `
  --run-commit 0b38ebd
```

Metrics:

```powershell
python -m benchmark.physics.cli metrics `
  --root Data/physics/benchmark `
  --baseline-run Data/physics/benchmark/runs/physics-week9-codex-headless/codex-baseline-text-G1-dev-r1-argfix `
  --candidate-run Data/physics/benchmark/runs/physics-week9-codex-headless/codex-candidate-text-G1-dev-r1-argfix
```

## Validation

| Condition | Output | Students passed |
| --- | --- | ---: |
| baseline | `codex-baseline-text-G1-dev-r1-argfix` | `8/8` |
| candidate-v2 | `codex-candidate-text-G1-dev-r1-argfix` | `8/8` |

Both outputs passed schema validation. The previous failed attempt is recorded
separately in `CODEX-DEV-ATTEMPT-1.md`; it failed before model-output
validation because the runner generated the unsupported `--ask-for-approval`
argument.

## Summary Metrics

| Metric | Baseline | Candidate-v2 | Candidate-v2 - Baseline |
| --- | ---: | ---: | ---: |
| exact_agreement | 0.8750 | 0.8958 | 0.0208 |
| macro_accuracy | 0.8750 | 0.8958 | 0.0208 |
| subquestion_mae | 0.0990 | 0.0807 | -0.0182 |
| total_score_mae | 0.4375 | 0.5938 | 0.1562 |
| within_1_point_rate | 0.8750 | 0.8750 | 0.0000 |
| severe_error_rate | 0.1250 | 0.1250 | 0.0000 |
| mean_signed_error | -0.0365 | -0.0182 | 0.0182 |

Paired student bootstrap for exact agreement, candidate minus baseline:

| Seed | Samples | Mean difference | 95% interval |
| ---: | ---: | ---: | ---: |
| 20260701 | 10000 | 0.0208 | [0.0000, 0.0521] |

## Interpretation

Candidate-v2 shows a small development-split improvement on exact agreement and
macro accuracy. It also reduces subquestion MAE, which means individual
subquestion scores are closer to gold on average.

The total-score MAE is worse for candidate-v2, and the severe error rate is
unchanged. This is useful but mixed evidence: candidate-v2 is not a clear final
winner from this dev run alone.

## Limitations

- This is a development split result, not a held-out test result.
- The sample has only 8 students, so the result is directional.
- This record compares Codex CLI baseline against Codex CLI candidate-v2 only.
- A full model benchmark still needs at least DeepSeek-vs-Codex comparison under
  the same packets, and ideally a held-out test run.
- `Data/` run directories remain ignored and are not tracked in Git.

## Privacy

No raw student transcript, raw prompt body, raw model response body, or
student-level output JSON is tracked in this record. The committed files contain
aggregate metrics and reproducibility metadata only.
