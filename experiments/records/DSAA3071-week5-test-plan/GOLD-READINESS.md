# DSAA3071 Week 5 Gold Score Readiness

Status: **not_ready**

No model calls are recorded by this checklist. This record checks only whether the human reference score table is complete enough for metrics.

## Anchors

- Course: `DSAA3071`
- Assessment: `week5_test`
- Gold CSV: `Data/DSAA3071/week5-benchmark-redaction-v3/gold/primary_scores.csv`
- Expected students: `22`
- Expected questions: `10`
- Expected score rows: `220`

## Result

The gold table structure is ready, but the scores are not filled yet.

| Check | Status | Detail |
| --- | --- | --- |
| `required_columns_present` | passed | all required columns are present |
| `all_expected_pairs_present_once` | passed | every expected student/question pair appears exactly once |
| `scores_complete` | failed | 220 blank scores |
| `scores_within_course_steps` | passed | all nonblank scores are within course ranges and score steps |

## Next Actions

1. Fill `primary_scores.csv` with human reference scores for all 22 anonymous students and 10 questions.
2. Keep scores as integer points for this DSAA3071 week 5 pilot unless the instructor supplies a finer official increment.
3. Re-run `validate-gold` after filling the table.
4. Only after this report becomes `ready`, run model packets and compute metrics.