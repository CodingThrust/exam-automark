# Physics SkillOpt Target Preflight Result

## Run

- Run timestamp: 2026-07-20T14:17:14Z
- Provider: DeepSeek public API
- Model: `deepseek-v4-pro`
- Split: `val`
- Items: 4 validation students
- Private output directory:
  `Data/physics/benchmark/skillopt/physics-week9-deepseek-training-r1/preflight/deepseek-target-val-r1`
- Git privacy policy: do not commit raw responses, per-student outputs, or the
  raw `summary.json` from `Data/`.

## Aggregate Result

| Metric | Value |
| --- | ---: |
| JSON/readiness status | `ready` |
| Items passed schema/parse scoring | 4 / 4 |
| Failed reason counts | `{}` |
| Hard exact-student match rate | 0.000000 |
| Soft exact-subquestion match average | 0.708333 |
| Exact subquestion matches | 34 / 48 |
| Total absolute score error | 11.5 |
| Mean absolute score error per student | 2.875 |
| Mean absolute score error per subquestion | 0.239583 |
| Total tokens | 53,081 |

## Interpretation

The preflight passed its primary reliability gate: all target calls returned
parseable compact JSON, every item could be scored, and there were no parse or
schema failure reasons. This means the earlier SkillOpt failure mode of
unusable target JSON is not reproduced under this compact preflight prompt.

The accuracy signal is still weak. `hard_rate = 0.0` means none of the four
validation students matched the gold scores exactly across all 12 subquestions.
This is a very strict metric, so the more informative number here is
`soft_avg = 0.708333`: 34 of 48 subquestion scores matched exactly.

## Decision

This result is good enough to proceed to a small next SkillOpt attempt, but not
good enough to claim any improvement. The next attempt should keep the run small
and use the compact target prompt path, then compare the resulting skill against
the same validation/test metrics.

If a future target preflight is repeated, require:

- `status == "ready"`
- `items_passed == items_expected`
- `reason_counts == {}`

Then inspect accuracy separately instead of treating parse readiness as a score
accuracy conclusion.
