# Zulip Settlement: TODO1 Meaningful Negative Results

```text
Topic: [exam-automark] TODO1 - meaningful negative-result retrospective

Status:
completed

Goal:
Explain why completed grading experiments did not improve their intended
accuracy signal. Exclude ordinary command, authentication, dependency, path,
and transient network errors.

What was done:
- Audited SkillOpt R4 and the DSAA3071 candidate-v3, v3.1-r2, and v3.2
  development sequence.
- Recomputed question-level, severe-error, total-score, and error-cancellation
  metrics from the private run outputs.
- Separated verified metric drivers from behavioral hypotheses and unresolved
  causes.

Evidence:
- experiments/records/physics-skillopt-deepseek-r4-run/FAILURE-ANALYSIS.md
- experiments/records/weekly-todo-integration-2026-07/TODO1-MEANINGFUL-NEGATIVE-RESULTS.md
- experiments/records/weekly-todo-integration-2026-07/TODO1-MEANINGFUL-NEGATIVE-RESULTS.json

Key result:
SkillOpt R4 generated an over-strict candidate from incorrectly merged
opposite-direction errors, so validation accuracy worsened and the gate
rejected it.

DSAA3071 candidate-v3 also worsened question-level accuracy versus R1.
Candidate-v3.1-r2 appeared better on student total MAE only because question
over-scores and under-scores cancelled more strongly.

Candidate-v3.2 is a small real question-level improvement, but only 4 of its 40
reduced total-error points came from lower question-level absolute error. The
other 36 points, or 90%, came from additional within-student cancellation.
C32 also added one severe-error pair, with Q6 contributing 19 additional
absolute-error points.

Failure causes:
- SkillOpt lost error direction while aggregating candidate evidence.
- Candidate-v3 over-applied proof-locality, cap, and wording requirements.
- Candidate-v3.1's total metric hid compensating item-level errors.
- Candidate-v3.2's global rules over-credited Q6 and did not solve Q8
  consistently.
- Joint rubric/prompt/skill changes and single runs prevent clean causal
  attribution.

What improved:
- We now distinguish true item-level improvement from total-score error
  cancellation.
- Negative-result selection excludes meaningless operational incidents.
- Candidate acceptance requirements now include a severe-error guardrail and a
  cancellation diagnostic.

How this helps the project:
It prevents a candidate from being accepted because aggregate totals look
better while individual question grading becomes less reliable. It also gives
candidate-v3.3 a focused Q6/Q8 target instead of another broad rewrite.

Limitations / prohibited claims:
- C32 has development evidence only and is not a final or held-out improvement.
- Official per-question rationales are unavailable.
- Behavioral explanations are diagnostic hypotheses, not verified human
  scoring rationales.
- One run per condition does not isolate model variation.

Decision:
Close C3 and C31-r2 as informative negative/mixed results. Keep C32 as a
development candidate only. Do not freeze it or run held-out until a controlled
Q6/Q8 audit and repeated matched development comparison pass.

Next action:
Start TODO3's latest-model defect audit on selected Q6/Q8/Q9 development cases,
then propose candidate-v3.3 changes with one-factor ablations and a
non-increasing severe-error gate.
```
