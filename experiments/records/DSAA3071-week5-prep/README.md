# DSAA3071 Week 5 Input Preparation

Status: local data preparation. No model calls were made.

The source `Data/DSAA3071/week5.pdf` is a combined student-answer PDF confirmed
by the user to contain 22 students. The pages also contain names and student
IDs, so the raw PDF must not be copied directly into prompt packets.

## Method

The preparation script renders each source page into a raster image, whites out
the top identity band, adds only the anonymous ID label, and writes a new PDF
for each student. This avoids leaving the original name or student ID pixels
under a PDF overlay.

Assumption:

- `week5.pdf` has 66 pages.
- There are 22 students.
- Each student occupies 3 consecutive pages.

## Command

Install `pypdfium2`, `Pillow`, and `reportlab`, then run from the repository
root:

```powershell
python experiments\records\DSAA3071-week5-prep\prepare_anonymized_week5.py `
  --source-pdf Data\DSAA3071\week5.pdf `
  --output-root Data\DSAA3071\benchmark `
  --student-count 22 `
  --pages-per-student 3 `
  --redaction-top-fraction 0.18 `
  --scale 2.0 `
  --preview-first-pages
```

Cross-platform equivalent:

```bash
python experiments/records/DSAA3071-week5-prep/prepare_anonymized_week5.py \
  --source-pdf Data/DSAA3071/week5.pdf \
  --output-root Data/DSAA3071/benchmark \
  --student-count 22 \
  --pages-per-student 3 \
  --redaction-top-fraction 0.18 \
  --scale 2.0 \
  --preview-first-pages
```

## Outputs

Generated local outputs are under ignored `Data/DSAA3071/benchmark/`:

- `anonymized/S###/week5.pdf`
- `manifest/student_index.csv`
- `manifest/privacy_review.csv`
- `manifest/prep-metadata.json`
- `privacy_review/previews/S###-p01.png`

Local run result:

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

## Privacy Gate

The generated PDFs are not approved for model runs until
`manifest/privacy_review.csv` is manually reviewed. The review must confirm that
no name, student ID, or other direct identifier remains visible.

If the top band hides useful answer content, rerun the script with a smaller
redaction fraction only after confirming that identifiers remain fully removed.
