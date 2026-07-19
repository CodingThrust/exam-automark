# DSAA3071 Week 5 Candidate-v3.2 Development Metrics

Status: **development metrics computed; held-out not run**

This report compares B0, R1, C3, C31-r2, and C32 on the seven-student development split using official per-question scores. It is calibration evidence only, not a final accuracy claim.

## Headline

C32 is the best development condition so far on aggregate MAE: question MAE improves from `R1=2.614` to `C32=2.557`, and total MAE improves from `R1=20.143` to `C32=14.429`. It also improves over C31-r2 on question MAE, total MAE, and severe-error rate.

The result is still not clean enough to freeze the skill: Q8 remains a major unresolved error source, Q6 worsens versus R1, and C32 severe-error rate remains slightly higher than R1.

## Runs

| Condition | Description | Validation | Total tokens | Question MAE | Normalized MAE | Exact agreement | Severe error rate | Total MAE | Signed error |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `B0` | baseline prompt + rubric v0 | passed (7/7) | 63448 | 3.343 | 0.173 | 0.500 | 0.243 | 27.429 | -2.743 |
| `R1` | baseline prompt + rubric v1 | passed (7/7) | 92633 | 2.614 | 0.152 | 0.514 | 0.214 | 20.143 | -2.014 |
| `C3` | candidate-v3 prompt + rubric v1 | passed (7/7) | 104803 | 2.814 | 0.158 | 0.500 | 0.243 | 20.143 | -2.014 |
| `C31_r2` | candidate-v3.1 r2 open-ended adequacy prompt + rubric v1 | failed (7/11) | 107658 | 2.929 | 0.164 | 0.529 | 0.257 | 18.429 | -1.843 |
| `C32` | candidate-v3.2 prompt + rubric v2 | passed (7/7) | 116758 | 2.557 | 0.149 | 0.529 | 0.229 | 14.429 | -1.243 |

## Comparisons

Negative MAE deltas are improvements. Positive exact-agreement deltas are improvements. Negative severe-error deltas are improvements.

| Comparison | Question MAE delta | Normalized MAE delta | Total MAE delta | Exact agreement delta | Severe error delta | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `R1_minus_B0` | -0.729 | -0.021 | -7.286 | 0.014 | -0.029 | Rubric v1 improves development metrics versus rubric v0. |
| `C3_minus_R1` | 0.200 | 0.005 | 0.000 | -0.014 | 0.029 | Candidate-v3 does not improve over rubric v1 with the baseline prompt on this split. |
| `C31_r2_minus_R1` | 0.314 | 0.011 | -1.714 | 0.014 | 0.043 | C31-r2 improves total MAE and exact agreement, but worsens question-level MAE and severe error rate. |
| `C32_minus_R1` | -0.057 | -0.003 | -5.714 | 0.014 | 0.014 | C32 improves question-level MAE and total MAE versus R1, but severe-error rate is still slightly worse. |
| `C32_minus_C31_r2` | -0.371 | -0.014 | -4.000 | 0.000 | -0.029 | C32 improves question-level MAE, total MAE, and severe-error rate versus C31-r2; exact agreement is unchanged. |
| `C32_minus_B0` | -0.786 | -0.024 | -13.000 | 0.029 | -0.014 | C32 is clearly better than B0 on aggregate development metrics. |

## Per-Question MAE

| Question | B0 | R1 | C3 | C31-r2 | C32 | Best on dev |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Q1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | B0, R1, C3, C31_r2, C32 |
| Q2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | B0, R1, C3, C31_r2, C32 |
| Q3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | B0, R1, C3, C31_r2, C32 |
| Q4 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | B0, R1, C3, C31_r2, C32 |
| Q5 | 7.000 | 4.857 | 5.857 | 2.571 | 2.714 | C31_r2 |
| Q6 | 2.143 | 1.714 | 1.857 | 2.714 | 4.429 | R1 |
| Q7 | 4.429 | 2.429 | 4.429 | 5.000 | 2.429 | R1, C32 |
| Q8 | 3.857 | 5.714 | 4.857 | 5.000 | 5.571 | B0 |
| Q9 | 14.857 | 9.714 | 9.714 | 11.714 | 9.000 | C32 |
| Q10 | 1.143 | 1.714 | 1.429 | 2.286 | 1.429 | B0 |

## C32 Q7-Q9 Score Table

This table records only anonymous IDs, official scores, C32 scores, and errors. It does not copy student answer text.

| Student | Question | Gold | C32 | C32 error |
| --- | --- | ---: | ---: | ---: |
| `S017` | Q7 | 20.000 | 17.000 | -3.000 |
| `S017` | Q8 | 9.000 | 5.000 | -4.000 |
| `S017` | Q9 | 25.000 | 12.000 | -13.000 |
| `S021` | Q7 | 15.000 | 16.000 | 1.000 |
| `S021` | Q8 | 0.000 | 5.000 | 5.000 |
| `S021` | Q9 | 12.000 | 10.000 | -2.000 |
| `S002` | Q7 | 10.000 | 15.000 | 5.000 |
| `S002` | Q8 | 10.000 | 3.000 | -7.000 |
| `S002` | Q9 | 25.000 | 25.000 | 0.000 |
| `S015` | Q7 | 10.000 | 13.000 | 3.000 |
| `S015` | Q8 | 10.000 | 4.000 | -6.000 |
| `S015` | Q9 | 25.000 | 17.000 | -8.000 |
| `S020` | Q7 | 18.000 | 18.000 | 0.000 |
| `S020` | Q8 | 10.000 | 1.000 | -9.000 |
| `S020` | Q9 | 10.000 | 2.000 | -8.000 |
| `S016` | Q7 | 0.000 | 0.000 | 0.000 |
| `S016` | Q8 | 8.000 | 5.000 | -3.000 |
| `S016` | Q9 | 25.000 | 5.000 | -20.000 |
| `S022` | Q7 | 10.000 | 5.000 | -5.000 |
| `S022` | Q8 | 10.000 | 5.000 | -5.000 |
| `S022` | Q9 | 25.000 | 13.000 | -12.000 |

## Findings

### 1. C32 Improves Aggregate Development Accuracy

Compared with R1, C32 reduces question-level MAE by `0.057` and total-score MAE by `5.714`. Compared with C31-r2, it reduces question-level MAE by `0.371`, total-score MAE by `4.000`, and severe-error rate by `0.029`.

This is the first candidate in the DSAA3071 development sequence that improves both question-level MAE and total-score MAE versus R1.

### 2. Q9 Improved But Is Still Under-Scored

Q9 MAE improves from `C31-r2=11.714` to `C32=9.000`, and it is also better than `R1=9.714`. However, several C32 Q9 scores are still substantially below the official score, so the conceptual-answer policy is improved but not solved.

### 3. Q7 Returned To R1-Level MAE

Q7 MAE improves from `C31-r2=5.000` back to `C32=2.429`, matching R1. This supports the v3.2 decision to preserve construction credit when a local proof mistake is present.

### 4. Q8 Remains The Main Blocker

Q8 remains unstable: `C32=5.571` MAE is only slightly better than `R1=5.714` and worse than `B0=3.857`. The v3.2 enumerator policy did not solve Q8 on this development split.

### 5. Severe Errors Still Need Attention

C32 reduces severe-error rate versus C31-r2, but it is still slightly worse than R1: `C32=0.229` versus `R1=0.214`. This matters because severe errors are more visible to instructors than small total-score improvements.

## Interpretation

C32 is a promising development improvement, not a final grading skill. The best next experiment is not another broad prompt rewrite; it is a focused Q8 diagnosis and then a held-out run only after the Q8 policy is stable enough to justify testing.

## Limitations

- Held-out not run; this is not a final accuracy claim.
- The development split has only seven anonymous students.
- The gold reference contains official per-question scores but not official rationales, so metrics evaluate score agreement rather than explanation quality.
- C32 changes rubric, prompt, and skill together by design; this measures the calibrated package, not an isolated single-factor ablation.
