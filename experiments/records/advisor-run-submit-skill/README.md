# Advisor run-and-submit grading skill

Date: 2026-07-23

Branch: `feat/advisor-run-submit-skill`

## Problem

The earlier GitHub Pages handoff was reproducible but still required the
advisor to copy many commands, make several unstated choices, and return results
through private chat. That slows repeated Kimi/Claude experiments and makes
failed attempts easy to lose.

## What was added

- One cross-agent skill, mirrored for Codex/OpenCode and Claude Code.
- A stable `scripts/advisor_experiment.py` entry point with `init`, `doctor`,
  `plan`, `prepare`, `run`, `package`, and `submit` commands.
- A generated eight-arm development preset:
  Kimi/Claude × frozen transcript-first/direct multimodal × baseline/candidate.
- Deterministic decision gates for transcript provenance, image privacy approval,
  matched student sets, development-before-held-out, immutable retries, and
  technical-failure classification.
- Automatic aggregate metrics packaging and focused Git branch/commit/push/PR
  submission through authenticated `gh` or an environment-only
  `GITHUB_TOKEN`.
- A privacy gate that rejects `Data/`, `.private-data/`, unsupported public file
  types, anonymous student IDs, per-student JSON keys, and common secret
  patterns.
- A shorter GitHub Pages starting prompt that tells the advisor's local agent
  to configure the environment and own the workflow to the PR URL.

Kimi uses Kimi Code CLI authentication in this workflow. It does not require a
Moonshot Platform API key.

## Key decisions

- Both input modes are first-class experiment arms. One may be reported as
  blocked, but it may not be silently replaced by the other.
- Multimodal packets are generated only from pages listed as approved in the
  privacy review.
- Text-only packets must record source kind, source path, and source run ID.
  Automatic transcripts are allowed but are labeled separately from
  human-reviewed transcripts.
- Held-out execution requires a separate explicit approval.
- Existing passed matching runs may be resumed; failed, incomplete, or
  mismatched directories are preserved and retried under a new identity.
- A technical failure is not an accuracy score. It is aggregated, packaged,
  and submitted as failure evidence.

## Verification

- `skill-creator` validation passed for both repository skill copies.
- The two skill directories are byte-for-byte identical.
- `190` core benchmark tests passed.
- `85` physics benchmark tests passed.
- An offline end-to-end smoke run built two privacy-approved image packets and
  exercised all eight generated arms. Every arm produced `8/8` schema-valid
  dry-run outputs.
- Repeating the same smoke run reused all eight matching passed arms without
  overwriting them.
- The smoke used the deterministic dry provider and made no Kimi, Claude, or
  other external model calls.

## How this improves the project

The advisor can now give one intent-level prompt and let the local agent perform
preflight, setup assistance, input preparation, both grading modes, validation,
safe reporting, and PR submission. The same path also captures negative and
technical results, so iteration history is less biased toward successful runs.
The current Physics preset explicitly reports `automatic-transcript`
provenance, preventing OCR/transcription errors from being silently attributed
to the grading model.

## Remaining acceptance test

The current development machine does not have authenticated Kimi Code, Claude
Code, or GitHub CLI available. After merge, the advisor should invoke the skill
on the advisor machine, approve environment/login setup, run the development
matrix with real CLIs, and return the automatically created PR URL. A live
held-out run remains locked until the development results are reviewed.
