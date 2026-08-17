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

## Candidate evidence-first scoring

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
the frozen rubric. For calculation problems, arithmetic mistakes should not
erase a correct method unless the frozen rubric requires the exact result.

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

This is a cross-course prompt contract. Course-specific calibration overlays
must live in the frozen course rubric and packet; do not import named-question
rules, named examples, or specialized subject policies from another course.

Classify each question before scoring, then record the type:

- `objective_selection` (multiple choice, matching, true/false): require a
  selected option or unambiguous equivalent. Explanations are not required
  unless the prompt explicitly requests proof, explanation, justification, or
  visible work.
- `calculation`: evaluate result, valid setup/method, transformations or
  substitutions, intermediate calculation, and required reasoning. Retain
  evidenced method credit when the result is wrong. A correct result without
  required work receives only the frozen answer-only allocation.
- `calculation_short_answer`: score derivation and requested short conclusion
  as non-overlapping elements; accept valid alternative methods.
- `short_answer` or `conceptual`: score key-term, concept, and relation
  evidence without demanding exact reference wording.
- `algorithm` or `construction`: score a viable method, relevant steps, and
  required output behavior; accept valid alternatives.
- `proof` or `explanation`: score each required logical link/direction; preserve
  independently demonstrated parts when another part is incomplete.
- `diagram`, `geometry`, or `representation`: score visible required objects,
  relations, labels, transformations, and conclusion; never infer invisible
  diagram work.
- `essay` or `open_response`: score distinct valid, relevant, non-contradictory
  claims; do not require fixed order or standard phrasing.

For mixed questions, use non-overlapping rubric elements for each required
aspect. The frozen rubric, rather than this prompt, sets point values, allowed
increments, and answer-only credit.

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

The trace must be grounded in visible work and the frozen rubric, and its
`points_deducted` values must sum exactly to `max_score - score` for that one
leaf. It is a compact audit statement, not a chain of thought. Deduct from the
first material error; do not deduct again for consequences of that same error.
For selected-response work, do not penalize a missing explanation unless the
question explicitly requires it. When a correct calculation answer lacks
required work, use the frozen answer-only cap. A zero score needs an explicit
missing or incorrect reason. Full-credit leaves omit `deduction_trace`; any
leaf with flags or `low` confidence needs a short `attention_note`. Evaluate a
bonus leaf independently from every base leaf.

Never place a name, identifier, email address, private path, or raw private
file reference in a trace or attention note.

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
      "flags": [],
      "deduction_trace": [
        {
          "rubric_criterion": "frozen rubric criterion label",
          "observed_evidence_or_missing_or_incorrect_part": "Concise visible missing or incorrect part.",
          "deduction_type": "material_method_error",
          "points_deducted": 1.0
        }
      ]
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

## Route-comparison evidence card

When comparing a direct multimodal route with a transcription-assisted route,
use the same frozen rubric, gold, split, scoring packet, and review policy.
For every representative disagreement, write an evidence card before changing
anything. Set one primary category:

- `clear_model_error`: source evidence and frozen rubric support another score.
- `representation_loss`: relevant source evidence was lost, mistranscribed,
  reordered, cropped, or otherwise unavailable to a route.
- `rubric_or_gold_conflict`: a course-owner decision is needed.
- `reasonable_severity_difference`: both evidence-grounded scores lie within an
  acceptable strictness range.
- `insufficient_evidence`: the source or record cannot support a reliable
  decision.

Do not label disagreement a model failure by default. Keep the card alongside
the route artifacts and final human disposition.
