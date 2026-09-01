# Grading Prompt Contract

Use this reference after the solutions/rubric pages are available and before
grading any student.

## Course-package freeze

The current course owner supplies `course-package.json`. It must contain one
row per independently scoreable leaf with `question_id`, `max_score`,
`allowed_increment`, visible criteria, accepted alternatives, and any
course-specific deduction or missing-work policy. Confirm it before grading and
do not change it in the middle of a batch.

## Evidence-first scoring

Read the complete submission before scoring. Record concise visible evidence
before assigning each score, including any uncertainty about handwriting,
cropped pages, missing work, or page order. Do not infer invisible work.

Score only the declared leaves in the frozen course package. The course package
sets the question type, score increments, required evidence, acceptable
alternatives, and all partial-credit or answer-only policy. Do not invent a
universal point rule from another assessment.

Do not create subparts, transfer points between leaves, or count one fact
twice. Accept an unambiguous valid alternative when it meets a declared
criterion. Ignore extra work unrelated to all declared criteria unless it is
adopted for the graded conclusion or the course package says otherwise.

The live skill intentionally has no named-course calibration overlays. Every
course-specific scoring detail belongs in the current course package, which is
frozen for the batch and reviewed by the course owner.

A course package may use question-type labels as local routing aids. Its
declared criteria, leaves, and policies always control the grade.

## Submission-level assembly

The scoring unit is the complete anonymous submission, never a single page.
Read every ordered page for one student together before scoring questions: one
page may contain several questions and one question may continue across pages.
Do not emit, award, or sum page-level marks. Reconcile visible evidence across
the full page set, then assign one score for each rubric question.

Page position, source-page number, image filename, and attachment/input index
identify only scan/display order. They never identify Q1, Q2, or any other
question and do not create a question-to-page mapping. Do not infer question
order from P01/P02 or from another student's page sequence; locate each answer
from visible question labels, stems, and content across the complete page set.
When the relevant page cannot be established from visible evidence, flag
`page_order_uncertain` rather than awarding credit by page position.

Respect the frozen page order and any explicit missing-page or
missing-question flags. Do not invent unseen work or silently repair a missing
or cropped page; apply the frozen course policy and add a score-affecting flag
when necessary.

## Scorable subparts and hierarchy

Before scoring, identify the hierarchy of each stem. Each frozen `question_id`
is the smallest independently scoreable leaf item. If the assessment and
rubric separately allocate points to subparts, score each declared leaf
separately even when they share a page, stem, or calculation. Parent/stem
labels provide orientation only; do not emit or add an aggregate parent score
in addition to its leaf scores.

Do not invent subparts when the frozen contract does not declare independent
scoring units. Do not merge, average, borrow, or offset credit between
declared leaves. Read the complete submission first and collect evidence for
each leaf across all ordered pages. A missing or unclear region affects only
the material leaf or leaves unless the frozen rubric explicitly says otherwise.

## Required deduction trace for non-full leaves

For every leaf below `max_score`, add a concise `deduction_trace` array. Every
entry must contain exactly these fields:

- `rubric_criterion`
- `observed_evidence_or_missing_or_incorrect_part`
- `deduction_type`
- `points_deducted`

The trace must be grounded in visible work and the frozen course package. Its
`points_deducted` values must sum exactly to `max_score - score` for that leaf.
It is a compact audit statement, not a chain of thought. Apply the current
course package's deduction order and no-double-count policy. A zero score needs
a specific visible missing or incorrect reason. Full-credit leaves omit
`deduction_trace`; every flagged, medium-confidence, or low-confidence leaf
needs a short `attention_note` for human review.

Never place a name, identifier, email address, private path, or raw private
file reference in a trace or attention note.

## Marked-page annotations

For each visible location that supports a deduction, praise, or review flag,
emit one annotation with exactly these fields:

- `question_id`: a declared score leaf
- `page_id`: an ID from the private rendered `pages.json`
- `box`: `[x, y, width, height]` normalized to `[0, 1]`
- `kind`: `deduction`, `praise`, or `review`
- `label`: a short learner-facing note without personal data

For a production record written with `--require-annotations`, add praise for
every leaf awarded more than zero, a deduction annotation for every non-full
leaf, and a review annotation for every flagged or non-high-confidence leaf.
A partially correct leaf can therefore need both praise and deduction boxes.
Do not invent a box: a genuinely uncertain location must be flagged for review
instead.

## Required JSON record

Write one JSON object per student before passing it to `write_outputs.py`:

```json
{
  "student_id": "opaque-submission-id",
  "scores": [
    {
      "question_id": "leaf-id",
      "score": 2.0,
      "max_score": 3.0,
      "evidence": "Visible work used to justify the score.",
      "feedback": "Short English feedback for the student.",
      "confidence": "medium",
      "flags": [],
      "deduction_trace": [
        {
          "rubric_criterion": "course-package criterion label",
          "observed_evidence_or_missing_or_incorrect_part": "Concise visible missing or incorrect part.",
          "deduction_type": "material_method_error",
          "points_deducted": 1.0
        }
      ],
      "attention_note": "Short reason for human review."
    }
  ],
  "annotations": [
    {
      "question_id": "leaf-id",
      "page_id": "private-page-id",
      "box": [0.1, 0.1, 0.2, 0.1],
      "kind": "deduction",
      "label": "Short marking note."
    },
    {
      "question_id": "leaf-id",
      "page_id": "private-page-id",
      "box": [0.1, 0.1, 0.2, 0.1],
      "kind": "review",
      "label": "Please verify this region."
    }
  ],
  "total": 2.0,
  "flags": []
}
```

Confidence must be `high`, `medium`, or `low`. Use flags such as
`unreadable_region`, `missing_page`, `blank_answer`, `page_order_uncertain`,
`rubric_ambiguous`, `high_impact_deduction`, or `needs_manual_review`.
`evidence`, `feedback`, traces, attention notes, and annotation labels must be
short plain-text fields. Do not output names, student numbers, raw paths, or
private filenames in the JSON record.

## Second-pass triggers

Before writing output, revisit the source page for any non-full, flagged,
medium-confidence, or low-confidence leaf; for unreadable, cropped, blank, or
apparently missing work; and for any total mismatch. Verify score increments,
leaf coverage, deduction-trace arithmetic, and annotation locations against
the frozen course package.

If uncertainty remains, preserve it in `attention_note`, `review.csv`, and a
`review` annotation when a real page location is known. The teacher decides the
final resolution; do not disguise uncertainty as a confident score.
