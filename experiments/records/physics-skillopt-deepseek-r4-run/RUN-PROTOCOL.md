# Physics SkillOpt DeepSeek R4 Run Protocol

## Purpose

This run is a small follow-up to the completed negative R3 diagnostic run. It
does not broaden the dataset. It tests one specific hypothesis:

> R3 target JSON failures were largely caused by too small a target completion
> budget, not by the physics grading task being impossible for the target model.

The target preflight on the validation split passed with 4 / 4 parseable compact
JSON outputs. Some DeepSeek calls used more than 8,000 completion tokens, while
R3 capped the target path at 4,096 tokens. R4 therefore raises the target budget
and timeout while keeping the SkillOpt run otherwise small.

## R4 Settings

- Dataset: Physics Week 9 SkillOpt text split.
- Train: 4 development students.
- Validation/selection: 4 development students.
- Test evaluation: 18 held-out students, used only by SkillOpt final reporting.
- Optimizer model: `deepseek-v4-pro`.
- Target model: `deepseek-v4-pro`.
- Backend: `openai_compatible`.
- Epochs: 1.
- Batch size: 4.
- Target max tokens: 12,000.
- Target timeout: 240 seconds.
- Output directory:
  `Data/physics/benchmark/skillopt/physics-week9-deepseek-training-r1/outputs/physics-week9-deepseek-skillopt-r4-target-budget`

## Step 1: Regenerate The Local No-Secret Package

Run from the exam repo:

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

python -m benchmark.physics.cli skillopt-deepseek-package `
  --split-dir Data\physics\benchmark\skillopt\physics-week9-text-split-v1 `
  --output-dir Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1 `
  --exam-automark-root D:\AI-Grading-Platform\exam-automark-multicourse `
  --skillopt-root D:\AI-Grading-Platform\SkillOpt `
  --model deepseek-v4-pro `
  --base-url https://api.deepseek.com `
  --run-name physics-week9-deepseek-skillopt-r4-target-budget `
  --target-max-tokens 12000 `
  --target-timeout-seconds 240
```

Expected safe output: one JSON object with
`record_type = physics_skillopt_deepseek_training_package` and
`contains_api_key = false`.

## Step 2: Run SkillOpt R4

Run from PowerShell. The command asks for the DeepSeek API key interactively and
does not store it in the repo.

```powershell
Set-Location "D:\AI-Grading-Platform\SkillOpt"

D:\AI-Grading-Platform\exam-automark-multicourse\Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1\commands.ps1
```

The generated command expands to:

```powershell
python scripts/train.py `
  --config "D:\AI-Grading-Platform\exam-automark-multicourse\Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1\configs\physics_grading\deepseek.yaml" `
  --out_root "D:\AI-Grading-Platform\exam-automark-multicourse\Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1\outputs\physics-week9-deepseek-skillopt-r4-target-budget" `
  --cfg-options `
  model.optimizer_backend=openai_compatible `
  model.target_backend=openai_compatible `
  model.optimizer=deepseek-v4-pro `
  model.target=deepseek-v4-pro `
  env.max_completion_tokens=12000 `
  env.exec_timeout=240
```

## Step 3: Return A Safe Summary

After the run finishes, return the terminal final summary and the exit code.
Do not paste raw student transcripts or raw target responses into chat.

Also check these private files locally:

```powershell
$root = "D:\AI-Grading-Platform\exam-automark-multicourse\Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1\outputs\physics-week9-deepseek-skillopt-r4-target-budget"
Test-Path "$root\summary.json"
Test-Path "$root\history.json"
Test-Path "$root\best_skill.md"
Get-ChildItem "$root" -Recurse -Filter result.json | Measure-Object
```

## Success Criteria

This run is successful as an engineering run if:

- it exits with code 0;
- it writes `summary.json`, `history.json`, and `best_skill.md`;
- selection/test target outputs are not dominated by JSON parse failures.

This run is successful as a SkillOpt improvement only if the selected/best skill
improves held-out score accuracy against the initial skill. Do not claim
improvement from a successful exit alone.

## Recorded Result

The R4 run completed, but it did not improve held-out hard score accuracy.
See `RESULT-SUMMARY.md` in this directory for the safe aggregate result summary.

## Stop Conditions

Stop and report the blocker if:

- API authentication fails;
- every target output fails JSON parsing;
- the run again shows completion budget exhaustion near the configured token
  limit;
- the output directory already exists and would mix old and new run artifacts.
