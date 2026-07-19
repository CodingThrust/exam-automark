# DSAA3071 Week 5 Dev DeepSeek Metrics

- Generated at: `2026-07-18T13:40:29.565710Z`
- Analysis commit: `619b0a9`
- Split: `development`
- Input mode: `text-only transcript`
- Gold source: official per-question scores
- Students: `7`
- Score rows: `70`
- Total score max: `130`

## Summary Metrics

| Metric | Baseline | Candidate v2 | Candidate - Baseline |
|---|---:|---:|---:|
| `exact_agreement` | 0.5000 | 0.5000 | +0.0000 |
| `question_score_mae` | 3.3429 | 3.4000 | +0.0571 |
| `normalized_question_mae` | 0.1786 | 0.1801 | +0.0015 |
| `total_score_mae` | 28.0000 | 30.5714 | +2.5714 |
| `total_score_mae_fraction_of_max` | 0.2154 | 0.2352 | +0.0198 |
| `total_score_rmse` | 28.7800 | 31.7220 | +2.9421 |
| `total_error_within_20_point_rate` | 0.1429 | 0.2857 | +0.1429 |
| `total_error_gt_20_point_rate` | 0.8571 | 0.7143 | -0.1429 |
| `legacy_total_error_gt_2_point_rate` | 1.0000 | 1.0000 | +0.0000 |
| `mean_signed_error` | -2.8000 | -3.0571 | -0.2571 |
| `macro_accuracy` | 0.5000 | 0.5000 | +0.0000 |

## Paired Bootstrap

- Metric: exact agreement, candidate minus baseline
- Seed: `20260701`
- Samples: `10000`
- Mean difference: `0.0000`
- 95% interval: `[-0.0571, 0.0571]`

## Interpretation

Candidate v2 ties baseline on question-level exact agreement on the DSAA3071 week 5 development split.
Candidate v2 is slightly worse on total-score MAE and normalized question MAE, although it reduces the rate of very large total-score errors above 20 points.
Both prompts systematically under-score this dev split: every student total error is negative in both conditions.

## Metric Notes

- `legacy_total_error_gt_2_point_rate` is the old physics severe-error rule and is too strict for a 130-point exam; it is kept only for continuity.
- `total_error_gt_20_point_rate` is the more interpretable DSAA3071 diagnostic in this note.
- `normalized_question_mae` accounts for different question max scores.

## Caveats

- Development split only; do not treat this as held-out evidence.
- These metrics use the pre-review `T1-dev-r1` packet. A later human review changed 14 / 70 question records, including 9 transcript texts. The reviewed snapshot is frozen separately and requires new packets and model runs before its metrics can be reported.
- `S016` PDF privacy residue was corrected after this text-only dev run; metrics are unchanged because the run used transcript packets, but future PDF packet use should rely on the corrected packet hashes.
