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
| DSAA3073 | 5 top-level PDFs | User confirmed 4 student answer PDFs and 1 question-plus-answer-key PDF | Needs anonymous packet input tree, rubric extraction, gold scores, and course ID confirmation because local labels appear inconsistent | Fastest small dry run after anonymization; not yet ready for accuracy claims |
| DSAA3071 | 2 top-level PDFs | User confirmed 1 combined PDF containing 22 students' answers and 1 question-plus-answer-key PDF | Anonymous candidate PDFs generated; needs manual privacy review, rubric extraction, and gold scores | Recommended next small pilot after privacy review |
| linearalgebra | 1 quiz PDF plus 135 submission files under `submissions/` | Actual student submissions exist across images, PDFs, HEIC, and one docx | Raw filenames contain identity-like prefixes; no rubric, solution, or gold score file is visible in the current tree | Best representative next pilot after anonymization and rubric/gold preparation |

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
band. User review approved the v3 anonymization on 2026-07-13. It is still not
ready for model calls until rubric extraction, gold score creation, and prompt
packet audit are complete.

DSAA3073 remains useful as a smaller backup pilot. It has four student answer
PDFs plus a question-and-answer key PDF, but the local course labels are also
unclear and the sample is smaller.

If the goal is a more representative second accuracy pilot, linear algebra is
stronger because it has many more submissions. It should not be run yet. The
next required step is to create a private anonymous snapshot with `S###` IDs,
preserve an identity map outside Git, and obtain or extract the rubric plus gold
scores.

## Next Actions

1. Extract the question IDs, maximum scores, score increments, and grading rules
   from the question-plus-answer-key PDF into an English rubric.
2. Create a gold score CSV for the same 22 anonymous IDs.
3. Build prompt packets and run `exam-benchmark audit-packet` before any model
   call.
4. Only after packet audit passes, decide whether to run DeepSeek text-only,
   another text-only provider, or a multimodal provider.

## Privacy Notes

- `Data/` remains ignored by Git.
- This record does not include raw filenames.
- Public experiment records may include aggregate counts, hashes, and anonymous
  IDs only.
- Any identity map from raw filenames to `S###` IDs must stay outside Git and
  outside prompt packets.
