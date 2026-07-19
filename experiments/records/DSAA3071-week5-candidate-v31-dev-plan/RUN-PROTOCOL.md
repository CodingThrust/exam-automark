# DSAA3071 Week 5 Candidate-v3.1 Development Run Protocol

Status: **packet-ready; model execution not started in this record**

This is a development-only rerun of the C3 condition. It uses the same
human-reviewed transcript snapshot, student split, course spec, output schema,
and `rubric_v1.json` as the previous B0/R1/C3 development ablation. The only
intended C3-v3.1 difference from R1 is the grading prompt plus skill snapshot.

## Packet Anchors

- Split: `development`
- Provider/model: `deepseek` / `deepseek-v4-pro`
- Input mode: `text-only`
- Source run: `T1-dev-human-reviewed-r1`
- Data snapshot hash: `95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37`
- Text source hash: `9f9be72bf088f211a3b5fc35db1439b3e965059ff55d5c0563e2880bdc7f4a00`
- B0 packet: `Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-B0-v0-reviewed-dev/B0-dev-reviewed-r1`
- R1 packet: `Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-R1-v1-reviewed-dev/R1-dev-reviewed-r1`
- C3-v3.1 packet: `Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C3-v31-reviewed-dev/C3-dev-reviewed-v31-r1`
- C3-v3.1 packet hash: `f295322f5e7d22576266810bd6c60d076967aecff4beeba19078dca9f705c21a`
- C3-v3.1 prompt hash: `b5a7baf7b748164fb6e12e1700868b1c07f42708ff9cb5a45f1b43cfcdc75a37`
- C3-v3.1 skill: `skill_candidate_v3_1`
- C3-v3.1 skill hash: `8cbdb7d2e5f4b2ad66f87dd545af621d966baf3e356cb90a33b9b734e6d1b55a`

## Windows PowerShell

Run from the repository root. This command only runs the new C3-v3.1 packet;
reuse the existing B0/R1 dev runs as controls unless you intentionally want to
rerun the full ablation.

```powershell
$secure = Read-Host "DeepSeek API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  $runCommit = git rev-parse --short HEAD

  python -m benchmark.core.cli run-model-packet `
    --provider deepseek --model deepseek-v4-pro --input-mode text-only `
    --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-C3-v31-reviewed-dev\C3-dev-reviewed-v31-r1 `
    --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-C31-text-dev-reviewed-r1 `
    --max-retries 2 --run-commit $runCommit
  $c31 = $LASTEXITCODE

  "C31 exit=$c31"
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
  --packet Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C3-v31-reviewed-dev/C3-dev-reviewed-v31-r1 \
  --output Data/DSAA3071/week5-benchmark-redaction-v3/runs/deepseek-C31-text-dev-reviewed-r1 \
  --max-retries 2 --run-commit "$run_commit"
c31=$?

unset DEEPSEEK_API_KEY
printf 'C31 exit=%s\n' "$c31"
```

Do not create held-out packets, held-out metrics, or final report claims from
this record. It is still a development calibration run.
