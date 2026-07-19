# DSAA3071 Week 5 Development Metrics

Status: **development metrics computed; held-out not run**

This report compares B0/R1/C3 on the seven-student development split using official per-question scores. It is calibration evidence only, not a final accuracy claim.

## Runs

| Condition | Packet | Run commit | Validation | Total tokens | Question MAE | Normalized MAE | Exact agreement | Severe error rate | Total MAE | Signed error |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | `B0-dev-reviewed-r1` | `3aecbcf` | passed (7/7) | 63448 | 3.343 | 0.173 | 0.500 | 0.243 | 27.429 | -2.743 |
| R1 | `R1-dev-reviewed-r1` | `3aecbcf` | passed (7/7) | 92633 | 2.614 | 0.152 | 0.514 | 0.214 | 20.143 | -2.014 |
| C3 | `C3-dev-reviewed-r3` | `70dd248` | passed (7/7) | 104803 | 2.814 | 0.158 | 0.500 | 0.243 | 20.143 | -2.014 |

## Comparisons

Negative MAE deltas are improvements. Positive exact-agreement deltas are improvements.

| Comparison | Question MAE delta | Normalized MAE delta | Total MAE delta | Exact agreement delta | Severe error delta | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `R1_minus_B0` | -0.729 | -0.021 | -7.286 | 0.014 | -0.029 | Rubric v1 improves the development metrics versus rubric v0. |
| `C3_minus_R1` | 0.200 | 0.005 | 0.000 | -0.014 | 0.029 | Candidate-v3 does not improve over rubric v1 with the baseline prompt on this split. |
| `C3_minus_B0` | -0.529 | -0.016 | -7.286 | 0.000 | 0.000 | Candidate-v3 plus rubric v1 improves versus B0, but the gain is mostly from rubric v1. |

## Per-Question MAE

| Question | B0 | R1 | C3 | Best on dev |
| --- | ---: | ---: | ---: | --- |
| Q1 | 0.000 | 0.000 | 0.000 | B0 |
| Q2 | 0.000 | 0.000 | 0.000 | B0 |
| Q3 | 0.000 | 0.000 | 0.000 | B0 |
| Q4 | 0.000 | 0.000 | 0.000 | B0 |
| Q5 | 7.000 | 4.857 | 5.857 | R1 |
| Q6 | 2.143 | 1.714 | 1.857 | R1 |
| Q7 | 4.429 | 2.429 | 4.429 | R1 |
| Q8 | 3.857 | 5.714 | 4.857 | B0 |
| Q9 | 14.857 | 9.714 | 9.714 | R1 |
| Q10 | 1.143 | 1.714 | 1.429 | B0 |

## Notes

- B0 and R1 use the authfix rerun directories because the first attempt failed with an invalid API key.
- C3 r2 failed schema validation because some model outputs used object/list evidence fields; C3 r3 fixes the prompt by requiring plain text evidence fields.
- The gold reference contains official per-question scores only, not detailed official rationales. Metrics therefore evaluate score agreement, not explanation quality.
- Development result: rubric v1 is clearly useful. Candidate-v3 r3 is better than B0 but not better than R1 on this split, so it should not be frozen as an accuracy improvement without further calibration or held-out evidence.
