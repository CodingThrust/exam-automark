---
name: run-submit-grading-benchmark
description: Configure an advisor's machine, prepare matched private grading packets, run reproducible Kimi Code and Claude Code development-then-test benchmarks in both frozen transcript-first and direct-multimodal modes, validate and summarize successes or failures, and submit only privacy-safe aggregate results through draft GitHub pull requests. Use for the AI Grading Test Handoff, repeated external benchmark runs, environment setup, sealed test execution, model/input-mode comparisons, or requests to return experiment results by PR.
---

# Run and Submit a Grading Benchmark

Own the handoff from first preflight through the pull-request URL. Do not hand
the user a long command list and stop. Inspect what is already available, ask
only for decisions or authority that cannot be discovered, perform the allowed
work, and report progress at environment, packet, run, validation, package, and
submission milestones.

The repository helper is the stable entry point:

```text
python scripts/advisor_experiment.py <command>
```

Read [decision-table.md](references/decision-table.md) before choosing an input
route or handling a failed gate. Read
[config-contract.md](references/config-contract.md) before editing a generated
configuration.

## Non-negotiable defaults

- Run the development split before the sealed test split. A normal complete
  campaign has eight matched development arms and eight matched test arms; do
  not call the campaign complete after only the eight development students.
- Treat `kimi` and `claude` as required engines unless the user explicitly
  narrows the experiment.
- Treat `text-only` and `multimodal` as separate required arms. Never silently
  substitute one for the other.
- Text-only means a frozen transcript-first packet with recorded provenance;
  label it `automatic-transcript` or `human-reviewed-transcript` from the
  manifest. Multimodal means direct grading from human-approved anonymized page
  images.
- Keep packets, prompts, images, transcripts, raw responses, CLI logs,
  per-student outputs, credentials, and local state under ignored `Data/` or
  `local/`.
- Submit aggregate metrics, run metadata, validation counts, and aggregated
  technical failure types only.
- A failed experiment is still an experiment result: package the failure cause
  and submit it instead of reporting only that nothing was produced.
- Never inspect test errors, change the frozen workflow based on test results,
  or run test without explicit user approval after the matched development
  arms pass. Treat test as one-shot acceptance evidence.

## 1. Locate the repository and establish scope

From the repository root, inspect:

```text
git status --short --branch
git remote -v
python --version
python scripts/advisor_experiment.py --help
```

Preserve unrelated local changes. Never add `Data/`, `.private-data/`,
`HANDOFF.md`, credentials, or files outside the generated experiment record.
If the user supplied configs, use them. Otherwise create separate private
development and test configs for one campaign:

```text
python scripts/advisor_experiment.py init --preset physics-week9 --split development --experiment-id <campaign>-development --output local/advisor-development.json
python scripts/advisor_experiment.py init --preset physics-week9 --split test --experiment-id <campaign>-test --output local/advisor-test.json
```

The preset generates matched Kimi/Claude × text/multimodal ×
baseline/candidate arms for the selected split. The development config uses all
eight frozen development students; the test config uses all 18 frozen test
students. Inspect the generated configs and adapt model aliases or packet paths
only when local evidence requires it.

## 2. Proactively configure the environment

Run:

```text
python scripts/advisor_experiment.py doctor --config local/advisor-development.json
python scripts/advisor_experiment.py doctor --config local/advisor-test.json
```

Explain each blocking check in plain language. For anything missing:

1. Detect the operating system, available package manager, existing CLI, Git
   remote, and PR authentication method.
2. Ask once for approval before installing software, changing login state, or
   restoring private data.
3. After approval, perform the setup and rerun `doctor`; do not merely paste
   installation instructions.
4. Use the advisor's own Kimi Code and Claude Code login. Kimi Code membership
   is not a Moonshot Platform API key; do not request `MOONSHOT_API_KEY` for
   this workflow.
5. Prefer an authenticated GitHub CLI for automatic push and PR creation. An
   environment-only `GITHUB_TOKEN` may be used for the PR API only when the
   Git remote can already push through a credential helper or SSH. Never write,
   echo, or inject a token into Git command arguments.
6. If `Data/` is missing, follow the repository's private-data handoff using
   the advisor's account. Confirm that `Data/` and `.private-data/` are ignored
   before continuing.

Before sending student data, ask permission because model probes may consume
subscription quota. After approval, run:

```text
python scripts/advisor_experiment.py probe --config local/advisor-development.json --approve-model-probes
python scripts/advisor_experiment.py probe --config local/advisor-test.json --approve-model-probes
```

The real run is blocked until every configured engine/model has a passing
zero-data receipt for the current commit. Never include a student answer in a
login or capability probe.

## 3. Freeze the decision and packet plan

Run:

```text
python scripts/advisor_experiment.py plan --config local/advisor-development.json
python scripts/advisor_experiment.py plan --config local/advisor-test.json
```

Verify that every required engine has both modes and both conditions, and that
paired comparisons use identical anonymous students, split, rubric target, and
run commit. State the decision to the user:

- both routes ready: run both;
- only one route ready: run the ready route only if useful, mark the other
  `blocked`, and do not call the experiment complete;
- frozen automatic transcripts with complete provenance: run them as the
  transcript-first arm, label them automatic, and keep OCR errors separate from
  grading errors;
- missing transcript provenance: block the text arm rather than calling it
  reviewed;
- raw or unapproved images: do not use them for the multimodal arm;
- a material packet mismatch: stop and repair the plan before model calls.

## 4. Prepare missing multimodal packets

Run:

```text
python scripts/advisor_experiment.py prepare --config local/advisor-development.json
```

The helper derives student IDs, course, prompt, rubric, condition, and split
from the frozen transcript packet, checks every selected image against the
privacy review, builds the matched image packet, and audits packet isolation. Do not
hand-copy student files or infer approval from filenames.

Use `--dry-run` first when packet selection changed. If an immutable packet
already exists and matches, reuse it. If it differs, create a new packet ID or
output root; never overwrite benchmark evidence.

## 5. Run and validate

First smoke-test packet IO without model calls:

```text
python scripts/advisor_experiment.py run --config local/advisor-development.json --dry-run
```

Use a fresh experiment ID or output root for the real run because outputs are
immutable. Then run:

```text
python scripts/advisor_experiment.py run --config local/advisor-development.json
```

The helper runs every independent arm through `scripts/run_headless_packet.py`,
checks `validation.json`, resumes only already-passed arms whose packet, engine,
model, mode, and run commit still match, and calculates configured paired
metrics. One failed arm must not prevent the other engine from producing
evidence. Never delete or overwrite a failed run. For a
retry, copy the config, give the run and output a new `-rN` identity, and retain
the failed attempt.

After each engine/mode milestone, report `students_passed/students_expected`.
Classify failures as environment/authentication, CLI/runtime, packet/input,
output-JSON/schema, quota/timeout, or scoring/accuracy. Do not mislabel a
technical failure as an accuracy result.

After all eight development arms pass, freeze the code, prompts, models,
packets, retry policy, and timeout policy. If the original request explicitly
authorized both development and test, that is sufficient approval; otherwise
ask once at this boundary. Then prepare and run the 18-student test split:

```text
python scripts/advisor_experiment.py prepare --config local/advisor-test.json
python scripts/advisor_experiment.py run --config local/advisor-test.json --dry-run --approve-heldout
python scripts/advisor_experiment.py run --config local/advisor-test.json --approve-heldout
```

Do not revise the candidate from test-set findings and rerun against the same
test set. Report development and test metrics separately.

## 6. Package every outcome

Run:

```text
python scripts/advisor_experiment.py package --config local/advisor-development.json
python scripts/advisor_experiment.py package --config local/advisor-test.json
```

The generated record under `experiments/records/` must answer:

- what ran and what did not;
- what changed relative to baseline;
- whether each arm validated;
- aggregate metrics and confidence calibration when available;
- aggregated technical failure types and the actual gate that failed;
- what the result improves for this project;
- limitations and the next concrete recommendation.

Inspect the generated `summary.json` and `RUN-REPORT.md`. Do not add manual
per-student examples to the PR. Case-level Sxxx/Qx diagnosis stays in the
private analysis workflow unless a separately approved anonymized aggregate
artifact is produced.

## 7. Submit a focused draft GitHub PR

Preview the safety gate:

```text
python scripts/advisor_experiment.py submit --config local/advisor-development.json --dry-run
python scripts/advisor_experiment.py submit --config local/advisor-test.json --dry-run
```

Then submit:

```text
python scripts/advisor_experiment.py submit --config local/advisor-development.json
git switch main
python scripts/advisor_experiment.py submit --config local/advisor-test.json
```

The helper must:

- reject staged or tracked private data;
- allow only JSON and Markdown inside the configured experiment record;
- scan for anonymous student IDs and common secret patterns;
- create or reuse only the configured `advisor-results/...` branch;
- stage only the configured record directory;
- commit, push, and open a draft PR with `gh`; an environment-only GitHub token
  may create the PR only after separately authenticated Git transport pushes
  the branch.

If the current agent exposes a trusted GitHub connector with PR creation, it
may create the PR after the same privacy checks and push. Otherwise configure
`gh` rather than falling back to a private chat. A compare URL is an emergency
fallback, not successful completion.

Leave both result PRs as drafts until YY reviews the aggregate records. Finish
with the development and test PR URLs, branches, commits, split-specific
student counts and metrics, completed arms, blocked or failed arms, and the
single most important next action.
