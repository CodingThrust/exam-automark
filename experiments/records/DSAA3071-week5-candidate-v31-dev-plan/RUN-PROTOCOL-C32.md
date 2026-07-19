# DSAA3071 Week 5 C32 Run Protocol

This protocol runs only the C32 development packet prepared for candidate-v3.2 with rubric-v2. It records the command line needed for reproducibility. It does not store the API key and does not require committing Data to GitHub.

## Inputs

- Packet id: `C32-dev-reviewed-r1`
- Packet path: `Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C32-v2-reviewed-dev/C32-dev-reviewed-r1`
- Prompt snapshot: `experiments/records/DSAA3071-week5-candidate-v31-dev-plan/prompts/grade_candidate_v3_2_strict_schema.txt`
- Rubric: `experiments/records/DSAA3071-week5-prep/rubric_v2.json`
- Skill snapshot: `experiments/skill_versions/skill_candidate_v3_2.json`
- Split: `development`
- Students: `S017`, `S021`, `S002`, `S015`, `S020`, `S016`, `S022`

## Windows PowerShell

Run from the repository root.

```powershell
$secure = Read-Host "DeepSeek API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  $runCommit = git rev-parse --short HEAD

  python -m benchmark.core.cli run-model-packet `
    --provider deepseek --model deepseek-v4-pro --input-mode text-only `
    --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-C32-v2-reviewed-dev\C32-dev-reviewed-r1 `
    --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-C32-text-dev-reviewed-r1 `
    --max-retries 4 --run-commit $runCommit
  $c32 = $LASTEXITCODE

  "C32 exit=$c32"
} finally {
  if ($bstr -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
  Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
}
```

## macOS/Linux

Run from the repository root.

```bash
read -r -s -p "DeepSeek API key: " DEEPSEEK_API_KEY
echo
export DEEPSEEK_API_KEY
run_commit="$(git rev-parse --short HEAD)"

python -m benchmark.core.cli run-model-packet \
  --provider deepseek --model deepseek-v4-pro --input-mode text-only \
  --packet Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C32-v2-reviewed-dev/C32-dev-reviewed-r1 \
  --output Data/DSAA3071/week5-benchmark-redaction-v3/runs/deepseek-C32-text-dev-reviewed-r1 \
  --max-retries 4 --run-commit "$run_commit"
c32=$?

unset DEEPSEEK_API_KEY
printf 'C32 exit=%s\n' "$c32"
```

## Interpretation Boundary

Passing this protocol means the model run completed and outputs passed schema validation. Accuracy conclusions require a separate metrics step against the official per-question scores.
