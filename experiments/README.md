# Reproducible Experiment Records

This directory stores code-side records for reproducible grading experiments.
It must not contain raw student submissions, identity maps, or unredacted data.

Each experiment should have a directory such as:

```text
experiments/records/2026-07-10-synthetic/
  plan.json           # before model calls
  experiment.json
  metrics.json
  note.typ
  note.pdf
```

Use `plan.json` before running a model. It records:

- Git branch and commit that define the planned workflow.
- Privacy-preserving data inventory path and snapshot hash.
- Course spec path.
- Prompt template hashes.
- Planned prompt packets for development and held-out splits.
- Notes about blocked work such as anonymization or rubric extraction.

Use `experiment.json` only after a reported model run exists. It is the result
audit anchor and records:

- Git branch and commit used for the run.
- Anonymous data snapshot hash.
- Prompt packet hashes for every condition.
- Course and assessment identifiers.
- Metrics path and Typst note path.

Reproduction should be possible from:

1. The Git commit in this repository.
2. The matching anonymous data snapshot from the private HKUST-GZ GitLab repo.
3. The prompt packet hashes and packet contents.
4. The documented CLI commands in the Typst note.

The private data repository may contain anonymized course data for physics,
DSAA3073, DSAA3701, and linear algebra. This public tool repository should only
contain synthetic fixtures and experiment metadata that does not identify
students.

Supporting directories:

- `prompt_templates/`: reusable model-facing prompt text that is copied into
  packets as `prompt.txt`.
- `skill_versions/`: frozen grading-skill snapshots. Plans and reported
  experiments should record the skill version used.
- `course_specs/`: course and assessment schemas used to create packet
  `course.json` files.
- `data_inventory/`: local data summaries with hashes, counts, extension
  distributions, and privacy notes. Raw filenames are intentionally omitted.
