# Physics Week 9 Codex Headless Dev Attempt 1

Status: CLI argument failure before model-output validation. This is not an accuracy result.

## Scope

This attempt used the Physics Week 9 development text-only grading packets:

| Condition | Packet | Output |
| --- | --- | --- |
| baseline | `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1` | `Data/physics/benchmark/runs/physics-week9-codex-headless/codex-baseline-text-G1-dev-r1` |
| candidate-v2 | `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1` | `Data/physics/benchmark/runs/physics-week9-codex-headless/codex-candidate-text-G1-dev-r1` |

Both packets used:

- provider: `codex_cli`
- engine: `codex`
- model: `gpt-5.5`
- Codex CLI version: `codex-cli 0.133.0`
- run commit: `b413772`
- split: development
- expected students: 8

## Observed Result

Both arms failed 0/8:

```text
baseline validation_status=failed, students_passed=0/8
candidate validation_status=failed, students_passed=0/8
```

Every student failed after three attempts with:

```text
RuntimeError: codex headless command failed with exit 2
```

The first stderr log showed:

```text
error: unexpected argument '--ask-for-approval' found
```

## Root Cause

The first runner version generated a Codex child command containing
`--ask-for-approval never`. The current installed Codex CLI accepts the
headless `exec` command, but this local `codex exec` invocation rejected that
argument with exit 2 before any valid grading JSON could be produced.

This failure therefore measures a runner/CLI compatibility bug, not the quality
of Codex grading and not the baseline-vs-candidate-v2 scoring accuracy.

## Fix Direction

The runner should remove `--ask-for-approval never` from the generated Codex
child command and keep the safer bounded execution shape:

```text
codex.cmd exec --json --output-last-message <last-message-file>
  --output-schema <packet>/output.schema.json
  --sandbox read-only
  --cd <packet>
  --model gpt-5.5 -
```

The existing failed local output directories should be kept as failed-attempt
evidence. A rerun must use new output directories, for example:

- `codex-baseline-text-G1-dev-r1-argfix`
- `codex-candidate-text-G1-dev-r1-argfix`

## Privacy

No raw student transcript, model response body, prompt body, or output JSON is
tracked in this record. The failed run directories remain under ignored `Data/`.
