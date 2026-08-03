# Course-generic grading comparison

## Scope

- Course / assessment: `DSAA3071` / `week4_full_q1_q10`
- Questions: `10`; maximum total: `130.0` points
- Anonymous population: `7` students; `70` question scores

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
| Baseline | `deepseek` | `deepseek-v4-pro` | `text-only` | `G1` | `passed` |
| Candidate | `codex_cli / codex` | `gpt-5.6-sol` | `text-only` | `w4-development-g1-codex-gpt56sol` | `passed` |

## Aggregate metrics

| Metric | Baseline | Candidate | Candidate - baseline |
| --- | ---: | ---: | ---: |
| `exact_agreement` | 0.4143 | 0.4571 | 0.0429 |
| `subquestion_mae` | 3.4571 | 2.3857 | -1.0714 |
| `mean_signed_error` | -2.8286 | -1.4143 | 1.4143 |
| `total_score_mae` | 28.2857 | 14.1429 | -14.1429 |
| `within_1_point_rate` | 0.0000 | 0.0000 | 0.0000 |
| `severe_error_rate` | 1.0000 | 1.0000 | 0.0000 |
| `macro_accuracy` | 0.4143 | 0.4571 | 0.0429 |

## Paired bootstrap

- Unit: student; metric: exact-agreement candidate minus baseline.
- Seed / samples: `20260701` / `10000`
- Mean difference: `0.0429`
- 95% interval: `[-0.0286, 0.1143]`

## Per-question aggregate metrics

Question identifiers are course metadata, not student identities.

| Question | Rows | Baseline exact | Candidate exact | Delta exact | Baseline MAE | Candidate MAE | Delta MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Q1` | 7 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q10` | 7 | 0.0000 | 0.1429 | 0.1429 | 4.1429 | 2.7143 | -1.4286 |
| `Q2` | 7 | 0.8571 | 0.8571 | 0.0000 | 0.1429 | 0.1429 | 0.0000 |
| `Q3` | 7 | 0.8571 | 0.8571 | 0.0000 | 0.1429 | 0.1429 | 0.0000 |
| `Q4` | 7 | 0.8571 | 0.8571 | 0.0000 | 0.7143 | 0.7143 | 0.0000 |
| `Q5` | 7 | 0.0000 | 0.1429 | 0.1429 | 6.8571 | 2.5714 | -4.2857 |
| `Q6` | 7 | 0.2857 | 0.7143 | 0.4286 | 1.8571 | 1.1429 | -0.7143 |
| `Q7` | 7 | 0.0000 | 0.0000 | 0.0000 | 5.0000 | 2.8571 | -2.1429 |
| `Q8` | 7 | 0.2857 | 0.0000 | -0.2857 | 8.0000 | 7.0000 | -1.0000 |
| `Q9` | 7 | 0.0000 | 0.0000 | 0.0000 | 7.7143 | 6.5714 | -1.1429 |

## Baseline confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 44 | 0.6136 |
| `low` | 11 | 0.1818 |
| `medium` | 15 | 0.0000 |

## Candidate confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 45 | 0.6667 |
| `low` | 6 | 0.0000 |
| `medium` | 19 | 0.1053 |
