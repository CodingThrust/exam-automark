# Physics Metrics Comparison

- Generated at: `2026-07-13T08:10:39.173606Z`
- Benchmark root: `Data\physics\benchmark`
- Baseline run: `Data\physics\benchmark\runs\physics-week9-baseline-candidate-v2\deepseek-baseline-text-G1-test-r1-strict-schema`
- Candidate run: `Data\physics\benchmark\runs\physics-week9-baseline-candidate-v2\deepseek-candidate-text-G1-test-r1-strict-schema`
- Students: `18`
- Score rows: `216`

## Summary Metrics

| Metric | Baseline | Candidate | Candidate - Baseline |
|---|---:|---:|---:|
| exact_agreement | 0.8102 | 0.8426 | 0.0324 |
| total_score_mae | 2.2639 | 2.0833 | -0.1806 |
| within_1_point_rate | 0.3333 | 0.5000 | 0.1667 |
| severe_error_rate | 0.4444 | 0.4444 | 0.0000 |
| subquestion_mae | 0.2002 | 0.1852 | -0.0150 |
| mean_signed_error | -0.1539 | -0.1389 | 0.0150 |
| macro_accuracy | 0.8102 | 0.8426 | 0.0324 |

## Paired Bootstrap

- Metric: exact agreement, candidate minus baseline
- Seed: `20260701`
- Samples: `10000`
- Mean difference: `0.0324`
- 95% interval: `[0.0046, 0.0602]`
