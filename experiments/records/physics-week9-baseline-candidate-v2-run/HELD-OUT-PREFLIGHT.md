# Held-Out Test Packet Preflight

Status: held-out test packets built and dry-run validated. Real model calls have
not been run.

Captured date: 2026-07-13, Asia/Shanghai.

## Scope

- course: `physics`
- assessment: `week9`
- split: held-out test
- students: 18 anonymous students
- provider for real run: `deepseek`
- model for real run: `deepseek-v4-pro`
- dry-run model: `deepseek-test`
- input mode: `text-only`
- source transcript run: `T1-test-r1`
- freeze record: `CANDIDATE-V2-FREEZE.md`

Student IDs:

`S001`, `S002`, `S003`, `S004`, `S005`, `S006`, `S007`, `S009`, `S011`,
`S014`, `S015`, `S017`, `S020`, `S021`, `S023`, `S024`, `S025`, `S026`.

## Held-Out Packet Outputs

These packet directories are local-only under ignored `Data/`.

| Role | Packet path | Prompt hash | Packet hash |
| --- | --- | --- | --- |
| baseline | `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-test-r1` | `8fe0b9bb69d56109b2bbecfcdd6ca05ebe2ae9dff76efe610ecfde0d831cfa5e` | `53be0b2ae80adb39b7fbb08405d7a076e036dcd547f5469254b630ad11960c18` |
| candidate v2 | `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-test-r1` | `1eb905236e6f4e4623399e4dc5cd77b80c69fa7a5ea3a2d6a2777f2dcc902c3f` | `bd369e450a9b2cf534cba2fa3c9862f6c81125d7d9709a9af1c3f3641a2a6dd7` |

Both packets use:

- text source hash:
  `df3b16d21a24b8427ec6adf638dec836f5a5834bc92f8d80044f33868d06f1f3`
- rubric hash:
  `a02e0531b3d78590c66d32e76eba170d2e0400e3e4a1c60436f4f5c2c8e93b21`
- output schema hash:
  `fb4a0a87ca7a4edc3386e5d0bce56af1fdce8f61f69a2f2f5c5a36e9bd93012c`

## Build Commands

Baseline packet:

```bash
python -m benchmark.core.cli build-text-grading-packet \
  --course experiments/course_specs/physics_week9.json \
  --packet-id G1-test-r1 \
  --condition G1 \
  --prompt experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_standard_v1_strict_schema.txt \
  --rubric Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1/rubric.json \
  --student-id S001 --student-id S002 --student-id S003 --student-id S004 \
  --student-id S005 --student-id S006 --student-id S007 --student-id S009 \
  --student-id S011 --student-id S014 --student-id S015 --student-id S017 \
  --student-id S020 --student-id S021 --student-id S023 --student-id S024 \
  --student-id S025 --student-id S026 \
  --transcript-source Data/physics/benchmark/transcripts/automatic/T1-test-r1 \
  --output-root Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema \
  --text-source-kind transcript \
  --source-run-id T1-test-r1 \
  --metadata split=held_out \
  --metadata prompt_template_id=grade_standard_v1_strict_schema \
  --metadata skill_version_id=skill_baseline_v1
```

Candidate v2 packet:

```bash
python -m benchmark.core.cli build-text-grading-packet \
  --course experiments/course_specs/physics_week9.json \
  --packet-id G1-test-r1 \
  --condition G1 \
  --prompt experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_candidate_v2_strict_schema.txt \
  --rubric Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1/rubric.json \
  --student-id S001 --student-id S002 --student-id S003 --student-id S004 \
  --student-id S005 --student-id S006 --student-id S007 --student-id S009 \
  --student-id S011 --student-id S014 --student-id S015 --student-id S017 \
  --student-id S020 --student-id S021 --student-id S023 --student-id S024 \
  --student-id S025 --student-id S026 \
  --transcript-source Data/physics/benchmark/transcripts/automatic/T1-test-r1 \
  --output-root Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema \
  --text-source-kind transcript \
  --source-run-id T1-test-r1 \
  --metadata split=held_out \
  --metadata prompt_template_id=grade_candidate_v2_strict_schema \
  --metadata skill_version_id=skill_candidate_v2
```

## Dry-Run Validation

| Role | Dry-run output | Validation |
| --- | --- | --- |
| baseline | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-test-r1-strict-schema-dry-run` | passed, 18/18 |
| candidate v2 | `Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-test-r1-strict-schema-dry-run` | passed, 18/18 |

Dry-run commands:

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-test \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-test-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-test-r1-strict-schema-dry-run \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1 \
  --dry-run

python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-test \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-test-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-test-r1-strict-schema-dry-run \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1 \
  --dry-run
```

## Next Real Run Commands

Real held-out runs must be executed by the project user from a local PowerShell
session with `DEEPSEEK_API_KEY` set. Codex must not send private student
transcripts to the public API from this execution environment.

Baseline held-out run:

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-test-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-test-r1-strict-schema \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1
```

Candidate v2 held-out run:

```bash
python -m benchmark.core.cli run-model-packet \
  --provider deepseek \
  --model deepseek-v4-pro \
  --input-mode text-only \
  --packet Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-test-r1 \
  --output Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-test-r1-strict-schema \
  --temperature 0 \
  --response-format json_object \
  --max-retries 1
```

## Stop Conditions

Stop and record the failure before comparing metrics if either real held-out run:

- has validation status other than `passed`
- has fewer than 18 passed students
- has provider/API errors
- has output directories whose names differ from the commands above
- is accidentally run with a prompt or packet hash that differs from this file
