# Development Metrics Strict Schema

Status: development split baseline and candidate v2 completed and evaluated.

Captured date: 2026-07-13, Asia/Shanghai.

## Scope

- course: `physics`
- assessment: `week9`
- split: development
- students: 8 anonymous students
- model: `deepseek-v4-pro`
- provider: `deepseek`
- endpoint: `https://api.deepseek.com`
- input mode: `text-only`
- text source status: anonymous, pilot-derived automatic transcript
- held-out test split: not run

## Valid Runs Used For Metrics

| Role | Run directory | Validation |
| --- | --- | --- |
| baseline | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-schema` | passed, 8/8 |
| candidate v2 | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-strict-schema` | passed, 8/8 |

Both valid runs used:

- model: `deepseek-v4-pro`
- temperature: `0`
- response format: `json_object`
- max retries: `1`
- run commit: `95622f0aead87187c6410ec0a38ba94cb2866dee`
- text source hash:
  `30e45836b26f6c05d0a55c2e436d5ace7078d01ae86932c3c64b27ad14e24cf8`
- rubric hash:
  `a02e0531b3d78590c66d32e76eba170d2e0400e3e4a1c60436f4f5c2c8e93b21`

Baseline packet:

- packet:
  `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1`
- prompt hash:
  `8fe0b9bb69d56109b2bbecfcdd6ca05ebe2ae9dff76efe610ecfde0d831cfa5e`
- packet hash:
  `e556b8f12cc32e975c6a27545efeddb2891cb85fa6d3060f57dec3d6abf92601`

Candidate v2 packet:

- packet:
  `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1`
- prompt hash:
  `1eb905236e6f4e4623399e4dc5cd77b80c69fa7a5ea3a2d6a2777f2dcc902c3f`
- packet hash:
  `8987ce06f54a46ba242703df0d028ffb8de56143a00a312b289e1f39fc7aed6d`

## Local Metric Artifacts

These artifacts are under ignored `Data/` and are not committed:

| Artifact | SHA-256 |
| --- | --- |
| `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/dev-metrics-strict-schema.json` | `68d40dee32f08d30a312ad39b0d86be7bd0d12da5608366ed0e337f4be487613` |
| `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/dev-student-total-errors-strict-schema.csv` | `3e1115567d1b75c7f6f6ea8656f1439b53ed2cd3b1155d14212a454c8417b176` |

## Aggregate Metrics

| Metric | Baseline | Candidate v2 | Direction |
| --- | ---: | ---: | --- |
| exact agreement | 0.7917 | 0.8542 | candidate better |
| macro accuracy | 0.7917 | 0.8542 | candidate better |
| subquestion MAE | 0.2214 | 0.1042 | candidate better |
| total score MAE | 2.1563 | 0.7500 | candidate better |
| within 1 point rate | 0.3750 | 0.7500 | candidate better |
| severe error rate | 0.3750 | 0.1250 | candidate better |
| mean signed error | -0.1797 | -0.0625 | candidate less biased |

Paired student bootstrap for candidate minus baseline exact agreement:

- mean difference: `0.0625`
- 95% interval: `[0.0104, 0.1458]`

## Per-Question Exact Agreement

| Question | Baseline | Candidate v2 |
| --- | ---: | ---: |
| Q1a | 0.875 | 0.875 |
| Q1b | 1.000 | 1.000 |
| Q1c | 0.875 | 0.875 |
| Q1d | 0.750 | 0.750 |
| Q2a | 0.500 | 0.625 |
| Q2b | 0.875 | 0.875 |
| Q3a | 0.875 | 0.875 |
| Q3b | 1.000 | 1.000 |
| Q3c | 0.750 | 0.750 |
| Q3d | 0.875 | 1.000 |
| Q3e | 0.625 | 0.750 |
| Q3f | 0.500 | 0.875 |

## Interpretation

On the development split, candidate v2 outperformed the baseline on all headline
aggregate metrics. The largest gains were lower total-score MAE and lower severe
error rate.

This is not yet a final conclusion because:

- the split has only 8 development students
- the text source is pilot-derived automatic transcript
- gold reference status is single primary rater
- held-out test split has not been run

Next step: update the Typst/PDF note with these development results, then decide
whether to freeze candidate v2 before any held-out test run.
