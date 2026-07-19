# Codex CLI Headless Mode Run Protocol

Status: protocol and runner dry-run ready. No real Codex or Claude model calls
were made in this branch.

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
  --sandbox read-only --ask-for-approval never `
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
  --sandbox read-only --ask-for-approval never \
  --cd <packet> --model gpt-5.6-codex -
```

## Claude Compatibility Boundary

Claude CLI is not installed on the current Windows machine, so Claude support is
implemented as a compatible runner boundary rather than a verified local model
run. If Claude CLI is installed later, use:

```bash
python scripts/run_headless_packet.py \
  --engine claude \
  --model <claude-model-id> \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-headless-claude/claude-baseline-text-G1-dev-r1 \
  --max-retries 2 \
  --run-commit "$(git rev-parse --short HEAD)"
```

Before reporting Claude results, record the exact Claude CLI version, model ID,
authentication mode, and command help output in the experiment record.

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
Codex condition should be recorded as `provider=codex_cli`. Differences in
hidden system behavior, CLI version, model routing, and account/auth mode must be
reported as limitations.

## Stop Conditions

Stop before a real headless run if:

- the packet is not a text-only grading packet;
- `Data/` would need to be committed;
- the worktree has uncommitted tracked changes;
- the Codex or Claude model name is not recorded;
- the CLI version cannot be recorded for a real run;
- output JSON fails validation;
- one comparison arm is rerun with different prompt, rubric, or packet hashes.
