# TODO1 Meaningful Negative-Result Retrospective

Date: 2026-07-25

## Technical summary

TODO1 should not catalogue every failed command. It should explain completed
experiments whose result changes a project decision.

Two experiment lines meet that standard:

1. Physics SkillOpt R4 produced a candidate, but the candidate made validation
   accuracy worse and was correctly rejected.
2. DSAA3071 candidate-v3 and candidate-v3.1 produced valid outputs, but their
   apparent gains were absent or driven by question-level errors cancelling in
   the student total. Candidate-v3.2 is a small real aggregate improvement, but
   its large total-score gain is still 90% error cancellation and it increases
   the severe-error count.

Ordinary command, authentication, dependency, path, and transient network
errors are excluded. They belong in runbooks, not an experiment retrospective.

## Which results belong in TODO1

| Result | Include? | Reason |
| --- | --- | --- |
| SkillOpt R4 candidate rejection | Yes | Completed optimization result; candidate accuracy worsened |
| DSAA3071 C3 versus R1 | Yes | Completed controlled development comparison; candidate worsened |
| DSAA3071 C31-r2 versus R1 | Yes | Total-score improvement hid worse question-level accuracy |
| DSAA3071 C32 versus R1 | As remediation with unresolved tradeoffs | Small aggregate improvement, but severe errors and cancellation remain |
| One-off CLI, auth, path, dependency, provider, or network errors | No | Operational incident, not evidence about grading quality |
| Physics candidate-v2 | No negative-result entry | Held-out results improved; unchanged severe-error rate belongs in the error-taxonomy TODO |
| Kimi/Claude advisor results | Not yet | Real external results have not returned |
| Autoresearch MVP | Not yet | The real loop is incomplete, so there is no completed negative experiment to explain |

## Candidate-v3 worsened the metric it was meant to improve

The authoritative comparison is seven DSAA3071 development students and ten
questions per student, for 70 student-question score pairs.

| Metric | R1 baseline | C3 candidate-v3 | C3 minus R1 |
| --- | ---: | ---: | ---: |
| Question MAE | 2.614 | 2.814 | +0.200 worse |
| Exact score pairs | 36 / 70 | 35 / 70 | -1 |
| Severe-error pairs | 15 / 70 | 17 / 70 | +2 worse |
| Item-level absolute error points | 183 | 197 | +14 worse |
| Student-total absolute error points | 141 | 141 | unchanged |

Question-level decomposition explains the net 14-point regression:

| Question | C3 minus R1 absolute-error points | Interpretation |
| --- | ---: | --- |
| Q5 | +7 | Worse |
| Q6 | +1 | Slightly worse |
| Q7 | +14 | Largest regression |
| Q8 | -6 | Improvement |
| Q9 | 0 | No aggregate change |
| Q10 | -2 | Improvement |

Q7 alone adds 14 absolute error points. Improvements on Q8 and Q10 offset the
additional errors on Q5 and Q6, leaving the same 14-point net regression.

The existing case review supports, but does not prove, three behavioral
explanations:

- candidate-v3 sometimes let a local proof flaw erase credit for an otherwise
  valid construction direction;
- material-error caps were triggered too broadly;
- required evidence labels could be treated as mandatory wording instead of
  accepting a valid semantic equivalent.

These are diagnostic hypotheses because the gold data contains official scores
but not official scoring rationales.

## Candidate-v3.1's total-score gain was error cancellation

C31-r2 looked better if only student total-score MAE was inspected:

| Metric | R1 baseline | C31-r2 | Change |
| --- | ---: | ---: | ---: |
| Question MAE | 2.614 | 2.929 | +0.314 worse |
| Exact score pairs | 36 / 70 | 37 / 70 | +1 |
| Severe-error pairs | 15 / 70 | 18 / 70 | +3 worse |
| Item-level absolute error points | 183 | 205 | +22 worse |
| Student-total absolute error points | 141 | 129 | -12 better |
| Within-student cancellation gap | 42 | 76 | +34 |

The identity is:

```text
student-total absolute error
= item-level absolute error - within-student cancellation
```

C31-r2 added 22 points of question-level error but added 34 points of
over-score/under-score cancellation. The resulting 12-point total-score
"improvement" is therefore not evidence of better per-question grading.

The main observed drivers were Q7 proof-credit instability and systematic Q9
under-scoring. The open-ended adequacy rule did not overcome the strict
element-by-element full-credit requirement.

## Candidate-v3.2 improved only slightly at question level

C32 is not a failed experiment. It is the first candidate in this development
sequence to reduce both question MAE and total-score MAE versus R1. However, the
size and source of those two improvements are very different:

| Metric | R1 baseline | C32 | Change |
| --- | ---: | ---: | ---: |
| Question MAE | 2.614 | 2.557 | -0.057 better |
| Exact score pairs | 36 / 70 | 37 / 70 | +1 |
| Severe-error pairs | 15 / 70 | 16 / 70 | +1 worse |
| Item-level absolute error points | 183 | 179 | -4 better |
| Student-total absolute error points | 141 | 101 | -40 better |
| Within-student cancellation gap | 42 | 78 | +36 |

Only 4 of the 40 reduced student-total error points come from lower
question-level absolute error. The other 36 points, or 90%, come from additional
within-student cancellation.

This does not erase the 4-point question-level improvement. It means total-score
MAE substantially overstates the strength of the improvement.

## Q6 offsets most of C32's gains

Negative values below are improvements; positive values are regressions.

| Question | C32 minus R1 absolute-error points | Severe-error pair change |
| --- | ---: | ---: |
| Q5 | -15 | -2 |
| Q6 | +19 | +2 |
| Q7 | 0 | 0 |
| Q8 | -1 | +1 |
| Q9 | -5 | 0 |
| Q10 | -2 | 0 |

The largest improvement is Q5, whose rubric did not change between v1 and v2.
The largest regression is Q6, whose rubric also did not change. The targeted
rubric changes were Q7-Q9.

Therefore the observed Q5/Q6 movement cannot be attributed to the targeted
Q7-Q9 rubric calibration. It can come from the global candidate prompt/skill,
the changed top-level grading policy, target-model variation, or a combination
of those factors.

The paired case review gives three useful examples without exposing student
identity:

- Q6 official score `8`: R1 scored `9`, while C32 scored `20` after inferring
  that tree, BFS, and an acceptance state demonstrated every essential
  simulation element.
- Q8 official score `9`: R1 scored `8`, while C32 applied the invalid-extra-
  output cap and reduced the score to `5`.
- Q9 official score `25`: R1 scored `22`, while C32 scored `12` because the
  valid evidence was considered too brief, despite the intended
  official-style-adequacy rule.

These cases show that the global rules are not applied consistently enough to
freeze C32 as the final skill.

## Scope, source, and metric validation

- Population: seven anonymous DSAA3071 Week 5 development students.
- Grain: 70 student-question pairs and seven student totals.
- Gold source: official per-question scores.
- Compared conditions: R1, C3, C31-r2, and C32.
- Fresh recomputation from the ignored local outputs reproduced the committed
  R1, C3, C31-r2, and C32 metrics exactly to six decimal places.
- C32 changes rubric, prompt, and skill together; it is a package comparison,
  not a single-factor ablation.
- Rubric v2 changes Q7, Q8, Q9 and the top-level grading policy. Q5, Q6, and Q10
  question rubrics are unchanged.

## What is verified, likely, and unresolved

### Verified

- C3 worsened question MAE, exact agreement, and severe-error rate versus R1.
- C31-r2's total-score improvement was caused by additional cancellation while
  question-level error worsened.
- C32 made a small four-point question-level improvement, added one severe
  error, and obtained 90% of its total-score improvement from cancellation.
- Q6 contributed 19 additional absolute-error points under C32.

### Likely but not causally proven

- Candidate-v3's proof and cap rules were too aggressive for the observed
  official scoring style.
- C32's global open-ended-adequacy and semantic-equivalence rules encouraged
  over-credit on Q6 by treating related terms as demonstrated relations.
- The Q8 invalid-output cap is too blunt for some official-scored answers.

### Unresolved

- Official per-question rationales are unavailable, so the exact human reason
  for each score cannot be confirmed.
- Each condition was run once and the recorded temperature is `null`; target
  variation was not measured.
- C32 has no held-out evidence.

## Project changes recommended before candidate-v3.3

1. Make question-level MAE and exact agreement the primary acceptance metrics.
   Treat total-score MAE as a guardrail, not the main objective.
2. Add a cancellation diagnostic to every grading comparison:
   item-level absolute error, student-total absolute error, and their gap.
3. Require severe-error count not to increase before accepting a candidate.
4. Isolate rubric, prompt, and skill changes in separate development arms before
   testing a combined package.
5. For Q6, distinguish a term being mentioned from a required relation being
   demonstrated. Do not infer branch addressing or accept-if-any behavior from
   tree/BFS wording alone.
6. For Q8, calibrate invalid-output deductions against reviewed official cases
   instead of applying a broad cap from one textual signal.
7. Run the latest model as a defect critic on the largest Q6/Q8/Q9 disagreements
   before editing the next candidate.
8. Repeat the matched development comparison before held-out testing so
   run-to-run variation is measured.

## Decision

Close candidate-v3 and C31-r2 as informative negative/mixed results. Keep C32
as a development candidate, not a frozen final skill. The next useful action is
a controlled Q6/Q8 defect audit and candidate-v3.3 design, not another broad
prompt rewrite.

## Further questions

- Can official rationales or instructor review be obtained for the selected
  Q6/Q8/Q9 disagreements?
- Does C32's four-point item-level improvement survive a repeated matched run?
- Which individual rule causes the Q6 over-credit: semantic equivalence,
  open-ended adequacy, official-style adequacy, or model variation?
