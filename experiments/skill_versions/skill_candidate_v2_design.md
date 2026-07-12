# grade-homework skill_candidate_v2 design

## Objective

Improve the grading skill as the experimental candidate after
`skill_baseline_v1`. The goal is not to claim higher accuracy yet; the goal is
to make the grading procedure more reproducible, auditable, and suitable for a
future baseline-vs-candidate experiment on the same prompt packets.

## Baseline limitations addressed

- The baseline skill stated an evidence-first workflow, but the operational
  contract was not separated from general guidance.
- The baseline referenced `scripts/` and `references/grading-prompt.md`, but the
  repository did not include those bundled resources.
- Partial-credit behavior was underspecified, especially for distinguishing a
  correct answer with a roughly correct process from a correct answer with a
  seriously conflicting process.
- The baseline did not have a distinct candidate snapshot after skill changes.

## Candidate v2 changes

- Add a "Candidate v2 grading contract" that requires visible evidence before
  every score.
- Freeze page order, question IDs, max scores, allowed increments, and
  partial-credit rules before grading students.
- Treat transcript/OCR as optional evidence, not as a presumed improvement over
  direct-image grading.
- Add explicit partial-credit rules: no 0.25-point scores; correct answer plus
  roughly correct process receives full credit; serious process conflicts may
  lose process points; wrong answers require careful process-credit review.
- Add bundled resources:
  - `references/grading-prompt.md`
  - `scripts/discover.py`
  - `scripts/to_images.py`
  - `scripts/write_outputs.py`
- Add `PyMuPDF` as the PDF rendering dependency for reproducible local page
  conversion.

## Experiment status

No model call has been run for this candidate. The next experiment should
compare `skill_baseline_v1` and `skill_candidate_v2` using the same anonymous
data snapshot, frozen split, course spec, rubric, and prompt packet discipline.

## Acceptance checks

- Codex and Claude skill mirrors are synchronized.
- Candidate snapshot hash differs from `skill_baseline_v1`.
- Referenced skill resources exist in both mirrors.
- Discovery and output-writing scripts pass synthetic tests.
- Physics dry-run packets remain model-call free and data stays outside Git.
