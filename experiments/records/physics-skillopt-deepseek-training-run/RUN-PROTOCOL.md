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
  configs/_base_/default.yaml
  configs/physics_grading/deepseek.yaml
  env.deepseek.ps1
  env.deepseek.sh
  expected-return-files.md
  manifest.json
```

The generated package contains no API key. It is ignored because it lives under
`Data/`.

## External SkillOpt Adapter Setup

The external SkillOpt checkout is prepared locally at:

```text
D:\AI-Grading-Platform\SkillOpt
```

Local files added or modified in that checkout:

```text
configs/physics_grading/deepseek.yaml
skillopt/envs/physics_grading/__init__.py
skillopt/envs/physics_grading/adapter.py
skillopt/envs/physics_grading/dataloader.py
skillopt/envs/physics_grading/rollout.py
skillopt/envs/physics_grading/skills/initial.md
scripts/train.py
scripts/eval_only.py
```

`scripts/train.py` and `scripts/eval_only.py` register `physics_grading` as a
local environment so SkillOpt can load the exported physics split. These are
local source-checkout changes for running the experiment; they are not committed
to the upstream Microsoft SkillOpt repository.

No-model smoke check:

```powershell
Set-Location D:\AI-Grading-Platform\SkillOpt

python -c "import json; from pathlib import Path; from skillopt.config import load_config, flatten_config; from scripts.train import get_adapter; cfg=flatten_config(load_config('configs/physics_grading/deepseek.yaml')); adapter=get_adapter(cfg); adapter.setup(cfg); loader=adapter.get_dataloader(); summary={'env':cfg.get('env'), 'optimizer_backend':cfg.get('optimizer_backend'), 'target_backend':cfg.get('target_backend'), 'train':len(loader.train_items), 'val':len(loader.val_items), 'test':len(loader.test_items), 'task_types':adapter.get_task_types(), 'skill_init_exists':Path(cfg.get('skill_init')).exists()}; print(json.dumps(summary, indent=2, sort_keys=True))"
```

Observed result:

```json
{
  "env": "physics_grading",
  "optimizer_backend": "openai_compatible",
  "skill_init_exists": true,
  "target_backend": "openai_compatible",
  "task_types": [
    "physics_week9_text_grading"
  ],
  "test": 18,
  "train": 4,
  "val": 4
}
```

Training package config smoke check:

```powershell
Set-Location D:\AI-Grading-Platform\SkillOpt

python -c "import json; from pathlib import Path; from skillopt.config import load_config, flatten_config; from scripts.train import get_adapter; cfg=flatten_config(load_config(r'D:\AI-Grading-Platform\exam-automark-multicourse\Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1\configs\physics_grading\deepseek.yaml')); adapter=get_adapter(cfg); adapter.setup(cfg); loader=adapter.get_dataloader(); summary={'env':cfg.get('env'), 'train':len(loader.train_items), 'val':len(loader.val_items), 'test':len(loader.test_items), 'skill_init_exists':Path(cfg.get('skill_init')).exists()}; print(json.dumps(summary, indent=2, sort_keys=True))"
```

Observed result:

```json
{
  "env": "physics_grading",
  "skill_init_exists": true,
  "test": 18,
  "train": 4,
  "val": 4
}
```

First run issue and fix:

- initial `commands.ps1` failed before any model call because the generated
  package config referenced `../_base_/default.yaml` but did not include
  `configs/_base_/default.yaml`;
- the package generator now copies or embeds the SkillOpt base config, and the
  regenerated ignored Data package passes the config smoke check above.

Second run issue and local fix:

- after config loading succeeded, SkillOpt failed on Windows while reading
  `skillopt/envs/physics_grading/skills/initial.md` with the platform default
  `gbk` codec;
- the local external SkillOpt checkout was patched to read `skill_init` with
  explicit UTF-8:

```python
with open(skill_init_path, encoding="utf-8") as f:
    skill_init = f.read()
```

This is a local source-checkout patch in
`D:\AI-Grading-Platform\SkillOpt\skillopt\engine\trainer.py`, not a change to
the upstream Microsoft SkillOpt repository.

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
- generated package includes `configs/_base_/default.yaml`,
- external SkillOpt checkout cloned from Microsoft SkillOpt `main`,
- local `physics_grading` SkillOpt adapter copied and registered,
- local Windows UTF-8 `skill_init` read patch applied to SkillOpt,
- no-model SkillOpt adapter smoke check passed,
- tests for the package generator.

Not completed:

- running DeepSeek SkillOpt training,
- evaluating returned `best_skill.md`.
