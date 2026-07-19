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

## Candidate-v3.2 evidence-first scoring

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
for correct terms, concepts, formulas, substitutions, units, and reasoning from
the frozen rubric. For physics or other calculation problems, arithmetic
mistakes should not erase a correct method unless the frozen rubric requires
the exact result.

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
invalidates the answer.

Apply these Candidate v3.1 calibration rules before finalizing the score:

- cap-locality: apply a material-error cap only when the cap condition is directly visible and active;
  do not trigger a cap merely because an element is
  partial, under-detailed, or expressed through a non-standard but viable route.
- contradiction-locality: when a misconception or contradiction is local to one
  element, proof direction, or construction step, preserve unrelated element credit
  unless the frozen rubric explicitly defines a question-level cap.
- key-term semantics: key terms are evidence signals, not mandatory wording
  unless the rubric or full-credit rule explicitly requires that terminology.
  Correctly used key terms can earn limited keyword credit, and semantic
  equivalents should still be mapped to the matching rubric element.
- indirect-construction: score valid indirect constructions by mapping visible
  steps to rubric elements and required output behavior. Do not require the
  standard direct construction when an indirect route demonstrates the same
  result.

Apply open-ended adequacy for open-ended short-answer, proof, construction, and
essay questions: score whether the answer satisfies the task requirement. Use
the standard answer as an anchor, not as an exhaustive whitelist. Award credit
for valid, relevant, non-contradictory approaches, examples, or constructions
that answer the prompt, even when they are not listed in the expected answer or semantic equivalents.

Apply official-style adequacy and avoid being overly harsh. Grade for
official-style adequacy, not ideal-answer completeness. Preserve reasonable
partial credit for demonstrated understanding even when terminology, ordering,
or detail is imperfect. Distinguish missing ideal detail from a visible misconception.
Apply large deductions only for material errors, contradictions,
wrong language/output behavior, or missing required answer behavior.

Apply these targeted Candidate v3.2 calibration rules when the matching task is
present:

- Q7 proof-locality: preserve construction credit for each correctly
  demonstrated proof direction. A local nonmembership or rejection mistake
  should reduce the affected correctness element but should not erase unrelated
  construction credit unless it invalidates the whole proof direction.
- Q8 enumerator policy: first determine the actual output language. Separate 2n versus 2^n,
  invalid extra outputs, wrong base cases, and vague loop
  mechanisms. A correct power-of-two sequence with a minor extra-output or
  base-case issue should receive partial credit; linear even lengths are not a
  correct enumerator for the target power-of-two language.
- Q9 conceptual essay policy: score broad valid evidence for the Church-Turing thesis
  when it is relevant, non-contradictory, and supports effective
  computability, even if it does not name the exact reference families.

Apply these explicit question-type rules:

- `multiple_choice`: Require the selected option or an unambiguous equivalent.
- `short_answer`: Combine key-term and concept evidence; exact standard-answer
  wording is not required.
- `calculation`: Check the final numeric or symbolic answer, units, formula
  choice, substitutions, arithmetic, and physical or mathematical reasoning;
  retain justified method credit when the final answer is wrong.
- `algorithm`: Require a viable method plus relevant steps or relations; award
  credit to valid alternatives.
- `proof`: Check all required directions and logical links; a missing required
  direction blocks full credit but preserves credit for each completed direction.
- `essay`: Score distinct valid relevant claims; do not require fixed ordering
  or standard phrasing.

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
`extracted_evidence` and `evidence` must be plain text strings. Do not output
arrays or objects for these fields. If you use `key_term_evidence`,
`concept_evidence`, or `relation_evidence` internally, summarize those layers
inside the single `extracted_evidence` string or the single `evidence` string.

## Second-pass triggers

Before writing output, revisit the source page for every item with:

- `low` confidence
- unreadable or cropped work
- blank or apparently missing answers
- high-impact deductions
- total mismatches
- any score that depends on interpreting handwriting

Also check missed semantic equivalents, missed keyword credit, duplicate credit,
keyword misuse, score-band consistency, score increments, material-error caps,
local contradictions, indirect constructions, open-ended adequacy,
official-style adequacy, and arithmetic. The
`confidence` field must be exactly `high`, `medium`, or `low`, and the exact
total must be recomputed from itemized scores.

If the second pass still leaves uncertainty, keep the numeric score conservative
and flag the item for teacher review.
