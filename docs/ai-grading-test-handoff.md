---
title: AI Grading Test Handoff
---

# AI Grading Test Handoff

This page is for an external reviewer or an AI coding assistant. Read this page,
then run the grading benchmark from a local checkout that has the private
`Data/` directory restored.

Do not upload raw student transcripts, raw model responses, per-student outputs,
or private PDFs to GitHub Pages.

## One-Sentence Goal

Run the Physics Week 9 text-only grading benchmark on fixed prompt packets, then
return validation status and aggregate metrics for baseline vs candidate-v2.

## Local Repository Root

Windows:

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"
git status --short --branch
git rev-parse --short HEAD
```

macOS/Linux:

```bash
cd /path/to/exam-automark
git status --short --branch
git rev-parse --short HEAD
```

## Required Local Inputs

These paths are private local inputs. They are intentionally not stored in
GitHub Pages.

| Role | Development packet | Held-out packet |
| --- | --- | --- |
| Baseline prompt/skill | `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1` | `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-test-r1` |
| Candidate-v2 prompt/skill | `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1` | `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-test-r1` |
| Gold scores and metrics root | `Data/physics/benchmark` | `Data/physics/benchmark` |

Run development first. Run held-out only after both development arms pass schema
validation.

The runner intentionally refuses to overwrite an existing output directory. If a
listed output directory already exists, append a suffix such as `-r2`,
`-authfix`, or `-cn-authfix` and report the actual path used.

## Required Per-Student Output Shape

Every model-produced student file must be a JSON object matching this contract:

```json
{
  "student_id": "S008",
  "scores": [
    {
      "question_id": "Q1a",
      "extracted_evidence": "short quote or paraphrase of the student answer evidence",
      "score": 1.0,
      "evidence": "brief grading rationale",
      "confidence": "high",
      "flags": []
    }
  ],
  "total": 30.0
}
```

Rules:

- `student_id` must match the packet student id exactly.
- `question_id` must match the course question ids exactly.
- `score` must use only valid point values from the rubric/course spec.
- `confidence` must be one of the allowed schema values, not a number.
- `total` must equal the sum of all question scores.
- Output one JSON object only. Do not include Markdown around JSON.

## Kimi Route

Use this route when the reviewer has a Moonshot/Kimi API key such as
`sk-kimi-...`.

If you are Kimi Code, use yourself as the shell executor and run the same Kimi
API commands below. Do not treat Kimi Code chat output as the benchmark result
unless a separate Kimi Code headless JSON mode is explicitly documented and
recorded.

### Kimi Auth Preflight

This preflight does not send student data. It only checks which endpoint accepts
the key.

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

$secure = Read-Host "Kimi / Moonshot API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

$env:MOONSHOT_API_KEY = $key

"=== Test CN endpoint: https://api.moonshot.cn/v1 ==="
python -c "import os; from openai import OpenAI; c=OpenAI(api_key=os.environ['MOONSHOT_API_KEY'], base_url='https://api.moonshot.cn/v1'); print([m.id for m in c.models.list().data][:10])"
$cn = $LASTEXITCODE

"=== Test AI endpoint: https://api.moonshot.ai/v1 ==="
python -c "import os; from openai import OpenAI; c=OpenAI(api_key=os.environ['MOONSHOT_API_KEY'], base_url='https://api.moonshot.ai/v1'); print([m.id for m in c.models.list().data][:10])"
$ai = $LASTEXITCODE

Remove-Item Env:MOONSHOT_API_KEY -ErrorAction SilentlyContinue
Remove-Variable key -ErrorAction SilentlyContinue

"kimi cn exit=$cn; kimi ai exit=$ai"
```

Use `--endpoint https://api.moonshot.cn/v1` if `cn exit=0`. Use
`--endpoint https://api.moonshot.ai/v1` if `ai exit=0`.

### Kimi Development Run

Replace `$endpoint` with the endpoint that passed preflight.

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

$secure = Read-Host "Kimi / Moonshot API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:MOONSHOT_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

try {
  $runCommit = git rev-parse --short HEAD
  $model = "kimi-k2.6"
  $endpoint = "https://api.moonshot.cn/v1"

  python -m benchmark.core.cli run-model-packet `
    --provider kimi `
    --model $model `
    --endpoint $endpoint `
    --input-mode text-only `
    --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-dev-r1 `
    --output Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-baseline-text-G1-dev-r1 `
    --max-retries 2 `
    --run-commit $runCommit
  $bdev = $LASTEXITCODE

  python -m benchmark.core.cli run-model-packet `
    --provider kimi `
    --model $model `
    --endpoint $endpoint `
    --input-mode text-only `
    --packet Data\physics\benchmark\text_packets\physics-week9-candidate-v2-text-strict-schema\G1-dev-r1 `
    --output Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-candidate-text-G1-dev-r1 `
    --max-retries 2 `
    --run-commit $runCommit
  $cdev = $LASTEXITCODE

  "kimi dev baseline exit=$bdev; kimi dev candidate exit=$cdev"
} finally {
  Remove-Item Env:MOONSHOT_API_KEY -ErrorAction SilentlyContinue
}
```

After both dev arms pass:

```powershell
python -m benchmark.physics.cli metrics `
  --root Data\physics\benchmark `
  --baseline-run Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-baseline-text-G1-dev-r1 `
  --candidate-run Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-candidate-text-G1-dev-r1 `
  --output-json Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-dev-G1-baseline-vs-candidate.metrics.json `
  --output-md Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-dev-G1-baseline-vs-candidate.metrics.md
```

### Kimi Held-Out Run

Run this only after both Kimi development arms pass.

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

$secure = Read-Host "Kimi / Moonshot API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:MOONSHOT_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

try {
  $runCommit = git rev-parse --short HEAD
  $model = "kimi-k2.6"
  $endpoint = "https://api.moonshot.cn/v1"

  python -m benchmark.core.cli run-model-packet `
    --provider kimi `
    --model $model `
    --endpoint $endpoint `
    --input-mode text-only `
    --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-test-r1 `
    --output Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-baseline-text-G1-test-r1 `
    --max-retries 2 `
    --run-commit $runCommit
  $btest = $LASTEXITCODE

  python -m benchmark.core.cli run-model-packet `
    --provider kimi `
    --model $model `
    --endpoint $endpoint `
    --input-mode text-only `
    --packet Data\physics\benchmark\text_packets\physics-week9-candidate-v2-text-strict-schema\G1-test-r1 `
    --output Data\physics\benchmark\runs\physics-week9-kimi-benchmark\kimi-candidate-text-G1-test-r1 `
    --max-retries 2 `
    --run-commit $runCommit
  $ctest = $LASTEXITCODE

  "kimi held-out baseline exit=$btest; kimi held-out candidate exit=$ctest"
} finally {
  Remove-Item Env:MOONSHOT_API_KEY -ErrorAction SilentlyContinue
}
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

## Claude Code Route

Use this route when Claude Code is installed and authenticated on the reviewer's
machine.

Preflight:

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"
claude --version
claude -p "Return exactly the word OK." --output-format json --max-turns 1 --model claude-sonnet-4-20250514
```

Development run:

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

$runCommit = git rev-parse --short HEAD
$model = "claude-sonnet-4-20250514"

python scripts\run_headless_packet.py `
  --engine claude `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-dev-r1 `
  --output Data\physics\benchmark\runs\physics-week9-headless-claude\claude-baseline-text-G1-dev-r1 `
  --max-retries 2 `
  --run-commit $runCommit
$baseline = $LASTEXITCODE

python scripts\run_headless_packet.py `
  --engine claude `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-candidate-v2-text-strict-schema\G1-dev-r1 `
  --output Data\physics\benchmark\runs\physics-week9-headless-claude\claude-candidate-text-G1-dev-r1 `
  --max-retries 2 `
  --run-commit $runCommit
$candidate = $LASTEXITCODE

"claude dev baseline exit=$baseline; claude dev candidate exit=$candidate"
```

After both dev arms pass:

```powershell
python -m benchmark.physics.cli metrics `
  --root Data\physics\benchmark `
  --baseline-run Data\physics\benchmark\runs\physics-week9-headless-claude\claude-baseline-text-G1-dev-r1 `
  --candidate-run Data\physics\benchmark\runs\physics-week9-headless-claude\claude-candidate-text-G1-dev-r1 `
  --output-json Data\physics\benchmark\runs\physics-week9-headless-claude\claude-dev-G1-baseline-vs-candidate.metrics.json `
  --output-md Data\physics\benchmark\runs\physics-week9-headless-claude\claude-dev-G1-baseline-vs-candidate.metrics.md
```

### Claude Code Held-Out Run

Run this only after both Claude development arms pass.

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

$runCommit = git rev-parse --short HEAD
$model = "claude-sonnet-4-20250514"

python scripts\run_headless_packet.py `
  --engine claude `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-test-r1 `
  --output Data\physics\benchmark\runs\physics-week9-headless-claude\claude-baseline-text-G1-test-r1 `
  --max-retries 2 `
  --run-commit $runCommit
$baseline = $LASTEXITCODE

python scripts\run_headless_packet.py `
  --engine claude `
  --model $model `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-candidate-v2-text-strict-schema\G1-test-r1 `
  --output Data\physics\benchmark\runs\physics-week9-headless-claude\claude-candidate-text-G1-test-r1 `
  --max-retries 2 `
  --run-commit $runCommit
$candidate = $LASTEXITCODE

"claude held-out baseline exit=$baseline; claude held-out candidate exit=$candidate"
```

After both held-out arms pass:

```powershell
python -m benchmark.physics.cli metrics `
  --root Data\physics\benchmark `
  --baseline-run Data\physics\benchmark\runs\physics-week9-headless-claude\claude-baseline-text-G1-test-r1 `
  --candidate-run Data\physics\benchmark\runs\physics-week9-headless-claude\claude-candidate-text-G1-test-r1 `
  --output-json Data\physics\benchmark\runs\physics-week9-headless-claude\claude-heldout-G1-baseline-vs-candidate.metrics.json `
  --output-md Data\physics\benchmark\runs\physics-week9-headless-claude\claude-heldout-G1-baseline-vs-candidate.metrics.md
```

## Required Run Directory Contents

Each successful run directory should contain:

- `run-metadata.json`
- `validation.json`
- `usage.json`
- `command.txt`
- `command.argv.json`
- `raw-responses.jsonl`
- `failures.jsonl`
- `outputs/<student_id>.json`

Claude Code runs also contain:

- `headless-prompts/<student_id>.prompt.txt`
- `cli-logs/<student_id>-a<attempt>.stdout`
- `cli-logs/<student_id>-a<attempt>.stderr`

These files stay local under ignored `Data/`.

## Return This Summary To YY

After running, return this JSON summary in chat. Do not paste raw student
answers or raw model responses.

```json
{
  "operator": "advisor_or_external_ai",
  "engine_route": "kimi_api_or_kimi_code_executor_or_claude_code",
  "repo_commit": "short git commit hash",
  "split": "development",
  "baseline_run": {
    "path": "Data/physics/benchmark/runs/...",
    "validation_status": "passed_or_failed",
    "students_expected": 8,
    "students_passed": 8
  },
  "candidate_run": {
    "path": "Data/physics/benchmark/runs/...",
    "validation_status": "passed_or_failed",
    "students_expected": 8,
    "students_passed": 8
  },
  "metrics": {
    "json": "Data/physics/benchmark/runs/...metrics.json",
    "markdown": "Data/physics/benchmark/runs/...metrics.md"
  },
  "blockers": []
}
```

## Stop Conditions

Stop and report a blocker if:

- the local `Data/` directory is missing;
- the target packet path is missing;
- API authentication fails before a model run;
- output JSON fails validation for every student;
- one arm passes and the other arm fails for an infrastructure reason;
- any command would commit or upload raw private data.

## Git Policy

Commit only safe files:

- code;
- documentation;
- prompt templates;
- aggregate metrics summaries;
- reproducibility notes.

Do not commit:

- `Data/`;
- raw PDFs;
- raw transcripts;
- raw model responses;
- per-student model outputs;
- API keys.
