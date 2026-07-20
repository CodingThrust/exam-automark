# Physics SkillOpt DeepSeek Training Run Protocol

## Purpose

This record prepares the first real SkillOpt training run for the physics week 9
text-only grading benchmark using DeepSeek as both the optimizer and target model.

This branch does not call DeepSeek. It generates a no-secret local run package
under ignored `Data/` so the actual training command can be run from PowerShell
after the API key is entered interactively.

## Prerequisites

- The exam repo is at `D:\AI-Grading-Platform\exam-automark-multicourse`.
- The physics SkillOpt split exists at
  `Data\physics\benchmark\skillopt\physics-week9-text-split-v1`.
- Microsoft SkillOpt should be installed from source `main`, not only PyPI, because
  the generic research `openai_compatible` backend is documented as requiring the
  source version until the next release.
- The external SkillOpt checkout is expected at `D:\AI-Grading-Platform\SkillOpt`.

Official references:

- https://microsoft.github.io/SkillOpt/docs/guideline.html
- https://microsoft.github.io/SkillOpt/docs/reference/config.html
- https://github.com/microsoft/SkillOpt

## Package Generation

PowerShell:

```powershell
Set-Location D:\AI-Grading-Platform\exam-automark-multicourse

.\.venv\Scripts\python.exe -m benchmark.physics.cli skillopt-deepseek-package `
  --split-dir Data\physics\benchmark\skillopt\physics-week9-text-split-v1 `
  --output-dir Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1 `
  --exam-automark-root D:\AI-Grading-Platform\exam-automark-multicourse `
  --skillopt-root D:\AI-Grading-Platform\SkillOpt `
  --model deepseek-v4-pro `
  --base-url https://api.deepseek.com `
  --run-name physics-week9-deepseek-skillopt-r1
```

Generated local package:

```text
Data/physics/benchmark/skillopt/physics-week9-deepseek-training-r1/
  README.md
  commands.ps1
  commands.sh
  env.deepseek.ps1
  env.deepseek.sh
  configs/physics_grading/deepseek.yaml
  expected-return-files.md
  manifest.json
```

The generated package contains no API key. It is ignored because it lives under
`Data/`.

## Actual Training Command

The generated PowerShell command is:

```powershell
Set-Location "D:\AI-Grading-Platform\SkillOpt"

. "D:\AI-Grading-Platform\exam-automark-multicourse\Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1\env.deepseek.ps1"

python scripts/train.py `
  --config "D:\AI-Grading-Platform\exam-automark-multicourse\Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1\configs\physics_grading\deepseek.yaml" `
  --out_root "D:\AI-Grading-Platform\exam-automark-multicourse\Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1\outputs\physics-week9-deepseek-skillopt-r1" `
  --cfg-options `
  model.optimizer_backend=openai_compatible `
  model.target_backend=openai_compatible `
  model.optimizer=deepseek-v4-pro `
  model.target=deepseek-v4-pro
```

`env.deepseek.ps1` prompts for the DeepSeek API key using `Read-Host
-AsSecureString`; the key is stored only in the current process environment and
removed by `commands.ps1` after the training command exits.

## Cost Boundary

Package generation is free and does not call a model.

Running `commands.ps1` will call the DeepSeek public API for both SkillOpt roles:

- optimizer: edits and improves the grading skill,
- target: grades physics items during rollouts.

This can consume DeepSeek API credits. Start with the one-epoch, one-worker config
before increasing batch size or epochs.

## Expected Return Files

After a successful SkillOpt run, collect:

- `best_skill.md`
- `history.json`
- `config.json`
- any metrics file emitted by SkillOpt,
- exact command line,
- terminal output summary and exit code.

The returned `best_skill.md` should then be evaluated inside `exam-automark`
against the existing physics metrics pipeline. The held-out `test/items.json` split
must only be used after the SkillOpt candidate is selected on validation.

## Current Status

Completed:

- no-secret DeepSeek training package generator,
- generated local package under ignored `Data/`,
- tests for the package generator.

Not completed:

- installing or updating SkillOpt source checkout,
- copying/registering the physics adapter inside SkillOpt,
- running DeepSeek SkillOpt training,
- evaluating returned `best_skill.md`.
