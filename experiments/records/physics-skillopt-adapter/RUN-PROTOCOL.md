# Physics SkillOpt Adapter Protocol

## Purpose

This record is the second step of TODO2. The previous SkillOpt pilot branch
created a metrics anchor from existing physics runs. This branch prepares the
actual data split that a Microsoft SkillOpt benchmark adapter can consume.

No SkillOpt training run is performed in this branch. The output is a private
SkillOpt-compatible split directory under `Data/` plus committed instructions for
adding a minimal adapter to an external SkillOpt checkout.

## Why Text-Only First

The physics benchmark has multimodal source PDFs/images, automatic transcripts,
and text-only grading packets. The first SkillOpt adapter should use the text-only
grading packet because it matches the already completed DeepSeek and Codex CLI
comparisons and avoids mixing transcript quality with grading-skill optimization.

Multimodal SkillOpt can be added later after the text-only loop is proven.

## Export Command

PowerShell:

```powershell
Set-Location D:\AI-Grading-Platform\exam-automark-multicourse

.\.venv\Scripts\python.exe -m benchmark.physics.cli skillopt-export `
  --root Data\physics\benchmark `
  --dev-packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-dev-r1 `
  --test-packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-test-r1 `
  --output-dir Data\physics\benchmark\skillopt\physics-week9-text-split-v1
```

macOS/Linux:

```bash
cd /path/to/exam-automark

python -m benchmark.physics.cli skillopt-export \
  --root Data/physics/benchmark \
  --dev-packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1 \
  --test-packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-test-r1 \
  --output-dir Data/physics/benchmark/skillopt/physics-week9-text-split-v1
```

Expected output:

```text
Data/physics/benchmark/skillopt/physics-week9-text-split-v1/
  manifest.json
  train/items.json
  val/items.json
  test/items.json
```

The generated split contains anonymous transcripts and gold scores. It must stay
under `Data/` and must not be committed to GitHub.

## Smoke Check Command

The smoke check validates the generated SkillOpt split without calling any model:

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m benchmark.physics.cli skillopt-smoke `
  --split-dir Data\physics\benchmark\skillopt\physics-week9-text-split-v1 `
  --output Data\physics\benchmark\skillopt\physics-week9-text-split-v1\smoke-check.json
```

macOS/Linux:

```bash
python -m benchmark.physics.cli skillopt-smoke \
  --split-dir Data/physics/benchmark/skillopt/physics-week9-text-split-v1 \
  --output Data/physics/benchmark/skillopt/physics-week9-text-split-v1/smoke-check.json
```

Expected status:

```json
{
  "failed_checks": [],
  "split_counts": {
    "test": 18,
    "train": 4,
    "val": 4
  },
  "status": "ready"
}
```

## Split Contract

- `train`: first half of the development packet by sorted anonymous student ID.
- `val`: second half of the development packet by sorted anonymous student ID.
- `test`: held-out physics text packet.

For the current physics week 9 dataset:

- train: `S008`, `S010`, `S012`, `S013`
- val: `S016`, `S018`, `S019`, `S022`
- test: 18 held-out anonymous students from `G1-test-r1`

The held-out `test` split is exported for final evaluation only. Do not use it for
SkillOpt candidate selection.

## Official SkillOpt Contract

Microsoft SkillOpt expects a custom benchmark to provide:

- a `SplitDataLoader` subclass,
- a rollout helper that calls the target model, scores each item, and persists
  `predictions/<item-id>/conversation.json`,
- an `EnvAdapter` subclass,
- a YAML config.

See `skillopt-physics-adapter-template.md` in this record for the external adapter
shape.

Official references:

- https://microsoft.github.io/SkillOpt/docs/guide/new-benchmark.html
- https://microsoft.github.io/SkillOpt/docs/reference/config.html
- https://github.com/microsoft/SkillOpt

## Current Status

Completed in this branch:

- export command,
- private split generation,
- tests for the exporter,
- adapter instructions.

Not completed in this branch:

- installing SkillOpt,
- registering the adapter in a SkillOpt checkout,
- running SkillOpt training,
- evaluating a generated `best_skill.md`.
