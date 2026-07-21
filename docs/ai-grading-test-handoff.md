---
title: AI Grading Test Handoff
---

# AI Grading Test Handoff

This page is for an external reviewer or an AI coding assistant. Read this page,
then run the grading benchmark from a local checkout. If `Data/` is missing,
restore it from the private HKUST-GZ GitLab repository documented below before
running models.

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

## Private Data Handoff

### Private Data Bootstrap From GitLab

The reviewer or the reviewer's AI assistant must restore the private `Data/`
directory before any model run can start. YY has already invited the advisor's
HKUST-GZ GitLab account to the private project, so the advisor's AI should use
the advisor's own GitLab login or advisor-owned read-only token to fetch
`Data/`. Do not ask YY to manually download `Data/` unless advisor-owned
GitLab access is unavailable. The private data source is:

```text
http://gitlab.hkust-gz.edu.cn/yyuan308/exam-automark-private.git
```

The GitHub Pages site is only the public instruction layer. It must not contain
raw student data, API keys, GitLab tokens, raw transcripts, raw model responses,
or per-student outputs.

### Required GitLab Access

Use advisor-owned GitLab access. The AI assistant should authenticate as the
advisor or external reviewer account that YY has invited to YY's private GitLab project.
It must not request YY's GitLab password, YY's browser session, or YY's personal
token.

Expected access flow:

1. YY has already invited the advisor's HKUST-GZ GitLab account to
   `yyuan308/exam-automark-private` with at least read repository access.
2. The advisor confirms that this URL opens when signed in as the advisor:
   `http://gitlab.hkust-gz.edu.cn/yyuan308/exam-automark-private`.
3. The advisor's AI uses one of the authentication paths below to restore
   `Data/`.

Authentication paths:

- Preferred for AI automation: the advisor creates a temporary GitLab Personal
  Access Token from the advisor account with read-only repository access, then
  sets `GITLAB_TOKEN` in the local shell. Delete or revoke the token after the
  benchmark if it was created only for this run.
- Fallback for interactive review: the advisor's machine has Git Credential
  Manager or an equivalent credential helper configured, and the advisor logs in
  when `git clone` prompts for GitLab credentials.

Advisor-token setup examples:

Windows PowerShell:

```powershell
$secure = Read-Host "Advisor GitLab token with read_repository access" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:GITLAB_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
```

macOS/Linux:

```bash
read -rsp "Advisor GitLab token with read_repository access: " GITLAB_TOKEN
echo
export GITLAB_TOKEN
```

Optional advisor-account preflight before downloading `Data/`:

Windows PowerShell:

```powershell
$projectApi = "http://gitlab.hkust-gz.edu.cn/api/v4/projects/yyuan308%2Fexam-automark-private"
Invoke-WebRequest -Headers @{ "PRIVATE-TOKEN" = $env:GITLAB_TOKEN } -Uri $projectApi -UseBasicParsing | Select-Object -ExpandProperty StatusCode
```

macOS/Linux:

```bash
curl -fL --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
  "http://gitlab.hkust-gz.edu.cn/api/v4/projects/yyuan308%2Fexam-automark-private" >/dev/null
```

If neither advisor-owned path is available, stop and report
`gitlab_auth_missing` as a blocker. If the already-invited advisor account
still receives a permission error, stop and report `advisor_gitlab_access_denied`.
Do not bypass permissions and do not request that private data be moved to the
public GitHub repo.

### Recommended: Download Repository Archive And Restore Data

This method is preferred for an AI assistant because it uses the advisor-owned
`GITLAB_TOKEN` from the environment and restores only the `Data/` directory
into the public checkout.

Windows PowerShell:

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

if (-not $env:GITLAB_TOKEN) {
  throw "Set advisor-owned GITLAB_TOKEN with read_repository access to YY's private GitLab repo before running this step."
}

$privateRoot = Join-Path (Get-Location) ".private-data"
New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null

$archive = Join-Path $privateRoot "exam-automark-private.zip"
$apiUrl = "http://gitlab.hkust-gz.edu.cn/api/v4/projects/yyuan308%2Fexam-automark-private/repository/archive.zip"

Invoke-WebRequest `
  -Headers @{ "PRIVATE-TOKEN" = $env:GITLAB_TOKEN } `
  -Uri $apiUrl `
  -OutFile $archive

Expand-Archive -LiteralPath $archive -DestinationPath $privateRoot -Force

$archiveRoot = Get-ChildItem -LiteralPath $privateRoot -Directory |
  Where-Object { $_.Name -like "exam-automark-private-*" } |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $archiveRoot) { throw "Could not find extracted GitLab archive root." }
if (-not (Test-Path -LiteralPath (Join-Path $archiveRoot.FullName "Data"))) {
  throw "The extracted private archive does not contain Data/."
}
if (Test-Path -LiteralPath ".\Data") {
  throw "Data/ already exists. Move or remove the existing local Data/ before restoring to avoid mixed snapshots."
}

Copy-Item -Recurse -LiteralPath (Join-Path $archiveRoot.FullName "Data") -Destination ".\Data"

Test-Path Data\physics\benchmark
```

macOS/Linux:

```bash
cd /path/to/exam-automark

if [ -z "${GITLAB_TOKEN:-}" ]; then
  echo "Set advisor-owned GITLAB_TOKEN with read_repository access to YY's private GitLab repo before running this step." >&2
  exit 2
fi

private_root=".private-data"
mkdir -p "$private_root"
archive="$private_root/exam-automark-private.zip"
api_url="http://gitlab.hkust-gz.edu.cn/api/v4/projects/yyuan308%2Fexam-automark-private/repository/archive.zip"

curl -fL --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" "$api_url" -o "$archive"
unzip -q "$archive" -d "$private_root"

archive_root="$(find "$private_root" -maxdepth 1 -type d -name 'exam-automark-private-*' | sort | tail -n 1)"
if [ -z "$archive_root" ] || [ ! -d "$archive_root/Data" ]; then
  echo "Could not find Data/ inside the extracted private GitLab archive." >&2
  exit 2
fi
if [ -e Data ]; then
  echo "Data/ already exists. Move or remove it before restoring to avoid mixed snapshots." >&2
  exit 2
fi

cp -R "$archive_root/Data" ./Data
test -d Data/physics/benchmark
```

### Fallback: Sparse Clone The Private GitLab Repository

Use this only when the archive API is unavailable. This relies on GitLab
credentials being available interactively or through the local Git credential
manager. Do not put credentials in the URL.

Windows PowerShell:

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

New-Item -ItemType Directory -Force -Path ".private-data" | Out-Null
git clone --filter=blob:none --no-checkout `
  http://gitlab.hkust-gz.edu.cn/yyuan308/exam-automark-private.git `
  .private-data\exam-automark-private

git -C .private-data\exam-automark-private sparse-checkout init --cone
git -C .private-data\exam-automark-private sparse-checkout set Data
git -C .private-data\exam-automark-private checkout main

if (Test-Path -LiteralPath ".\Data") {
  throw "Data/ already exists. Move or remove it before restoring to avoid mixed snapshots."
}
Copy-Item -Recurse -LiteralPath ".private-data\exam-automark-private\Data" -Destination ".\Data"
```

macOS/Linux:

```bash
cd /path/to/exam-automark

mkdir -p .private-data
git clone --filter=blob:none --no-checkout \
  http://gitlab.hkust-gz.edu.cn/yyuan308/exam-automark-private.git \
  .private-data/exam-automark-private

git -C .private-data/exam-automark-private sparse-checkout init --cone
git -C .private-data/exam-automark-private sparse-checkout set Data
git -C .private-data/exam-automark-private checkout main

if [ -e Data ]; then
  echo "Data/ already exists. Move or remove it before restoring to avoid mixed snapshots." >&2
  exit 2
fi
cp -R .private-data/exam-automark-private/Data ./Data
```

### Required Data Layout

After restore, the repository should look like this:

```text
exam-automark/
  Data/
    physics/
      benchmark/
        text_packets/
        runs/
        gold/
```

Minimum data needed for this Physics Week 9 benchmark:

- `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1`
- `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1`
- `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-test-r1`
- `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-test-r1`
- the Physics benchmark gold-score files under `Data/physics/benchmark`

Before running models, verify the packets exist:

```powershell
Test-Path Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-dev-r1
Test-Path Data\physics\benchmark\text_packets\physics-week9-candidate-v2-text-strict-schema\G1-dev-r1
Test-Path Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-test-r1
Test-Path Data\physics\benchmark\text_packets\physics-week9-candidate-v2-text-strict-schema\G1-test-r1
```

All four checks should return `True`.

Also verify `Data/` and the temporary private checkout are not going to be committed.

Windows PowerShell:

```powershell
git status --short -- Data .private-data
git check-ignore -q Data/physics/benchmark; $LASTEXITCODE
git check-ignore -q .private-data; $LASTEXITCODE
```

macOS/Linux:

```bash
git status --short -- Data .private-data
git check-ignore -q Data/physics/benchmark; echo $?
git check-ignore -q .private-data; echo $?
```

`git status --short -- Data .private-data` should print nothing. Both
`git check-ignore` checks should return exit code `0`.

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
API commands below. Do not treat Kimi Code chat output as the benchmark result;
use the documented Kimi Code headless JSON mode instead (see "Kimi Code
Headless Route" below).

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

### Kimi Code Headless Route

Use this route when the reviewer has Kimi Code installed and logged in with a
Kimi membership subscription, and no Moonshot Open Platform API key is
available. It runs `kimi --output-format stream-json --prompt` non-interactively
per student; usage counts against the subscription's weekly quota and 5-hour
rate window.

Preflight:

```bash
kimi --version
kimi -p "Return exactly the word OK." --output-format stream-json
```

Development run (bash shown; use equivalent PowerShell paths on Windows).
`--model` takes a Kimi Code model alias such as `kimi-code/k3`:

```bash
runCommit="$(git rev-parse --short HEAD)"
model="kimi-code/k3"

python scripts/run_headless_packet.py \
  --engine kimi \
  --model "$model" \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-headless-kimi/kimi-baseline-text-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$runCommit"

python scripts/run_headless_packet.py \
  --engine kimi \
  --model "$model" \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-headless-kimi/kimi-candidate-text-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$runCommit"
```

After both dev arms pass, compute metrics with `python -m benchmark.physics.cli
metrics` pointing `--baseline-run` and `--candidate-run` at the two output
directories above. Run the held-out split the same way, only after both
development arms pass. Run-directory contents match the Claude Code route
(`headless-prompts/`, `cli-logs/`, `raw-responses.jsonl`, and so on), with
`provider: kimi_cli` in `run-metadata.json`.

## Kimi K3 Multimodal Route (Paper Images)

Use this route to grade directly from scanned paper-page images with the
multimodal `kimi-k3` model, instead of grading from transcripts. The per-student
output contract, validation, run-directory layout, and metrics commands are
identical to the text-only Kimi route above; only the packet inputs and
`--input-mode` differ.

Packet input rules for multimodal runs:

- `inputs/<student_id>/` must contain page images only (`.jpg`, `.jpeg`,
  `.png`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`), sorted so page order is
  correct (for example `page-001.jpg`, `page-002.jpg`).
- PDFs are rejected: convert each PDF page to an image first.
- Text files (transcripts) are rejected in multimodal packets.

Build multimodal packets with the generic `build-packet` command, pointing
`--input-root` at the anonymized page-image directory (`course.json`,
`prompt.txt`, and `rubric.json` can be reused from the corresponding text
packet):

```bash
SRC=Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1
python -m benchmark.core.cli build-packet \
  --course "$SRC/course.json" \
  --packet-id G1-dev-r1 \
  --condition G1 \
  --task grade \
  --prompt "$SRC/prompt.txt" \
  --rubric "$SRC/rubric.json" \
  --student-id S001 --student-id S002 --student-id S003 --student-id S004 \
  --student-id S005 --student-id S006 --student-id S007 --student-id S008 \
  --input-root Data/physics/benchmark/anonymized \
  --output-root Data/physics/benchmark/image_packets/physics-week9-baseline-image \
  --metadata split=development
```

There are two ways to run a multimodal packet:

1. **API route** (`run-model-packet --provider kimi --input-mode multimodal`):
   the runner embeds the page images as base64 `image_url` parts in one chat
   completion per student. Requires a Moonshot Open Platform API key.
2. **Headless route** (`run-headless-packet --engine kimi --input-mode
   multimodal`): the Kimi Code agent reads the page-image files from the
   packet with its own file tools and grades them. Runs under the reviewer's
   Kimi membership subscription; no platform API key needed. Recorded as
   `provider: kimi_cli` with `input_mode: multimodal` in `run-metadata.json`.

API route (same auth preflight and endpoint choice as the text-only Kimi
route; `--max-retries 2` recommended):

```bash
export MOONSHOT_API_KEY=...   # advisor-owned Kimi key, unset after the run
python -m benchmark.core.cli run-model-packet \
  --provider kimi \
  --model kimi-k3 \
  --endpoint https://api.moonshot.cn/v1 \
  --input-mode multimodal \
  --packet Data/physics/benchmark/image_packets/physics-week9-baseline-image/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-kimi-k3-multimodal/kimi-k3-baseline-image-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$(git rev-parse --short HEAD)"
```

Headless route:

```bash
python scripts/run_headless_packet.py \
  --engine kimi \
  --model kimi-code/k3 \
  --input-mode multimodal \
  --packet Data/physics/benchmark/image_packets/physics-week9-baseline-image/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-headless-kimi-multimodal/kimi-k3-baseline-image-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$(git rev-parse --short HEAD)"
```

Add `--dry-run` to smoke-test packet IO and validation without an API key.
Run the development split first; run held-out only after both development arms
pass, exactly as in the text-only route. Compare arms with the same
`python -m benchmark.physics.cli metrics` command, pointing `--baseline-run`
and `--candidate-run` at the multimodal run directories.

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

Headless engine runs (Claude Code, Kimi Code) also contain:

- `headless-prompts/<student_id>.prompt.txt`
- `cli-logs/<student_id>-a<attempt>.stdout`
- `cli-logs/<student_id>-a<attempt>.stderr`

These files stay local under ignored `Data/`.

## Return This Summary To YY

After running, return this JSON summary in chat. Include how `Data/` was
restored, but do not paste raw student answers, raw model responses, tokens,
or private GitLab URLs containing credentials.

```json
{
  "operator": "advisor_or_external_ai",
  "data_restore": {
    "source": "HKUST-GZ GitLab yyuan308/exam-automark-private",
    "auth_identity": "advisor_gitlab_account_already_invited_by_YY",
    "method": "advisor_token_archive_or_advisor_interactive_sparse_clone",
    "status": "restored_or_blocked"
  },
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

- the local `Data/` directory is missing and GitLab restore cannot run;
- the target packet path is missing;
- advisor-owned GitLab authentication is missing or fails;
- the already-invited advisor GitLab account still receives access denied;
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
