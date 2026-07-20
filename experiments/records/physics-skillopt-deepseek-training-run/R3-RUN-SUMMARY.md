# SkillOpt DeepSeek R3 Run Summary

Date: 2026-07-20

## Run Identity

- Run name: `physics-week9-deepseek-skillopt-r3-compact-utf8`
- Environment: `physics_grading`
- Optimizer model: `deepseek-v4-pro`
- Target model: `deepseek-v4-pro`
- Optimizer backend: `openai_compatible`
- Target backend: `openai_compatible`
- Epochs: 1
- Batch size: 4
- Workers: 1
- Seed: 42
- Output directory:
  `Data/physics/benchmark/skillopt/physics-week9-deepseek-training-r1/outputs/physics-week9-deepseek-skillopt-r3-compact-utf8`

## Final Console Result

```text
steps=1 accept=0 reject=1 skip=0
best_score=0.0000 (step 0)
wall=2542s
baseline test_hard=0.1111
best-on-val test_hard=0.0000 test_soft=0.0000
final/last test_hard=0.0000 test_soft=0.0000
total tokens=476,749
exit=0
```

## Structured Summary

From `summary.json`:

- baseline selection hard: 0.0000
- best selection hard: 0.0000
- final selection hard: 0.0000
- step count: 1
- accepts: 0
- rejects: 1
- skips: 0
- best step: 0
- best origin: `initial_skill`
- baseline test hard: 0.1111
- best test hard: 0.0000
- final test hard: 0.0000
- test delta hard: -0.1111
- wall time: 2541.9 seconds

Token usage:

| Stage | Calls | Prompt Tokens | Completion Tokens | Total Tokens |
|---|---:|---:|---:|---:|
| rollout | 48 | 230,559 | 193,575 | 424,134 |
| analyst | 2 | 41,903 | 5,556 | 47,459 |
| merge | 1 | 1,198 | 2,271 | 3,469 |
| ranking | 1 | 845 | 842 | 1,687 |
| total | 52 | 274,505 | 202,244 | 476,749 |

## Step 1 Details

From `steps/step_0001/step_record.json`:

- rollout hard: 0.5000
- rollout soft: 0.5000
- rollout items: 4
- failure patches: 1
- success patches: 1
- merged edits: 3
- ranked edits: 2
- edit apply: 2 applied, 0 skipped, 0 errors
- candidate selection hard: 0.0000
- candidate selection soft: 0.0000
- action: reject
- candidate hash: `22083a6c01e990ab`

The candidate skill appended rules about strict JSON output, tolerance handling,
and independent per-criterion scoring. These edits are plausible, but the
selection gate rejected the candidate because it did not improve the validation
score.

## Output Reliability Diagnostics

Aggregated from per-item `result.json` files:

| Phase | Items | Hard Rate | Main Failure Pattern |
|---|---:|---:|---|
| selection baseline | 4 | 0.0000 | 4 JSON parse errors |
| train rollout | 4 | 0.5000 | 2 OK, 2 JSON parse errors |
| candidate selection | 4 | 0.0000 | 4 JSON parse errors |
| baseline test | 18 | 0.1111 | 2 OK, 16 JSON parse errors |
| best-on-val test | 18 | 0.0000 | 18 JSON parse errors |
| final test | 18 | 0.0000 | 18 JSON parse errors |

Several failed target responses were empty or truncated even under compact
score-only JSON. Therefore this run should be interpreted as a completed
negative/diagnostic SkillOpt run, not as evidence that SkillOpt improved the
grading skill.

## Conclusion

This run satisfies the engineering milestone of running the SkillOpt loop
end-to-end with DeepSeek on the physics split. It does not satisfy the scientific
goal of showing improved score accuracy.

The current blocker is target-output reliability under the DeepSeek
OpenAI-compatible backend inside SkillOpt. The next iteration should first reduce
target failure rate before claiming skill optimization results.

## Recommended Next Iteration

1. Add a strict local JSON repair/retry pass for empty, truncated, or malformed
   target responses.
2. Consider scoring one physics subquestion group at a time instead of all 12
   subquestions in one target call.
3. Re-run only after target parse success is high on the validation split.
4. Keep the held-out/test result from this run as diagnostic only; do not present
   it as a valid model-improvement conclusion.
