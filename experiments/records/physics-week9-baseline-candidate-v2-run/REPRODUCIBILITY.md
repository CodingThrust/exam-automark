# Physics Week 9 Reproducibility Note

Status: pre-model-call protocol note. No model outputs are recorded by this
file.

This note defines how another reviewer can reproduce the planned Physics Week 9
baseline vs candidate v2 experiment from the same code, private data snapshot,
prompt packets, and model-facing prompts.

## Version Anchors

- Public tool repository: `CodingThrust/exam-automark`
- Experiment branch: `codex/physics-week9-baseline-candidate-v2-run`
- Plan anchor commit recorded in both branch plans: `36e7201`
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

## Known Limits Before Model Runs

- No baseline or candidate v2 model calls have been made yet.
- The private data snapshot must be available to the reviewer.
- DeepSeek is selected as the first provider because a teacher-provided private
  API key is available, but the exact model ID, SDK version, and generation
  parameters must still be recorded at run time.
- The current software snapshot is Windows-specific. macOS/Linux reviewers
  should record their own software snapshots before running models.
- Physics Week 9 remains a pilot-derived benchmark and should not be treated as
  a final multi-course conclusion.
