# Physics Week 9 Reproducibility Note

Status: development model-run reproducibility note. Development outputs are
recorded in local ignored `Data/` artifacts and summarized in Git records.

This note defines how another reviewer can reproduce the planned Physics Week 9
baseline vs candidate v2 experiment from the same code, private data snapshot,
prompt packets, and model-facing prompts.

## Version Anchors

- Public tool repository: `CodingThrust/exam-automark`
- Experiment branch: `codex/physics-week9-baseline-candidate-v2-run`
- Plan anchor commit recorded in both branch plans: `af6a928`
- Data snapshot hash:
  `e0b47a06a3ec12417a70a773ac8d5728ebbbd40c8991ac7ec7a11c2a92d2a6f3`
- Branch readiness record:
  `experiments/records/physics-week9-baseline-candidate-v2-run/run-readiness.md`
- Local software snapshot:
  `experiments/records/physics-week9-baseline-candidate-v2-run/software-environment.md`

The local software snapshot is a machine-specific record. Windows paths such as
`C:\Tools\typst` document the current Windows workstation only. They are not
requirements for macOS or Linux reproduction.

Before a real model run, capture a fresh software snapshot at the exact model-run
commit and record `git rev-parse HEAD` in the run metadata.

## Data Placement

Raw or anonymized student data must stay outside the public Git repository.
Place the private data snapshot under the repository root as:

```text
Data/
```

The planned Physics Week 9 prompt packets must exist at:

```text
Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/
Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/
```

`Data/` is ignored by Git. The private HKUST-GZ GitLab repository should carry
the anonymized data and the prompt packets, or provide instructions to rebuild
the same packets from the public plans and templates.

## Prompt Packet Contract

Each packet is self-contained. The model or reviewer should work from the packet
root and use only files inside that packet:

```text
prompt.txt
INSTRUCTIONS.md
manifest.json
course.json
rubric.json
output.schema.json
inputs/
outputs/
```

The model-facing prompt text uses relative file names only. It does not require
Windows drive letters, backslash paths, or a specific operating system. This is
the main cross-platform contract: run the model from the packet root, and write
outputs under that packet's `outputs/` directory.

For grading packets, `rubric.json` is model-facing and must be English. For all
packets, `prompt.txt` and `INSTRUCTIONS.md` must be English.

## Planned Packets

Baseline packets:

| Packet | Task | Split | Packet root |
| --- | --- | --- | --- |
| `T1-dev-r1` | transcribe | development | `Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/T1-dev-r1` |
| `T1-test-r1` | transcribe | heldout | `Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/T1-test-r1` |
| `G1-dev-r1` | grade | development | `Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/G1-dev-r1` |
| `G1-test-r1` | grade | heldout | `Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/G1-test-r1` |

Candidate v2 packets:

| Packet | Task | Split | Packet root |
| --- | --- | --- | --- |
| `T1-dev-r1` | transcribe | development | `Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/T1-dev-r1` |
| `T1-test-r1` | transcribe | heldout | `Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/T1-test-r1` |
| `G1-dev-r1` | grade | development | `Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/G1-dev-r1` |
| `G1-test-r1` | grade | heldout | `Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/G1-test-r1` |

## Cross-Platform Readiness Check

Run from the repository root. The command uses forward-slash relative paths that
work on Windows, macOS, and Linux with Python's `pathlib`.

```bash
python -m benchmark.core.cli check-run-readiness \
  --baseline-plan experiments/records/physics-week9-baseline-candidate-v2-run/baseline-plan.json \
  --candidate-plan experiments/records/physics-week9-baseline-candidate-v2-run/candidate-v2-plan.json
```

The command must return:

```json
{"failed_checks": [], "markdown_output": null, "output": null, "status": "ready"}
```

If it is not `ready`, do not run models.

## macOS/Linux Reproduction Quickstart

These commands are written with POSIX shell syntax and forward-slash relative
paths. They are intended for macOS or Linux reviewers who already have access to
the private `Data/` snapshot.

1. Check out the experiment code.

```bash
git clone https://github.com/CodingThrust/exam-automark.git
cd exam-automark
git checkout codex/physics-week9-baseline-candidate-v2-run
git rev-parse HEAD
```

The held-out metrics in this record were produced from run commit:

```text
9cce18378abb19d817040cb56599457108d7d575
```

The latest record commit after metrics documentation is:

```text
d6bbdf14cc392cae018e176bc66540d1937764ed
```

2. Create a Python environment.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install openai==2.45.0
```

3. Place the private data snapshot.

The repository root should contain:

```text
Data/physics/benchmark/
```

At minimum, the reviewer needs the same anonymous transcripts, gold score CSVs,
text packets, and run outputs referenced by the records in this directory.

4. Run the readiness gate.

```bash
python -m benchmark.core.cli check-run-readiness \
  --baseline-plan experiments/records/physics-week9-baseline-candidate-v2-run/baseline-plan.json \
  --candidate-plan experiments/records/physics-week9-baseline-candidate-v2-run/candidate-v2-plan.json
```

Expected result:

```json
{"failed_checks": [], "markdown_output": null, "output": null, "status": "ready"}
```

5. Validate held-out packets without calling the provider.

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-test \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-test-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-test-r1-strict-schema-dry-run-local \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1 \
  --dry-run

python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-test \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-test-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-test-r1-strict-schema-dry-run-local \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1 \
  --dry-run
```

Both dry-runs should report `students_expected: 18`,
`students_passed: 18`, and `validation_status: passed`.

6. Re-run the real held-out model calls only if authorized.

Do not place the API key in a file or Git commit.

```bash
read -rsp "DeepSeek API key: " DEEPSEEK_API_KEY
echo
export DEEPSEEK_API_KEY

python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-test-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-test-r1-strict-schema \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1

python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-test-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-test-r1-strict-schema \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1

unset DEEPSEEK_API_KEY
```

7. Render the Typst note.

Install Typst with the platform package manager or the official binary, then run:

```bash
typst compile \
  experiments/records/physics-week9-baseline-candidate-v2-run/note.typ \
  experiments/records/physics-week9-baseline-candidate-v2-run/note.pdf
```

The metrics JSON/CSV artifacts are stored under ignored `Data/`. The current
metrics calculation used the project metric functions recorded in
`benchmark.physics.metrics`; a first-class CLI wrapper for metrics regeneration
is still future work.

## Packet Audit Commands

Run these from the repository root after the private `Data/` snapshot is in
place.

```bash
python -m benchmark.core.cli audit-packet --packet Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/T1-dev-r1
python -m benchmark.core.cli audit-packet --packet Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/T1-test-r1
python -m benchmark.core.cli audit-packet --packet Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/G1-dev-r1
python -m benchmark.core.cli audit-packet --packet Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/G1-test-r1
python -m benchmark.core.cli audit-packet --packet Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/T1-dev-r1
python -m benchmark.core.cli audit-packet --packet Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/T1-test-r1
python -m benchmark.core.cli audit-packet --packet Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/G1-dev-r1
python -m benchmark.core.cli audit-packet --packet Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/G1-test-r1
```

Each audit should report no findings.

## Model Execution Protocol

For each packet:

1. Set the working directory to the packet root.
2. Give the model `prompt.txt` as the task prompt.
3. Allow access only to the files inside the packet root.
4. Require one JSON output file per anonymous `student_id` under `outputs/`.
5. Validate each output against `output.schema.json`.
6. Record the provider, model name, model/API version, generation parameters,
   start time, end time, packet hash, prompt hash, and any retries.

For multimodal runs, the model may read PDFs or images directly if the provider
supports them. If another tool converts PDFs to images or text first, record the
conversion tool name, version, command, and output hash before grading.

For text-only runs, use the packet's provided text inputs or recorded
transcription outputs. Do not silently replace multimodal inputs with text
without recording the conversion path.

## Prompt Cross-Platform Audit

Local audit date: 2026-07-12.

Files checked in the eight dry-run packets:

- `prompt.txt`
- `INSTRUCTIONS.md`
- `manifest.json`
- `course.json`
- `rubric.json`
- `output.schema.json`

Audit result:

- no CJK characters were found in these model-facing packet control files
- no Windows drive-letter paths were found in these packet control files
- no UNC paths were found in these packet control files
- packet prompts refer to `manifest.json`, `course.json`, `rubric.json`,
  `inputs/`, and `outputs/` by relative names

Therefore the prompt packets are designed to be usable on macOS or Linux. The
remaining limitation is that this has not yet been validated by an actual
macOS/Linux model run.

## Development Run Status

The development split has been run with strict-schema text-only packets:

- baseline:
  `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-schema`
- candidate v2:
  `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-strict-schema`
- both runs validated 8/8 students
- metrics record:
  `experiments/records/physics-week9-baseline-candidate-v2-run/DEV-METRICS-STRICT-SCHEMA.md`

## Held-Out Run Status

The held-out split has been run with frozen strict-schema text-only packets:

- baseline:
  `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-test-r1-strict-schema`
- candidate v2:
  `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-test-r1-strict-schema`
- both runs validated 18/18 students
- metrics record:
  `experiments/records/physics-week9-baseline-candidate-v2-run/HELD-OUT-METRICS-STRICT-SCHEMA.md`

## Known Limits After Held-Out Runs

- The private data snapshot must be available to the reviewer.
- DeepSeek model ID, SDK version, generation parameters, prompt hashes, packet
  hashes, and usage are recorded in the strict-schema run metadata.
- The current software snapshot is Windows-specific. macOS/Linux reviewers
  should record their own software snapshots before running models.
- Held-out severe-error rate did not improve, so severe-error reduction remains
  unresolved.
- Physics Week 9 remains a pilot-derived benchmark and should not be treated as
  a final multi-course conclusion.
