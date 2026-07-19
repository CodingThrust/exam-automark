# DSAA3071 Week 5 Candidate-v3.1 r2 Development Run Protocol

Status: **packet-ready; model execution not started in this record**

This is a development-only rerun of the C3 condition. It supersedes
`C3-dev-reviewed-v31-r1` before any accepted model result from v3.1 was used as
evidence. The only intended C3-v3.1 r2 difference from R1 is the grading prompt
plus skill snapshot.

## Packet Anchors

- Split: `development`
- Provider/model: `deepseek` / `deepseek-v4-pro`
- Input mode: `text-only`
- Source run: `T1-dev-human-reviewed-r1`
- Data snapshot hash: `95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37`
- Text source hash: `9f9be72bf088f211a3b5fc35db1439b3e965059ff55d5c0563e2880bdc7f4a00`
- B0 packet: `Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-B0-v0-reviewed-dev/B0-dev-reviewed-r1`
- R1 packet: `Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-R1-v1-reviewed-dev/R1-dev-reviewed-r1`
- C3-v3.1 r2 packet: `Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C3-v31-reviewed-dev/C3-dev-reviewed-v31-r2`
- C3-v3.1 r2 packet hash: `d30d5366d8386f6fdbe4621d428e8b739c0b4f0f95b5f7d69941046a6f5e7173`
- C3-v3.1 r2 prompt hash: `ba5113e1dec1a0a690422dc44a4cd03dce83c37d28eab68cb310974bea0c47c5`
- C3-v3.1 r2 skill: `skill_candidate_v3_1_r2`
- C3-v3.1 r2 skill hash: `f3c3fbe8ecb856d30cc950f7a252d1e6efa7463e3a59ad8261c760819e0d6e27`

## Windows PowerShell

Run from the repository root. This command only runs the new C3-v3.1 r2 packet;
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
    --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-C3-v31-reviewed-dev\C3-dev-reviewed-v31-r2 `
    --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-C31-r2-text-dev-reviewed-r1 `
    --max-retries 2 --run-commit $runCommit
  $c31r2 = $LASTEXITCODE

  "C31-r2 exit=$c31r2"
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
  --packet Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C3-v31-reviewed-dev/C3-dev-reviewed-v31-r2 \
  --output Data/DSAA3071/week5-benchmark-redaction-v3/runs/deepseek-C31-r2-text-dev-reviewed-r1 \
  --max-retries 2 --run-commit "$run_commit"
c31r2=$?

unset DEEPSEEK_API_KEY
printf 'C31-r2 exit=%s\n' "$c31r2"
```

Do not create held-out packets, held-out metrics, or final report claims from
this record. It is still a development calibration run.
