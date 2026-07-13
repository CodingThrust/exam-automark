# Multi-Course Pilot Inventory

Status: inventory comparison only. No model calls were made.

This record compares the current local data layout for DSAA3073, DSAA3071, and
linear algebra so the next grading experiment can be chosen from first
principles. It records only safe metadata: counts, extension distributions,
layout flags, and blockers. Raw filenames, student answers, identity maps, and
student-visible work are intentionally omitted.

## Version Anchor

- Repository branch: `codex/multi-course-pilot-inventory`
- Base commit: `694618f`
- Scan date: `2026-07-13`
- Existing inventories:
  - `experiments/data_inventory/DSAA3073.json`
  - `experiments/data_inventory/DSAA3071.json`
  - `experiments/data_inventory/linearalgebra.json`
- Existing draft course specs:
  - `experiments/course_specs/DSAA3073_week2_test.json`
  - `experiments/course_specs/DSAA3071_week5_test.json`
  - `experiments/course_specs/linearalgebra_quiz1.json`

## Readiness Criteria

A course is ready for a reproducible grading-accuracy pilot only when all of
these are true:

1. Anonymous student submissions are available as packet inputs.
2. A rubric or solution can be converted into an English model-facing rubric.
3. Gold scores or human reference scores exist for the same anonymous students.
4. The question IDs, maximum scores, and score increments are known.
5. Prompt packets can be built with relative paths and audited before model
   calls.
6. Metrics can be recomputed from local run outputs and gold scores.

## Course Findings

| Course | Current data shape | Useful assets observed | Main blockers | Pilot readiness |
| --- | --- | --- | --- | --- |
| DSAA3073 | 1 remaining top-level PDF after correction | Four previously observed student-answer PDFs were corrected to DSAA3071 week 2, 3, 4, and 6 sources | Local folder contents are inconsistent; clean DSAA3073 submissions, rubric, and gold scores are not available | Retired from current pilot selection |
| DSAA3071 | 6 top-level source PDFs plus generated benchmark folders | Week 5 combined PDF with 22 students' answers, week 5 question-plus-answer key, and additional week 2, 3, 4, and 6 student-answer sources | Week 5 anonymous candidate PDFs are approved, but gold scores are not filled and prompt packets are not audited; week 2, 3, 4, and 6 still need separate preparation | Recommended current pilot remains week 5; other weeks are later expansion data |
| linearalgebra | 1 quiz PDF plus 135 submission files under `submissions/` | Actual student submissions exist across images, PDFs, HEIC, and one docx | Raw filenames contain identity-like prefixes; no rubric, solution, or gold score file is visible in the current tree | Best representative next pilot after anonymization and rubric/gold preparation |

## Data Correction On 2026-07-13

The supervisor/user clarified that the four student-answer PDFs previously
observed under `Data/DSAA3073` are actually DSAA3071 week 2, 3, 4, and 6
student-answer sources. They were moved to `Data/DSAA3071` in the local private
data tree. `Data/` remains ignored by Git.

As a result, DSAA3073 is not a current pilot candidate. It should only be
reopened if a clean DSAA3073 data snapshot with confirmed submissions, rubric,
and gold scores is supplied.

## Recommendation

If the goal is to enter multi-course packet construction as quickly as possible,
start with DSAA3071. It has one combined PDF with 22 students' answers plus a
question-and-answer key PDF. That is enough for a small but meaningful packet
workflow once the combined PDF is split or indexed into anonymous `S###` inputs
and a human gold table is created.

The first anonymized candidate input tree was generated under ignored
`Data/DSAA3071/benchmark/`, but user review found that the full-width redaction
band hid some question and answer content. The v2 candidate used smaller
left/right header rectangles, but user review found that top-middle student IDs
remained visible. The current v3 candidate is under
`Data/DSAA3071/benchmark-redaction-v3/` and uses a full-width top 8% redaction
band. User review approved the v3 anonymization on 2026-07-13. The draft
English rubric and a blank gold-score template have been created. Q8 has been
confirmed as `0^(2^n)`. It is still not ready for model calls until gold scores
are filled and prompt packets are audited.

The newly corrected DSAA3071 week 2, 3, 4, and 6 sources expand the future
DSAA3071 data pool, but they are not ready for model calls. Each week still
needs privacy review/anonymization, rubric extraction, gold-score planning, and
packet audit before it can enter a reproducible experiment.

If the goal is a more representative second accuracy pilot, linear algebra is
stronger because it has many more submissions. It should not be run yet. The
next required step is to create a private anonymous snapshot with `S###` IDs,
preserve an identity map outside Git, and obtain or extract the rubric plus gold
scores.

## Next Actions

1. Human-review `experiments/records/DSAA3071-week5-prep/rubric_v0.json`.
2. Fill `Data/DSAA3071/benchmark-redaction-v3/gold/primary_scores.csv` for the
   22 anonymous IDs.
3. Build prompt packets and run `exam-benchmark audit-packet` before any model
   call.
4. Only after packet audit passes, decide whether to run DeepSeek text-only,
   another text-only provider, or a multimodal provider.
5. Treat DSAA3071 week 2, 3, 4, and 6 as later expansion candidates after week
   5 has a complete reproducible run.

## Privacy Notes

- `Data/` remains ignored by Git.
- This record does not include raw filenames.
- Public experiment records may include aggregate counts, hashes, and anonymous
  IDs only.
- Any identity map from raw filenames to `S###` IDs must stay outside Git and
  outside prompt packets.
