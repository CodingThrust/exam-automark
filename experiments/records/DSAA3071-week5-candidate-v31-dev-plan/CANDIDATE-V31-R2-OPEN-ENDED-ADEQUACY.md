# Candidate-v3.1 r2 Open-Ended Adequacy Note

Status: **development calibration; no held-out evidence**

Candidate-v3.1 r2 is a small prompt and skill calibration created before any
candidate-v3.1 model run was accepted as evidence. It preserves the r1 packet
for reproducibility and creates a new `C3-dev-reviewed-v31-r2` packet.

## Rationale

The DSAA3071 Week 5 development results showed large disagreements on open-ended
questions, especially Q8 and Q9. Candidate-v3.1 r1 already accepted semantic
equivalents, but that rule can still treat the standard answer as a near
whitelist. For open-ended questions, a student's valid response may satisfy the
task without being an equivalent paraphrase of the listed expected answer.

## Added Rule

Candidate-v3.1 r2 adds **open-ended adequacy**:

- for open-ended short-answer, proof, construction, and essay questions, score
  whether the answer satisfies the task requirement;
- use the standard answer as an anchor, not as an exhaustive whitelist;
- award credit for valid, relevant, non-contradictory approaches, examples, or
  constructions that answer the prompt, even when they are not listed in the
  expected answer or semantic equivalents;
- continue to withhold credit for answers that are off-task, contradictory, or
  incompatible with the frozen rubric.

This change is intended to reduce over-penalization on open-ended items while
keeping the evidence-first, integer-score, no-duplicate-credit, cap-locality,
contradiction-locality, key-term semantics, indirect-construction, and
calculation rules.

No final accuracy claim should be made until r2 is run and compared against the
existing B0/R1 controls. No held-out claim is allowed from this development
record.
