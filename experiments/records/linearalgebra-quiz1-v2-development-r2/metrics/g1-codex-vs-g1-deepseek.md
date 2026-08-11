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
| Baseline | `codex_cli / codex` | `gpt-5.6-sol` | `text-only` | `G1-codex-v5_2_r2-dev-r2` | `passed` |
| Candidate | `deepseek` | `deepseek-v4-pro` | `text-only` | `G1` | `passed` |

## Aggregate metrics

| Metric | Baseline | Candidate | Candidate - baseline |
| --- | ---: | ---: | ---: |
| `exact_agreement` | 0.8733 | 0.8467 | -0.0267 |
| `subquestion_mae` | 0.5367 | 1.2067 | 0.6700 |
| `mean_signed_error` | 0.0033 | -0.9467 | -0.9500 |
| `total_score_mae` | 3.0333 | 8.6333 | 5.6000 |
| `within_1_point_rate` | 0.5000 | 0.2667 | -0.2333 |
| `severe_error_rate` | 0.4000 | 0.6667 | 0.2667 |
| `macro_accuracy` | 0.8733 | 0.8467 | -0.0267 |

## Paired bootstrap

- Unit: student; metric: exact-agreement candidate minus baseline.
- Seed / samples: `20260701` / `10000`
- Mean difference: `-0.0267`
- 95% interval: `[-0.0533, 0.0000]`

## Per-question aggregate metrics

Question identifiers are course metadata, not student identities.

| Question | Rows | Baseline exact | Candidate exact | Delta exact | Baseline MAE | Candidate MAE | Delta MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Q1a` | 30 | 0.9333 | 0.9667 | 0.0333 | 0.3333 | 0.1667 | -0.1667 |
| `Q1b` | 30 | 1.0000 | 0.9333 | -0.0667 | 0.0000 | 0.3333 | 0.3333 |
| `Q1c` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q1d` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q1e` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q2a` | 30 | 0.6333 | 0.5667 | -0.0667 | 1.4333 | 2.3333 | 0.9000 |
| `Q2b` | 30 | 0.7667 | 0.8333 | 0.0667 | 0.8333 | 0.8667 | 0.0333 |
| `Q3` | 30 | 0.9667 | 0.8667 | -0.1000 | 0.0667 | 0.7667 | 0.7000 |
| `Q3bonus` | 30 | 0.9333 | 0.9667 | 0.0333 | 0.6667 | 0.3333 | -0.3333 |
| `Q4` | 30 | 0.5000 | 0.3333 | -0.1667 | 2.0333 | 7.2667 | 5.2333 |

## Baseline confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 257 | 0.9261 |
| `low` | 3 | 0.3333 |
| `medium` | 40 | 0.5750 |

## Candidate confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 273 | 0.9084 |
| `low` | 3 | 0.0000 |
| `medium` | 24 | 0.2500 |
