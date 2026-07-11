# Skill Versions

This directory records frozen versions of grading skills used by planned or
reported experiments.

`skill_baseline_v1.json` is the current `grade-homework` baseline before
candidate skill changes. It records:

- source paths for the Codex and Claude skill mirrors
- SHA-256 hashes over normalized LF UTF-8 text
- whether the mirrors are synchronized
- the canonical hash used by experiment plans

Experiments that evaluate skill changes should create a new snapshot, such as
`skill_candidate_v2.json`, and reference it from `plan.json` or
`experiment.json`.

`skill_candidate_v2.json` records the full `grade-homework` skill directories,
including bundled `scripts/` and `references/`, because candidate v2 changes are
not limited to `SKILL.md`.

`skill_candidate_v2_design.md` explains the intended grading-behavior changes
before any model run uses the candidate.
