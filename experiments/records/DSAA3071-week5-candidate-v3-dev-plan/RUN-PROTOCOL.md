# DSAA3071 Week 5 Candidate-v3 Development Ablation Protocol

Status: **packet-ready; model execution not started**

This is a development-only B0/R1/C3 ablation over the human-reviewed transcript
snapshot `T1-dev-human-reviewed-r1`. It records no model outputs and contains
no API key. Run commands only after explicit approval.

## Packet Anchors

- Source: `Data/DSAA3071/week5-benchmark-redaction-v3/transcripts/T1-dev-human-reviewed-r1`
- Source snapshot hash: `95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37`
- Split: `development`
- Settings: `deepseek`, `deepseek-v4-pro`, `text-only`, repetition `1`
- B0: baseline strict prompt, rubric v0, `skill_baseline_v1`
- R1: baseline strict prompt, rubric v1, `skill_baseline_v1`
- C3: candidate-v3 strict prompt with calculation support, rubric v1,
  `skill_candidate_v3`

## Windows PowerShell

Run from the repository root. The key is kept only in the current process and
removed even when a run fails.

```powershell
$secure = Read-Host "DeepSeek API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  $runCommit = git rev-parse --short HEAD

  python -m benchmark.core.cli run-model-packet `
    --provider deepseek --model deepseek-v4-pro --input-mode text-only `
    --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-B0-v0-reviewed-dev\B0-dev-reviewed-r1 `
    --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-B0-text-dev-reviewed-r1 `
    --max-retries 2 --run-commit $runCommit
  $b0 = $LASTEXITCODE

  python -m benchmark.core.cli run-model-packet `
    --provider deepseek --model deepseek-v4-pro --input-mode text-only `
    --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-R1-v1-reviewed-dev\R1-dev-reviewed-r1 `
    --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-R1-text-dev-reviewed-r1 `
    --max-retries 2 --run-commit $runCommit
  $r1 = $LASTEXITCODE

  python -m benchmark.core.cli run-model-packet `
    --provider deepseek --model deepseek-v4-pro --input-mode text-only `
    --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-C3-v1-reviewed-dev\C3-dev-reviewed-r2 `
    --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-C3-text-dev-reviewed-r2 `
    --max-retries 2 --run-commit $runCommit
  $c3 = $LASTEXITCODE

  "B0 exit=$b0; R1 exit=$r1; C3 exit=$c3"
} finally {
  if ($bstr -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
  Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
}
```

## macOS/Linux

```bash
read -r -s -p "DeepSeek API key: " DEEPSEEK_API_KEY; printf '\n'
export DEEPSEEK_API_KEY
run_commit=$(git rev-parse --short HEAD)

python -m benchmark.core.cli run-model-packet \
  --provider deepseek --model deepseek-v4-pro --input-mode text-only \
  --packet Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-B0-v0-reviewed-dev/B0-dev-reviewed-r1 \
  --output Data/DSAA3071/week5-benchmark-redaction-v3/runs/deepseek-B0-text-dev-reviewed-r1 \
  --max-retries 2 --run-commit "$run_commit"
b0=$?

python -m benchmark.core.cli run-model-packet \
  --provider deepseek --model deepseek-v4-pro --input-mode text-only \
  --packet Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-R1-v1-reviewed-dev/R1-dev-reviewed-r1 \
  --output Data/DSAA3071/week5-benchmark-redaction-v3/runs/deepseek-R1-text-dev-reviewed-r1 \
  --max-retries 2 --run-commit "$run_commit"
r1=$?

python -m benchmark.core.cli run-model-packet \
  --provider deepseek --model deepseek-v4-pro --input-mode text-only \
  --packet Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C3-v1-reviewed-dev/C3-dev-reviewed-r2 \
  --output Data/DSAA3071/week5-benchmark-redaction-v3/runs/deepseek-C3-text-dev-reviewed-r2 \
  --max-retries 2 --run-commit "$run_commit"
c3=$?

unset DEEPSEEK_API_KEY
printf 'B0 exit=%s; R1 exit=%s; C3 exit=%s\n' "$b0" "$r1" "$c3"
```

Do not create held-out packets, metrics, or reports from this development-only
record. All packets and future raw outputs remain under ignored `Data/`.
