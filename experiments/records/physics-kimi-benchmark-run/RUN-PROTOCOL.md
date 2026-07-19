# Physics Week 9 Kimi Benchmark Run Protocol

Status: pre-run protocol. No Kimi model calls are recorded by this file.

## Purpose

Run Kimi on the same Physics Week 9 text-only prompt packets that were used for
the DeepSeek and Codex CLI benchmark report. This keeps the comparison at the
same assessment, split, prompt packet, rubric, transcript source, output schema,
and metrics layer.

## Provider Settings

| Field | Value |
| --- | --- |
| Provider | `kimi` |
| Model | `kimi-k2.6` |
| API style | OpenAI-compatible Chat Completions |
| Default endpoint | `https://api.moonshot.ai/v1` |
| API key environment variable | `MOONSHOT_API_KEY` |
| Input mode | `text-only` |
| Response format | `json_object` |
| Max retries | `2` |

The Kimi API key must never be committed, printed into command records, or saved
inside `experiments/records/`. The runner records only the environment-variable
name, endpoint, provider, model, packet hash, prompt hash, rubric hash, command,
and aggregate validation status.

## Windows PowerShell

Run development first. If both development arms pass validation, run held-out.

```powershell
$secure = Read-Host "Kimi / Moonshot API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:MOONSHOT_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

$runCommit = git rev-parse --short HEAD
$model = "kimi-k2.6"

python -m benchmark.core.cli run-model-packet `
  --provider kimi `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-dev-r1 `
  --output Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-baseline-text-G1-dev-r1 `
  --max-retries 2 `
  --run-commit $runCommit
$bdev = $LASTEXITCODE

python -m benchmark.core.cli run-model-packet `
  --provider kimi `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-candidate-v2-text-strict-schema\G1-dev-r1 `
  --output Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-candidate-text-G1-dev-r1 `
  --max-retries 2 `
  --run-commit $runCommit
$cdev = $LASTEXITCODE

Remove-Item Env:MOONSHOT_API_KEY
"kimi dev baseline exit=$bdev; kimi dev candidate exit=$cdev"
```

After both development arms pass:

```powershell
python -m benchmark.physics.cli metrics `
  --root Data\physics\benchmark `
  --baseline-run Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-baseline-text-G1-dev-r1 `
  --candidate-run Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-candidate-text-G1-dev-r1 `
  --output-json Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-dev-G1-baseline-vs-candidate.metrics.json `
  --output-md Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-dev-G1-baseline-vs-candidate.metrics.md
```

Held-out commands:

```powershell
$secure = Read-Host "Kimi / Moonshot API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:MOONSHOT_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

$runCommit = git rev-parse --short HEAD
$model = "kimi-k2.6"

python -m benchmark.core.cli run-model-packet `
  --provider kimi `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-test-r1 `
  --output Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-baseline-text-G1-test-r1 `
  --max-retries 2 `
  --run-commit $runCommit
$btest = $LASTEXITCODE

python -m benchmark.core.cli run-model-packet `
  --provider kimi `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-candidate-v2-text-strict-schema\G1-test-r1 `
  --output Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-candidate-text-G1-test-r1 `
  --max-retries 2 `
  --run-commit $runCommit
$ctest = $LASTEXITCODE

Remove-Item Env:MOONSHOT_API_KEY
"kimi held-out baseline exit=$btest; kimi held-out candidate exit=$ctest"
```

After both held-out arms pass:

```powershell
python -m benchmark.physics.cli metrics `
  --root Data\physics\benchmark `
  --baseline-run Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-baseline-text-G1-test-r1 `
  --candidate-run Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-candidate-text-G1-test-r1 `
  --output-json Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-heldout-G1-baseline-vs-candidate.metrics.json `
  --output-md Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-heldout-G1-baseline-vs-candidate.metrics.md
```

## macOS/Linux

```bash
read -rsp "Kimi / Moonshot API key: " MOONSHOT_API_KEY
echo
export MOONSHOT_API_KEY

run_commit="$(git rev-parse --short HEAD)"
model="kimi-k2.6"

python -m benchmark.core.cli run-model-packet \
  --provider kimi \
  --model "$model" \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-kimi-benchmark/kimi-baseline-text-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$run_commit"
bdev=$?

python -m benchmark.core.cli run-model-packet \
  --provider kimi \
  --model "$model" \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-kimi-benchmark/kimi-candidate-text-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$run_commit"
cdev=$?

unset MOONSHOT_API_KEY
printf 'kimi dev baseline exit=%s; kimi dev candidate exit=%s\n' "$bdev" "$cdev"
```

Use the same pattern for `G1-test-r1` after the development split passes.

## Interpretation Gate

Kimi should not be added to the benchmark conclusion until:

- both baseline and candidate runs pass schema validation;
- the metrics JSON and Markdown are generated from the completed run folders;
- the report compares the same split and packet hashes as DeepSeek and Codex CLI;
- severe-error rate is reported even if exact agreement improves.

## Privacy

`Data/` remains ignored by Git. Raw student transcripts, raw model responses,
per-student model outputs, and metrics generated from private data stay local
unless separately approved for the private HKUST-GZ GitLab repository.
