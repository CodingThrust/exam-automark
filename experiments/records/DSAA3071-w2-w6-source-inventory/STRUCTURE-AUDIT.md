# DSAA3071 Weeks 2, 4, and 6 Source Structure Audit

Status: preparation only; no model run
Audit date: 2026-08-02

This public-safe record contains only page counts, anonymous page positions,
question metadata, and readiness gates. It contains no student identity,
answer text, grades, raw images, or private layouts.

## Bottom line

| Week | Verified source structure | Preparation state | Model ready? |
| --- | --- | --- | --- |
| W2 | 23 core three-page answer groups, plus one non-contiguous group and five nonempty attachment candidates | Private final layout still needs six ownership decisions | No |
| W4 | 22 complete three-page answer groups; roster and separator pages are identified | Local v0 header-masked draft exists; all reviews are pending | No |
| W6 | 21 complete three-page answer groups; roster and separator pages are identified | Local v0 header-masked draft exists; all reviews are pending | No |

Recommended preparation order: **W4 -> W6 -> W2**. W4 and W6 have verified
complete answer groups. W2 must not be forced into a regular pattern until its
exceptional pages have been adjudicated.

## What was checked

- Each source PDF and official solution PDF was matched to the SHA-256 in
  [source-inventory.json](source-inventory.json).
- Private visual checks verified page order and page-footer labels. No
  identity-based mapping was placed in Git.
- The audit did not call a model or construct a grading packet.

## Week 2

- The 92-page scan contains 23 labelled `Page 1/2/3 of 3` core answer groups
  (69 labelled answer pages).
- One core group is non-contiguous: source pages `5, 6, 11`. This is only a
  label-based pairing until a private reviewer confirms the page ownership.
- Five nonempty, unnumbered pages (`16, 20, 28, 32, 88`) may be continuation
  sheets. A reviewer must assign them to an anonymous candidate or explicitly
  exclude them; physical position alone is insufficient.
- The official assessment totals 130 points: Q1-Q4 are 5 points each; Q5=12,
  Q6=13, Q7=20, Q8=25, Q9=20, Q10=20.
- Q7 is the strongest multimodal-vs-transcript candidate because it contains a
  GNFA/state-transition representation. Q5-Q6 and Q9-Q10 are sensitive to
  formal-symbol transcription. Q8-Q10 need a frozen proof-scoring policy.

## Week 4

- The 90-page scan has one private roster/total-score page, 22 complete
  three-page answer groups (`3-5`, `7-9`, ..., `87-89`), and 23 verified
  separator pages.
- The local v0 preparation has 66 anonymous page images and 22 anonymous PDFs.
  It masks the common identity header only. Existing grading marks have not
  been declared removed, so every review is pending and `model_run_allowed` is
  false.
- The official assessment totals 130 points: Q1-Q4=20 combined multiple-choice
  points; Q5=25, Q6=15, Q7=15, Q8=15, Q9=25, Q10=15.
- Q6 (TM configuration notation) and Q8 (trace/spatial notation) are the
  strongest direct-multimodal versus transcription candidates. Q1-Q4 are only
  a low-ambiguity calibration set.

## Week 6

- The 86-page scan has one private roster/total-score page, 21 complete
  three-page answer groups (`3-5`, `7-9`, ..., `83-85`), and 22 verified
  separator pages.
- The local v0 preparation has 63 anonymous page images and 21 anonymous PDFs.
  It masks the common identity header only. All three human reviews remain
  pending, so the output is not model-ready.
- The official assessment totals 130 points: Q1-Q4 are 5 points each; Q5=12,
  Q6=13, Q7=25, Q8=30, Q9=15, Q10=15.
- Q5-Q10 are the meaningful multimodal comparison set: they contain algorithm
  descriptions, diagonalization, proof structure, hierarchy notation, and
  counting arguments. Q1-Q4 remain a calibration baseline.

## Non-negotiable release gates

For every answer page, all of the following must pass before any model call:

1. Privacy: no name, student ID, or other direct identifier remains.
2. Blindness: no pre-existing score, tick/cross, total, or grader comment can
   leak human gold.
3. Content preservation: masking has not hidden a question or answer needed
   for the declared scope.
4. Evaluation contract: frozen question scope, rubric, question-level human
   gold, and development/held-out split.
5. Fair modality comparison: the direct-multimodal and fresh-model-transcript
   arms use the same anonymous candidates, question scope, rubric, and split.
   A human-reviewed transcript is a diagnostic reference, not a silent
   replacement for the model's own transcript.

## Next decision

W2 remains blocked only by private adjudication of the non-contiguous group and
five attachment candidates. W4 and W6 can now proceed to page-level
grading-mark masking and the three human reviews. The question scope (full 130
points or a written-question subset) must be frozen before extracting
question-level gold or comparing models.
