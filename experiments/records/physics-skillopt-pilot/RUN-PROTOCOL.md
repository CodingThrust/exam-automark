# Physics SkillOpt Pilot Protocol

## Purpose

This record starts TODO2: try SkillOpt on the physics dataset and show whether a
grading skill can improve score accuracy.

This branch does not run SkillOpt training yet. It creates a reproducible
pre-adapter anchor from existing physics development-split runs. The anchor is meant
to tell SkillOpt, the researcher, and the reviewer what the current grading skill
improves, where it still fails, and which validation gate a future SkillOpt candidate
must pass.

## Why This Shape

SkillOpt trains the natural-language skill document, not model weights. The official
new-benchmark guide says a custom benchmark needs:

- a `SplitDataLoader` subclass,
- a rollout helper that calls the target model, scores each item, and persists
  conversations for reflection,
- an `EnvAdapter` subclass,
- a YAML config.

The physics benchmark already has frozen prompts, rubric files, private data,
model outputs, and metrics. Before adding a full SkillOpt adapter, we first export a
privacy-safe summary from the existing runs. This avoids sending raw student answers
or handwritten transcripts into an optimizer loop before the benchmark contract is
clear.

Official references:

- https://github.com/microsoft/SkillOpt
- https://raw.githubusercontent.com/microsoft/SkillOpt/main/docs/guide/new-benchmark.md
- https://raw.githubusercontent.com/microsoft/SkillOpt/main/docs/reference/cli.md
- https://raw.githubusercontent.com/microsoft/SkillOpt/main/docs/reference/config.md

## Local Reproduction Command

PowerShell:

```powershell
Set-Location D:\AI-Grading-Platform\exam-automark-multicourse

.\.venv\Scripts\python.exe -m benchmark.physics.cli skillopt-pilot `
  --root Data\physics\benchmark `
  --baseline-run Data\physics\benchmark\runs\physics-week9-baseline-candidate-v2\deepseek-baseline-text-G1-dev-r1-strict-schema `
  --candidate-run Data\physics\benchmark\runs\physics-week9-baseline-candidate-v2\deepseek-candidate-text-G1-dev-r1-strict-schema `
  --output-json Data\physics\benchmark\runs\physics-week9-skillopt-pilot\pre-skillopt-dev-anchor.json `
  --output-md Data\physics\benchmark\runs\physics-week9-skillopt-pilot\pre-skillopt-dev-anchor.md
```

macOS/Linux:

```bash
cd /path/to/exam-automark

python -m benchmark.physics.cli skillopt-pilot \
  --root Data/physics/benchmark \
  --baseline-run Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-schema \
  --candidate-run Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-strict-schema \
  --output-json Data/physics/benchmark/runs/physics-week9-skillopt-pilot/pre-skillopt-dev-anchor.json \
  --output-md Data/physics/benchmark/runs/physics-week9-skillopt-pilot/pre-skillopt-dev-anchor.md
```

The generated files live under `Data/` and should stay out of Git.

## Acceptance Gate

A SkillOpt-generated candidate skill should be accepted on the development
validation subset only if:

- exact agreement improves,
- macro accuracy improves,
- total score MAE does not worsen,
- severe error rate does not worsen.

The held-out physics test split must not be used for candidate selection. It is only
for the final check after the skill candidate has been selected.

## Output Contract

The `skillopt-pilot` command writes:

- `record_type`
- generated timestamp
- baseline/candidate run paths
- privacy scope
- train and validation anonymous student IDs
- train and validation metrics
- validation weak-question ranking
- score-level feedback with anonymous student ID, question ID, gold score,
  baseline score, candidate score, and error direction

It does not write raw student answers, redacted PDFs, image paths, model transcripts,
or extracted evidence text.

## Next SkillOpt Adapter Work

After this pilot anchor is reviewed, the full adapter should:

1. Materialize physics train/validation/test items from private `Data/`.
2. Use the current grading skill as `env.skill_init`.
3. Run rollouts against a configured target model.
4. Persist per-item conversations for SkillOpt reflection.
5. Score with the existing physics metrics logic.
6. Accept candidate skill edits only through the validation gate above.
7. Evaluate the selected best skill once on held-out test.

## Status

Current status: scaffold only. No new model call and no SkillOpt training run has
been performed in this branch.
