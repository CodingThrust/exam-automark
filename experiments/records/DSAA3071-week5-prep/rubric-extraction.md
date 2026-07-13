# DSAA3071 Week 5 Rubric Extraction

Status: draft rubric extracted from `week5-5.test-solution.pdf`. No model calls
were made.

Source SHA-256:
`aeab881a2e23bcd29c6174419c0d0904ab706ec560314053cb1557958370d94f`

## Extracted Structure

| Question | Points | Topic |
| --- | ---: | --- |
| Q1 | 5 | Multitape TM simulation overhead |
| Q2 | 5 | NTM deterministic simulation overhead |
| Q3 | 5 | Enumerator definition |
| Q4 | 5 | Church-Turing thesis |
| Q5 | 20 | Simulating a 2-tape TM on one tape |
| Q6 | 20 | Simulating an NTM deterministically |
| Q7 | 20 | Turing-recognizable languages and enumerators |
| Q8 | 10 | Enumerator for a zero-string language |
| Q9 | 25 | Evidence for the Church-Turing thesis |
| Q10 | 15 | TM robustness and restricted variants |

Total: 130 points.

## Clarification

Q8 is confirmed by the user as `0^(2^n)`, not `0^(2n)`. Therefore the expected
output lengths are powers of two: 1, 2, 4, 8, and so on. The rubric treats
epsilon as not required for Q8 unless the instructor later supplies a different
official correction.

## Outputs

- Draft model-facing rubric:
  `experiments/records/DSAA3071-week5-prep/rubric_v0.json`
- Course spec updated:
  `experiments/course_specs/DSAA3071_week5_test.json`
- Local gold score template:
  `Data/DSAA3071/benchmark-redaction-v3/gold/primary_scores.csv`

## Remaining Work

1. Human review of `rubric_v0.json`.
2. Fill gold scores for the 22 anonymous students.
3. Build and audit DSAA3071 prompt packets before any model call.
