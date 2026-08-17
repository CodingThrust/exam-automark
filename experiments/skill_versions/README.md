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

`skill_candidate_v3.json`, `skill_candidate_v3_1.json`, and
`skill_candidate_v3_1_r2.json` record later concept-aware grading contracts.
Candidate v3.1 is a development calibration of v3 that preserves the
calculation rule while adding locality and semantic equivalence safeguards. The
r2 snapshot adds open-ended adequacy for open-ended short-answer, proof,
construction, and essay questions.

`skill_candidate_v5.json` remains the frozen whole-submission candidate used
before independent subpart handling was added. `skill_candidate_v5_1.json`
records the successor contract: declared score IDs are the smallest
independently scoreable leaves, parent stems are orientation only, and evidence
may still be assembled across all ordered pages of a submission.

`skill_candidate_v5_2.json` records the next generic safeguard: page position,
source-page labels, image filenames, and attachment indices are locators only,
not question IDs or a question-to-page mapping. It preserves whole-submission,
leaf-level evidence assembly for submissions whose scanned page order differs
from assessment question order.

`skill_candidate_v5_3.json` records the successor cross-course deduction-trace
contract. Every non-full declared leaf must carry a concise, rubric-grounded
deduction trace whose point total equals that leaf's withheld credit. The
contract is versioned so it does not rewrite or retrospectively validate frozen
v5.2 packets and results.
