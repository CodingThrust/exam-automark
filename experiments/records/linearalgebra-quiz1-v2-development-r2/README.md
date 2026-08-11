# Linear Algebra Quiz 1 — development r2

This public record compares four controlled routes against frozen human gold on the
development split only: 30 anonymized submissions and 300 minimal score items.
It contains aggregate-only artifacts. Raw submissions, transcriptions, human gold,
per-submission results, prompts containing student work, and private paths are not
published.

## Routes and readiness

| Route | Role | Provider / model | Input | Validation |
| --- | --- | --- | --- | --- |
| M1 | Direct grading | Codex CLI / `gpt-5.6-sol` | Multimodal | 30 / 30 passed |
| T1 | Transcription | Codex CLI / `gpt-5.6-sol` | Multimodal | 30 / 30 passed |
| G1-Codex | Transcript grading | Codex CLI / `gpt-5.6-sol` | Text-only | 30 / 30 passed |
| G1-DeepSeek | Transcript grading | DeepSeek / `deepseek-v4-pro` | Text-only | 30 / 30 passed |

M1 and T1 can run independently because both consume the frozen anonymized image
packet. Both G1 routes consume the same validated T1 transcript commitment. The
two public lineage bindings verify that relationship without exposing any student-
level content.

## Aggregate development results

| Scoring route | Exact leaf agreement | Total-score MAE | Within 1 point | Severe-error rate | Mean signed error |
| --- | ---: | ---: | ---: | ---: | ---: |
| M1 | 89.0% | 2.53 | 50.0% | 46.7% | +0.16 |
| G1-Codex | 87.3% | 3.03 | 50.0% | 40.0% | +0.00 |
| G1-DeepSeek | 84.7% | 8.63 | 26.7% | 66.7% | -0.95 |

On this development run, M1 has the lowest total-score MAE. G1-Codex is close on
exact agreement and has a lower severe-error rate, while G1-DeepSeek is materially
weaker on these development metrics. These descriptive results are not a held-out
comparison and are not a production-readiness claim.

T1 is not a scoring condition, so it is reported as a validated transcription
readiness gate rather than as an accuracy row.

## Integrity and recovery notes

The first G1-DeepSeek attempt was retained privately for audit but excluded from
metrics because it had incomplete structural validation. Its failures were caused
only by a redundant model-reported total that disagreed with the deterministic
course total derived from valid leaf scores. The generic runner now requires the
field but writes the deterministic course-calculated total after all leaf-level
validation succeeds. A fresh, complete retry produced the reported 30 / 30 run;
no outputs were overwritten or merged.

All scoring routes use the generic `skill_candidate_v5_2` snapshot. Its page-order
rule treats attachment order and labels such as `P01` only as source-page locators,
never as question numbers. The frozen course/rubric contract, including the
100-point cap, is applied deterministically.

## Public artifact map

- `multi-route.aggregate.json` — strict, aggregate-only cross-route dashboard data.
- `multi-route-dashboard.typ` and `multi-route-dashboard.pdf` — the Typst dashboard.
- `metrics/` — three pairwise aggregate comparison reports.
- `t1-readiness.aggregate.json` — aggregate transcription readiness.
- `g1-codex-lineage.aggregate.json` and `g1-deepseek-lineage.aggregate.json` —
  privacy-safe transcript lineage bindings.
- `route-contract.json` — frozen public route identity and common snapshot contract.
- `experiment.json` — schema-validated experiment manifest.

## Reproduction environment

The record was produced on Windows 11 Pro (`10.0.26200`), PowerShell
`5.1.26100.7705`, Python `3.12.10`, and Typst `0.15.0`. The final public dashboard
was generated at commit `affb313530394ed26c68b3615dee3d0c2e0c56a8`; individual
route provenance is recorded below because the final recovery involved a generic
runner fix after the earlier routes had completed.

| Route | Run identifier | Runtime commit | Packet hash |
| --- | --- | --- | --- |
| M1 | `LA-v2-M1-codex-dev-30-v5_2-r2` | `394dc2b6bde868db6df80f06b90b6f9ab14c3662` | `d70093ab5bd474d8edcbb71c489d29232b656ed736385014b69c5b02a77b65b2` |
| T1 | `LA-v2-T1-codex-dev-30-v5_2-r2` | `394dc2b6bde868db6df80f06b90b6f9ab14c3662` | `3112779297d1385e77fc2a3de8619bdb220b64e9bc180e95d2b73c1dbf283b14` |
| G1-Codex | `LA-v2-G1-codex-dev-30-v5_2-r2` | `3b78e071169984ad54eac607ee86cc1f17dc7dd5` | `271588f95aeec311892116f8c6aac64cd99451d7e4aa3b466ce4f6f924a3f5d2` |
| G1-DeepSeek | `LA-v2-G1-deepseek-dev-30-v5_2-r2-retry1-canonical-total` | `39a208f` | `271588f95aeec311892116f8c6aac64cd99451d7e4aa3b466ce4f6f924a3f5d2` |

## Run configuration and timing

All routes used their provider's configured model identifier, JSON-object response
format, and at most two retries. Temperature, top-p, and max-token overrides were
not set, so provider defaults applied. No file-conversion tool was executed during
these runs: all routes consumed a previously frozen anonymous snapshot. Providers
did not expose a more granular backend release than the model identifier shown.

| Route | Start (UTC) | End (UTC) | Provider / model | Task and input |
| --- | --- | --- | --- | --- |
| M1 | 2026-08-11T08:26:20Z | 2026-08-11T10:18:11Z | Codex CLI / `gpt-5.6-sol` | Grade, multimodal |
| T1 | 2026-08-11T08:26:20Z | 2026-08-11T10:29:07Z | Codex CLI / `gpt-5.6-sol` | Transcribe, multimodal |
| G1-Codex | 2026-08-11T10:29:24Z | 2026-08-11T11:04:00Z | Codex CLI / `gpt-5.6-sol` | Grade, text-only |
| G1-DeepSeek | 2026-08-11T11:10:38Z | 2026-08-11T11:24:21Z | DeepSeek / `deepseek-v4-pro` | Grade, text-only |

The shared anonymized snapshot digest is
`6c7bf60f199a80eb27bad6cde854ce2d60eacd1fbe6995305a22226cd2797c54`.
The grading rubric digest is
`90482f67ac7787a17e65d5360d78573d7d731a2bcd3f69b56f9d06162e1cea8d`.
The candidate-skill snapshot digest is
`d623f29cfce9cb327bcd553d427c44d261c7bd10c216c67632853a43d800ccfe`.

The public dashboard can be regenerated from the committed aggregate-only
artifacts with the project CLI. Recreating model runs or pairwise metrics requires
private inputs and is deliberately outside this public record.

```powershell
python -B -m benchmark.core.cli render-multi-route-report `
  --m1-metrics experiments/records/linearalgebra-quiz1-v2-development-r2/metrics/m1-vs-g1-codex.json `
  --g1-codex-metrics experiments/records/linearalgebra-quiz1-v2-development-r2/metrics/m1-vs-g1-codex.json `
  --g1-deepseek-metrics experiments/records/linearalgebra-quiz1-v2-development-r2/metrics/m1-vs-g1-deepseek.json `
  --t1-readiness experiments/records/linearalgebra-quiz1-v2-development-r2/t1-readiness.aggregate.json `
  --route-contract experiments/records/linearalgebra-quiz1-v2-development-r2/route-contract.json `
  --g1-codex-lineage experiments/records/linearalgebra-quiz1-v2-development-r2/g1-codex-lineage.aggregate.json `
  --g1-deepseek-lineage experiments/records/linearalgebra-quiz1-v2-development-r2/g1-deepseek-lineage.aggregate.json `
  --output-json experiments/records/linearalgebra-quiz1-v2-development-r2/multi-route.aggregate.json `
  --output-typst experiments/records/linearalgebra-quiz1-v2-development-r2/multi-route-dashboard.typ
```

Compile the resulting Typst source with a pinned Typst `0.15.0` installation. The
published PDF was visually checked for a clear, single-page layout.

## Limitations and next gate

This is one human rater's frozen development reference on one Linear Algebra quiz.
It does not estimate held-out accuracy, inter-rater agreement, calibration on a
new course, or the effect on teacher workload in live marking. The next meaningful
evaluation gate is a separately authorized held-out experiment, after any
development-driven prompt or rubric changes are frozen.
