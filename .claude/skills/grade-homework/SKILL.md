---
name: grade-homework
description: Use when a teacher or TA needs to grade a batch of scanned homework, quiz, or exam submissions against a course-provided rubric. It groups multi-page scans, keeps the roster private, produces grades and review CSVs, and renders checked annotations on each submission.
---

# grade-homework

## Scope and privacy boundary

This is a cross-course delivery skill. It provides evidence-based grading,
private roster handling, scan rendering, structured outputs, annotations, and
human-review handoff. It does not supply subject knowledge, point allocations,
partial-credit bands, canonical forms, required work, or penalties. Those rules
belong only in the frozen course package for the current assessment.

Never import a rule, example, point value, or error pattern from a previous
course or data set. If the current course package does not settle a scoring
question, stop and ask the course owner instead of guessing.

## What this skill produces

- `grades/grades.csv` - opaque ID, local name, local student number, item
  scores, total, uncertainties, and flags.
- `grades/review.csv` - one row for every flagged or non-high-confidence leaf.
- `grades/feedback/<submission_id>.md` - concise feedback.
- `grades/annotations/<submission_id>.json` - validated annotation data.
- `grades/marked/<submission_id>/` - annotated PNG pages plus a marked PDF.

These are private per-person records. They never belong in Git, a public report,
a pull request, or a model prompt. The output helpers reject an unignored
directory inside a Git worktree.

## Private input contract

Use a private, ignored working directory with `course-package.json`,
`roster.csv`, and `submissions/<submission_id>/` directories. `roster.csv`
must have exactly `submission_id,student_name,student_number`; it is local-only
and must never be included in a model-facing record. Start the course package
from `references/course-package-template.json`, replace every placeholder, and
freeze it before grading begins.

PDFs and ordinary image formats render in Python. DOCX files require
LibreOffice or `soffice`.

If DOCX conversion is unavailable, do not claim that the pages were rendered.
Put that submission in review or install the approved converter before grading.

## Workflow

Skill root: the directory containing this `SKILL.md`. Resolve scripts and
references relative to that directory; do not assume a Claude- or Codex-specific
home path.

### Generic grading contract

Score visible evidence from the complete submission, not assumed intent. Record
a concise evidence note before assigning a score. The frozen course package
controls the question type, score leaves, required evidence, alternatives,
increments, and every partial-credit decision.

Do not invent subparts, transfer points between leaves, or count one visible
fact twice. Accept an unambiguous valid alternative when it satisfies a
course-package criterion. Do not penalize extra work that is irrelevant to all
declared criteria unless the submission adopts it for the graded conclusion or
the course package explicitly says otherwise.

The course package owns all scoring detail. It may define different policies for
different question types, methods, representations, answer-only work, and
partial credit. This live skill deliberately does not turn a previous course's
calibration into a universal rule.

The course package may declare question types when that helps its own rubric.
The type is only a routing aid: the package's explicit criteria, score leaves,
and policies always control the grade.

### Submission-level assembly

The grading unit is the entire anonymous submission, not an individual page.
Before scoring any question, assemble and read every ordered page assigned to
that student. A page may contain evidence for several questions, and evidence
for one question may continue across pages. Do not award, emit, or sum
page-level marks. Instead, reconcile all visible evidence for each question
across the student's complete supplied page set, then assign that question's
single rubric score.

Page position, source-page number, image filename, and input index identify
only source/display order. They are never question numbers or a question-to-page
mapping: do not assume that P01 (or the first image) is Q1, that P02 is Q2, or
that different submissions use the same physical question order. Locate each
declared leaf from its visible question label, stem, answer content, and any
course-declared mapping; reconcile evidence across the full submission before
scoring. If the visible content cannot reliably establish the relevant page or
pages, flag `page_order_uncertain` rather than assigning credit by page position.

Respect the packet's frozen page order and any explicit missing-page or
missing-question flags. Do not infer absent work from a neighboring page or
silently repair a missing/cropped page. Use the course-frozen missing-work rule
and flag any score-affecting uncertainty for review.

### Scorable subparts and hierarchy

Before scoring, identify the hierarchy of each stem. Each frozen `question_id`
must represent the smallest independently scoreable leaf item. When the
assessment and rubric separately allocate points to subparts, score each
declared leaf separately, even when several leaves share a stem, page, or
calculation. Use any parent/stem label only for orientation: never emit or add
an aggregate parent score in addition to leaf scores.

Do not invent subparts when the frozen course contract does not declare
independent scoring units, and do not merge, average, borrow, or offset credit
between declared leaves. Assemble the whole submission first, then gather all
visible evidence for each leaf across its ordered pages. A missing or unclear
region affects only the material leaf or leaves unless the frozen rubric
explicitly sets a wider rule.

### Deduction trace contract

For every non-full-credit leaf, record a concise `deduction_trace` with one or
more entries. Each entry has exactly `rubric_criterion`,
`observed_evidence_or_missing_or_incorrect_part`, `deduction_type`, and
`points_deducted`. The entries must be checkable against visible work and the
frozen rubric; their `points_deducted` values must sum exactly to
`max_score - score` for that leaf. This is a short audit record, not hidden
reasoning or a chain of thought.

Apply the course package's deduction order and no-double-count policy. A zero
score must state specific visible missing or incorrect evidence. Full-credit
leaves omit `deduction_trace`; a flagged, medium-confidence, or low-confidence
leaf must add a brief `attention_note` and appear in review output. Treat any
course-declared bonus leaf independently from base-leaf scoring.

Do not put a name, student identifier, email address, private path, or raw
private-file reference in a deduction trace or attention note.

### Course-package boundary

The current course package decides how calculations, selected responses,
proofs, diagrams, simplification, alternatives, bonus work, partial credit,
and dependent consequences are handled. This skill only enforces that the
chosen score is evidence-based, traceable, and arithmetically valid. OCR or
transcription may assist reading but never replaces the source pages.

### Release safeguards

Before release, review every row in `review.csv`, inspect every marked page,
and spot-check a representative set of unflagged submissions. A teacher owns
the final score and any course-package correction.

### Step 1 - Validate the private batch

Validate the roster, then discover the batch:

```bash
python <skill_root>/scripts/roster.py roster.csv
python <skill_root>/scripts/discover.py . --roster roster.csv
```

For a new production batch, use `submissions/<submission_id>/` directories.
If discovery reports a grouping, roster, missing-scan, or solution ambiguity,
stop and resolve the source data with the TA. Do not silently guess a student
identity or page grouping. The legacy filename-prefix mode remains only for
older workflows without a roster.

### Step 2 - Freeze the course package

Read `<skill_root>/references/grading-prompt.md`, inspect the assessment, and
confirm the current `course-package.json` with the course owner. It must cover
the leaf hierarchy, point values, increments, visible criteria, alternatives,
partial-credit policy, missing/illegible-work policy, and annotation guidance.
If any needed scoring rule is absent, stop and ask; do not infer it from a
solution format or a previous course.


### Step 3 - Render, grade, write, and mark

For each submission group, render all scans before scoring:

```bash
python <skill_root>/scripts/render_submission.py \
  submissions/<submission_id> rendered/<submission_id> \
  --submission-id <submission_id>
```

Read the whole rendered page set together. Score only the frozen course leaves,
record visible evidence, attach confidence and flags, and return the JSON
contract in `grading-prompt.md`. Every non-full leaf needs the four-field
deduction trace; every review-needed leaf needs an attention note.

Write one private record at a time:

```bash
echo "$RECORD_JSON" | python <skill_root>/scripts/write_outputs.py grades \
  --roster roster.csv \
  --course-package course-package.json \
  --require-annotations
```

Then render the marked pages:

```bash
python <skill_root>/scripts/annotate_submission.py \
  rendered/<submission_id>/pages.json \
  grades/annotations/<submission_id>.json \
  grades/marked/<submission_id>
```

The writer validates the scores and creates `grades.csv` plus `review.csv`.
The annotation renderer fails closed for an invalid page, box, or label; never
fabricate a marking location.

With `--require-annotations`, every score-bearing leaf needs a `praise` box,
every non-full leaf needs a `deduction` box, and every review-needed leaf needs
a `review` box. A partially correct leaf can therefore need both praise and
deduction boxes. If a real location cannot be established, do not invent one:
flag it for teacher review before release.

### Step 4 - Recovery and release

The writer skips a `student_id` already present in the same grades CSV and
rejects a header change, preventing a silent mid-batch rubric mix. For a
re-grade, create a new private run directory; do not overwrite an existing
marked submission or silently delete prior grading history.

Before release, reconcile all `review.csv` rows, inspect marked pages, and
provide the teacher with the private CSV and marked files. Report skipped scan
groups and their reasons. The teacher reviews flagged work and makes the final
score decision.

## Failure modes

- **Missing or ambiguous course material**: stop until the course owner supplies
  a complete package and source solution/rubric.
- **Unknown roster group, missing scan, or duplicate grouping**: stop that batch
  and resolve the TA's source data; do not infer an identity.
- **DOCX converter unavailable**: put the affected submission in review; do not
  claim pages were rendered.
- **Invalid score, trace, or annotation**: correct the private record against the
  frozen course package before release.

## Quality bar

This skill supports a teacher with traceable, private records and visual marking.
It is not a teacher replacement. Course-specific quality claims require that
course's own approved rubric, human review, and validation process.
