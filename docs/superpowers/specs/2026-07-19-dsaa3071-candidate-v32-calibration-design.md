# DSAA3071 Candidate-v3.2 Calibration Design

## Goal

Create a small development-only calibration for DSAA3071 Week 5 after the
C31-r2 error diagnosis. The goal is not to make a final held-out claim. The
goal is to prepare a better candidate grading skill and rubric packet for a
repeatable development rerun.

## Scope

This calibration is limited to the diagnosed Q7/Q8/Q9 failure modes:

- Q7 proof scoring: preserve construction credit when a local nonmembership or
  rejection mistake is present, unless it invalidates a required proof
  direction.
- Q8 enumerator scoring: separate correct power-of-two language generation from
  invalid extra outputs, `2n` versus `2^n`, vague loop mechanisms, and base-case
  issues.
- Q9 conceptual essay scoring: align more closely with official-style grading
  by accepting broad valid evidence for the Church-Turing thesis, not only the
  three currently encoded evidence families.

No held-out run, report rendering, or multi-course expansion is included in
this design.

## Calibration Principle

Candidate-v3.2 must explicitly avoid being overly harsh. This does not mean
inflating scores or ignoring errors. It means:

- grade for official-style adequacy, not ideal-answer completeness;
- do not treat the reference answer as a rigid checklist when the student's
  answer gives a valid, relevant, non-contradictory alternative;
- preserve partial credit for demonstrated understanding even when terminology,
  ordering, or detail is imperfect;
- distinguish missing ideal detail from a visible misconception;
- apply large deductions only for material errors, contradictions, wrong
  language/output behavior, or missing required answer behavior.

This principle should be model-facing in English so it is reproducible across
DeepSeek, Codex headless, Claude headless, or other future model runners.

## Assets To Add

1. `rubric_v2.json`
   - Source: copy from `rubric_v1.json`.
   - Change only Q7/Q8/Q9.
   - Keep integer score steps and total points unchanged.
   - Keep the rubric model-facing and English.

2. Candidate-v3.2 prompt template
   - Source: copy from candidate-v3.1.
   - Add an official-style tolerance rule.
   - Add targeted rules for conceptual essay, enumerator/construction, and
     proof-locality.
   - Keep existing safeguards: evidence-first, no duplicate credit,
     cap-locality, contradiction-locality, integer scores, strict JSON schema,
     calculation logic for physics-style questions.

3. Candidate-v3.2 skill snapshot
   - Preserve v3.1 as historical evidence.
   - Create a new snapshot so future runs know exactly which grading skill was
     used.

4. Development packet and run record
   - Build a new C32 development packet only.
   - Record prompt hash, rubric hash, skill hash, packet hash, command lines,
     and no-model-call readiness.
   - Do not run the model as part of the packet preparation step.

## Expected Output

The implementation should produce:

- a tracked `rubric_v2.json`;
- a tracked candidate-v3.2 prompt template and strict-schema model-facing copy;
- a tracked candidate-v3.2 skill snapshot;
- a tracked experiment record directory update for the C32 dev packet;
- an ignored Data packet under the DSAA3071 Week 5 benchmark directory;
- PowerShell and macOS/Linux commands for running the C32 development packet.

## Validation

Before the branch is considered ready:

- tests for candidate-v3.2 assets must prove the official-style tolerance rule
  and targeted Q7/Q8/Q9 rules exist in model-facing assets;
- existing candidate-v3 and candidate-v3.1 tests must remain passing;
- the packet audit must pass;
- `git ls-files -- Data` must remain empty;
- no raw student answer text or identity information may be copied into tracked
  experiment records.

## Non-Goals

- Do not tune on held-out data.
- Do not claim final accuracy improvement from development results.
- Do not modify physics conclusions.
- Do not introduce quarter-point scoring.
- Do not upload or track `Data` in GitHub.
