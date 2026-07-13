# Physics Metrics Comparison

- Generated at: `2026-07-13T08:10:54.437014Z`
- Benchmark root: `Data\physics\benchmark`
- Baseline run: `Data\physics\benchmark\runs\physics-week9-baseline-candidate-v2\deepseek-baseline-text-G1-dev-r1-strict-schema`
- Candidate run: `Data\physics\benchmark\runs\physics-week9-baseline-candidate-v2\deepseek-candidate-text-G1-dev-r1-strict-schema`
- Students: `8`
- Score rows: `96`

## Summary Metrics

| Metric | Baseline | Candidate | Candidate - Baseline |
|---|---:|---:|---:|
| exact_agreement | 0.7917 | 0.8542 | 0.0625 |
| total_score_mae | 2.1562 | 0.7500 | -1.4062 |
| within_1_point_rate | 0.3750 | 0.7500 | 0.3750 |
| severe_error_rate | 0.3750 | 0.1250 | -0.2500 |
| subquestion_mae | 0.2214 | 0.1042 | -0.1172 |
| mean_signed_error | -0.1797 | -0.0625 | 0.1172 |
| macro_accuracy | 0.7917 | 0.8542 | 0.0625 |

## Paired Bootstrap

- Metric: exact agreement, candidate minus baseline
- Seed: `20260701`
- Samples: `10000`
- Mean difference: `0.0625`
- 95% interval: `[0.0104, 0.1458]`
