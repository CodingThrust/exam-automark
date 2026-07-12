# Strict Confidence Rerun Plan

Status: strict-confidence packets built and dry-run validated. Real rerun not
executed by Codex.

Captured date: 2026-07-12, Asia/Shanghai.

## Reason

The first real baseline development run failed validation because DeepSeek
returned numeric confidence values such as `0.95` and `1.0`. The output schema
requires string confidence values only:

- `"high"`
- `"medium"`
- `"low"`

The first attempt is recorded in `BASELINE-DEV-ATTEMPT-1.md` and must be
retained as a failed real run attempt. Its retained local directory is
`Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-failed-validation`.

## Strict Prompt Sources

Tracked prompt sources:

- baseline:
  `experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_standard_v1_strict_confidence.txt`
- candidate v2:
  `experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_candidate_v2_strict_confidence.txt`

Both prompts add the same output-format constraint:

> The `confidence` field must be exactly one of the strings `"high"`,
> `"medium"`, or `"low"`. Do not use numeric confidence values such as `0.95`,
> `0.9`, or `1.0`.

## Strict Packet Outputs

These packet directories are local-only under ignored `Data/`:

| Condition | Packet path | Prompt hash | Packet hash |
| --- | --- | --- | --- |
| baseline | `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-confidence/G1-dev-r1` | `6a929e425e46438bec24120a080a585036cfa539e814081317b9f5a0a250dc2d` | `c158968bbe90bafafd909ba4a04bb841c8aea1d1bf9e3154b23a98315c47649a` |
| candidate v2 | `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-confidence/G1-dev-r1` | `25afb01c5043bf9854c9cf98b9f092c6ae63ec1fefab057379563abd41f309fc` | `0f031998bc49a00751f0e18d81731db7cbae85e2b18a15b1d7e2b616ab05fb62` |

Both packets use the same text source hash:

`30e45836b26f6c05d0a55c2e436d5ace7078d01ae86932c3c64b27ad14e24cf8`

## Dry-Run Validation

| Run | Output path | Status |
| --- | --- | --- |
| baseline strict-confidence dry-run | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-confidence-dry-run` | passed, 8/8 |
| candidate strict-confidence dry-run | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-strict-confidence-dry-run` | passed, 8/8 |

## Next Real Run Order

Run only the strict-confidence baseline first:

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-confidence/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-confidence \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1
```

If and only if the strict-confidence baseline validation passes 8/8, run the
strict-confidence candidate:

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-confidence/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-strict-confidence \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1
```

Do not delete or overwrite the first failed baseline run. Do not run held-out
test packets at this stage.
