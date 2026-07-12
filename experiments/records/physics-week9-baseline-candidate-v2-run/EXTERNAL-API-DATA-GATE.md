# External API Data Gate

Status: supervisor approval clarified; Codex external execution remains blocked.

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

## Approval Recorded

Approval was reported by the project user on 2026-07-12:

- approver: course supervisor/advisor, exact name not recorded in this file
- provider allowed: `deepseek`
- endpoint allowed: `https://api.deepseek.com`
- allowed input mode: `text-only`
- allowed data split: development split only, `G1-dev-r1`
- allowed text source:
  `Data/physics/benchmark/transcripts/automatic/T1-dev-r1`
- data status: anonymous, pilot-derived automatic transcript
- API key handling: key value must not be printed, committed, copied into
  command records, or written into any report
- held-out test split: not approved for execution at this stage

This approval permits the two real development commands recorded in
`DEEPSEEK-DEV-RUN-COMMANDS.md`:

- `deepseek-baseline-text-G1-dev-r1`
- `deepseek-candidate-text-G1-dev-r1`

## Supervisor Clarification

The project user reported the supervisor's explicit follow-up response on
2026-07-12:

- For questions 1 and 2, anonymized data is acceptable.
- Running the development split first is acceptable.
- A public DeepSeek API is preferred over an internal endpoint because it has
  stronger external credibility for the experiment.
- Recording/accepting provider data-retention, logging, and privacy terms is
  acceptable.
- Recording the approval statement in the experiment record is acceptable.
- The supervisor requested that a first version be produced quickly.

Interpretation for this experiment record:

- approved provider: `deepseek`
- approved endpoint: `https://api.deepseek.com`
- approved content: anonymous student transcript text, course question text,
  grading prompt, and rubric/scoring rules
- approved split for the next run: development split only
- held-out test split: still not part of the next run step
- API key handling: key value must remain outside Git, command records, and
  reports

## Codex Execution Status

After the approval was recorded, Codex attempted to start the real baseline
development run. The execution environment blocked the command because it would
transmit anonymous but real/pilot-derived course and student transcript data to
the external DeepSeek API.

Result:

- real baseline DeepSeek run: not executed by Codex
- real candidate DeepSeek run: not executed by Codex
- real baseline output directory: not created
- real candidate output directory: not created
- API key value: not printed, not committed, not copied into records

This is an execution-environment policy limit, not a readiness failure in the
experiment framework. The reproducible command plan remains recorded, but Codex
must not bypass the external-data restriction.

## Safer Alternatives

If external API approval is not granted, use one of these alternatives:

- run the same packet format against an institution-approved internal endpoint
- run a local model on the anonymous transcript packets
- create a synthetic non-student packet for end-to-end API testing only
- postpone real model calls until the private HKUST-GZ GitLab data governance
  path is settled
