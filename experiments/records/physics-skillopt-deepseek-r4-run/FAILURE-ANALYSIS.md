# Physics SkillOpt DeepSeek R4 Failure Analysis

Date: 2026-07-25

## Direct answer

The R4 candidate was rejected because its validation score was worse than the
initial skill:

| Validation metric | Initial skill | Candidate | Change |
| --- | ---: | ---: | ---: |
| Hard exact-student accuracy | 1 / 4 (0.2500) | 0 / 4 (0.0000) | -0.2500 |
| Soft exact-subquestion accuracy | 38 / 48 (0.7917) | 23 / 48 (0.4792) | -0.3125 |

The configured gate metric was `hard`. SkillOpt accepts a candidate only when
its gate score is strictly greater than the current score. The candidate scored
`0.0000`, below the current `0.2500`, so the gate kept the initial skill.

This was the correct accept/reject decision for the observed run. Changing the
gate to `soft` would not have saved this candidate because its soft score also
decreased.

## What the candidate changed

The candidate appended one global rule:

> When a rubric criterion awards points for a specific step, award that point
> only if the step is explicitly shown. Do not infer the step from a correct
> final answer alone.

The rule was generated from two non-exact training cases and was recorded with
`support_count = 2`.

The problem is that the two training errors had opposite directions:

| Anonymous training case | Gold | Initial prediction | Error direction |
| --- | ---: | ---: | --- |
| Hemispherical-spreading calculation | 3 | 2 | under-scored by 1 |
| Large-particle path reasoning | 2 | 3 | over-scored by 1 |

The first answer showed the correct area relation and final value. Its gold
label awarded full credit even though the compact transcript did not explicitly
show every conversion step. The second answer named the correct path and said
gravity increases faster, but did not state the rubric's required
`R^3`-versus-`R^2` comparison.

The optimizer's failure summary treated both cases as the same
"missing explicit step but points were awarded" error. That diagnosis fits the
over-scored case, but it does not fit the under-scored case. A stricter global
rule cannot correct both directions.

## What was bad about the candidate

### 1. Its evidence aggregation lost the error direction

The optimizer grouped an under-score and an over-score under one cause, then
reported two supporting cases for a one-directional edit. `support_count = 2`
therefore overstated the real support for the edit.

The candidate-generation stage needs to preserve at least:

- predicted minus gold score;
- rubric criterion affected;
- whether the error was an over-score or under-score;
- whether missing evidence came from the student or from transcription.

Edits should not merge cases whose required corrections point in opposite
directions.

### 2. It over-generalized one local correction

The new rule was absolute and applied to every rubric criterion. It conflicted
with the seed skill's more balanced policy:

- award full credit when the final answer is correct and the visible method is
  broadly consistent, unless the rubric explicitly requires a missing step;
- award result credit but not omitted setup credit for unsupported answers.

The candidate removed that distinction. In the paired, parseable validation
cases, it changed four question scores; every change reduced a score and every
change increased error:

| Paired validation evidence | Initial skill | Candidate |
| --- | ---: | ---: |
| Exact subquestion scores | 26 / 36 | 23 / 36 |
| Total absolute score error | 8.50 | 11.75 |
| Changed question scores | - | 4, all reductions |

This pattern is consistent with systematic over-penalization. Because the
initial and candidate results came from separate model calls, it is not a clean
causal estimate of the appended sentence by itself; repeated paired calls would
be required for that claim. It is nevertheless direct evidence that the
candidate did not generalize on this validation run.

### 3. Output reliability was improved, not solved

R4 produced 48 item-level result records. Forty-seven contained parseable
predictions. One candidate-validation call consumed the full 12,000 completion
tokens and returned an empty response, which was scored as:

- hard: `0`;
- soft: `0`;
- total absolute error sentinel: `999`.

That failed item was the only exact student under the initial validation run,
so it also made the hard score fall from `0.25` to `0.00`. This is partly a
technical reliability failure, separate from the candidate's scoring policy.

Even after excluding that failed item and comparing only the three cases with
predictions on both sides, the candidate was still worse: exact subquestions
fell from 26 to 23 and absolute error rose from 8.50 to 11.75.

### 4. The validation design was too coarse and too noisy

Hard accuracy requires all 12 question scores for one student to match exactly.
With four validation students, the score moves only in increments of `0.25`.
This is too coarse for detecting small grading improvements.

The baseline and candidate were each evaluated once. The target sampling
temperature was not pinned in the recorded run configuration, and no repeated
paired evaluation was used. The experiment therefore mixed skill effects with
run-to-run target-model variation.

## Why the held-out hard score also decreased

The candidate was rejected and never became the current or best skill. Both
the baseline held-out evaluation and the final held-out evaluation used the
same initial skill, with identical system and user prompts for all 18 held-out
items.

Despite identical prompts:

- only 9 / 18 complete score vectors were identical across the two calls;
- 14 / 216 individual question predictions changed;
- hard exact-student accuracy changed from 5 / 18 to 4 / 18;
- soft exact-subquestion accuracy changed from 181 / 216 to 182 / 216;
- total absolute score error improved from 37.75 to 35.25.

Therefore the reported held-out hard delta of `-0.0556` is not a candidate-skill
effect. It is a repeat-evaluation difference for the same initial skill. It
also demonstrates why one hard metric alone is not a stable optimization
signal here.

## Root-cause classification

| Layer | Observed cause | Evidence strength |
| --- | --- | --- |
| Candidate generation | Opposite-direction errors were merged into one stricter edit | Direct artifact evidence |
| Grading policy | The edit over-generalized "explicit step" and lost balanced process/result credit | Direct rule comparison; validation pattern supports it |
| Data/transcription | Compact transcripts can omit or corrupt evidence that affected human gold scoring | Observed in development records; exact contribution not isolated |
| Target reliability | One empty 12,000-token candidate validation output | Direct artifact evidence |
| Metric design | Four-student hard gate changes in 0.25 increments | Deterministic metric property |
| Evaluation design | Single independent calls did not isolate candidate effects | Direct protocol evidence |

## What R4 did improve

R4 was still useful as an engineering result:

- it completed the full SkillOpt loop;
- 47 / 48 target records were parseable, a large reliability improvement over
  R3;
- the validation gate prevented a harmful candidate from becoming the selected
  skill;
- it exposed concrete weaknesses in error aggregation, metric choice, and
  repeatability.

It did not improve grading accuracy and must not be reported as doing so.

## Improvement options

### Option A: close R4 as a negative result

Record the lessons above, do not rerun the same configuration, and move effort
to the higher-priority mainline grading and multimodal comparison work.

- Benefit: no further model cost; scientifically honest.
- Cost: does not produce a positive SkillOpt result.
- Risk: leaves the optimization pipeline weaknesses unresolved.

### Option B: repair the measurement and candidate gates before R5

Recommended if SkillOpt remains a required project direction.

Implement these offline checks before another paid run:

1. preserve error direction and rubric criterion in reflection inputs;
2. reject a proposed edit when its supporting cases require opposite changes;
3. add a policy-conflict lint against the seed skill;
4. use paired repeated validation calls and report mean plus variation;
5. gate primarily on soft subquestion accuracy, with hard accuracy and total
   absolute error as guardrails;
6. make parse failure a separate reliability gate and retry/repair it before
   accuracy scoring;
7. require more than one supporting example per direction before making a
   global rule.

- Benefit: directly addresses every observed R4 failure layer.
- Cost: moderate engineering and additional evaluation calls.
- Risk: the four-student validation set may remain too small.

### Option C: run a narrow criterion-level proof of concept

Choose one or two high-disagreement rubric criteria, construct a larger
development set at that criterion level, and optimize only the corresponding
decision rule before returning to whole-paper grading.

- Benefit: cheaper, denser feedback and a more attainable SkillOpt signal.
- Cost: result applies only to the selected criteria.
- Risk: a positive result may not generalize to full-paper grading.

## Recommendation

Do not rerun R4 unchanged. Close it as a negative result now. If a positive
SkillOpt experiment is still required, combine Option B's safeguards with
Option C's narrow scope, and keep the sealed held-out set out of candidate
selection.

## Evidence

Public records:

- `RESULT-SUMMARY.md`
- `RUN-PROTOCOL.md`
- `../physics-skillopt-deepseek-training-run/R3-RUN-SUMMARY.md`
- `../physics-skillopt-target-reliability/RESULT-SUMMARY.md`

Private, ignored run artifacts used for this analysis:

- `summary.json`
- `history.json`
- `steps/step_0001/step_record.json`
- `steps/step_0001/trajectory_digest.json`
- `steps/step_0001/merged_patch.json`
- paired item-level `result.json` files

No raw student transcript, student identifier, or provider response is included
in this public report.
