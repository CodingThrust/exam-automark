# C31-r2 Attempt 1 and Recovery Plan

Status: **partial model run; recovery packet prepared**

The first `C3-dev-reviewed-v31-r2` model run was started from commit `416fedb`
with output directory:

`Data/DSAA3071/week5-benchmark-redaction-v3/runs/deepseek-C31-r2-text-dev-reviewed-r1`

## Result

The run did not pass validation because only 3 of 7 expected anonymous students
completed successfully.

Passed:

- `S017`
- `S021`
- `S002`

Failed:

- `S015`: `APIConnectionError`, 3 attempts
- `S020`: `APITimeoutError`, 3 attempts
- `S016`: `APIConnectionError`, 3 attempts
- `S022`: `APIConnectionError`, 3 attempts

This is a provider/network failure, not a schema validation failure. The three
passed outputs should be preserved. The failed students should be rerun through
a recovery packet instead of rerunning all seven students.

## Recovery Packet

- Packet id: `C3-dev-reviewed-v31-r2-recovery1`
- Packet path: `Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C3-v31-reviewed-dev/C3-dev-reviewed-v31-r2-recovery1`
- Packet hash: `a9898d58f14071fadab935175d946f04842ecfdc08c0dde12235c6d186246f64`
- Prompt hash: `ba5113e1dec1a0a690422dc44a4cd03dce83c37d28eab68cb310974bea0c47c5`
- Rubric hash: `6798e56675bc16429eb98543ed4f85822b0658b8f412d902443130a754e7444c`
- Skill version: `skill_candidate_v3_1_r2`
- Failed-student list: `students-c31-r2-recovery1.txt`

The recovery packet uses the same prompt, rubric, course spec, source
transcripts, provider/model setting, and split as the original r2 run. Its only
intentional difference is the reduced anonymous student set.

## Windows PowerShell Recovery Command

Run from the repository root. Use a new output directory; do not overwrite the
partial attempt.

```powershell
$secure = Read-Host "DeepSeek API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  $runCommit = git rev-parse --short HEAD

  python -m benchmark.core.cli run-model-packet `
    --provider deepseek --model deepseek-v4-pro --input-mode text-only `
    --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-C3-v31-reviewed-dev\C3-dev-reviewed-v31-r2-recovery1 `
    --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-C31-r2-text-dev-reviewed-r1-recovery1 `
    --max-retries 4 --run-commit $runCommit
  $recovery = $LASTEXITCODE

  "C31-r2 recovery1 exit=$recovery"
} finally {
  if ($bstr -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
  Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
}
```

After the recovery run passes, combine the 3 successful outputs from the
original partial run with the 4 outputs from the recovery run for development
metrics. Do not make held-out or final accuracy claims from this development
record.
