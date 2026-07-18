# DSAA3071 Week 5 Development Model-Run Protocol

Status: **dev_metrics_recorded**

This record tracks the DSAA3071 week 5 development model-run stage after the
official per-question gold scores became ready. DeepSeek model calls were run
from local text-only transcript packets; raw outputs live under ignored `Data/`,
and safe metrics summaries live in this record directory.

## Anchors

- Branch: `codex/dsaa3071-week5-dev-model-runs`
- Base commit: `ff854ef`
- Course: `DSAA3071`
- Assessment: `week5_test`
- Development students: `S017`, `S021`, `S002`, `S015`, `S020`, `S016`, `S022`
- Official gold status: `ready`
- PDF packet readiness status: `packet-ready`
- Model-run status: `completed_dev_metrics_recorded`

## Current Blocker

The existing development grading packets use PDF inputs:

- Baseline: `Data/DSAA3071/week5-benchmark-redaction-v3/dry_run_packets/DSAA3071-week5-baseline-v1-lf/G1-dev-r1`
- Candidate v2: `Data/DSAA3071/week5-benchmark-redaction-v3/dry_run_packets/DSAA3071-week5-candidate-v2-lf/G1-dev-r1`

DeepSeek public API is treated as text-only in this repository, so it cannot run
these PDF grading packets directly. The next required source artifact is one
transcript JSON file per development student.

Expected transcript source:

`Data/DSAA3071/week5-benchmark-redaction-v3/transcripts/T1-dev-r1`

## Transcript Schema

Each transcript file may be either `<student_id>.json` or
`<student_id>/transcript.json`.

Each file must contain:

```json
{
  "student_id": "S017",
  "answers": [
    {
      "question_id": "Q1",
      "text": "visible student answer only",
      "unclear": false
    }
  ]
}
```

There must be exactly one answer for every question in
`experiments/course_specs/DSAA3071_week5_test.json`.

## Current Transcript Readiness

Tracked report:

`experiments/records/DSAA3071-week5-dev-model-run/transcript-readiness-dev.json`

Current status: `ready`

Missing transcripts: none

## Recheck Transcript Readiness

Windows PowerShell:

```powershell
python -m benchmark.core.cli validate-transcripts `
  --course experiments\course_specs\DSAA3071_week5_test.json `
  --transcript-source Data\DSAA3071\week5-benchmark-redaction-v3\transcripts\T1-dev-r1 `
  --students-file experiments\records\DSAA3071-week5-test-plan\students-development.txt `
  --output experiments\records\DSAA3071-week5-dev-model-run\transcript-readiness-dev.json
```

macOS/Linux:

```bash
python -m benchmark.core.cli validate-transcripts \
  --course experiments/course_specs/DSAA3071_week5_test.json \
  --transcript-source Data/DSAA3071/week5-benchmark-redaction-v3/transcripts/T1-dev-r1 \
  --students-file experiments/records/DSAA3071-week5-test-plan/students-development.txt \
  --output experiments/records/DSAA3071-week5-dev-model-run/transcript-readiness-dev.json
```

## Build Text-Only Grading Packets After Transcripts Are Ready

Baseline:

```powershell
python -m benchmark.core.cli build-text-grading-packet `
  --course experiments\course_specs\DSAA3071_week5_test.json `
  --packet-id G1-dev-r1 `
  --condition G1 `
  --prompt experiments\records\DSAA3071-week5-test-plan\prompts\grade_standard_v1_strict_schema.txt `
  --rubric experiments\records\DSAA3071-week5-prep\rubric_v0.json `
  --students-file experiments\records\DSAA3071-week5-test-plan\students-development.txt `
  --transcript-source Data\DSAA3071\week5-benchmark-redaction-v3\transcripts\T1-dev-r1 `
  --output-root Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-baseline-v1-dev-text `
  --text-source-kind transcript `
  --source-run-id T1-dev-r1 `
  --metadata experiment_id=DSAA3071-week5-dev-model-run `
  --metadata split=development `
  --metadata skill_version_id=skill_baseline_v1 `
  --metadata prompt_template_id=grade_standard_v1_strict_schema `
  --metadata data_snapshot_hash=cf87b373395e381d9d07bbd370c1faa772372b760557b0581dcf9e8a93c04c28
```

Candidate v2:

```powershell
python -m benchmark.core.cli build-text-grading-packet `
  --course experiments\course_specs\DSAA3071_week5_test.json `
  --packet-id G1-dev-r1 `
  --condition G1 `
  --prompt experiments\records\DSAA3071-week5-test-plan\prompts\grade_candidate_v2_strict_schema.txt `
  --rubric experiments\records\DSAA3071-week5-prep\rubric_v0.json `
  --students-file experiments\records\DSAA3071-week5-test-plan\students-development.txt `
  --transcript-source Data\DSAA3071\week5-benchmark-redaction-v3\transcripts\T1-dev-r1 `
  --output-root Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-candidate-v2-dev-text `
  --text-source-kind transcript `
  --source-run-id T1-dev-r1 `
  --metadata experiment_id=DSAA3071-week5-dev-model-run `
  --metadata split=development `
  --metadata skill_version_id=skill_candidate_v2 `
  --metadata prompt_template_id=grade_candidate_v2_strict_schema `
  --metadata data_snapshot_hash=cf87b373395e381d9d07bbd370c1faa772372b760557b0581dcf9e8a93c04c28
```

## DeepSeek Dev Run Commands After Text Packets Are Ready

Run from PowerShell after setting `DEEPSEEK_API_KEY` locally:

```powershell
$runCommit = git rev-parse --short HEAD

python -m benchmark.core.cli run-model-packet `
  --provider deepseek `
  --model deepseek-v4-pro `
  --input-mode text-only `
  --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-baseline-v1-dev-text\G1-dev-r1 `
  --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-baseline-text-G1-dev-r1 `
  --max-retries 2 `
  --run-commit $runCommit

python -m benchmark.core.cli run-model-packet `
  --provider deepseek `
  --model deepseek-v4-pro `
  --input-mode text-only `
  --packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-candidate-v2-dev-text\G1-dev-r1 `
  --output Data\DSAA3071\week5-benchmark-redaction-v3\runs\deepseek-candidate-text-G1-dev-r1 `
  --max-retries 2 `
  --run-commit $runCommit
```

These commands should not be run until transcript readiness is `ready`.

## 2026-07-18 Continuation Update

- Continuation branch: `codex/dsaa3071-week5-dev-transcripts`
- Packet generation base commit: `c9a56c4`
- Model-run commit policy: record `git rev-parse --short HEAD` at run time
- Transcript readiness: `ready` for all 7 development students.
- Baseline text packet hash: `edd797e817b12daec0e6efea5167d0b107c59ab67f18ff9b77d285dbc648a26f`
- Candidate v2 text packet hash: `febdb58c74b1f031d6f84a2c20e3edd5a8da0e811df6ce26864f2ea9df82d011`
- Shared transcript source hash: `163e919ed6995d789e6cb785a1bd172567a4baf8b2751cbe789f01126660e39e`
- DeepSeek baseline run status: `passed`, 7 / 7 students.
- DeepSeek candidate v2 run status: `passed`, 7 / 7 students.
- Metrics summary: `experiments/records/DSAA3071-week5-dev-model-run/DEV-METRICS.md`
- Metrics JSON: `experiments/records/DSAA3071-week5-dev-model-run/dev-metrics-deepseek.json`

Privacy note: visual inspection found a residual handwritten identity string on `S016` page 1 in the anonymized v3 PDF. The text-only transcripts exclude it, but PDF packets from this redaction version should not be sent to a model until the PDF is corrected.
