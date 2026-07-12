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

## DeepSeek Input Boundary

DeepSeek must not be treated as a direct image-grading provider for this run.
The official DeepSeek Chat Completion API documents text `content` fields for
chat messages and lists text chat model IDs such as `deepseek-v4-flash` and
`deepseek-v4-pro`. It does not define the image-content interface needed to
grade the current `.jpg` packet inputs directly.

Local packet inspection on 2026-07-12 found that the current `G1-dev-r1` and
`T1-dev-r1` packet inputs are `.jpg` files. Therefore:

- do not send existing `G1-*` image packets directly to DeepSeek;
- run DeepSeek only on text-only grading packets;
- record the text source before grading;
- record the text-source hash before grading;
- treat any unverified legacy transcript as pilot/provisional evidence only.

The preferred final route is:

```text
image packet -> recorded transcription/OCR step -> text-only grading packet -> DeepSeek grading -> metrics
```

Text-source options:

| Option | Use | Status | Required record |
| --- | --- | --- | --- |
| vision model transcription | final multimodal-to-text route | preferred | model/provider, command or UI protocol, prompt, output hash |
| existing `Data/physics/benchmark/transcripts/automatic/T1-*` | provisional DeepSeek dry run | allowed only if labeled pilot-derived | source path, transcript hash, original run provenance |
| local OCR tool | OCR baseline only | not enough for final math-handwriting claims by itself | tool name, version, command, output hash |
| human-reviewed transcript | text upper-bound or adjudication route | valid if reviewer and review protocol are recorded | reviewer protocol, CSV/hash, review date |

If no text source can be verified, stop before calling DeepSeek.

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
| input_mode | `text_only`; image input is blocked for DeepSeek |
| text_source | transcript/OCR/human-review source path and hash |
| command_line | exact command used, with secret values redacted |
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

For DeepSeek, these image packets are source packets, not directly executable
grading packets. A text-only grading packet must be built or selected before
the DeepSeek call.

## Command-Line Recording

Every DeepSeek call must record the exact command line before execution. The
command record must not contain the API key value; it may contain the environment
variable name `DEEPSEEK_API_KEY`.

The first development-run command plan is recorded in:

- `experiments/records/physics-week9-baseline-candidate-v2-run/DEEPSEEK-DEV-RUN-COMMANDS.md`

Each run directory must include:

- `command.txt`: exact shell command, with secret values redacted;
- `command.argv.json`: parsed argv list if a CLI wrapper is used;
- `run-metadata.json`: provider, model, parameters, packet hash, prompt hash,
  text-source hash, git commit, and software snapshot path.

Planned packet-based CLI shape:

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1 \
  --temperature 0 \
  --response-format json_object
```

This command shape is a required implementation target before real DeepSeek
model calls. If the actual CLI differs, record the actual command and update
this protocol before running the held-out split.

## Execution Order

1. Confirm the worktree is clean.
2. Run branch readiness and packet audits.
3. Capture a fresh software environment snapshot at the exact run commit.
4. Verify the text source for DeepSeek grading and record its hash.
5. Build or select text-only baseline and candidate grading packets.
6. Record the exact DeepSeek command line for the baseline development run.
7. Run baseline text-only `G1-dev-r1` with DeepSeek.
8. Record the exact DeepSeek command line for the candidate development run.
9. Run candidate v2 text-only `G1-dev-r1` with DeepSeek.
10. Validate output JSON for both development grading packets.
11. If both development grading packets are valid, repeat the same command-recording and validation process for the held-out split.
12. Compute metrics against human gold scores.
13. Write the Typst/PDF report.

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
- DeepSeek is asked to grade image-only packet inputs directly
- the DeepSeek command line is not recorded before execution
- the text-source path and hash are not recorded
- output JSON cannot be validated
- API quota, network, or provider errors affect only one arm of the comparison
- private student content would need to be committed to Git
