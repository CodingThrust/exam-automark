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

## Cross-Platform Requirements

Experiment records should be written in English unless they quote source
material or record a local machine path. Model-facing prompts, rubrics,
partial-credit rules, grading evidence, and feedback fields should be English
so that another reviewer can reproduce the run without translating the
instructions.

Prompt packets must use relative paths in model-facing instructions. Do not put
Windows drive letters, UNC paths, user-specific home directories, or local
absolute paths in `prompt.txt`, `INSTRUCTIONS.md`, `manifest.json`,
`course.json`, `rubric.json`, or `output.schema.json`. Local absolute paths may
appear only in machine-specific environment snapshots.

Every model-run record should include:

- the exact `git rev-parse HEAD` commit hash
- operating system name and version
- shell version when relevant
- Python version and package versions used by the run
- Typst version when a PDF report is compiled
- model provider, model name, API/model version when available, and generation
  parameters
- any conversion tool versions for multimodal-to-image or multimodal-to-text
  preprocessing

Windows, macOS, and Linux reviewers may have different local software paths.
Those paths are environment facts, not reproduction requirements. Reproduction
commands should prefer repository-relative paths and `python -m ...` invocations.

The private data repository may contain anonymized course data for physics,
DSAA3073, DSAA3071, and linear algebra. This public tool repository should only
contain synthetic fixtures and experiment metadata that does not identify
students.

Supporting directories:

- `knowledge/`: reusable research-process notes, including the source-of-truth
  layers, readiness levels, and negative controls used by grading experiments.
- `prompt_templates/`: reusable model-facing prompt text that is copied into
  packets as `prompt.txt`.
- `skill_versions/`: frozen grading-skill snapshots. Plans and reported
  experiments should record the skill version used.
- `course_specs/`: course and assessment schemas used to create packet
  `course.json` files.
- `data_inventory/`: local data summaries with hashes, counts, extension
  distributions, and privacy notes. Raw filenames are intentionally omitted.
