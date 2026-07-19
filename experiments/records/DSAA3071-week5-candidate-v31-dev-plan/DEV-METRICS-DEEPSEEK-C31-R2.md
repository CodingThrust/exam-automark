# DSAA3071 Week 5 Candidate-v3.1 r2 Development Metrics

Status: **development metrics computed; held-out not run**

This report compares B0, R1, C3, and C31-r2 on the seven-student development split using official per-question scores. It is calibration evidence only, not a final accuracy claim.

## Runs

| Condition | Description | Validation | Total tokens | Question MAE | Normalized MAE | Exact agreement | Severe error rate | Total MAE | Signed error |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `B0` | baseline prompt + rubric v0 | passed (7/7) | 63448 | 3.343 | 0.173 | 0.500 | 0.243 | 27.429 | -2.743 |
| `R1` | baseline prompt + rubric v1 | passed (7/7) | 92633 | 2.614 | 0.152 | 0.514 | 0.214 | 20.143 | -2.014 |
| `C3` | candidate-v3 prompt + rubric v1 | passed (7/7) | 104803 | 2.814 | 0.158 | 0.500 | 0.243 | 20.143 | -2.014 |
| `C31_r2` | candidate-v3.1 r2 open-ended adequacy prompt + rubric v1 | passed_after_recovery (7/7) | 107658 | 2.929 | 0.164 | 0.529 | 0.257 | 18.429 | -1.843 |

## Comparisons

Negative MAE deltas are improvements. Positive exact-agreement deltas are improvements.

| Comparison | Question MAE delta | Normalized MAE delta | Total MAE delta | Exact agreement delta | Severe error delta | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `R1_minus_B0` | -0.729 | -0.021 | -7.286 | 0.014 | -0.029 | Rubric v1 improves development metrics versus rubric v0. |
| `C3_minus_R1` | 0.200 | 0.005 | 0.000 | -0.014 | 0.029 | Candidate-v3 does not improve over rubric v1 with the baseline prompt on this split. |
| `C31_r2_minus_R1` | 0.314 | 0.011 | -1.714 | 0.014 | 0.043 | C31-r2 improves total MAE and exact agreement, but worsens question-level MAE and severe error rate. |
| `C31_r2_minus_C3` | 0.114 | 0.006 | -1.714 | 0.029 | 0.014 | C31-r2 improves total MAE and exact agreement versus C3, but not question-level MAE. |
| `C31_r2_minus_B0` | -0.414 | -0.010 | -9.000 | 0.029 | 0.014 | C31-r2 is clearly better than B0 on total MAE, but severe question-level errors remain. |

## Per-Question MAE

| Question | B0 | R1 | C3 | C31-r2 | Best on dev |
| --- | ---: | ---: | ---: | ---: | --- |
| Q1 | 0.000 | 0.000 | 0.000 | 0.000 | B0, R1, C3, C31_r2 |
| Q2 | 0.000 | 0.000 | 0.000 | 0.000 | B0, R1, C3, C31_r2 |
| Q3 | 0.000 | 0.000 | 0.000 | 0.000 | B0, R1, C3, C31_r2 |
| Q4 | 0.000 | 0.000 | 0.000 | 0.000 | B0, R1, C3, C31_r2 |
| Q5 | 7.000 | 4.857 | 5.857 | 2.571 | C31_r2 |
| Q6 | 2.143 | 1.714 | 1.857 | 2.714 | R1 |
| Q7 | 4.429 | 2.429 | 4.429 | 5.000 | R1 |
| Q8 | 3.857 | 5.714 | 4.857 | 5.000 | B0 |
| Q9 | 14.857 | 9.714 | 9.714 | 11.714 | R1, C3 |
| Q10 | 1.143 | 1.714 | 1.429 | 2.286 | B0 |

## C31-r2 Run Composition

- First attempt: `deepseek-C31-r2-text-dev-reviewed-r1`, 3/7 outputs passed; 4 students failed due to provider/network errors.
- Recovery 1: `deepseek-C31-r2-text-dev-reviewed-r1-recovery1`, 0/4 outputs passed due to provider/network errors.
- Recovery 2: `deepseek-C31-r2-text-dev-reviewed-r1-recovery2`, 4/4 outputs passed.
- Combined C31-r2 metric set: `S017`, `S021`, `S002` from the first attempt plus `S015`, `S020`, `S016`, `S022` from recovery2.

## Notes

- C31-r2 contains the open-ended adequacy rule for Q8/Q9-style answers: valid answers can receive credit even when they do not match the reference wording exactly.
- The best signal is mixed: total-score calibration improved, but question-level grading remains unstable for Q7, Q8, and Q9.
- The gold reference has official per-question scores only, not detailed official rationales. Metrics evaluate score agreement, not explanation quality.
- Development result: C31-r2 is promising for total-score alignment, but it should not be frozen as the final grading skill before held-out evaluation and question-level error review.
