# DSAA3071 Candidate v3 and Rubric v1 Design

Status: **pending user review**

Date: 2026-07-18

## Objective

Improve grading accuracy for calculation, concept-heavy short-answer,
algorithm-description, proof, and essay questions while preserving
reproducibility and the existing physics-compatible grading safeguards. The
immediate development target is DSAA3071 week 5. The reusable output is a
course-independent candidate-v3 grading policy plus a course-specific rubric
v1.

## Constraints

- Preserve `rubric_v0.json`, candidate-v2 prompts, skill snapshot, packets,
  runs, and metrics as immutable historical evidence.
- Use only the seven development students to calibrate v1 and v3.
- Do not inspect or use held-out gold scores during calibration.
- Do not place student answer text, PDFs, or identifiable data in tracked
  prompts, rubrics, skills, plans, or records.
- Keep model-facing rubric and prompt text in English.
- Preserve integer scoring and prohibit 0.25-point increments.
- Build all post-review packets from
  `Data/DSAA3071/week5-benchmark-redaction-v3/transcripts/T1-dev-human-reviewed-r1`.
- Never overwrite an existing packet or model-run directory.

## Responsibility Boundaries

### Candidate v3

Candidate v3 defines a reusable grading procedure. It is responsible for:

- question-type-aware grading;
- extracting key-term, conceptual, and relational evidence;
- calculation-aware handling of final numeric or symbolic answers, units,
  formulas, substitutions, arithmetic, and justified method credit;
- semantic-equivalence decisions;
- partial-credit decisions;
- handling omissions, misuse, and contradictions;
- preventing duplicate credit;
- second-pass checks for both excessive deductions and superficial keyword
  matching;
- schema, confidence, flag, and total validation.
- schema-compatible evidence serialization: internal evidence layers must be
  summarized into plain text `extracted_evidence` and `evidence` fields.

It must not contain DSAA3071-specific answers or student examples.

### Rubric v1

Rubric v1 defines DSAA3071 week 5 content and score calibration. It is
responsible for:

- accepted key terms and semantic equivalents;
- essential concepts and supporting details;
- credit levels for each non-overlapping scoring element;
- question-specific score bands;
- material errors and score caps;
- full-credit requirements.

It must not contain student answer text or anonymous student IDs.

### Gold Scores

`primary_scores.csv` is evaluation evidence. Development rows may inform general
rubric calibration, but gold scores must never enter a prompt packet. Held-out
rows remain sealed until v1 and v3 are frozen.

## Rubric v1 Structure

Retain the existing course, assessment, question ID, type, maximum-score, score
step, and expected-answer fields. Replace purely checklist-style short-answer
criteria with the following model-facing structure.

### Scoring Elements

Each non-overlapping `scoring_element` has:

- `id`: stable identifier;
- `importance`: `essential` or `supporting`;
- `key_terms`: accepted terms, abbreviations, and close variants;
- `semantic_equivalents`: descriptions that demonstrate the same idea without
  the standard keyword;
- `meaning`: the concept represented by the terms;
- `levels`: integer credit for `mentioned_only`, `partial_understanding`, and
  `demonstrated`;
- `required_for_full_credit`: whether this element must be demonstrated for a
  full score.

The levels are mutually exclusive. A keyword and its explanation belong to one
element and cannot receive duplicate credit.

### Score Bands

Each question defines score bands such as `full`, `substantially_correct`,
`partially_correct`, `minimal_relevant`, and `no_credit`. Bands specify integer
ranges and conceptual requirements. The element subtotal selects a provisional
score. The highest band whose requirements are met supplies an upper bound; it
never raises the subtotal. Material-error caps may lower that bound further.

### Material Errors

Each `material_error` identifies a misconception, the scoring elements it
affects, and any justified question-level score cap. A local error should not
erase unrelated correct evidence. A question-level cap is allowed only when a
contradiction breaks the central conclusion or required construction.

## Candidate-v3 Scoring Algorithm

For every question:

1. Identify the question type.
2. Record only visible student evidence before assigning points.
3. Extract three evidence layers:
   - `key_term_evidence`;
   - `concept_evidence`;
   - `relation_evidence`, including logical, procedural, or causal links.
4. Map evidence to each rubric scoring element using exactly one state:
   - `absent`;
   - `mentioned_only`;
   - `partial_understanding`;
   - `demonstrated`;
   - `misused_or_contradicted`.
5. Award the integer credit associated with that state. A correctly used or
   relevant keyword may earn limited partial credit even without a complete
   explanation. A misused keyword earns no automatic credit.
6. Sum non-overlapping element credit. Determine the highest score band whose
   conceptual requirements are met, then cap the subtotal at that band's maximum
   and at any stricter material-error cap. A band cannot increase a subtotal.
7. Award full credit only when all required essential elements are demonstrated
   or expressed through unambiguous semantic equivalents, required terminology
   is present when the question explicitly asks for it, and no material
   contradiction invalidates the answer.
8. Do not penalize different wording, order, notation, concise expression,
   minor language errors, or omission of optional supporting detail.
9. If the final conclusion is wrong, retain justified credit for correctly
   demonstrated terms, concepts, formulas, substitutions, units, and reasoning
   unless the rubric explicitly makes the conclusion indispensable. In physics
   or other calculation problems, arithmetic mistakes should not erase a
   correct method unless the rubric requires the exact result.
10. Run a second pass that checks unreadable evidence, high-impact deductions,
    missed semantic equivalents, missed keyword credit, duplicate credit,
    keyword misuse, score-band consistency, and arithmetic totals.

## Question-Type Rules

- `multiple_choice`: score the selected option or an unambiguous equivalent.
- `short_answer`: combine key-term and concept evidence; exact standard-answer
  wording is not required.
- `calculation`: check the final numeric or symbolic answer, units, formula
  choice, substitutions, arithmetic, and physical or mathematical reasoning;
  retain justified method credit when the final answer is wrong.
- `algorithm`: require a viable method and relevant steps or relationships;
  alternative valid constructions receive credit.
- `proof`: identify required directions and logical links; missing a required
  direction prevents full credit but does not erase the completed direction.
- `essay`: score distinct valid claims and their relevance; fixed ordering and
  standard phrasing are unnecessary.

## Calibration Procedure

1. Subset gold scores using `students-development.txt` before computing any
   calibration summary.
2. Compare v0 criteria and completed model predictions with development gold by
   question.
3. Use the official solution plus development discrepancies to identify overly
   strict requirements, missing keyword credit, and inappropriate score caps.
4. Write only general scoring elements, equivalents, bands, and misconceptions
   into v1. Do not copy student text or student-specific scores into v1.
5. Validate question IDs, maximum scores, integer levels, non-overlapping
   elements, and total points.
6. Freeze rubric v1 and candidate-v3 hashes before any new model call.

## Three-Condition Development Experiment

All three conditions use the same human-reviewed transcript snapshot, model,
provider settings, repetition, student list, and output schema.

| Condition | Prompt | Rubric | Purpose |
|---|---|---|---|
| `B0` | baseline v1 | rubric v0 | post-review historical reference |
| `R1` | baseline v1 | rubric v1 | isolate rubric-calibration effect |
| `C3` | candidate v3 | rubric v1 | isolate candidate-v3 policy effect |

Required comparisons:

- `R1 - B0`: rubric effect;
- `C3 - R1`: candidate-v3 prompt and skill effect;
- `C3 - B0`: combined improvement.

Readiness must use a controlled-difference matrix rather than requiring every
artifact hash to be equal across all conditions:

- `B0` versus `R1`: rubric and packet hashes may differ; prompt, skill, data,
  students, model settings, and output schema must match.
- `R1` versus `C3`: prompt, skill, and packet hashes may differ; rubric, data,
  students, model settings, and output schema must match.
- Any difference not declared by this matrix blocks the experiment.

The primary accuracy metrics remain question-score MAE, normalized
question-score MAE, total-score MAE, exact agreement, and signed error. Report
per-question results, especially Q5-Q10, and token usage. Do not run held-out
students until the development design is frozen.

## Versioned Artifacts

Implementation should create or update the following versioned artifacts:

- `experiments/records/DSAA3071-week5-prep/rubric_v1.json`;
- `experiments/prompt_templates/grade_candidate_v3.txt`;
- an experiment-specific strict-schema candidate-v3 prompt snapshot;
- `.agents/skills/grade-homework/` candidate-v3 contract and reference;
- the synchronized `.claude/skills/grade-homework/` mirror;
- `experiments/skill_versions/skill_candidate_v3.json` and a design note;
- focused tests for key-term partial credit, semantic equivalents,
  no-double-counting, question-type rules, mirror synchronization, and privacy;
- a new three-condition DSAA3071 development plan and readiness record.

Historical v0/v2 files and outputs remain unchanged.

## Failure Handling

- Invalid rubric structure or non-integer level points blocks packet creation.
- Overlapping elements or a subtotal above the question maximum blocks
  readiness.
- Missing required score bands, question IDs, or full-credit rules blocks
  readiness.
- Object-valued or array-valued `extracted_evidence` or `evidence` fails model
  output validation; candidate-v3 must serialize these fields as plain text.
- Student text or gold-score leakage into tracked prompt/rubric artifacts blocks
  readiness.
- Baseline and candidate plans with different data, student, model, rubric where
  equality is required, or output-schema anchors block comparison.
- Low-confidence semantic interpretation remains scored conservatively and is
  flagged for manual review.

## Acceptance Criteria

- Rubric v1 covers all ten questions and totals 130 points.
- Every concept-heavy question has explicit scoring elements, keyword-only
  partial credit, semantic equivalents, score bands, and material-error rules.
- Candidate v3 follows the agreed key-term, concept, and relation algorithm.
- Candidate v3 includes a calculation rule that preserves physics-style process
  credit for correct methods, formulas, substitutions, units, and reasoning.
- Codex and Claude skill mirrors are byte-synchronized.
- v0, v2, historical packets, and historical runs remain unchanged.
- No `Data/` files or student answer text are tracked.
- All focused and existing grading tests pass.
- The three development conditions pass readiness before model execution.
- No model call is made as part of the implementation step.

## Non-Goals

- No held-out evaluation in this change.
- No multimodal model call in this change.
- No use of individual development answers as few-shot prompt examples.
- No claim that candidate v3 improves accuracy until the three-condition model
  experiment is completed.
