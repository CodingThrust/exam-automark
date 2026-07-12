# Held-Out Metrics Strict Schema

Status: held-out baseline and candidate v2 runs completed, validated, and
evaluated.

Captured date: 2026-07-13, Asia/Shanghai.

## Scope

- course: `physics`
- assessment: `week9`
- split: held-out test
- students: 18 anonymous students
- model: `deepseek-v4-pro`
- provider: `deepseek`
- endpoint: `https://api.deepseek.com`
- input mode: `text-only`
- text source status: anonymous, pilot-derived automatic transcript
- candidate status: frozen in `CANDIDATE-V2-FREEZE.md`

## Valid Runs Used For Metrics

| Role | Run directory | Validation | Notes |
| --- | --- | --- | --- |
| baseline | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-test-r1-strict-schema` | passed, 18/18 | `S005` and `S009` required 2 attempts |
| candidate v2 | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-test-r1-strict-schema` | passed, 18/18 | `S025` required 2 attempts |

Both valid runs used:

- model: `deepseek-v4-pro`
- temperature: `0`
- response format: `json_object`
- max retries: `1`
- run commit: `9cce18378abb19d817040cb56599457108d7d575`
- text source hash:
  `df3b16d21a24b8427ec6adf638dec836f5a5834bc92f8d80044f33868d06f1f3`
- rubric hash:
  `a02e0531b3d78590c66d32e76eba170d2e0400e3e4a1c60436f4f5c2c8e93b21`

Baseline packet:

- packet:
  `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-test-r1`
- prompt hash:
  `8fe0b9bb69d56109b2bbecfcdd6ca05ebe2ae9dff76efe610ecfde0d831cfa5e`
- packet hash:
  `53be0b2ae80adb39b7fbb08405d7a076e036dcd547f5469254b630ad11960c18`
- started UTC: `2026-07-12T18:03:43.858922Z`
- ended UTC: `2026-07-12T18:44:06.543615Z`
- total tokens: `275482`

Candidate v2 packet:

- packet:
  `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-test-r1`
- prompt hash:
  `1eb905236e6f4e4623399e4dc5cd77b80c69fa7a5ea3a2d6a2777f2dcc902c3f`
- packet hash:
  `bd369e450a9b2cf534cba2fa3c9862f6c81125d7d9709a9af1c3f3641a2a6dd7`
- started UTC: `2026-07-12T18:44:07.100683Z`
- ended UTC: `2026-07-12T19:23:35.343887Z`
- total tokens: `294056`

## Local Metric Artifacts

These artifacts are under ignored `Data/` and are not committed:

| Artifact | SHA-256 |
| --- | --- |
| `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/held-out-metrics-strict-schema.json` | `a3603da725da8756fc3e455b65983cf3f0a5065901593b633a21137c0d854de9` |
| `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/held-out-student-total-errors-strict-schema.csv` | `3ff370986be4212bf5eeb6fc1dcf3547ab5b5427b7761d0abe88d75d0412bbc7` |

## Aggregate Metrics

| Metric | Baseline | Candidate v2 | Direction |
| --- | ---: | ---: | --- |
| exact agreement | 0.8102 | 0.8426 | candidate better |
| macro accuracy | 0.8102 | 0.8426 | candidate better |
| subquestion MAE | 0.2002 | 0.1852 | candidate better |
| total score MAE | 2.2639 | 2.0833 | candidate better |
| within 1 point rate | 0.3333 | 0.5000 | candidate better |
| severe error rate | 0.4444 | 0.4444 | no improvement |
| mean signed error | -0.1539 | -0.1389 | candidate slightly less biased |

Paired student bootstrap for candidate minus baseline exact agreement:

- mean difference: `0.0324`
- 95% interval: `[0.0046, 0.0602]`

## Per-Question Exact Agreement

| Question | Baseline | Candidate v2 | Difference |
| --- | ---: | ---: | ---: |
| Q1a | 0.8889 | 0.8889 | 0.0000 |
| Q1b | 0.9444 | 0.9444 | 0.0000 |
| Q1c | 0.7778 | 0.9444 | 0.1667 |
| Q1d | 0.8333 | 0.7778 | -0.0556 |
| Q2a | 0.6667 | 0.7222 | 0.0556 |
| Q2b | 0.8333 | 0.8889 | 0.0556 |
| Q3a | 0.8889 | 0.8889 | 0.0000 |
| Q3b | 0.8333 | 0.7778 | -0.0556 |
| Q3c | 0.9444 | 0.9444 | 0.0000 |
| Q3d | 0.6667 | 0.6667 | 0.0000 |
| Q3e | 0.7222 | 0.8333 | 0.1111 |
| Q3f | 0.7222 | 0.8333 | 0.1111 |

## Interpretation

On the held-out test split, candidate v2 improves the baseline on exact
agreement, macro accuracy, subquestion MAE, total score MAE, within-1-point
rate, and mean signed error.

The main caveat is severe-error rate: candidate v2 did not improve severe-error
rate on the held-out split. Both baseline and candidate v2 have severe-error
rate `0.4444`, so this remains the key risk to investigate before making a
strong operational claim.

This held-out result supports candidate v2 as better than the baseline for this
Physics Week 9 text-only pilot, but it is still not a final cross-course or
multimodal conclusion.

Next step: update the experiment note/PDF with held-out metrics and then decide
whether to report candidate v2 as the current text-only pilot winner or open a
candidate v3 branch focused on severe-error reduction.
