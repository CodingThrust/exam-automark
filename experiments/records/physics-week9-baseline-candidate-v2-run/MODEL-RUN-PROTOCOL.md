# Physics Week 9 Model Run Protocol

Status: planned. No model calls are recorded by this file.

This protocol defines the first real model run for the Physics Week 9
baseline-vs-candidate-v2 experiment. The first run should test whether the
candidate grading skill improves grading accuracy under one fixed model
provider. It should not be used as a cross-model comparison.

## Research Question

Does `skill_candidate_v2` produce scores closer to the human gold scores than
`skill_baseline_v1` on the same Physics Week 9 data snapshot, using the same
model provider, model version, student inputs, output schema, and generation
parameters?

The held-out test split is the decision split. The development split can be used
to find execution defects, schema failures, and obvious prompt-packet issues,
but it must not be used as the final evidence for replacing the baseline.

## Comparison Design

Hold constant:

- course: `physics`
- assessment: `week9`
- data snapshot:
  `e0b47a06a3ec12417a70a773ac8d5728ebbbd40c8991ac7ec7a11c2a92d2a6f3`
- model provider and model name
- model parameters
- student IDs and input hashes
- output schema
- rubric hash for grade packets
- transcription prompt for transcribe packets

Change only:

- grading skill version
- grade prompt template

The primary comparison is therefore:

```text
baseline grading prompt/skill vs candidate v2 grading prompt/skill
```

under one fixed DeepSeek model configuration.

## Provider Plan

The first provider should be DeepSeek because the project already has access to
a teacher-provided DeepSeek API key. OpenAI API access is not required for this
run.

Record these provider fields before any model call:

| Field | Required value |
| --- | --- |
| provider | `deepseek` |
| api_key_source | `teacher_provided_private_key` |
| endpoint | `https://api.deepseek.com` unless the teacher provides another endpoint |
| model | exact model ID used by the API call |
| temperature | exact value used |
| top_p | exact value used, or `not_set` |
| max_tokens | exact value used, or `not_set` |
| response_format | JSON object or provider equivalent |
| retry_policy | maximum retries and repair prompt policy |
| run_commit | exact `git rev-parse HEAD` |
| software_snapshot | path to the software environment record captured at run time |

Do not commit API keys, `.env` files, request headers, or raw credentials.

## Packets

Use these packet roots under ignored `Data/`:

| Plan | Packet | Task | Split | Students |
| --- | --- | --- | --- | --- |
| baseline | `T1-dev-r1` | transcribe | development | 8 |
| baseline | `T1-test-r1` | transcribe | heldout | 18 |
| baseline | `G1-dev-r1` | grade | development | 8 |
| baseline | `G1-test-r1` | grade | heldout | 18 |
| candidate v2 | `T1-dev-r1` | transcribe | development | 8 |
| candidate v2 | `T1-test-r1` | transcribe | heldout | 18 |
| candidate v2 | `G1-dev-r1` | grade | development | 8 |
| candidate v2 | `G1-test-r1` | grade | heldout | 18 |

Baseline root:

```text
Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/
```

Candidate v2 root:

```text
Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/
```

Each packet must be executed from its packet root using only files inside that
root. The model-facing prompt is always `prompt.txt`.

## Execution Order

1. Confirm the worktree is clean.
2. Run branch readiness and packet audits.
3. Capture a fresh software environment snapshot at the exact run commit.
4. Run baseline `G1-dev-r1`.
5. Run candidate v2 `G1-dev-r1`.
6. Validate output JSON for both development grading packets.
7. If both development grading packets are valid, run baseline `G1-test-r1`.
8. Run candidate v2 `G1-test-r1`.
9. Compute metrics against human gold scores.
10. Write the Typst/PDF report.

Transcription packets are part of the full multimodal-vs-text benchmark, but
the first grading-skill decision can start from grading packets if their inputs
already contain the frozen text or multimodal material required by the packet.
If transcription outputs are used as grading inputs, record the exact
transcription run IDs and hashes before grading.

## Output Contract

For each run, create a run directory under:

```text
Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/
```

Suggested run directory names:

```text
deepseek-baseline-G1-dev-r1
deepseek-candidate-G1-dev-r1
deepseek-baseline-G1-test-r1
deepseek-candidate-G1-test-r1
```

Each run directory should contain:

- `run-metadata.json`
- `raw-responses.jsonl`
- one validated JSON output per student, or a documented equivalent
- `validation.json`
- `failures.jsonl` if any student output fails
- `usage.json` if the provider returns token usage

The public Git repository should only receive reduced, privacy-safe artifacts:
metrics, tables, charts, report files, and metadata that do not expose private
student work or credentials.

## Metrics

Compute metrics separately for development and held-out splits:

- total-score MAE
- subquestion MAE
- exact agreement rate
- within-1-point rate
- severe error rate
- mean signed error
- overgrade count and rate
- undergrade count and rate
- invalid-output count and rate
- per-question MAE and agreement

Primary decision metric:

```text
held-out total-score MAE
```

Secondary checks:

```text
held-out exact agreement
held-out within-1-point agreement
held-out severe overgrade count
held-out invalid-output rate
per-question regressions
```

## Decision Rule

Prefer candidate v2 only if the held-out grading run shows:

- lower total-score MAE than baseline,
- no increase in invalid-output rate,
- no material increase in severe overgrading,
- no obvious per-question regression that would be unacceptable for teaching
  use.

If candidate v2 improves full-credit recognition but increases overgrading on
partially correct answers, do not replace the baseline yet. Record the failure
mode and revise the grading skill in a new branch.

## Conclusion Template

Use this structure after the held-out metrics are available:

```text
On the held-out Physics Week 9 test split, candidate v2 changed total-score MAE
from BASELINE_MAE to CANDIDATE_MAE, exact agreement from BASELINE_EXACT to
CANDIDATE_EXACT, and severe overgrading cases from BASELINE_SEVERE_OVERGRADE to
CANDIDATE_SEVERE_OVERGRADE.

Because RESULT_SUMMARY, candidate v2 SHOULD_OR_SHOULD_NOT replace the baseline
for the next grading-skill iteration.
```

## Stop Conditions

Stop before or during model execution if:

- readiness is not `ready`
- a packet audit fails
- the worktree is dirty before model calls
- the model-facing prompt or rubric is changed after readiness
- the provider model ID is unknown
- generation parameters are not recorded
- output JSON cannot be validated
- API quota, network, or provider errors affect only one arm of the comparison
- private student content would need to be committed to Git

