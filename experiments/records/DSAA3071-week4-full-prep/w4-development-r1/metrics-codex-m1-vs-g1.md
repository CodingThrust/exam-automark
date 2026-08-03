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
| Baseline | `codex_cli / codex` | `gpt-5.6-sol` | `text-only` | `w4-development-g1-codex-gpt56sol` | `passed` |
| Candidate | `codex_cli / codex` | `gpt-5.6-sol` | `multimodal` | `w4-development-m1-codex-gpt56sol` | `passed` |

## Aggregate metrics

| Metric | Baseline | Candidate | Candidate - baseline |
| --- | ---: | ---: | ---: |
| `exact_agreement` | 0.4571 | 0.4286 | -0.0286 |
| `subquestion_mae` | 2.3857 | 2.2000 | -0.1857 |
| `mean_signed_error` | -1.4143 | -1.1714 | 0.2429 |
| `total_score_mae` | 14.1429 | 11.7143 | -2.4286 |
| `within_1_point_rate` | 0.0000 | 0.0000 | 0.0000 |
| `severe_error_rate` | 1.0000 | 1.0000 | 0.0000 |
| `macro_accuracy` | 0.4571 | 0.4286 | -0.0286 |

## Paired bootstrap

- Unit: student; metric: exact-agreement candidate minus baseline.
- Seed / samples: `20260701` / `10000`
- Mean difference: `-0.0286`
- 95% interval: `[-0.0857, 0.0000]`

## Per-question aggregate metrics

Question identifiers are course metadata, not student identities.

| Question | Rows | Baseline exact | Candidate exact | Delta exact | Baseline MAE | Candidate MAE | Delta MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Q1` | 7 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Q10` | 7 | 0.1429 | 0.0000 | -0.1429 | 2.7143 | 3.4286 | 0.7143 |
| `Q2` | 7 | 0.8571 | 0.8571 | 0.0000 | 0.1429 | 0.1429 | 0.0000 |
| `Q3` | 7 | 0.8571 | 0.8571 | 0.0000 | 0.1429 | 0.1429 | 0.0000 |
| `Q4` | 7 | 0.8571 | 0.8571 | 0.0000 | 0.7143 | 0.7143 | 0.0000 |
| `Q5` | 7 | 0.1429 | 0.1429 | 0.0000 | 2.5714 | 1.7143 | -0.8571 |
| `Q6` | 7 | 0.7143 | 0.5714 | -0.1429 | 1.1429 | 1.1429 | 0.0000 |
| `Q7` | 7 | 0.0000 | 0.0000 | 0.0000 | 2.8571 | 2.8571 | 0.0000 |
| `Q8` | 7 | 0.0000 | 0.0000 | 0.0000 | 7.0000 | 5.0000 | -2.0000 |
| `Q9` | 7 | 0.0000 | 0.0000 | 0.0000 | 6.5714 | 6.8571 | 0.2857 |

## Baseline confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 45 | 0.6667 |
| `low` | 6 | 0.0000 |
| `medium` | 19 | 0.1053 |

## Candidate confidence accuracy

| Confidence | Score rows | Exact agreement |
| --- | ---: | ---: |
| `high` | 58 | 0.5172 |
| `medium` | 12 | 0.0000 |
