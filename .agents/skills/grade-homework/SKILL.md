---
name: grade-homework
description: Use when the user wants to grade a folder of student homework, quiz, or exam submissions against a teacher-provided solutions or rubric document. Handles mixed PDF, image, and DOCX inputs, produces a grades CSV and per-student English feedback, and explicitly flags ambiguous, unreadable, missing, or high-impact grading items for teacher review. Triggers on phrases like "grade the homework", "mark HW9", "batch grade submissions", or "批作业".
---

# grade-homework

## When to use

- User wants to grade a folder of student submissions.
- A solutions document is present (either auto-discoverable by filename or provided explicitly).
- Student filenames follow `<student>_..._<original>.<ext>`.

Do NOT use for: single-file grading (just read it inline), plagiarism detection, or rewriting the solutions doc.

## What this skill produces

- `<working_dir>/grades/grades.csv` — one row per student, per-question columns, total, flags.
- `<working_dir>/grades/feedback/<student>.md` — English feedback, per-question breakdown, flags summary.

## Prerequisites (conditional on submission formats)

Only `.docx` submissions need an external conversion toolchain. PDF and image
submissions go through Python alone, so most courses won't need anything
beyond `uv`.

Probe at the start of Step 1 (after `discover.py` reports what's present):

```bash
# Only if discover.py finds any .docx submissions
if ls "$PWD"/*.docx >/dev/null 2>&1; then
  if ! command -v libreoffice >/dev/null 2>&1 && ! command -v soffice >/dev/null 2>&1; then
    if ! { command -v pandoc >/dev/null 2>&1 \
        && { command -v google-chrome >/dev/null 2>&1 \
          || command -v chromium     >/dev/null 2>&1; }; }; then
      echo "MISSING: docx toolchain (need libreoffice OR pandoc+browser)"
    fi
  fi
fi
```

If the toolchain is missing, ask via `AskUserQuestion` whether to install
before grading begins. Without it, `.docx` submissions are silently flagged
`needs_manual_review` and grading proceeds for the rest — call out exactly
how many students that affects so the user can make an informed choice.

When the user says yes, figure out the right install command for their
environment at runtime (inspect `uname -s` and which of `brew`/`apt`/`dnf`/
`pacman`/`winget`/etc. is available — see `bootstrap` Step 0 for the
detection pattern), and propose the commands via `AskUserQuestion` before
running them. Notes on package naming:

- `libreoffice` may be `libreoffice-fresh` on Arch and `--cask libreoffice`
  on Homebrew; on Windows use `TheDocumentFoundation.LibreOffice` via winget.
- Headless browser for the fallback path: `google-chrome` or `chromium` —
  either works.
- `inkscape` is only needed by the fallback path when a `.docx` embeds WMF/EMF
  images. Install on demand if `to_images.py` flags missing inkscape during a
  run; otherwise leave it alone.

## Workflow

Skill root: the directory containing this `SKILL.md`. Resolve scripts and
references relative to that directory; do not assume a Claude- or Codex-specific
home path.

### Candidate grading contract

Grade from visible evidence, not from assumed intent. For every scored question,
first record the visible equation, statement, diagram feature, answer text, or
blank-answer marker. Assign points only after that evidence is written down.

For every question, identify the question type and extract
`key_term_evidence`, `concept_evidence`, and `relation_evidence`. Map each
non-overlapping rubric scoring element to exactly one state: `absent`,
`mentioned_only`, `partial_understanding`, `demonstrated`, or
`misused_or_contradicted`. A correctly used relevant keyword may receive the
rubric's limited `mentioned_only` credit; a misused keyword receives no
automatic credit. Treat an unambiguous semantic equivalent as evidence for the
matching element without requiring standard wording, notation, or ordering.

Award the integer credit for that one state only. Do not award duplicate credit:
a keyword and its explanation belong to one element, and overlapping evidence
cannot receive points twice. Sum non-overlapping element credit into a subtotal.
Use the highest satisfied score band and any material-error cap only as upper
bounds; they cannot raise the subtotal. Full credit requires every required
essential element to be demonstrated or expressed by a semantic equivalent,
required terminology when explicitly requested, and no material contradiction.

When the final answer is wrong, retain justified process credit for correct
terms, concepts, formulas, substitutions, units, and reasoning unless the
frozen rubric makes the conclusion indispensable. For calculation problems,
arithmetic mistakes should not erase a correct method unless the frozen rubric
requires the exact result. When the final answer is correct and the process is
roughly correct, award full credit when the frozen requirements are met.

Candidate v3.1 adds four calibration rules for concept, proof, and construction
answers:

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

Candidate v3.1 r2 adds open-ended adequacy: for open-ended short-answer, proof,
construction, and essay questions, score whether the answer satisfies the task requirement.
Use the standard answer as an anchor, not as an exhaustive whitelist. Award
credit for valid, relevant, non-contradictory approaches, examples, or
constructions that answer the prompt, even when they are not listed in the expected answer or semantic equivalents.

Candidate v3.2 adds official-style adequacy: grade for official-style adequacy,
not ideal-answer completeness, and avoid being overly harsh. Preserve reasonable
partial credit for demonstrated understanding even when terminology, ordering,
or detail is imperfect. Distinguish missing ideal detail from a visible misconception.
Apply large deductions only for material errors, contradictions,
wrong language/output behavior, or missing required answer behavior.

Candidate v3.2 is a cross-course contract. Course-specific calibration overlays
belong in that course's frozen rubric and packet, never in this reusable skill.
Do not carry rules for named questions, named languages, named theorems, or a
previous course into another course merely because their labels look similar.

Classify every question from the prompt and frozen rubric *before* scoring. Use
the most specific applicable type, and record it in the grading record:

- `objective_selection` (including multiple choice, matching, and true/false):
  require a selected option or an unambiguous equivalent. Do not require an
  explanation for true/false or other selected-response items unless the prompt
  explicitly asks to prove, explain, justify, or show work.
- `calculation`: check the final numeric or symbolic result, method/setup,
  transformations or substitutions, intermediate calculation, and any
  mathematical or domain reasoning required by the rubric. Retain justified
  method credit if the final result is wrong. If the result is correct but
  required working is absent, award only the course-frozen answer-only credit;
  do not invent a universal amount.
- `calculation_short_answer`: score both the visible derivation and the short
  conclusion/classification requested by the question. A valid alternative
  derivation is acceptable; the reference solution is an anchor, not a required
  route.
- `short_answer` or `conceptual`: combine key-term, concept, and relation
  evidence; exact standard-answer wording is not required.
- `algorithm` or `construction`: require a viable method plus relevant steps,
  relations, and required output behavior; award credit to valid alternatives.
- `proof` or `explanation`: check each required logical direction/link and
  preserve credit for independently completed parts. A missing required part
  blocks full credit but does not erase unrelated demonstrated work.
- `diagram`, `geometry`, or `representation`: score the observable required
  objects, relations, labels, transformations, and conclusion. Do not assume a
  missing diagram feature from accompanying prose.
- `essay` or `open_response`: score distinct valid, relevant, non-contradictory
  claims against the task requirement; do not require fixed ordering or
  standard phrasing.

When a question genuinely combines types, use non-overlapping rubric elements
for each required aspect rather than forcing it into a narrower legacy label.
The type controls what evidence is relevant; the frozen rubric controls points,
score increments, and any answer-only allocation.

Freeze the grading protocol before student grading starts:

- page ordering for solutions and each student submission
- rubric question IDs, maximum points, and allowed score increments
- partial-credit rules; do not introduce quarter-point or 0.25-point scores
- treatment of missing pages, blank answers, unreadable work, and alternative correct methods

Treat transcript or OCR text as an optional aid. The Physics Week 9 pilot does
not prove that transcript workflows are generally better than direct-image
grading, so never claim that a transcript route is automatically more accurate.

### Benchmark-informed safeguards

The Physics Week 9 internal benchmark does not prove that transcript workflows
are generally better than the direct-image baseline. Treat transcript or OCR
steps as optional evidence aids, not as an automatic accuracy improvement.

Before grading, freeze the page ordering, rubric, question IDs, point ranges,
and allowed score increments. During grading, use an evidence-first pass: record the
visible equation, statement, text, or blank-answer marker before assigning
points. Run a second-pass review for low confidence, unreadable regions, blank
or apparently missing answers, total mismatches, and high-impact deductions.
At handoff, report flagged items and which questions they concentrate on; ask
the teacher to spot-check at least 3 students and all flagged items before
publishing grades.

### Route comparison and calibration

If a course authorizes a route comparison, evaluate direct multimodal grading
and transcription-assisted grading as separate conditions with the same frozen
rubric, gold, split, prompt packet, and review policy. Transcription is an
evidence aid, not ground truth; never let it silently replace the page image.

For each representative disagreement, create an evidence card before changing
the prompt, rubric, or skill. Classify it as exactly one primary cause:

- `clear_model_error`: visible source evidence and frozen rubric support a
  different score.
- `representation_loss`: a route lost, mistranscribed, reordered, cropped, or
  failed to expose relevant source evidence.
- `rubric_or_gold_conflict`: the frozen scoring rule or reference answer needs
  course-owner adjudication.
- `reasonable_severity_difference`: both readings are evidence-supported but
  differ within an acceptable strictness range.
- `insufficient_evidence`: source quality or record does not support a reliable
  conclusion.

Do not assume a disagreement is a model error. Preserve the card, route
artifacts, and human decision so future prompt changes are auditable.

### Step 1 — Discover

Run `discover.py` on the working directory containing submissions. Parse the JSON:

```bash
python <skill_root>/scripts/discover.py "$PWD"
```

If `solutions_error` is non-null, surface it to the user and stop. If the user passed a solutions path explicitly, use that instead of auto-discovery.

`discover.py` recurses into subdirectories (so `./submissions/` is picked up automatically) and skips hidden files/dirs. The JSON also includes a `late_students` list — student names whose filename contains `_LATE_` (case-insensitive). Surface the list to the user before grading so they can decide whether to apply a late-submission policy.

### Step 2 — Load the grading prompt and parse the rubric

Read `<skill_root>/references/grading-prompt.md` and follow it.

Convert the solutions file to page images:

```bash
python <skill_root>/scripts/to_images.py <solutions_file> /tmp/grade-homework/solutions/
```

View the solutions images, verify deterministic **page ordering**, parse the
`[N pts]` allocations into a rubric table, and **confirm with the user before
continuing**. Freeze the page list, rubric, question IDs, point ranges, and
allowed score increments before grading. If no `[N pts]` markers are found, stop and
ask for point allocations.

Partial-credit conventions:
1. Do not use 0.25-point or quarter-point scores.
2. Award full credit when the student's final answer is correct and the process
   is roughly correct, including mathematically equivalent alternative methods.
3. Deduct process points only when the final answer is correct but the process
   seriously conflicts with the standard solution, required method, or visible
   reasoning expectations.
4. When the final answer is wrong, inspect the student's process carefully and
   award the appropriate process credit from the frozen rubric.
5. Preserve the frozen point increment; if the rubric is unclear, ask the
   teacher before introducing a new increment.
6. If handwriting, page order, or missing work affects the score, add an
   explicit flag instead of hiding the uncertainty in the numeric score.


### Step 3 — Grade students one at a time

For each student (in alphabetical order unless the user specifies otherwise):

1. Convert each of that student's files to images:

   ```bash
   python <skill_root>/scripts/to_images.py "<student_file>" /tmp/grade-homework/<student>/
   ```

   If any file returns exit code 3 (`docx_unsupported`), include a `needs_manual_review` flag for that student and skip that file — do not block the whole run.

2. Verify page ordering and question-to-page coverage before reading answers.
   Missing, duplicated, rotated, or unreadable pages require an explicit flag.

3. Use an evidence-first pass. For every question, record the visible equation,
   statement, diagram feature, answer text, or blank-answer marker before
   assigning points. **Do not guess** missing work or silently repair a
   student's reasoning.

4. Score only against the frozen rubric. Validate each score against its range
   and allowed increment, then recompute section and assignment totals.
   Attach `high`, `medium`, or `low` confidence plus explicit ambiguity flags.

5. Run a **second-pass** review for every low-confidence item, unreadable region,
   blank or apparently missing answer, total mismatch, and high-impact
  deduction. Also check missed semantic equivalents, missed keyword credit,
  duplicate credit, keyword misuse, score-band consistency, material-error
  caps, local contradictions, indirect constructions, open-ended adequacy,
  official-style adequacy, and arithmetic.
   The second pass must revisit the source image and evidence, not merely repeat
   the first score.

6. Produce the JSON record only after those checks pass.
   `extracted_evidence` and `evidence` must be plain text strings. Do not output
   arrays or objects for these fields. If you use `key_term_evidence`,
   `concept_evidence`, or `relation_evidence` internally, summarize those layers
   inside the single `extracted_evidence` string or the single `evidence`
   string.

7. Pipe the record into `write_outputs.py`:

   ```bash
   echo "$RECORD_JSON" | python <skill_root>/scripts/write_outputs.py "$PWD/grades"
   ```

8. After every 3 students, briefly summarize progress to the user so they can course-correct early.

### Step 4 — Recovery

If `grades/grades.csv` already exists at the start of a run, `write_outputs.py`
will skip any student already present. Preserve immutable benchmark records:
never overwrite a benchmark run, prompt, rubric, or prediction file. For an
ordinary re-grade, archive the prior row and feedback before creating a clearly
identified replacement; do not silently delete grading history.

### Step 5 — Handoff

When all students are graded, list:

- Any students skipped (with reason).
- The total number of flagged items and which questions they concentrate on — this is what the teacher should spot-check before publishing grades.

## Failure modes

- **No solutions file / multiple candidates** → stop, ask user.
- **No `[N pts]` markers** → stop, ask user for allocations.
- **DOCX submission with no conversion toolchain** → `to_images.py` tries `libreoffice`/`soffice` first, then `pandoc + google-chrome/chromium` (extracts WMF/EMF → PNG via `inkscape` if present, converts HTML→PDF via headless Chrome). If neither path works, the student is flagged `needs_manual_review` and grading continues.
- **CSV header mismatch mid-run** (`write_outputs.py` exit 4) → rubric changed; stop and reconcile with user.

## Quality bar

This skill uses evidence-first grading plus targeted second-pass review. It is
**not** a substitute for teacher review: spot-check at least 3 students against
your own grading before publishing, and always review flagged items.

The Physics Week 9 internal benchmark used one run per condition and a single
primary-rater reference. Its transcript-based GPT condition did not outperform
the historical direct baseline overall, so do not claim a general accuracy
improvement. Treat page ordering, frozen rubrics, evidence, confidence, and
second-pass review as auditability safeguards, with extra attention to the
lowest-agreement Physics Week 9 questions; do not generalize those error
patterns beyond this benchmark.
