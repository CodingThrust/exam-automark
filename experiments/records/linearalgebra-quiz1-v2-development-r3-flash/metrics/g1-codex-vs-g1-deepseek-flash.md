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
| Candidate | `deepseek` | `deepseek-v4-flash` | `text-only` | `G1` | `passed` |

## Aggregate metrics

| Metric | Baseline | Candidate | Candidate - baseline |
| --- | ---: | ---: | ---: |
| `exact_agreement` | 0.8733 | 0.8633 | -0.0100 |
| `subquestion_mae` | 0.5367 | 0.8167 | 0.2800 |
| `mean_signed_error` | 0.0033 | 0.0100 | 0.0067 |
| `total_score_mae` | 3.0333 | 4.7667 | 1.7333 |
| `within_1_point_rate` | 0.5000 | 0.4667 | -0.0333 |
| `severe_error_rate` | 0.4000 | 0.5333 | 0.1333 |
| `macro_accuracy` | 0.8733 | 0.8633 | -0.0100 |

## Paired bootstrap

- Unit: student; metric: exact-agreement candidate minus baseline.
- Seed / samples: `20260701` / `10000`
- Mean difference: `-0.0100`
- 95% interval: `[-0.0433, 0.0200]`

## Per-question aggregate metrics

Question identifiers are course metadata, not student identities.

| Question | Rows | Baseline exact | Candidate exact | Delta exact | Baseline MAE | Candidate MAE | Delta MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Q1a` | 30 | 0.9333 | 0.9333 | 0.0000 | 0.3333 | 0.3333 | 0.0000 |
| `Q1b` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q1c` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q1d` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q1e` | 30 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q2a` | 30 | 0.6333 | 0.6000 | -0.0333 | 1.4333 | 2.3667 | 0.9333 |
| `Q2b` | 30 | 0.7667 | 0.8000 | 0.0333 | 0.8333 | 0.6667 | -0.1667 |
| `Q3` | 30 | 0.9667 | 0.9000 | -0.0667 | 0.0667 | 0.4667 | 0.4000 |
| `Q3bonus` | 30 | 0.9333 | 0.9667 | 0.0333 | 0.6667 | 0.3333 | -0.3333 |
| `Q4` | 30 | 0.5000 | 0.4333 | -0.0667 | 2.0333 | 4.0000 | 1.9667 |

## Baseline confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 257 | 0.9261 |
| `low` | 3 | 0.3333 |
| `medium` | 40 | 0.5750 |

## Candidate confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 253 | 0.9605 |
| `low` | 4 | 0.2500 |
| `medium` | 43 | 0.3488 |
