# Candidate-v3 r3 Development Diagnosis

Status: **development diagnosis; no held-out evidence**

This note diagnoses why `C3-dev-reviewed-r3` did not outperform `R1` on the
DSAA3071 week 5 development split. It uses only aggregate score differences
from anonymous development outputs and official per-question scores. It does
not include student answer text or PDF content.

## Summary

`R1` is the best development condition so far. Candidate-v3 r3 improves over
`B0`, but it does not improve over `R1`.

| Comparison | Question MAE delta | Total MAE delta | Exact agreement delta |
| --- | ---: | ---: | ---: |
| `R1_minus_B0` | -0.729 | -7.286 | 0.014 |
| `C3_minus_R1` | 0.200 | 0.000 | -0.014 |
| `C3_minus_B0` | -0.529 | -7.286 | 0.000 |

Negative MAE deltas are improvements. The development result says that
`rubric_v1` helps, while candidate-v3 r3 needs more calibration.

## Where C3 Loses to R1

| Question | C3 better | Equal | C3 worse | R1 MAE | C3 MAE | Pattern |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Q5 | 1 | 4 | 2 | 4.857 | 5.857 | C3 sometimes applies a material-error cap too aggressively. |
| Q6 | 4 | 0 | 3 | 1.714 | 1.857 | Mixed; C3 is not consistently worse. |
| Q7 | 0 | 1 | 6 | 2.429 | 4.429 | C3 over-penalizes local proof flaws and loses construction credit. |
| Q8 | 4 | 2 | 1 | 5.714 | 4.857 | C3 helps overall but still misses some indirect constructions. |
| Q9 | 3 | 0 | 4 | 9.714 | 9.714 | Mean tie; C3 is stricter about named evidence in some cases. |
| Q10 | 1 | 5 | 1 | 1.714 | 1.429 | C3 is slightly better overall. |

## Failure Modes

1. **Material-error caps are too eager.**
   Candidate-v3 r3 can treat a partially specified method as a central material
   error even when the answer still demonstrates several essential elements.
   This hurts Q5 most.

2. **Local contradictions can erase too much credit.**
   In proof-style answers, candidate-v3 r3 sometimes lets a local flaw in one
   direction reduce credit for otherwise visible construction evidence. This
   hurts Q7 most.

3. **Key terms can be treated as mandatory wording.**
   Candidate-v3 r3 sometimes demands named examples or exact terminology even
   when the rubric allows semantic equivalents. This is visible in Q9.

4. **Indirect valid constructions need more careful mapping.**
   For algorithm/construction answers, candidate-v3 r3 should not dismiss an
   indirect route merely because it is not the standard direct construction.
   It should map visible steps to the nearest scoring elements and withhold full
   credit only when the required output behavior is not demonstrated.

## Candidate-v3.1 Calibration Target

The next candidate should keep the evidence-first structure, calculation rule,
integer scoring, schema-compatible evidence strings, and no-duplicate-credit
rule. The minimal calibration should add:

- a cap-locality rule: apply material-error caps only when the cap condition is
  directly visible and active, not merely because an element is partial;
- a contradiction-locality rule: preserve unrelated element credit when a local
  misconception affects only one element or proof direction;
- a key-term semantics rule: key terms are accepted evidence signals, not
  mandatory wording unless the rubric explicitly requires terminology;
- an indirect-construction rule: score valid indirect constructions by mapping
  visible steps to rubric elements, while still requiring the frozen rubric's
  full-credit conditions.

No held-out run should be started until candidate-v3.1 passes packet readiness
and is explicitly approved for another development run.
