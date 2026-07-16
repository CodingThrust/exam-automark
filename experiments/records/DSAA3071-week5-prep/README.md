# DSAA3071 Week 5 Input Preparation

Status: local data preparation. No model calls were made.

The source `Data/DSAA3071/DSAA3071-W5Test.pdf` is a combined student-answer PDF
confirmed by the user to contain 22 students. It was previously named
`Data/DSAA3071/week5.pdf`; the rename was made on 2026-07-13 to match the
DSAA3071 week naming convention, and the SHA-256 hash is unchanged. The pages
also contain names and student IDs, so the raw PDF must not be copied directly
into prompt packets.

## Method

The preparation script renders each source page into a raster image, whites out
configured identity rectangles, adds only the anonymous ID label, and writes a
new PDF for each student. This avoids leaving the original name or student ID
pixels under a PDF overlay.

Assumption:

- `DSAA3071-W5Test.pdf` has 66 pages.
- There are 22 students.
- Each student occupies 3 consecutive pages.

## Command

Install `pypdfium2`, `Pillow`, and `reportlab`, then run from the repository
root:

```powershell
python experiments\records\DSAA3071-week5-prep\prepare_anonymized_week5.py `
  --source-pdf Data\DSAA3071\DSAA3071-W5Test.pdf `
  --output-root Data\DSAA3071\benchmark `
  --student-count 22 `
  --pages-per-student 3 `
  --redaction-rect 0,0,0.48,0.08 `
  --redaction-rect 0.62,0,1,0.08 `
  --scale 2.0 `
  --preview-all-pages
```

Cross-platform equivalent:

```bash
python experiments/records/DSAA3071-week5-prep/prepare_anonymized_week5.py \
  --source-pdf Data/DSAA3071/DSAA3071-W5Test.pdf \
  --output-root Data/DSAA3071/benchmark \
  --student-count 22 \
  --pages-per-student 3 \
  --redaction-rect 0,0,0.48,0.08 \
  --redaction-rect 0.62,0,1,0.08 \
  --scale 2.0 \
  --preview-all-pages
```

## Outputs

Generated local outputs are under ignored `Data/DSAA3071/benchmark/`:

- `anonymized/S###/week5.pdf`
- `manifest/student_index.csv`
- `manifest/privacy_review.csv`
- `manifest/prep-metadata.json`
- `privacy_review/previews/S###-p01.png`

Local run result:

- v1 output root: `Data/DSAA3071/benchmark`
- source PDF page count: 66
- anonymous students generated: 22
- pages per student: 3
- generated student PDFs: 22
- generated first-page privacy previews: 22
- `student_index.csv` rows: 22
- `privacy_review.csv` rows: 66
- privacy review status: pending
- model run allowed: false
- source SHA-256:
  `ab691a2614ce854e53f7830c6ae3c4d35c98b1961db34cbaac99ee7563258cb9`

Known issue:

- v1 used a full-width top 18% redaction band. User review found that some
  question and answer content was hidden.
- v2 should be generated from the original source PDF with smaller left and
  right header rectangles, not by editing the v1 PDFs.

V2 local run result:

- v2 output root: `Data/DSAA3071/benchmark-redaction-v2`
- redaction rectangles:
  - `0,0,0.48,0.08`
  - `0.62,0,1,0.08`
- source PDF page count: 66
- anonymous students generated: 22
- pages per student: 3
- generated student PDFs: 22
- generated page previews: 66
- `student_index.csv` rows: 22
- `privacy_review.csv` rows: 66
- privacy review status: pending
- model run allowed: false

Known issue:

- v2 left the top-middle student ID visible on each PDF.

V3 local run result:

- v3 output root: `Data/DSAA3071/benchmark-redaction-v3`
- redaction rectangle:
  - `0,0,1,0.08`
- source PDF page count: 66
- anonymous students generated: 22
- pages per student: 3
- generated student PDFs: 22
- generated page previews: 66
- `student_index.csv` rows: 22
- `privacy_review.csv` rows: 66
- privacy review status: approved by user
- privacy reviewed at: `2026-07-13T10:26:50.903989Z`
- model run allowed: false until rubric extraction, gold score creation, and
  prompt packet audit are complete

V3 is the approved anonymized input candidate for the next DSAA3071 packet
preparation step.

## Additional DSAA3071 Source Files

On 2026-07-13, the user added question-plus-answer-key PDFs for DSAA3071 weeks
2, 3, 4, and 6. Together with the previously corrected student-answer PDFs,
DSAA3071 now has week 2, 3, 4, 5, and 6 source coverage. Only week 5 has been
anonymized and privacy-approved so far. Weeks 2, 3, 4, and 6 still require
separate privacy review, anonymization, rubric extraction, gold-score planning,
and packet audit before any model call.

## Rubric And Gold Template

The draft English rubric was extracted from
`Data/DSAA3071/week5-5.test-solution.pdf`:

- `experiments/records/DSAA3071-week5-prep/rubric_v0.json`
- source SHA-256:
  `aeab881a2e23bcd29c6174419c0d0904ab706ec560314053cb1557958370d94f`

The local gold score template was generated under ignored `Data/`:

- `Data/DSAA3071/benchmark-redaction-v3/gold/primary_scores.csv`
- rows: 220
- students: 22
- questions: 10
- filled scores: 0

The template must be manually filled before metrics can be computed.

## Packet Dry Run

On 2026-07-16, baseline and candidate-v2 DSAA3071 week 5 prompt packets were
built from the approved v3 anonymized PDFs without making any model calls.
The dry-run record is tracked at:

- `experiments/records/DSAA3071-week5-test-plan/PACKET-DRY-RUN.md`

The tracked records include:

- deterministic anonymous dev/held-out split files
- baseline and candidate-v2 strict-schema prompt snapshots
- baseline plan: `experiments/records/DSAA3071-week5-test-plan/plan.json`
- candidate-v2 plan:
  `experiments/records/DSAA3071-week5-test-plan/candidate-v2-plan.json`
- audit-passed packet hashes for all T1/G1 dev/test packets

The generated packets live under ignored `Data/` and must not be committed:

- `Data/DSAA3071/benchmark-redaction-v3/dry_run_packets/DSAA3071-week5-baseline-v1-lf/`
- `Data/DSAA3071/benchmark-redaction-v3/dry_run_packets/DSAA3071-week5-candidate-v2-lf/`

This is still not an accuracy experiment. Gold scores, transcript outputs, and
the multimodal/headless run protocol remain pending.

## Privacy Gate

The generated PDFs are not approved for model runs until
`manifest/privacy_review.csv` is manually reviewed. The review must confirm that
no name, student ID, or other direct identifier remains visible.

If the top band hides useful answer content, rerun the script with a smaller
redaction fraction only after confirming that identifiers remain fully removed.
