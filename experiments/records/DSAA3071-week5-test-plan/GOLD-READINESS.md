# DSAA3071 Week 5 Gold Score Readiness

Status: **ready**

No model calls are recorded by this checklist. This record checks only whether the human reference score table is complete enough for metrics.

## Anchors

- Course: `DSAA3071`
- Assessment: `week5_test`
- Gold CSV: `Data/DSAA3071/week5-benchmark-redaction-v3/gold/primary_scores.csv`
- Expected students: `22`
- Expected questions: `10`
- Expected score rows: `220`

## Result

The gold table is complete using the official per-question gradebook scores
that were manually transferred into the private `Data/` CSV by the researcher.
The public record stores only readiness counts and checks, not raw student
scores.

| Check | Status | Detail |
| --- | --- | --- |
| `required_columns_present` | passed | all required columns are present |
| `all_expected_pairs_present_once` | passed | every expected student/question pair appears exactly once |
| `scores_complete` | passed | no blank scores |
| `scores_within_course_steps` | passed | all nonblank scores are within course ranges and score steps |

## Next Actions

1. Treat `primary_scores.csv` as the official per-question reference for DSAA3071 week 5.
2. Keep the official gradebook source and any identity mapping in the private data repository only.
3. Run model packets against the frozen baseline and candidate prompt packets.
4. Compute metrics only from model outputs and this ready gold reference.
