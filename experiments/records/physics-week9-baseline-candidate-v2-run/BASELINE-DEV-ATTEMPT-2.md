# Baseline Development Attempt 2

Status: real DeepSeek run failed validation.

Captured date: 2026-07-13, Asia/Shanghai.

## Run Identity

- run id from original command: `deepseek-baseline-text-G1-dev-r1-strict-confidence`
- local retained directory:
  `deepseek-baseline-text-G1-dev-r1-strict-confidence-failed-validation`
- provider: `deepseek`
- endpoint: `https://api.deepseek.com`
- model: `deepseek-v4-pro`
- input mode: `text-only`
- packet:
  `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-confidence/G1-dev-r1`
- output:
  `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-confidence-failed-validation`

## Validation Summary

| Field | Value |
| --- | --- |
| students expected | 8 |
| students passed | 7 |
| students failed | 1 |
| validation status | `failed` |

Failed row:

| Student | Attempts | Error |
| --- | ---: | --- |
| `S019` | 2 | `total must equal the sum of question scores` |

## Diagnosis

The strict-confidence prompt fixed the previous numeric-confidence failure, but
one output still failed because the reported `total` did not equal the sum of
the itemized question scores.

This is an output-format validation failure, not a direct scoring-quality
comparison result. The run must not be used for baseline-vs-candidate metrics.

## Remediation

Create strict-schema prompt packets that explicitly require:

- `confidence` as one of `"high"`, `"medium"`, or `"low"`
- `total` as the exact arithmetic sum of all itemized `score` fields

The failed output directory is retained with the `failed-validation` suffix to
prevent confusion with successful metric-bearing runs.
