# Pre-Model-Call Preflight

Status: offline preflight complete. No real DeepSeek API call was made.

Captured date: 2026-07-12, Asia/Shanghai.

Git branch: `codex/physics-week9-baseline-candidate-v2-run`

Git commit: `93f843f405df5cbf4d4d4cd1524c77a153121959`

## Checks Performed

| Check | Result |
| --- | --- |
| Run readiness | `ready` |
| `Data/` Git tracking | ignored by `.gitignore` |
| Baseline text packet | already present |
| Candidate v2 text packet | already present |
| Baseline dry-run validation | passed, 8/8 students |
| Candidate v2 dry-run validation | passed, 8/8 students |
| Real API calls | none |

## Text-Only Packet Inputs

Both baseline and candidate v2 packets use:

- packet id: `G1-dev-r1`
- split: `development`
- text source: `Data/physics/benchmark/transcripts/automatic/T1-dev-r1`
- text source status: provisional, pilot-derived automatic transcript
- text source hash:
  `30e45836b26f6c05d0a55c2e436d5ace7078d01ae86932c3c64b27ad14e24cf8`
- students: `S008`, `S010`, `S012`, `S013`, `S016`, `S018`, `S019`, `S022`

Prompt packet locations:

- baseline:
  `Data/physics/benchmark/text_packets/physics-week9-baseline-text/G1-dev-r1`
- candidate v2:
  `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text/G1-dev-r1`

These packet directories are under ignored `Data/` and are not committed.

## Provider Readiness

The user reported that a DeepSeek API key is prepared. The current
Codex/PowerShell process does not yet expose `DEEPSEEK_API_KEY`.

The real model run must not start until:

- `openai` is installed for the OpenAI-compatible DeepSeek API client
- `DEEPSEEK_API_KEY` is set in the process environment
- a fresh software environment snapshot is captured at the exact run commit

The API key value must never be printed, committed, or copied into any record.

## Next Command Gate

After installing the provider SDK and setting `DEEPSEEK_API_KEY`, run only the
development split first:

1. baseline: `deepseek-baseline-text-G1-dev-r1`
2. candidate v2: `deepseek-candidate-text-G1-dev-r1`

Do not run held-out test packets until the development outputs validate and the
candidate v2 rule set is either accepted or revised.
