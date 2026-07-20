# Physics SkillOpt Target Reliability Preflight

## Purpose

This record isolates one question before running another full SkillOpt optimization:

> Can the target grading model reliably return parseable compact JSON for the
> physics SkillOpt validation split?

The previous SkillOpt diagnostic run completed, but it did not improve score
accuracy. Its main blocker was target-rollout reliability: some target calls
returned empty, truncated, or non-JSON text, so SkillOpt could not trust the
feedback signal. This preflight is a cheaper gate before spending another full
optimizer run.

## Scope

- Dataset: physics Week 9 text-only SkillOpt split.
- Split: `val` by default, 4 validation students.
- Provider/model: DeepSeek API, `deepseek-v4-pro`.
- Input mode: frozen text transcript only.
- Prompted output format: compact JSON with only `student_id`, `scores`, and `total`.
- No optimizer/reflection/update step is run here.
- No raw data or model outputs are committed to Git.

## Command

Windows PowerShell:

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

$secure = Read-Host "DeepSeek API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

python -m benchmark.physics.cli skillopt-target-preflight `
  --split-dir Data\physics\benchmark\skillopt\physics-week9-text-split-v1 `
  --output-dir Data\physics\benchmark\skillopt\physics-week9-deepseek-training-r1\preflight\deepseek-target-val-r1 `
  --split val `
  --model deepseek-v4-pro

$preflight = $LASTEXITCODE
Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
"SkillOpt target preflight exit=$preflight"
```

macOS/Linux:

```bash
cd /path/to/exam-automark
read -rsp "DeepSeek API key: " DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY

python -m benchmark.physics.cli skillopt-target-preflight \
  --split-dir Data/physics/benchmark/skillopt/physics-week9-text-split-v1 \
  --output-dir Data/physics/benchmark/skillopt/physics-week9-deepseek-training-r1/preflight/deepseek-target-val-r1 \
  --split val \
  --model deepseek-v4-pro

preflight=$?
unset DEEPSEEK_API_KEY
echo "SkillOpt target preflight exit=$preflight"
```

## Output Files

The command writes ignored private run artifacts under:

```text
Data/physics/benchmark/skillopt/physics-week9-deepseek-training-r1/preflight/deepseek-target-val-r1/
```

Expected files:

- `summary.json`: aggregate parse/scoring status.
- `outputs/<student_id>/target_system_prompt.txt`: exact system prompt sent to the target model.
- `outputs/<student_id>/target_user_prompt.txt`: exact user prompt and compact schema sent to the target model.
- `outputs/<student_id>/raw_response.txt`: raw model response.
- `outputs/<student_id>/conversation.json`: system/user/assistant transcript for reproducibility.
- `outputs/<student_id>/result.json`: parsed prediction, gold scores, and hard/soft/error metrics.

## Readiness Rule

Continue to another full SkillOpt run only if:

- `summary.json.status == "ready"`
- `items_passed == items_expected`
- `reason_counts == {}`

If the status is `failed`, inspect `reason_counts` and the corresponding
`outputs/<student_id>/raw_response.txt` before changing optimizer settings.

## Interpretation

This preflight is not an accuracy conclusion. It is only a target-model
reliability check for the validation split. A passing preflight means the target
can produce machine-readable scores in the same compact format that SkillOpt
uses during rollout. It does not prove the grading skill has improved.
