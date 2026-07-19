# Claude Code Reproduction Guide

This guide explains how an external reviewer can reproduce the text-only
grading experiment with Claude Code in headless mode. It is written for a
machine that has the private `Data/` directory restored locally.

No real Claude model call has been made in this repository yet. The Claude
runner boundary is dry-run tested and records the exact command shape that a
reviewer should use for the first real Claude run.

## What This Reproduces

The Claude Code run uses the same prompt packets as the DeepSeek and Codex CLI
physics Week 9 text-only experiments:

- baseline packet:
  `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1`
- candidate-v2 packet:
  `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1`

The comparison is valid only when these are fixed:

- git commit hash;
- packet directory and packet hash;
- prompt hash;
- rubric hash;
- transcript source hash;
- split and anonymous student IDs;
- provider/model/CLI version.

## Prerequisites

Run from the repository root.

```powershell
Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"
git status --short --branch
git rev-parse --short HEAD
```

For this branch-level reproduction guide, the reviewer should be on:

```text
codex/claude-headless-support
```

or on a later `main` commit after this branch has been merged.

Install and authenticate Claude Code following Anthropic's official Claude Code
CLI reference:

- https://docs.anthropic.com/en/docs/claude-code/cli-usage

Then verify that the command-line tool is available:

```powershell
claude --version
claude --help
```

Check that non-interactive print mode can return structured JSON:

```powershell
claude -p "Return exactly the word OK." --output-format json --max-turns 1 --model claude-sonnet-4-20250514
```

The output should be an outer Claude Code JSON object containing a string
`result` field. The experiment runner parses that `result` string as the model's
grading response.

## Windows PowerShell Run

Choose a new output directory for each real run. Do not reuse an existing output
directory, because the runner intentionally refuses to overwrite prior results.

```powershell
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

"baseline exit=$baseline; candidate exit=$candidate"
```

## macOS/Linux Run

```bash
run_commit="$(git rev-parse --short HEAD)"
model="claude-sonnet-4-20250514"

python scripts/run_headless_packet.py \
  --engine claude \
  --model "$model" \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-headless-claude/claude-baseline-text-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$run_commit"

baseline=$?

python scripts/run_headless_packet.py \
  --engine claude \
  --model "$model" \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-headless-claude/claude-candidate-text-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$run_commit"

candidate=$?

echo "baseline exit=$baseline; candidate exit=$candidate"
```

## Internal Claude Command Shape

For each student, the runner pipes the composed grading prompt to Claude Code:

```text
claude -p --output-format json --max-turns 1 --model claude-sonnet-4-20250514
```

Claude Code returns an outer JSON object. The runner extracts the outer `result`
field and then validates that string as the required grading JSON against the
packet's `output.schema.json`.

## Expected Output Files

Each run writes:

- `run-metadata.json`
- `validation.json`
- `usage.json`
- `command.txt`
- `command.argv.json`
- `raw-responses.jsonl`
- `failures.jsonl`
- `outputs/<student_id>.json`
- `headless-prompts/<student_id>.prompt.txt`
- `cli-logs/<student_id>-a<attempt>.stdout`
- `cli-logs/<student_id>-a<attempt>.stderr`

For a successful run, `validation.json` should report:

```json
{
  "status": "passed",
  "students_expected": 8,
  "students_failed": 0,
  "students_passed": 8
}
```

`run-metadata.json` should record:

- `provider: claude_cli`
- `engine: claude`
- `model: claude-sonnet-4-20250514`
- `engine_version` from `claude --version`
- `run_commit`
- `packet_hash`
- `prompt_hash`
- `rubric_hash`
- `text_source_hash`

## Metrics

After both baseline and candidate-v2 pass validation, compare them against the
physics gold scores:

```powershell
python -m benchmark.physics.cli metrics `
  --root Data\physics\benchmark `
  --baseline-run Data\physics\benchmark\runs\physics-week9-headless-claude\claude-baseline-text-G1-dev-r1 `
  --candidate-run Data\physics\benchmark\runs\physics-week9-headless-claude\claude-candidate-text-G1-dev-r1 `
  --output-json Data\physics\benchmark\runs\physics-week9-headless-claude\claude-dev-G1-baseline-vs-candidate.metrics.json `
  --output-md Data\physics\benchmark\runs\physics-week9-headless-claude\claude-dev-G1-baseline-vs-candidate.metrics.md
```

macOS/Linux:

```bash
python -m benchmark.physics.cli metrics \
  --root Data/physics/benchmark \
  --baseline-run Data/physics/benchmark/runs/physics-week9-headless-claude/claude-baseline-text-G1-dev-r1 \
  --candidate-run Data/physics/benchmark/runs/physics-week9-headless-claude/claude-candidate-text-G1-dev-r1 \
  --output-json Data/physics/benchmark/runs/physics-week9-headless-claude/claude-dev-G1-baseline-vs-candidate.metrics.json \
  --output-md Data/physics/benchmark/runs/physics-week9-headless-claude/claude-dev-G1-baseline-vs-candidate.metrics.md
```

## Privacy And Git Policy

Do not commit `Data/`, `raw-responses.jsonl`, `outputs/`,
`headless-prompts/`, or `cli-logs/`.

The committed repository should contain only:

- code;
- prompt templates;
- packet manifests and hashes when safe;
- aggregate metrics summaries;
- reproducibility commands;
- report source files.

The raw private PDFs, transcripts, per-student model outputs, and raw Claude
responses remain in ignored `Data/` and should be shared only through the
private HKUST-GZ GitLab data repository.

## Troubleshooting

If `claude` is not recognized, install Claude Code and reopen the terminal.

If authentication fails, run Claude Code's login/auth setup and repeat:

```powershell
claude --version
claude -p "Return exactly the word OK." --output-format json --max-turns 1 --model claude-sonnet-4-20250514
```

If the runner says the output directory already exists, choose a new output
directory suffix such as `-r2` instead of deleting the prior attempt.

If validation fails, inspect only the local ignored files:

- `validation.json`
- `failures.jsonl`
- `cli-logs/*.stderr`

Then record whether the failure was a CLI/auth/schema failure or a true grading
result. Do not treat failed validation as an accuracy result.
