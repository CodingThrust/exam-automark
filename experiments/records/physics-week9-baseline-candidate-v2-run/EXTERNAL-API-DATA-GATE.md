# External API Data Gate

Status: real DeepSeek dev run not executed.

Captured date: 2026-07-12, Asia/Shanghai.

Git branch: `codex/physics-week9-baseline-candidate-v2-run`

## Why The Run Is Gated

The planned real DeepSeek run would send the development text packet to an
external API endpoint:

- provider: `deepseek`
- endpoint: `https://api.deepseek.com`
- input mode: `text-only`
- text source:
  `Data/physics/benchmark/transcripts/automatic/T1-dev-r1`

Although the packet is anonymous and stored under ignored `Data/`, it still
contains course assessment material and pilot-derived student work transcripts.
Sending this content to an external model provider is an external data
disclosure and requires explicit approval before execution.

## Current Technical Status

| Item | Status |
| --- | --- |
| `openai` SDK | installed, `2.45.0` |
| `DEEPSEEK_API_KEY` in current process | set |
| Run readiness | ready |
| Baseline dry-run | passed, 8/8 |
| Candidate v2 dry-run | passed, 8/8 |
| Real baseline DeepSeek run | not executed |
| Real candidate DeepSeek run | not executed |

No real model output directory was created for:

- `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1`
- `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1`

## Approval Needed Before Real Runs

Before running either real DeepSeek command, record explicit approval that:

- the text packets are sufficiently anonymized for external API processing
- the DeepSeek API is allowed for this course data
- the external provider data-retention and privacy terms are acceptable
- the run is limited to the development split first
- the API key value will not be printed, committed, or copied into any record

If approval is granted, record the approver, date, allowed provider, allowed
data split, and any restrictions in this experiment record before running the
commands in `DEEPSEEK-DEV-RUN-COMMANDS.md`.

## Safer Alternatives

If external API approval is not granted, use one of these alternatives:

- run the same packet format against an institution-approved internal endpoint
- run a local model on the anonymous transcript packets
- create a synthetic non-student packet for end-to-end API testing only
- postpone real model calls until the private HKUST-GZ GitLab data governance
  path is settled
