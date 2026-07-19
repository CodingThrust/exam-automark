# Codex CLI Headless Mode Run Protocol

Status: Codex and Claude runner boundaries are dry-run ready. A real Codex
physics development run is recorded separately under
`experiments/records/physics-week9-codex-headless-run/`. No real Claude model
call has been made in this repository yet.

## Purpose

This TODO adds a reproducible headless scoring path for the same text-only
prompt packets used in the DeepSeek experiments. The main comparison it enables
is:

```text
DeepSeek public API run vs Codex CLI headless run
```

under the same packet hash, prompt hash, rubric hash, anonymous student IDs, and
git commit hash.

Codex CLI should be recorded as an `OpenAI/Codex` condition, not as the same
surface as ChatGPT web or the ChatGPT desktop UI. It uses the Codex CLI entry
point and whichever authentication/model configuration is active on the runner's
machine. If Codex is authenticated through ChatGPT login, it consumes
ChatGPT/Codex usage. If it is authenticated through an API key, billing follows
the API key's model access and token usage.

## Source From Official Codex Manual

The local Codex manual fetched on 2026-07-19 identifies Codex CLI as the terminal
entry point for developer work and documents `codex exec` as the non-interactive
command. It also distinguishes ChatGPT plan usage from API-key usage for Codex
CLI automation.

## Source From Official Claude Code CLI Reference

The Anthropic Claude Code CLI reference documents `claude -p` / `--print` as
non-interactive print mode, `--output-format json` as structured print output,
`--max-turns` as a bound on non-interactive agent turns, and `--model` as the
model selector:

- <https://docs.anthropic.com/en/docs/claude-code/cli-usage>

The Claude JSON print output wraps the assistant response in a JSON object. The
runner therefore reads the outer `result` field and treats that string as the
model's grading JSON.

## Headless Prompt Snapshot

The runner prepends the stable wrapper prompt tracked at:

- `experiments/records/Codex-CLI-headless-mode/headless-mode-prompt.md`

The packet-specific grading prompt remains the packet's own `prompt.txt`. The
actual per-student prompt is written locally under the ignored run directory:

```text
<run-output>/headless-prompts/<student_id>.prompt.txt
```

Those local prompts may contain transcript text and must not be committed.

## Reproducing Script

Use the thin Python wrapper:

```text
scripts/run_headless_packet.py
```

It delegates to:

```text
python -m benchmark.core.cli run-headless-packet
```

The runner writes the same core run shape as the DeepSeek runner:

- `run-metadata.json`
- `command.txt`
- `command.argv.json`
- `raw-responses.jsonl`
- `failures.jsonl`
- `validation.json`
- `usage.json`
- `outputs/<student_id>.json`

## Windows PowerShell Dry Run

Run from the repository root. This validates packet IO and output schema without
calling Codex.

```powershell
$runCommit = git rev-parse --short HEAD

python scripts\run_headless_packet.py `
  --engine codex `
  --model gpt-5.6-codex `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text\G1-dev-r1 `
  --output Data\physics\benchmark\runs\physics-week9-headless-codex\codex-baseline-text-G1-dev-r1-dryrun `
  --dry-run `
  --run-commit $runCommit
```

## Windows PowerShell Real Codex Run

PowerShell may block `codex.ps1`. The runner therefore records the internal
Windows command as `codex.cmd exec`.

```powershell
$runCommit = git rev-parse --short HEAD

python scripts\run_headless_packet.py `
  --engine codex `
  --model gpt-5.6-codex `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text\G1-dev-r1 `
  --output Data\physics\benchmark\runs\physics-week9-headless-codex\codex-baseline-text-G1-dev-r1 `
  --max-retries 2 `
  --run-commit $runCommit
```

Equivalent direct Codex command shape used internally for each student:

```powershell
codex.cmd exec --json --output-last-message <last-message-file> `
  --output-schema <packet>\output.schema.json `
  --sandbox read-only `
  --cd <packet> --model gpt-5.6-codex -
```

## macOS/Linux Codex Run

Run from the repository root:

```bash
run_commit="$(git rev-parse --short HEAD)"

python scripts/run_headless_packet.py \
  --engine codex \
  --model gpt-5.6-codex \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-headless-codex/codex-baseline-text-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$run_commit"
```

Equivalent direct command shape:

```bash
codex exec --json --output-last-message <last-message-file> \
  --output-schema <packet>/output.schema.json \
  --sandbox read-only \
  --cd <packet> --model gpt-5.6-codex -
```

## Claude Headless Boundary

Claude CLI is not installed on the current Windows machine, so Claude support is
implemented as a dry-run verified runner boundary rather than a verified local
model run. If Claude CLI is installed later, use the same packet runner with
`--engine claude`.

A reviewer-facing step-by-step guide is tracked at:

- `experiments/records/Codex-CLI-headless-mode/CLAUDE-CODE-REPRODUCTION.md`

Windows PowerShell:

```powershell
$runCommit = git rev-parse --short HEAD

python scripts\run_headless_packet.py `
  --engine claude `
  --model claude-sonnet-4-20250514 `
  --input-mode text-only `
  --packet Data\physics\benchmark\text_packets\physics-week9-baseline-text-strict-schema\G1-dev-r1 `
  --output Data\physics\benchmark\runs\physics-week9-headless-claude\claude-baseline-text-G1-dev-r1 `
  --max-retries 2 `
  --run-commit $runCommit
```

macOS/Linux:

```bash
run_commit="$(git rev-parse --short HEAD)"

python scripts/run_headless_packet.py \
  --engine claude \
  --model claude-sonnet-4-20250514 \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-headless-claude/claude-baseline-text-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$run_commit"
```

Equivalent direct Claude command shape used internally for each student:

```bash
claude -p --output-format json --max-turns 1 --model claude-sonnet-4-20250514
```

The student's prompt is piped to stdin. Claude's outer JSON response is kept in
the ignored `raw-responses.jsonl` and the runner parses its `result` field as the
actual grading response to validate against `output.schema.json`.

Before reporting Claude results, record the exact Claude CLI version, model ID,
authentication mode, command help output, and whether the account uses Claude
subscription access or API billing in the experiment record.

## Comparison With DeepSeek

This can form a fair model/provider comparison only when all of these are fixed:

- same packet directory and packet hash;
- same prompt hash and rubric hash;
- same split and anonymous student IDs;
- same output schema and validation rules;
- same transcript source hash for text-only grading;
- same git commit hash from `git rev-parse --short HEAD`;
- no prompt or rubric edits after readiness.

The DeepSeek condition remains `provider=deepseek` through the public API. The
Codex condition should be recorded as `provider=codex_cli`. The Claude condition
should be recorded as `provider=claude_cli`. Differences in hidden system
behavior, CLI version, model routing, output wrapper format, and account/auth
mode must be reported as limitations.

## Stop Conditions

Stop before a real headless run if:

- the packet is not a text-only grading packet;
- `Data/` would need to be committed;
- the worktree has uncommitted tracked changes;
- the Codex or Claude model name is not recorded;
- the CLI version cannot be recorded for a real run;
- output JSON fails validation;
- one comparison arm is rerun with different prompt, rubric, or packet hashes.
