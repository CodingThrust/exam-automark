# Course-generic grading comparison

## Scope

- Course / assessment: `linearalgebra` / `quiz1`
- Questions: `10`; maximum total: `100.0` points
- Anonymous population: `30` students; `300` question scores

This report is aggregate-only. It excludes student IDs, individual scores, raw answers, evidence, prompts, model responses, and private paths.

## Run provenance

| Check | Status |
| --- | --- |
| Run validation | `passed` |
| Course/assessment metadata | `matched` |
| Anonymous population | `matched_by_exact_question_coverage` |
| Data-snapshot relation | `matched` |

| Run | Provider / engine | Model | Input mode | Condition | Validation |
| --- | --- | --- | --- | --- | --- |
| Baseline | `codex_cli / codex` | `gpt-5.6-sol` | `multimodal` | `M1-codex-v5_2_r2-dev-r2` | `passed` |
| Candidate | `deepseek` | `deepseek-v4-pro` | `text-only` | `G1` | `passed` |

## Aggregate metrics

| Metric | Baseline | Candidate | Candidate - baseline |
| --- | ---: | ---: | ---: |
| `exact_agreement` | 0.8900 | 0.8467 | -0.0433 |
| `subquestion_mae` | 0.5100 | 1.2067 | 0.6967 |
| `mean_signed_error` | 0.1567 | -0.9467 | -1.1033 |
| `total_score_mae` | 2.5333 | 8.6333 | 6.1000 |
| `within_1_point_rate` | 0.5000 | 0.2667 | -0.2333 |
| `severe_error_rate` | 0.4667 | 0.6667 | 0.2000 |
| `macro_accuracy` | 0.8900 | 0.8467 | -0.0433 |

## Paired bootstrap

- Unit: student; metric: exact-agreement candidate minus baseline.
- Seed / samples: `20260701` / `10000`
- Mean difference: `-0.0433`
- 95% interval: `[-0.0733, -0.0167]`

## Per-question aggregate metrics

Question identifiers are course metadata, not student identities.

| Question | Rows | Baseline exact | Candidate exact | Delta exact | Baseline MAE | Candidate MAE | Delta MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Q1a` | 30 | 0.9333 | 0.9667 | 0.0333 | 0.3333 | 0.1667 | -0.1667 |
| `Q1b` | 30 | 1.0000 | 0.9333 | -0.0667 | 0.0000 | 0.3333 | 0.3333 |
| `Q1c` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q1d` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q1e` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q2a` | 30 | 0.7667 | 0.5667 | -0.2000 | 1.5333 | 2.3333 | 0.8000 |
| `Q2b` | 30 | 0.8000 | 0.8333 | 0.0333 | 0.7333 | 0.8667 | 0.1333 |
| `Q3` | 30 | 0.9333 | 0.8667 | -0.0667 | 0.1667 | 0.7667 | 0.6000 |
| `Q3bonus` | 30 | 0.9333 | 0.9667 | 0.0333 | 0.6667 | 0.3333 | -0.3333 |
| `Q4` | 30 | 0.5333 | 0.3333 | -0.2000 | 1.6667 | 7.2667 | 5.6000 |

## Baseline confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 286 | 0.9091 |
| `medium` | 14 | 0.5000 |

## Candidate confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 273 | 0.9084 |
| `low` | 3 | 0.0000 |
| `medium` | 24 | 0.2500 |
