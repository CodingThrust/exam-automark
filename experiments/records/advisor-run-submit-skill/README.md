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
  `probe`, `plan`, `prepare`, `run`, `package`, and `submit` commands.
- Generated two-stage development and sealed-test presets: Kimi and Claude each
  transcribe the approved anonymous images, their strict outputs generate
  engine-specific baseline/candidate text packets, and both engines also run
  direct multimodal baseline/candidate grading. The workflow covers all eight
  development students first and then all 18 test students.
- Deterministic decision gates for transcript provenance, image privacy approval,
  matched student sets, development-before-held-out, immutable retries, and
  technical-failure classification.
- Automatic aggregate metrics packaging and focused Git
  branch/commit/push/draft-PR submission through authenticated `gh`. An
  environment-only `GITHUB_TOKEN` is limited to PR API creation after Git
  transport is separately authenticated.
- Automatic `CROSS-PROVIDER-COMPARISON.md` and JSON generation that places new
  Kimi/Claude candidate-v2 metrics beside the already committed DeepSeek/Codex
  evidence while keeping historical frozen-transcript, fresh-transcript, and
  direct-multimodal routes visibly distinct.
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
- Text-only packets must be generated from the same engine's fresh
  transcription output and record source kind, source path, source run ID, and
  transcription packet hash. Historical transcripts are comparison context,
  not a substitute for the new transcription stage.
- Test execution requires development to pass and an explicit full-campaign or
  test approval. Test findings may not be used to tune and rerun the same test.
- Real student-data runs require a user-approved, zero-data engine/model probe
  receipt for the current commit.
- Claude text runs have no tools; Claude multimodal runs expose only `Read` and
  allow enough turns to read the page images. Every student CLI call has a
  finite timeout, and systemic authentication/quota failures stop the arm
  early.
- Existing passed matching runs may be resumed; failed, incomplete, or
  mismatched directories are preserved and retried under a new identity.
  Reuse also requires the same commit, retry policy, timeout, model, mode, and
  packet.
- A technical failure is not an accuracy score. It is aggregated, packaged,
  and submitted as failure evidence.
- Public metric artifacts are rebuilt from an aggregate allowlist so local
  absolute paths and JSON-key student identifiers cannot leak into the PR.

## Verification

- `skill-creator` validation passed for both repository skill copies.
- The two skill directories are byte-for-byte identical.
- Core benchmark tests cover strict headless transcription, fresh transcript
  packet generation, and committed historical-result loading.
- `85` physics benchmark tests passed.
- An independent clean-context forward test followed the skill through
  `doctor`, `plan`, `prepare`, and dry-run without hidden instructions. Its
  finding that `.private-data/` was not independently checked was fixed and
  covered by a regression test.
- An offline end-to-end smoke run built baseline, candidate, and canonical T1
  privacy-approved image packets; produced Kimi and Claude transcriptions at
  `8/8` each; generated four engine-specific text packets; and exercised all
  eight grading arms at `8/8`.
- Repeating the same smoke run reused all eight matching passed arms without
  overwriting them.
- A separate sealed-test smoke run produced two `18/18` strict transcript runs,
  four engine-specific text packets, and eight `18/18` grading arms. All
  `180/180` dry-run outputs validated without external model calls.
- The final fresh-config smoke test also exposed and fixed two automation
  defects: child-run JSON polluted the top-level machine-readable output, and
  the conceptual baseline/candidate label was not persisted for safe reuse.
- The smoke used the deterministic dry provider and made no Kimi, Claude, or
  other external model calls.

## How this improves the project

The advisor can now give one intent-level prompt and let the local agent perform
preflight, setup assistance, input preparation, both grading modes, validation,
safe reporting, and PR submission. The same path also captures negative and
technical results, so iteration history is less biased toward successful runs.
The current Physics preset now measures each engine's transcription stage
explicitly, preventing a new model's grading result from being attributed to a
historical transcript it never produced. The result PR also gives the advisor a
single table containing prior DeepSeek/Codex and new Kimi/Claude evidence.

## Remaining acceptance test

GitHub CLI is now installed and authenticated on the development machine, and
the implementation was returned as draft PR `#29`. This machine still does not
have authenticated Kimi Code or Claude Code, so the remaining acceptance test
is deliberately on the advisor machine: invoke the skill, approve
environment/login setup, run the development matrix with the real CLIs, freeze
the workflow, then run the 18-student test matrix and return both automatically
created draft result PR URLs.
