# Candidate-v3.1 Calibration Note

Status: **development calibration; no held-out evidence**

Candidate-v3.1 is a minimal follow-up to the DSAA3071 Week 5 development
diagnosis in `../DSAA3071-week5-candidate-v3-dev-plan/CANDIDATE-V3-R3-DIAGNOSIS.md`.
It is not a new conclusion about accuracy. It creates a new model-facing prompt
and skill snapshot so that the next DeepSeek run can test whether the following
calibrations help on the development split.

## What Changed From Candidate-v3

Candidate-v3.1 keeps the candidate-v3 evidence-first structure, integer scoring,
schema-compatible string evidence fields, second-pass review, question-type
rules, no duplicate credit, and the independent calculation rule.

It adds four grading rules:

- **cap-locality:** apply a material-error cap only when the cap condition is directly visible and active.
- **contradiction-locality:** preserve unrelated element credit when a flaw is
  local to one proof direction, construction step, or rubric element.
- **key-term semantics:** key terms are evidence signals, not mandatory wording
  unless the frozen rubric explicitly requires terminology.
- **indirect-construction:** score valid indirect constructions by mapping
  visible steps to rubric elements and required output behavior.

## Evaluation Scope

This record only prepares another development run. If candidate-v3.1 improves
development metrics, it should still be treated as calibrated on the dev split.
No held-out claim is allowed until a separate held-out packet and report are
approved and run.
