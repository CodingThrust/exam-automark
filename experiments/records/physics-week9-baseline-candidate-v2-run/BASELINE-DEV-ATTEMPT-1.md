# Baseline Development Attempt 1

Status: real DeepSeek run failed validation.

Captured date: 2026-07-12, Asia/Shanghai.

## Run Identity

- run id: `deepseek-baseline-text-G1-dev-r1`
- provider: `deepseek`
- endpoint: `https://api.deepseek.com`
- model: `deepseek-v4-pro`
- input mode: `text-only`
- packet:
  `Data/physics/benchmark/text_packets/physics-week9-baseline-text/G1-dev-r1`
- output:
  `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1`
- run commit: `730d9562ad97f34d69f96046db7c6162ae7c1fc9`
- prompt hash:
  `f8aeee5434c5db7b54f9d7b5dbb01b303bd84e48c5d4957731aeb038950953ea`
- packet hash:
  `bfcc88babd54ba9fa11931ef2616bd5a4d8c1775e7ede6a191710582eb76062f`
- rubric hash:
  `a02e0531b3d78590c66d32e76eba170d2e0400e3e4a1c60436f4f5c2c8e93b21`
- text source hash:
  `30e45836b26f6c05d0a55c2e436d5ace7078d01ae86932c3c64b27ad14e24cf8`

## Validation Summary

| Field | Value |
| --- | --- |
| students expected | 8 |
| students passed | 4 |
| students failed | 4 |
| validation status | `failed` |

Failed rows:

| Student | Attempts | Error |
| --- | ---: | --- |
| `S010` | 2 | `invalid confidence: 0.95` |
| `S013` | 2 | `invalid confidence: 1.0` |
| `S016` | 2 | `invalid confidence: 0.95` |
| `S019` | 2 | `invalid confidence: 1.0` |

## Diagnosis

DeepSeek returned numeric confidence values such as `0.95` and `1.0`.
The frozen output schema requires `confidence` to be exactly one of:

- `"high"`
- `"medium"`
- `"low"`

This is an output-format validation failure, not a direct scoring-quality
comparison result. The run must not be used for baseline-vs-candidate metrics.

## Remediation

Create strict-confidence prompt packets that explicitly forbid numeric
confidence values and require the string enum from `output.schema.json`.

New prompt source files:

- `experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_standard_v1_strict_confidence.txt`
- `experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_candidate_v2_strict_confidence.txt`

The failed output directory must be retained as an attempted real run record.
