# AI Grading Autoresearch Program

This program is a lightweight operating manual for an autonomous grading
research loop. It is inspired by `karpathy/autoresearch`, but it is scoped to
`exam-automark` and must preserve student-data isolation.

## Mission

Improve a grading skill under controlled experiment conditions.

You may propose a candidate grading skill or grading prompt change, evaluate it
on the development split, and keep it only when the metrics and guardrails
improve. Held-out test is locked until the development gate passes.

## Non-Negotiable Boundaries

- Do not read or write raw `Data/` submissions during candidate generation.
- Do not put gold scores, identity maps, previous predictions, reports, or
  metrics into prompt packets.
- Do not tune on held-out test.
- Do not modify metrics code, packet audit code, or gold-score files to make a
  candidate look better.
- Do not modify `benchmark/physics/skillopt.py`,
  `benchmark/physics/skillopt_adapter.py`, existing Physics SkillOpt records,
  model runners, or prompt packet builders as part of this design/dry-run
  scaffold.
- Do not run real model calls unless the human explicitly starts a real run.
- Keep experiment records in English unless quoting source material or local
  paths.

## In-Scope Files

Read these before proposing a candidate:

- `experiments/README.md`
- `experiments/prompt_templates/README.md`
- `experiments/skill_versions/README.md`
- `benchmark/core/packets.py`
- `benchmark/core/plans.py`
- `benchmark/core/readiness.py`
- `benchmark/core/model_runner.py`
- `benchmark/physics/skillopt.py` and `benchmark/physics/skillopt_adapter.py`
  as read-only references for the current Physics SkillOpt scaffold
- the selected course spec under `experiments/course_specs/`
- the selected data inventory under `experiments/data_inventory/`
- the latest accepted skill snapshot under `experiments/skill_versions/`

The editable surface for a real SkillOpt iteration is intentionally narrow:

- `.agents/skills/grade-homework/`
- `.claude/skills/grade-homework/`
- `experiments/prompt_templates/grade_candidate_*.txt`
- `experiments/skill_versions/skill_candidate_*.json`
- candidate design notes under `experiments/skill_versions/`
- experiment records under `experiments/records/`

Do not edit packet builders, metrics, gold scores, or data inventories as part
of candidate optimization.

## Setup

1. Confirm the git branch and commit.
2. Confirm the working tree is clean before a real model run.
3. Choose a run ID, for example `physics-week9-skillopt-0001`.
4. Confirm baseline and latest accepted candidate skill snapshots.
5. Confirm course spec and data inventory paths.
6. Confirm development and held-out packet IDs are frozen.
7. Run the dry-run scaffold first:

```bash
python experiments/records/autoresearch-design/run_experiment.py \
  --mode dry-run \
  --record-id physics-week9-skillopt-0001 \
  --course-spec experiments/course_specs/physics_week9.json \
  --data-inventory experiments/data_inventory/physics.json \
  --baseline-skill experiments/skill_versions/skill_baseline_v1.json \
  --candidate-skill experiments/skill_versions/skill_candidate_v2.json
```

## SkillOpt Candidate Generation

For each candidate:

1. Read previous development metrics and failure notes.
2. Write a one-paragraph hypothesis.
3. Make one bounded skill or prompt change.
4. Mirror the change across `.agents/skills/` and `.claude/skills/` if it is a
   skill change.
5. Snapshot the candidate skill.
6. Record the candidate ID, changed files, and expected metric movement.
7. Stop if the candidate requires gold scores or held-out feedback to justify
   itself.

Candidate IDs must be monotonic:

```text
skill_candidate_autoresearch_0001
skill_candidate_autoresearch_0002
skill_candidate_autoresearch_0003
```

## Development Run

Development runs may use real models only after the human explicitly approves a
real run. Until then, use dry-run mode.

The model runner must:

- use the same packet IDs for baseline and candidate
- use the same student IDs and input hashes
- validate every output against `output.schema.json`
- record provider, model, parameters, packet hash, prompt hash, and run commit
- write raw outputs under ignored local run directories, not Git

## Metrics

Compute metrics against gold scores only after outputs are complete.

Primary metric:

- `total_score_mae`, lower is better

Guardrails:

- `subquestion_mae` must not regress materially
- `exact_agreement` should improve or remain stable
- `within_1_point_rate` should improve or remain stable
- `severe_error_rate` must not increase
- absolute `mean_signed_error` must not grow materially
- missing and invalid outputs must be zero for an automatic pass

## Development Decision

Keep the candidate only when:

- the primary metric improves
- no guardrail fails
- output validation passes
- the change is reviewable and bounded
- the explanation matches the observed metric movement

Reject the candidate when:

- it crashes or times out
- it leaks data or attempts to inspect forbidden files
- it improves one number by making the skill brittle
- it fails schema validation
- it regresses severe-error behavior
- it requires held-out tuning to look promising

Every rejected candidate gets a record. Do not erase the audit trail.

## Held-Out Gate

Held-out test is unlocked only after a development pass. On held-out:

- run the frozen candidate exactly once per approved protocol
- compute the same metrics
- record results even if they reject the candidate
- do not modify the candidate based on held-out findings

If held-out fails, record the failure and roll back to the previous accepted
candidate. Future candidates must be generated from development evidence only.

## Rollback

Before a real run, commit the candidate snapshot. If rejected:

1. Write the experiment record with rejection reason.
2. Preserve local raw outputs needed for audit.
3. Restore the active branch to the last accepted candidate by a revert commit
   or another explicit, reviewed git operation.
4. Append the rejected candidate to the run ledger.

Never silently delete the rejected candidate record.

## Headless Agent Templates

The concrete commands depend on the local Codex and Claude CLIs. The experiment
record should store the exact command used. Initial templates:

```bash
codex exec --full-auto --prompt-file experiments/records/autoresearch-design/program.md
```

```bash
claude -p "$(Get-Content -Raw experiments/records/autoresearch-design/program.md)"
```

These are templates only. A real setup must pin CLI versions, approval mode,
working directory, branch, and environment variables before use.
