# AI Grading Autoresearch Workflow Design

Status: design plus minimal executable dry-run scaffold. No model calls were
made, no prompt packets were rebuilt, and no files under `Data/` are touched by
this record.

## MVP Dry-Run

The directory now includes a single-prompt dry-run entry point:

- `single-prompt.md`: human-readable one-prompt instruction for an AI runner.
- `run-dry-run.ps1`: Windows PowerShell command wrapper.
- `run_experiment.py`: deterministic dry-run record builder.
- `dry-run-result.json`: committed sample output from the dry-run loop.

This MVP demonstrates the autoresearch control shape: read tracked inputs,
compare a baseline metric with a candidate metric, accept or reject the
candidate, and write a structured experiment record. It is not yet a full
model-driven autoresearch run.

## Purpose

This directory adapts the key ideas from
`https://github.com/karpathy/autoresearch` to AI grading experiments in
`exam-automark`. The target future workflow is:

```text
one prompt
  -> generate a candidate grading skill
  -> run development packets
  -> compute metrics against gold scores
  -> keep or reject the candidate
  -> only if it passes, unlock held-out test
  -> write an experiment record and report
```

The first implementation should be conservative. It should orchestrate the
experiment framework that already exists here instead of replacing it:

- prompt packet construction and audit in `benchmark.core.packets`
- plan records in `benchmark.core.plans`
- run-readiness gates in `benchmark.core.readiness`
- model-run dry-run support in `benchmark.core.model_runner`
- physics metrics in `benchmark.physics.metrics`
- reusable prompt templates in `experiments/prompt_templates/`
- frozen grading skill snapshots in `experiments/skill_versions/`

## Autoresearch Ideas To Keep

`karpathy/autoresearch` is intentionally small. The useful design ideas are:

- a human-written `program.md` acts like lightweight organization code for the
  agent
- the editable surface is narrow, so candidate diffs remain reviewable
- the evaluator is fixed and treated as ground truth
- each experiment has a bounded budget and a single primary metric
- every candidate is either kept, discarded, or marked crashed
- rejected candidates are rolled back while their outcome is still logged
- logs are append-only experiment evidence, while raw run outputs can remain
  outside Git

For grading, the equivalent of "edit `train.py` and optimize `val_bpb`" is:

```text
edit a candidate grading skill/prompt packet contract
run the same dev split against the same gold scores
optimize grading agreement and error metrics
```

## Migration To AI Grading

The AI grading loop should use the following surfaces.

| Autoresearch | AI grading equivalent |
| --- | --- |
| `program.md` | agent instructions in this directory |
| `train.py` | candidate grading skill and grading prompt |
| `prepare.py` | fixed data inventory, course spec, packet builder, evaluator |
| `val_bpb` | primary grading metric, initially `total_score_mae` |
| `results.tsv` | structured experiment record plus optional local run ledger |
| keep/discard branch advance | accept/reject candidate skill snapshot |

The loop must never let the candidate see gold scores, previous model outputs,
identity maps, or held-out test results. The candidate only receives blind
prompt packets.

## Dev/Test Gate

The development split is the only split an agent may iterate on.

Development gate:

- packet audit passes for all packets
- outputs validate against `output.schema.json`
- all expected anonymous student IDs are present
- gold scores are read only by the metrics stage
- candidate improves the primary metric versus baseline
- guardrails do not regress beyond thresholds
- the candidate diff remains reviewable and does not widen the editable surface

Held-out gate:

- held-out packets are frozen before any candidate iteration
- held-out is not run until the development gate passes
- no failed candidate may be retried on held-out
- a held-out failure rejects or quarantines the candidate; it must not trigger
  new tuning on held-out

## Prompt Packet Contract

Prompt packets remain the isolation boundary. A valid autoresearch run should
record:

- packet path and packet hash
- `prompt.txt` hash
- `course.json` hash
- `rubric.json` hash for grading packets
- input hashes by anonymous student ID
- split metadata: `development` or `heldout`
- skill version ID and skill hash

The packet audit should keep rejecting paths or text that leak gold scores,
metrics, identity maps, previous predictions, or reports.

## Gold Scores

Gold scores are not model input. They are evaluator-only data used after model
outputs are complete. A future generalized runner should treat gold records as:

- split-scoped
- versioned by data snapshot hash
- inaccessible to candidate generation
- loaded only inside metrics computation
- summarized in experiment records without exposing identities

Physics currently uses `Data/physics/benchmark/gold/primary_scores.csv` through
the metrics code. DSAA3073, DSAA3701, and linear algebra should define the same
kind of gold-score contract before they enter the autoresearch loop.

## Metrics

Initial primary metric:

- `total_score_mae`, lower is better

Initial guardrails:

- `subquestion_mae`, lower is better
- `exact_agreement`, higher is better
- `within_1_point_rate`, higher is better
- `severe_error_rate`, lower is better
- `mean_signed_error`, absolute value should not grow materially
- missing, invalid, or schema-repaired outputs must be reported

Candidate acceptance should prefer robust improvements over tiny metric wins
that add brittle grading instructions. A small improvement with a much simpler
skill may be accepted; a small improvement with a sprawling prompt should be
rejected or sent for teacher review.

## SkillOpt

SkillOpt is the proposed candidate generator. It is not a new model provider;
it is the policy that asks a headless coding agent to propose one bounded skill
change at a time.

SkillOpt responsibilities:

- read the baseline skill, latest accepted candidate, course spec, rubric
  policy, and development metric failures
- propose one candidate change with a clear hypothesis
- edit only the allowed skill/prompt files for the current run
- create a new skill snapshot before any model run
- avoid touching packet builders, metrics, gold scores, or raw data
- write rationale, expected failure modes, and rollback notes

Candidate IDs should be monotonic, for example
`skill_candidate_autoresearch_0001`.

## Relationship To Current SkillOpt Work

Current `origin/main` already contains a Physics SkillOpt pilot and adapter
scaffold under `benchmark/physics/skillopt.py`,
`benchmark/physics/skillopt_adapter.py`,
`experiments/records/physics-skillopt-pilot/`, and
`experiments/records/physics-skillopt-adapter/`. This TODO8 record is an
upper-level autoresearch workflow design. It documents how a future one-prompt
research loop should coordinate candidate generation, dev metrics, gate
decisions, held-out unlocks, and rollback handling.

This record intentionally does not modify or replace the current Physics
SkillOpt scaffold, model runners, prompt packet builders, metrics code,
existing experiment records, or `Data/`. A future implementation may call the
stable SkillOpt adapter as one component, but that integration is outside this
design/dry-run PR.

## Codex Headless

Codex headless is the natural runner for SkillOpt inside this repository
because it can edit files, run local CLIs, and commit candidate snapshots. The
first real version should run Codex with a prompt that points at `program.md`
and gives it a dedicated candidate branch.

The design assumes these phases:

1. `skillopt-generate`: Codex proposes and snapshots a candidate.
2. `dev-run`: the model runner evaluates development packets.
3. `dev-metrics`: metrics compare baseline and candidate.
4. `dev-decision`: the orchestrator accepts or rejects.
5. `heldout-run`: only accepted candidates advance to held-out.

The scaffold records command templates, but it does not execute headless Codex.

## Claude Headless

Claude headless can be used as a second implementation of the same SkillOpt
contract, especially because this repo mirrors skills under `.claude/skills/`.
The Claude path must follow the same packet and metric gates as Codex. A
candidate generated by Claude is accepted only if the resulting snapshot and
metrics satisfy the same schema.

The point of supporting both agents is not to compare brands. It is to make the
research organization portable: the program, packet contract, gate thresholds,
and experiment record should be agent-agnostic.

## Experiment Record

Each autoresearch iteration should produce one structured record:

- git branch and commit
- candidate ID
- baseline and candidate skill snapshots
- safe course spec and data inventory paths
- prompt packet IDs and hashes
- dev run status and metric deltas
- gate decision and rationale
- held-out run status, if unlocked
- rollback action for rejected or crashed candidates
- links to Typst/PDF notes when a report exists

`schema.json` describes the proposed record shape. `run_experiment.py` can emit
a dry-run record now, without models.

## Rollback And Rejected Candidates

Rejected candidates should not disappear. The repository should keep:

- candidate ID
- candidate diff or snapshot hash
- dev metrics
- rejection reason
- crash or validation failure summary
- rollback target commit

The working branch should then return to the last accepted candidate. For
future real runs, prefer non-destructive rollback mechanics:

- commit the candidate before evaluation
- tag or record the candidate commit in the experiment record
- if rejected, create a revert commit or move the active experiment branch back
  only after the record is written
- never delete local raw outputs that are needed to audit the rejection

## Current Scaffold

Files in this directory:

- `README.md`: this design
- `program.md`: agent-facing workflow instructions
- `schema.json`: proposed structured experiment record schema
- `run_experiment.py`: dry-run orchestrator skeleton

Example dry run:

```bash
python experiments/records/autoresearch-design/run_experiment.py \
  --mode dry-run \
  --record-id physics-week9-autoresearch-dry-run \
  --course-spec experiments/course_specs/physics_week9.json \
  --data-inventory experiments/data_inventory/physics.json \
  --baseline-skill experiments/skill_versions/skill_baseline_v1.json \
  --candidate-skill experiments/skill_versions/skill_candidate_v2.json \
  --generated-at 2026-07-15T00:00:00Z
```

The dry run prints JSON. Use `--output <path>` to save it under an experiment
record directory when a real run is being planned.
