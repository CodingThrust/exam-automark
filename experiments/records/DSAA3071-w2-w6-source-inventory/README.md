# DSAA3071 W2/W3/W4/W6 Source PDF Inventory

Status: source PDFs organized and fingerprinted. No anonymization, transcript
review, prompt packets, or model calls were made in this record.

## What This Records

This record pairs each DSAA3071 weekly-test student-answer PDF with the matching
question-plus-solution PDF:

| Week | Student-answer source | Pages | Question+solution source | Pages |
| --- | --- | ---: | --- | ---: |
| W2 | `Data/DSAA3071/DSAA3071-W2Test.pdf` | 92 | `Data/DSAA3071/week2-2.test-solution.pdf` | 4 |
| W3 | `Data/DSAA3071/DSAA3071-W3Test.pdf` | 46 | `Data/DSAA3071/week3-3.test-solution.pdf` | 4 |
| W4 | `Data/DSAA3071/DSAA3071-W4Test.pdf` | 90 | `Data/DSAA3071/week4-4.test-solution.pdf` | 4 |
| W6 | `Data/DSAA3071/DSAA3071-W6Test.pdf` | 86 | `Data/DSAA3071/week6-6.test-solution.pdf` | 4 |

The machine-readable source of truth is:

- `experiments/records/DSAA3071-w2-w6-source-inventory/source-inventory.json`

## Privacy And Git Policy

The actual PDFs stay under ignored `Data/`. This tracked record contains only
repo-relative paths, file sizes, page counts, and SHA-256 hashes. It contains no
student names, student IDs, answer text, solution text, images, or extracted
transcripts.

The student-answer PDFs are still raw private source files. They are not approved
for model runs, prompt packets, public reports, or GitHub commits until they have
separate anonymization outputs and manual privacy approval.

## Current Limitation

This is a data-readiness record, not an experiment result. It does not yet tell
us scoring accuracy for W2/W3/W4/W6. The next reproducible step is to choose one
week, confirm the student/page structure, anonymize it, create a rubric and gold
score sheet, then build audited prompt packets.
