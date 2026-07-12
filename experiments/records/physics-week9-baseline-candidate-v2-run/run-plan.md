# Physics Week 9 Baseline vs Candidate v2 Run Plan

Status: planned, no model calls yet.

This branch is a dependent experiment branch. It starts from
`codex/repro-experiment-framework @ c34427c` and depends on the framework draft
PR. Do not merge this branch before the framework PR is reviewed or rebased
onto `main`.

## Purpose

Run a controlled Physics Week 9 comparison between:

- baseline grading skill: `skill_baseline_v1`
- candidate grading skill: `skill_candidate_v2`

The question is not whether AI grading is generally solved. The question is
whether candidate v2 improves the Physics Week 9 grading workflow under the
same data snapshot, same rubric, same student inputs, same output schema, and
same transcription prompt.

## Fixed Inputs

Use the branch-specific physics plan copies as the source of record for model
execution on this branch:

- Branch baseline plan:
  `experiments/records/physics-week9-baseline-candidate-v2-run/baseline-plan.json`
- Branch candidate plan:
  `experiments/records/physics-week9-baseline-candidate-v2-run/candidate-v2-plan.json`

These plan copies preserve the same packet IDs, prompt hashes, skill hashes,
data snapshot hash, packet paths, and packet hashes as the framework plans. They
only update the run branch and run-branch anchor so the pre-run gate can verify
the actual experiment branch.

The framework plans remain:

- Baseline plan:
  `experiments/records/physics-week9-standard-plan/plan.json`
- Candidate plan:
  `experiments/records/physics-week9-candidate-v2-plan/plan.json`
- Current pre-run gate:
  `experiments/records/physics-week9-run-readiness.json`
- Course spec:
  `experiments/course_specs/physics_week9.json`
- Data inventory:
  `experiments/data_inventory/physics.json`

The data snapshot hash is:

`e0b47a06a3ec12417a70a773ac8d5728ebbbd40c8991ac7ec7a11c2a92d2a6f3`

Real student data remains under ignored `Data/` paths and must not be committed.

The pre-model-call software environment snapshot is recorded in:

- `experiments/records/physics-week9-baseline-candidate-v2-run/software-environment.json`
- `experiments/records/physics-week9-baseline-candidate-v2-run/software-environment.md`

Capture a fresh software environment snapshot at the exact model-run commit.

## Packets To Run

Use the already built prompt packets under ignored `Data/`:

Baseline packet root:

`Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/`

Candidate packet root:

`Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/`

Planned packet IDs:

| Packet | Task | Split | Purpose |
| --- | --- | --- | --- |
| `T1-dev-r1` | transcribe | development | Check transcription workflow and output format. |
| `T1-test-r1` | transcribe | heldout | Held-out transcription run. |
| `G1-dev-r1` | grade | development | Check grading workflow and output format. |
| `G1-test-r1` | grade | heldout | Held-out grading comparison. |

Do not change packet contents before model execution. If any packet changes,
regenerate the packet hash and the run-readiness report before running models.

## Pre-Run Gate On This Branch

Before any model call on this branch:

1. Confirm the worktree is clean.
2. Generate the branch-specific run-readiness record from:
   - `experiments/records/physics-week9-baseline-candidate-v2-run/baseline-plan.json`
   - `experiments/records/physics-week9-baseline-candidate-v2-run/candidate-v2-plan.json`
3. Confirm the current branch is `codex/physics-week9-baseline-candidate-v2-run`.
4. Confirm baseline and candidate still use:
   - same course and assessment
   - same data snapshot
   - same student IDs and input hashes per packet
   - same rubric hash for grade packets
   - same transcription prompt hash
   - different grading prompt and skill hashes
5. Confirm `Data/` is ignored and no `Data/` files are tracked.
6. Confirm all model-facing rubrics and prompts are English.
7. Confirm required runtime software and provider SDKs are installed and
   version-recorded.

No model call should happen unless the branch-specific readiness status is
`ready`.

## Rubric Language Policy

The teacher confirmed that rubric-based grading is acceptable, but the rubric
must be in English.

For this experiment:

- model-facing rubrics must be English
- model-facing prompt instructions must be English
- partial-credit rules must be English
- grading evidence and feedback fields should be English
- non-English source notes must be translated into an English rubric before
  packet construction

If a rubric translation changes scoring meaning, stop and ask the teacher before
running models. If an English rubric changes after packets are built, rebuild the
affected packets and regenerate readiness.

## Model Run Recording

For every model-facing packet, record:

- run ID
- branch and commit
- provider and model display name
- API/model version if available
- temperature and other generation parameters
- packet path and packet hash
- prompt path and prompt hash
- software environment record path
- start time and end time
- output directory
- failure, retry, or manual intervention notes

Expected output location:

`Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/`

Suggested run IDs:

- `baseline-T1-dev-r1`
- `baseline-T1-test-r1`
- `baseline-G1-dev-r1`
- `baseline-G1-test-r1`
- `candidate-T1-dev-r1`
- `candidate-T1-test-r1`
- `candidate-G1-dev-r1`
- `candidate-G1-test-r1`

Model outputs remain outside Git until they are reduced into shareable
metadata, metrics, and report artifacts.

## Metrics Plan

After model outputs are complete and validated, compute at least:

- total score MAE
- subquestion MAE
- exact agreement rate
- within-1-point rate
- severe error rate
- per-question accuracy or agreement
- mean signed error, to detect bias
- missing-output and invalid-output counts

Report metrics separately for development and held-out splits. Do not combine
them into a single headline without also showing the split-level values.

## Report Plan

The final report should be a Typst/PDF note, not only a Markdown summary.

It should include:

- research question
- data snapshot and privacy statement
- branch, commit, prompt hashes, packet hashes, and skill hashes
- reproduction commands
- run table with model metadata
- baseline vs candidate metric tables
- bar charts for key metrics
- per-question comparison
- failure and retry notes
- limitations

The report must state that Physics Week 9 is a pilot-derived benchmark and must
not be generalized to all courses without DSAA3073, DSAA3701, and linear algebra
follow-up experiments.

## Stop Conditions

Stop before model calls if:

- readiness is not `ready`
- any packet audit fails
- `Data/` appears in tracked files
- prompt hashes differ from the recorded plan unexpectedly
- rubric or student inputs changed without a new data snapshot record
- model-facing rubric text is not English
- required runtime software is missing or unversioned
- teacher feedback changes the candidate v2 scoring policy

## Current Status

No model calls have been made on this branch.
