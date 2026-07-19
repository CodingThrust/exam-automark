# DSAA3071 Week 5 C31-r2 Error Diagnosis

Status: **development error diagnosis recorded; no held-out evidence**

This note diagnoses why `C31_r2` improved total-score MAE but worsened
question-level MAE and severe error rate on the seven-student DSAA3071 Week 5
development split. It uses only anonymous IDs, official per-question scores,
model scores, flags, and aggregate metrics.

## Scope

- Split: development
- Students: `S017`, `S021`, `S002`, `S015`, `S020`, `S016`, `S022`
- Focus questions: `Q7`, `Q8`, `Q9`
- Gold source: official per-question scores
- Model condition: `C31_r2`
- Run composition: first C31-r2 attempt outputs for `S017`, `S021`, `S002`;
  recovery2 outputs for `S015`, `S020`, `S016`, `S022`

## Checks Performed

- Confirmed `C31_r2` validation passed after recovery: 7/7 anonymous students.
- Confirmed Q7/Q8/Q9 gold rows are present for the seven development students.
- Compared `B0`, `R1`, `C3`, and `C31_r2` scores against official scores.
- Reviewed C31-r2 model flags and score rationales for the largest anonymous
  score errors without copying student answer text into this record.

## Headline Result

`C31_r2` improves total-score MAE but not question-level accuracy:

| Condition | Question MAE | Exact agreement | Severe error rate | Total MAE |
| --- | ---: | ---: | ---: | ---: |
| `B0` | 3.343 | 0.500 | 0.243 | 27.429 |
| `R1` | 2.614 | 0.514 | 0.214 | 20.143 |
| `C3` | 2.814 | 0.500 | 0.243 | 20.143 |
| `C31_r2` | 2.929 | 0.529 | 0.257 | 18.429 |

Compared with `R1`, `C31_r2` has:

- question MAE delta: `+0.314` worse
- normalized question MAE delta: `+0.011` worse
- total MAE delta: `-1.714` better
- exact agreement delta: `+0.014` better
- severe error delta: `+0.043` worse

Interpretation: the total-score improvement is real for this development split,
but it is partly caused by compensating item-level errors. It should not be
treated as a robust grading-skill improvement.

## Q7-Q9 Score Table

| Student | Question | Gold | R1 | C3 | C31-r2 | C31 error | C31 confidence | C31 flags |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `S017` | Q7 | 20 | 18 | 17 | 19 | -1 | high |  |
| `S017` | Q8 | 9 | 8 | 10 | 10 | +1 | high |  |
| `S017` | Q9 | 25 | 22 | 19 | 15 | -10 | medium |  |
| `S021` | Q7 | 15 | 9 | 5 | 7 | -8 | medium |  |
| `S021` | Q8 | 0 | 8 | 6 | 8 | +8 | medium |  |
| `S021` | Q9 | 12 | 4 | 2 | 2 | -10 | medium |  |
| `S002` | Q7 | 10 | 11 | 13 | 15 | +5 | medium |  |
| `S002` | Q8 | 10 | 1 | 3 | 10 | +0 | high |  |
| `S002` | Q9 | 25 | 22 | 15 | 14 | -11 | medium |  |
| `S015` | Q7 | 10 | 10 | 13 | 13 | +3 | high |  |
| `S015` | Q8 | 10 | 0 | 3 | 0 | -10 | high |  |
| `S015` | Q9 | 25 | 14 | 17 | 17 | -8 | medium | `unclear_region` |
| `S020` | Q7 | 18 | 15 | 14 | 5 | -13 | medium | `needs_manual_review` |
| `S020` | Q8 | 10 | 4 | 1 | 0 | -10 | medium | `needs_manual_review` |
| `S020` | Q9 | 10 | 2 | 7 | 2 | -8 | medium |  |
| `S016` | Q7 | 0 | 0 | 0 | 0 | +0 | high |  |
| `S016` | Q8 | 8 | 6 | 10 | 10 | +2 | medium |  |
| `S016` | Q9 | 25 | 2 | 9 | 2 | -23 | medium |  |
| `S022` | Q7 | 10 | 5 | 2 | 5 | -5 | low | `incomplete_proof`, `missing_recognizer_to_enumerator`, `missing_nonmembership` |
| `S022` | Q8 | 10 | 6 | 8 | 6 | -4 | medium | `incorrect_base_case_epsilon`, `vague_loop_mechanism` |
| `S022` | Q9 | 25 | 13 | 10 | 13 | -12 | medium | `missing_absence_of_counterexamples` |

## Findings

### 1. Q9 Dominates The Remaining Error

Q9 has the largest C31-r2 question-level error:

- C31-r2 Q9 MAE: `11.714`
- C31-r2 Q9 exact agreement: `0.000`
- C31-r2 Q9 severe error rate: `1.000`
- C31-r2 Q9 signed error mean: `-11.714`

All seven development students are under-scored on Q9. This is the clearest
diagnostic signal.

Likely cause: rubric/prompt alignment mismatch with official grading. The
current rubric says full credit requires three requested evidence families:
equivalent computation models, TM variant robustness, and absence of
counterexamples. C31-r2 also says full credit requires every rubric-required
essential element. In practice, official scores appear more tolerant of broad
conceptual evidence than the current element-by-element rule. The new
open-ended adequacy rule does not override the strict full-credit requirement.

Risk: C31-r2 can systematically under-score conceptual essay answers when a
student gives broad but official-accepted evidence rather than the exact three
families encoded in `rubric_v1.json`.

### 2. Q8 Is Unstable In Both Directions

Q8 has large positive and negative errors:

- `S021`: C31-r2 over-scores by `+8`
- `S015`: C31-r2 under-scores by `-10`
- `S020`: C31-r2 under-scores by `-10`

Likely cause: the Q8 rubric does not clearly distinguish these cases:

- an enumerator that outputs an invalid extra string;
- an enumerator that generates linear even lengths instead of powers of two;
- an incomplete or vague loop that gestures at powers of two.

The official score distribution suggests that some of these distinctions matter
strongly, but the current prompt/rubric leaves the model room to treat them as
partial rather than decisive.

Risk: repeated reruns may move Q8 scores around without truly improving the
grading skill, because the scoring policy itself is under-specified.

### 3. Q7 Has One High-Impact Candidate Regression

Q7 is not uniformly worse, but it has a high-impact regression:

- `S020` drops from `R1=15` to `C31-r2=5`, while gold is `18`.

Likely cause: C31-r2 applies contradiction-locality and element-state scoring
more sharply when it sees an invalid nonmembership/rejection step. This may be
too punitive for the official grading style if the answer still demonstrates
most of the construction.

Risk: candidate-style proof scoring may over-penalize a local logical mistake
instead of preserving enough credit for the correct construction direction.

### 4. Total MAE Improvement Is Not Enough Evidence

C31-r2 improves total MAE from `20.143` to `18.429`, but Q7/Q8/Q9 show enough
item-level instability that this cannot be treated as an unambiguous skill
improvement.

Likely cause: total-score MAE can improve when over-scoring in one question
partly cancels under-scoring in another. The development evidence therefore
needs question-level diagnostics, not only total-score metrics.

## Recommended Next Step

Do not rerun the same C31-r2 packet immediately. The next useful step is a
small **candidate-v3.2 / rubric-v2 calibration** focused only on the diagnosed
failure modes:

1. Q9: make conceptual-essay grading match official-style evidence more closely.
   The rubric should allow broad valid evidence for the Church-Turing thesis
   without requiring exact membership in the three current evidence families
   when the official score would treat the answer as adequate.
2. Q8: add explicit policy for invalid extra outputs, `2n` versus `2^n`, and
   vague loop mechanisms.
3. Q7: preserve construction credit when a local nonmembership mistake is
   present, unless the mistake invalidates the whole proof direction.

After that calibration, build a fresh packet and run only the development split
again before any held-out test.

## Limitations

- Gold scores contain official per-question scores but not official rationales.
- The diagnosis uses model rationales and anonymous scores; it does not prove
  the official reason for any score.
- Because this is development data, these findings are calibration guidance,
  not final accuracy evidence.
