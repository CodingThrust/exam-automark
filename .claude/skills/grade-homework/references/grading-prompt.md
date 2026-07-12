# Grading Prompt Contract

Use this reference after the solutions/rubric pages are available and before
grading any student.

## Rubric freeze

Create a rubric table with one row per question:

- `question_id`
- `max_score`
- `allowed_increment`
- `expected_evidence`
- `partial_credit_notes`

Confirm this table with the teacher before grading. Do not change question IDs,
max scores, or increments in the middle of a run. If the rubric is incomplete,
stop and ask.

## Evidence-first scoring

For each student and question, write the evidence before the score:

- visible equation, statement, diagram feature, answer text, or blank marker
- page number or file reference when available
- any uncertainty about handwriting, cropped pages, missing work, or page order

Score only against the frozen rubric. Do not infer invisible work. Do not give
0.25-point or quarter-point scores. If the final answer is correct and the
process is roughly correct, award full credit. Deduct process points only when a
correct final answer is supported by a process that seriously conflicts with
the standard solution, required method, or visible reasoning expectations. When
the final answer is wrong, inspect the work carefully and award process credit
from the frozen rubric.

## Required JSON record

Write one JSON object per student before passing it to `write_outputs.py`:

```json
{
  "student_id": "anonymous_or_filename_student_id",
  "scores": [
    {
      "question_id": "Q1",
      "score": 2.0,
      "max_score": 3.0,
      "evidence": "Visible work used to justify the score.",
      "feedback": "Short English feedback for the student.",
      "confidence": "high",
      "flags": []
    }
  ],
  "total": 2.0,
  "flags": []
}
```

Confidence must be `high`, `medium`, or `low`. Use flags such as
`unreadable_region`, `missing_page`, `blank_answer`, `page_order_uncertain`,
`rubric_ambiguous`, `high_impact_deduction`, or `needs_manual_review`.

## Second-pass triggers

Before writing output, revisit the source page for every item with:

- `low` confidence
- unreadable or cropped work
- blank or apparently missing answers
- high-impact deductions
- total mismatches
- any score that depends on interpreting handwriting

If the second pass still leaves uncertainty, keep the numeric score conservative
and flag the item for teacher review.
