---
name: grade-homework
description: Use when the user wants to grade a folder of student homework submissions against a teacher-provided solutions document — handles mixed formats (PDF, JPG, DOCX), produces a grades CSV and per-student English feedback with explicit flagging of ambiguous items for teacher review. Triggers on phrases like "grade the homework", "mark HW9", "批作业".
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

### Benchmark-informed safeguards

The Physics Week 9 internal benchmark does not prove that transcript workflows
are generally better than the direct-image baseline. Treat transcript or OCR
steps as optional evidence aids, not as an automatic accuracy improvement.

Before grading, freeze the page ordering, rubric, question IDs, point ranges,
and quarter-point rules. During grading, use an evidence-first pass: record the
visible equation, statement, text, or blank-answer marker before assigning
points. Run a second-pass review for low confidence, unreadable regions, blank
or apparently missing answers, total mismatches, and high-impact deductions.
At handoff, report flagged items and which questions they concentrate on; ask
the teacher to spot-check at least 3 students and all flagged items before
publishing grades.

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
quarter-point rules before grading. If no `[N pts]` markers are found, stop and
ask for point allocations.

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
   statement, or blank-answer marker before assigning points. **Do not guess**
   missing work or silently repair a student's reasoning.

4. Score only against the frozen rubric. Validate each score against its range
   and quarter-point increment, then recompute section and assignment totals.
   Attach `high`, `medium`, or `low` confidence plus explicit ambiguity flags.

5. Run a **second-pass** review for every low-confidence item, unreadable region,
   blank or apparently missing answer, total mismatch, and high-impact
   deduction. The second pass must revisit the source image and evidence, not
   merely repeat the first score.

6. Produce the JSON record only after those checks pass.

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
