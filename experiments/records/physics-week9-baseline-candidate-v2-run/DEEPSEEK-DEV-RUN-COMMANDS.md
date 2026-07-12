# Physics Week 9 DeepSeek Dev Run Commands

Status: updated command plan. The first real baseline attempt failed validation
because the model returned numeric confidence values. Use the strict-confidence
rerun plan before any candidate or held-out run.

This file records the exact command-line plan for the first DeepSeek development
split run after `build-text-grading-packet` and `run-model-packet` were merged
to `main`.

## Scope

Run only the development split first:

- baseline: `skill_baseline_v1` with `grade_standard_v1`
- candidate: `skill_candidate_v2` with `grade_candidate_v2`
- provider: `deepseek`
- input mode: `text-only`
- text source: `Data/physics/benchmark/transcripts/automatic/T1-dev-r1`
- text source status: provisional, pilot-derived automatic transcript

Do not run the held-out split until both development runs validate.

## Pre-Run Checks

Run from the repository root:

```bash
python -m benchmark.core.cli check-run-readiness \
  --baseline-plan experiments/records/physics-week9-baseline-candidate-v2-run/baseline-plan.json \
  --candidate-plan experiments/records/physics-week9-baseline-candidate-v2-run/candidate-v2-plan.json
```

The result must be `ready`.

Install and record the provider SDK before a real API call if it is missing.
This runner uses the OpenAI-compatible Python SDK to call DeepSeek. The API key
must be provided through the environment as `DEEPSEEK_API_KEY`; do not write the
key value into any command, file, Git commit, or report.

## Build Baseline Text Packet

```bash
python -m benchmark.core.cli build-text-grading-packet \
  --course experiments/course_specs/physics_week9.json \
  --packet-id G1-dev-r1 \
  --condition G1 \
  --prompt Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/G1-dev-r1/prompt.txt \
  --rubric Data/physics/benchmark/dry_run_packets/physics-week9-standard-plan-lf/G1-dev-r1/rubric.json \
  --student-id S008 \
  --student-id S010 \
  --student-id S012 \
  --student-id S013 \
  --student-id S016 \
  --student-id S018 \
  --student-id S019 \
  --student-id S022 \
  --transcript-source Data/physics/benchmark/transcripts/automatic/T1-dev-r1 \
  --output-root Data/physics/benchmark/text_packets/physics-week9-baseline-text \
  --text-source-kind transcript \
  --source-run-id T1-dev-r1 \
  --metadata split=development \
  --metadata prompt_template_id=grade_standard_v1 \
  --metadata skill_version_id=skill_baseline_v1
```

## Build Candidate Text Packet

```bash
python -m benchmark.core.cli build-text-grading-packet \
  --course experiments/course_specs/physics_week9.json \
  --packet-id G1-dev-r1 \
  --condition G1 \
  --prompt Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/G1-dev-r1/prompt.txt \
  --rubric Data/physics/benchmark/dry_run_packets/physics-week9-candidate-v2-lf/G1-dev-r1/rubric.json \
  --student-id S008 \
  --student-id S010 \
  --student-id S012 \
  --student-id S013 \
  --student-id S016 \
  --student-id S018 \
  --student-id S019 \
  --student-id S022 \
  --transcript-source Data/physics/benchmark/transcripts/automatic/T1-dev-r1 \
  --output-root Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text \
  --text-source-kind transcript \
  --source-run-id T1-dev-r1 \
  --metadata split=development \
  --metadata prompt_template_id=grade_candidate_v2 \
  --metadata skill_version_id=skill_candidate_v2
```

The two generated packet manifests must have the same `metadata.text_source_hash`
and the same per-student `input_hashes`.

## Dry-Run Baseline

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-test \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-dry-run \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1 \
  --dry-run
```

## Dry-Run Candidate

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-test \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-dry-run \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1 \
  --dry-run
```

Both dry-runs must pass validation for all 8 development students.

## Real DeepSeek Baseline Dev Run

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1 \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1
```

## Real DeepSeek Candidate Dev Run

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text/G1-dev-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1 \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1
```

## Required Run Artifacts

Each real run directory must contain:

- `command.txt`
- `command.argv.json`
- `run-metadata.json`
- `raw-responses.jsonl`
- `outputs/Sxxx.json`
- `validation.json`
- `usage.json`
- `failures.jsonl`

Stop before held-out runs if either development run has validation failures,
missing outputs, unexpected retries, or provider/API errors.

## Real Baseline Attempt 1 Status

The original baseline command produced
`Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1`
and failed validation:

- students expected: 8
- students passed: 4
- students failed: 4
- failed reason: numeric `confidence` values such as `0.95` and `1.0`

See `BASELINE-DEV-ATTEMPT-1.md`.

## Strict-Confidence Rerun

Use the strict-confidence prompt sources and packet paths recorded in
`STRICT-CONFIDENCE-RERUN.md`.

Run the strict-confidence baseline first. Do not run candidate v2 until that
baseline rerun validates 8/8.
