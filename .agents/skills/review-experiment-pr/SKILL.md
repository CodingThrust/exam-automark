---
name: review-experiment-pr
description: Use before opening or reviewing a PR for reproducible AI grading experiments. Checks branch discipline, data isolation, prompt packets, experiment manifests, Typst notes, tests, and pilot-result caveats.
---

# review-experiment-pr

## When to use

- Before opening a PR that changes benchmark, prompt, report, grading, or data workflow code.
- When reviewing a PR that claims AI grading accuracy, reproducibility, or cross-course support.
- When a contributor asks for PR training, experiment review, or a reproducibility checklist.

Do NOT use this skill to run a model or judge student answers. This skill reviews
the experiment process, not the grades themselves.

## Required review stance

Treat every experiment PR as a reproducibility artifact. The PR is not ready
until a reviewer can answer:

1. What Git branch and commit produced the result?
2. Which anonymous data snapshot was used?
3. Which prompt packet was used, and where is `prompt.txt`?
4. Which rubric and output schema were used?
5. Which metrics file and Typst note report the result?
6. Which limitations prevent overclaiming?
7. If no model run has happened yet, which `plan.json` records the intended
   data inventory, course spec, and prompt template hashes?
8. Which `grade-homework` skill version was used, and what are its skill
   hashes?
9. Which operating system, software versions, model versions, and conversion
   tools produced the run?

## Checklist

### 1. Branch and Git record

- Confirm work is not done directly on `main`.
- Confirm the branch name identifies the experiment or framework change.
- Confirm the PR description mentions the branch and final commit.
- Confirm generated data, raw submissions, identity maps, and private snapshots
  are not staged.

Suggested commands:

```bash
git status --short --branch
git diff --stat
git check-ignore -v Data Data/physics Data/physics/benchmark
```

### 2. Data isolation

- Public Git may contain code, synthetic fixtures, schemas, prompt templates,
  report templates, and experiment metadata.
- Public Git must not contain raw submissions, real student names, `student_map`,
  private grade references, or unredacted images.
- The private HKUST-GZ GitLab data repo may contain anonymized snapshots.
- Original non-anonymized data should remain local or in a stricter storage area.

Reject the PR if it force-adds `Data/` or any file that reveals student identity.

### 3. Prompt packet reproducibility

Every model-facing experiment must have a packet with:

```text
INSTRUCTIONS.md
manifest.json
course.json
prompt.txt
output.schema.json
inputs/
outputs/
```

Grade packets must also include:

```text
rubric.json
```

The packet manifest must record:

- `prompt_hash`
- `course_hash`
- `rubric_hash` for grading
- `output_schema_hash`
- `input_hashes`

Model-facing packet files must be English and cross-platform:

- `prompt.txt`, `INSTRUCTIONS.md`, and grading `rubric.json` must be English.
- Packet instructions should use relative file names such as `manifest.json`,
  `inputs/`, and `outputs/`.
- Reject Windows drive letters, UNC paths, or user-specific absolute paths in
  model-facing packet files.

Run packet audit before approving:

```bash
python -m benchmark.core.cli audit-packet --packet <packet>
```

The audit must not report leaked `gold`, `student_map`, `primary_scores`,
`reviewer_scores`, `predictions.csv`, or `metrics` content.

### 4. Experiment plan or record

Planned experiments that have not run a model yet should have an
`experiments/records/<id>/plan.json` file. It must include:

- `experiment_id`
- `course_id`
- `assessment_id`
- `status`
- `git_branch`
- `git_commit`
- `data_inventory_path`
- `data_snapshot_hash`
- `course_spec_path`
- `skill_version_id`
- `skill_source_paths`
- `skill_hashes`
- `prompt_template_hashes`
- `planned_packets`

Do not require metrics or a Typst results note for a `plan.json`; require clear
notes about blocked items such as rubric extraction or anonymization.

Every reported experiment with results must have an
`experiments/records/<id>/experiment.json` file. It must include:

- `experiment_id`
- `course_id`
- `assessment_id`
- `git_branch`
- `git_commit`
- `data_snapshot_hash`
- `prompt_packet_hashes`
- `conditions`
- `metrics_path`
- `note_path`
- `skill_version_id`, `skill_source_paths`, and `skill_hashes` when the result
  is intended to evaluate a grading-skill version
- exact model provider, model name, API/model version when available, generation
  parameters, and start/end timestamps
- a software environment record with OS, shell, Python, package, Typst, and
  conversion-tool versions relevant to the run

If the experiment is a legacy pilot, the record must say `pilot` and must not
claim final or general accuracy conclusions.

### 5. Typst note and report

Every PR that presents results should include or update a Typst note. The note
must include:

- Research question or benchmark purpose.
- Private data snapshot location and hash.
- Prompt packet hashes.
- Reproduction commands.
- Metrics definitions.
- Tables or charts for results when metrics exist.
- Limitations and caveats.

If `typst` is unavailable, the PR may include `.typ` only, but the PR must state
that PDF compilation was not verified.

### 6. Cross-course schema

For DSAA3073, DSAA3701, linear algebra, or future courses, the PR should add
course specs instead of copying physics-specific constants. Check that:

- Question IDs are data-driven.
- Max scores and score steps are course-specific.
- Anonymous ID rules are explicit.
- Image/PDF/transcript modes are declared.
- Tests use synthetic fixtures, not private student data.

### 7. Skill version tracking

If the PR is intended to improve the grading skill, require a frozen skill
snapshot such as:

```text
experiments/skill_versions/skill_baseline_v1.json
```

Check that:

- `skill_version_id` is named in every relevant `plan.json` or
  `experiment.json`.
- `.agents/skills/grade-homework/SKILL.md` and
  `.claude/skills/grade-homework/SKILL.md` are synchronized.
- Skill hashes are computed over normalized LF UTF-8 text, so Windows and Unix
  line endings do not create false skill versions.
- Candidate skill changes get a new version ID instead of overwriting the
  baseline.

### 8. Metrics and claims

Accuracy claims must identify:

- Population: development, held-out, all, or transcript subset.
- Reference status: single rater, reviewer complete, or adjudicated.
- Missing predictions and terminal failures.
- Bias and total-score error, not only exact agreement.
- Whether conditions are controlled reruns or historical baselines.

Reject wording that turns the Physics Week 9 pilot into a general claim that
transcript-based grading is better than direct-image grading.

### 9. Tests

Before approval, run offline tests:

```bash
python -m unittest <relevant modules>
```

For broad framework changes, run all test modules. Do not require model calls
for PR review unless the PR explicitly changes model execution code.

## Review output format

Report findings first, ordered by severity:

- P0: privacy leak, identity leak, or gold/reference leak.
- P1: reproducibility broken, missing prompt packet, missing experiment record,
  or unreviewable data dependency.
- P2: unclear metrics, weak caveats, missing Typst note, or missing focused test.
- P3: polish, wording, or documentation improvements.

Then list:

- Reproduction commands checked.
- Files reviewed.
- Residual risks.

If no issues are found, say the PR is process-ready and name any remaining
manual checks, such as teacher review of flagged grading items.
