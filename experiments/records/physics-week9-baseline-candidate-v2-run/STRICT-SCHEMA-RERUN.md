# Strict Schema Rerun Plan

Status: strict-schema baseline and candidate development runs passed validation.

Captured date: 2026-07-13, Asia/Shanghai.

## Reason

The strict-confidence baseline rerun passed 7/8 students but failed validation
for `S019` because `total` did not equal the sum of itemized question scores.

The previous failed attempts are retained:

- `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-failed-validation`
- `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-confidence-failed-validation`

## Strict Schema Prompt Sources

Tracked prompt sources:

- baseline:
  `experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_standard_v1_strict_schema.txt`
- candidate v2:
  `experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_candidate_v2_strict_schema.txt`

Both prompts explicitly require:

- `confidence` must be exactly `"high"`, `"medium"`, or `"low"`
- `total` must equal the arithmetic sum of all itemized `score` fields exactly

## Next Steps

1. Record development metrics in the Typst/PDF note.
2. Decide whether to freeze candidate v2 based on development results.
3. Do not run held-out test packets until the workflow is frozen.

## Strict Schema Packet Outputs

These packet directories are local-only under ignored `Data/`:

| Condition | Packet path | Prompt hash | Packet hash |
| --- | --- | --- | --- |
| baseline | `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1` | `8fe0b9bb69d56109b2bbecfcdd6ca05ebe2ae9dff76efe610ecfde0d831cfa5e` | `e556b8f12cc32e975c6a27545efeddb2891cb85fa6d3060f57dec3d6abf92601` |
| candidate v2 | `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1` | `1eb905236e6f4e4623399e4dc5cd77b80c69fa7a5ea3a2d6a2777f2dcc902c3f` | `8987ce06f54a46ba242703df0d028ffb8de56143a00a312b289e1f39fc7aed6d` |

Both packets use the same text source hash:

`30e45836b26f6c05d0a55c2e436d5ace7078d01ae86932c3c64b27ad14e24cf8`

## Dry-Run Validation

| Run | Output path | Status |
| --- | --- | --- |
| baseline strict-schema dry-run | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-schema-dry-run` | passed, 8/8 |
| candidate strict-schema dry-run | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-strict-schema-dry-run` | passed, 8/8 |

## Next Real Run Order

Run only the strict-schema baseline first:

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-schema \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1
```

If and only if the strict-schema baseline validation passes 8/8, run the
strict-schema candidate:

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-strict-schema \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1
```

## Real Development Run Status

Both strict-schema development runs were executed by the project user and passed
validation:

| Run | Output path | Status |
| --- | --- | --- |
| baseline strict-schema | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-schema` | passed, 8/8 |
| candidate strict-schema | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-strict-schema` | passed, 8/8 |

The development metrics are recorded in `DEV-METRICS-STRICT-SCHEMA.md`.
