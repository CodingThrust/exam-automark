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

## Candidate-v3 evidence-first scoring

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

Identify the question type before scoring. For each scoring element, record
`key_term_evidence`, `concept_evidence`, and `relation_evidence`, then use
exactly one state: `absent`, `mentioned_only`, `partial_understanding`,
`demonstrated`, or `misused_or_contradicted`. A correctly used keyword can earn
only the rubric's limited `mentioned_only` credit. An unambiguous semantic
equivalent can demonstrate the matching meaning without standard phrasing.
Do not award duplicate credit: a keyword and its explanation are one element,
and overlapping evidence cannot be credited twice.

Sum the integer scores for non-overlapping elements. Score bands and a
material-error cap are upper bounds only and cannot raise the subtotal. Award
full credit only when all required essential elements are demonstrated, required
terminology is present when explicitly requested, and no material contradiction
invalidates the answer. For an algorithm, credit a viable alternative method;
for a proof, keep the completed direction's credit; for an essay, credit distinct
valid relevant claims; and for multiple choice, require the selected option or
an unambiguous equivalent.

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

Also check missed semantic equivalents, missed keyword credit, duplicate credit,
keyword misuse, score-band consistency, score increments, and arithmetic. The
`confidence` field must be exactly `high`, `medium`, or `low`, and the exact
total must be recomputed from itemized scores.

If the second pass still leaves uncertainty, keep the numeric score conservative
and flag the item for teacher review.
