# Physics SkillOpt DeepSeek R4 Result Summary

## Result

R4 completed as an engineering run, but it did not satisfy the SkillOpt
improvement criterion.

The run tested whether the negative R3 result was mainly caused by target output
truncation. R4 raised the target completion budget to 12,000 tokens and the
target timeout to 240 seconds while keeping the Physics Week 9 train,
validation, and held-out test split unchanged.

## Safe Aggregate Metrics

Source file, ignored locally:
`Data/physics/benchmark/skillopt/physics-week9-deepseek-training-r1/outputs/physics-week9-deepseek-skillopt-r4-target-budget/summary.json`

- Run date: 2026-07-21 local time.
- Optimizer model: `deepseek-v4-pro`.
- Target model: `deepseek-v4-pro`.
- Backend: `openai_compatible`.
- Steps: 1.
- Accepted edits: 0.
- Rejected edits: 1.
- Skipped edits: 0.
- Best skill origin: `initial_skill`.
- Final skill origin: `initial_skill`.
- Baseline selection hard score: 0.2500.
- Best/final selection hard score: 0.2500.
- Baseline held-out test hard score: 0.2778.
- Final held-out test hard score: 0.2222.
- Held-out hard-score delta: -0.0556.
- Baseline held-out test soft score: 0.8380.
- Final held-out test soft score: 0.8426.
- Total wall time: 4,220.9 seconds, about 70.3 minutes.
- Total model calls: 50.
- Total tokens: 616,435.

Local sanity check:

- `result.json` files found: 48.
- Parseable prediction records found: 47.
- Candidate-validation JSON failures found: 1. The failed call consumed the
  full 12,000 completion-token budget and returned an empty response.

This means R4 largely, but not completely, addressed the R3 engineering blocker
around invalid or truncated target JSON outputs. The candidate skill also made
the paired parseable validation results worse, so SkillOpt rejected it. The
final reported skill remained the initial skill lineage.

The baseline and final held-out evaluations both used that same initial skill.
Their hard-score difference is therefore run-to-run target-model variation, not
the effect of the rejected candidate. See `FAILURE-ANALYSIS.md` for the
candidate edit, paired validation evidence, and exact gate explanation.

## Interpretation

R4 should be recorded as a negative SkillOpt result, not as an improvement.

The higher target budget made the run more reliable, but reliability alone did
not produce a better grading skill. On this small Physics Week 9 split, one
epoch with four train items and four validation items appears too weak or too
noisy to demonstrate the advisor-requested outcome: "On physics dataset, show
improvement in score accuracy."

The held-out soft score increased slightly, from 0.8380 to 0.8426, while the
hard score decreased from 0.2778 to 0.2222. Because both evaluations used the
same initial skill, neither change demonstrates a SkillOpt improvement.

## Next Options

Recommended next step: stop expanding this R4 line and report the negative
result honestly. If the advisor still requires a positive SkillOpt result, the
next controlled attempt should change the optimization target rather than only
raise token limits.

Reasonable follow-up designs:

- Use a simpler target skill with fewer grading fields so SkillOpt edits have a
  clearer effect.
- Optimize only one or two high-disagreement physics questions before scaling to
  the full paper.
- Increase train/validation examples if more gold labels are available.
- Add a deterministic repair-and-retry wrapper before passing target outputs to
  SkillOpt scoring.
- Use a model with stronger instruction-following as the optimizer while
  keeping DeepSeek as the target grader, if budget and reproducibility allow it.

For the weekly TODO integration, this result should be described as:

> SkillOpt was integrated and run on the Physics Week 9 dataset with DeepSeek.
> The R4 run completed reliably after increasing target output budget, but it
> did not improve held-out hard score accuracy. More controlled optimization
> design is needed before claiming SkillOpt improves the grading skill.
