# Advisor experiment config contract

Generate the normal Physics Week 9 development config with
`advisor_experiment.py init`. Edit only when the experiment differs from that
preset.

## Top-level fields

- `schema_version`: currently `1`.
- `experiment_id`: unique kebab-case identity.
- `split`: `development` by default; `heldout` or `test` requires explicit
  approval at run time.
- `benchmark_root`: ignored root containing gold scores and packets.
- `state_path`: ignored JSON run state; the helper derives a sibling
  `*-model-probes.json` zero-data receipt from it.
- `record_dir`: the only public directory that `package` and `submit` may
  create or stage; it must be below `experiments/records/`.
- `required_engines`: normally `["kimi", "claude"]`.
- `required_input_modes`: normally `["text-only", "multimodal"]`.
- `packet_builds`: recipes that reuse the frozen prompt/rubric/student set from
  transcript packets while taking actual inputs from approved anonymized image
  roots.
- `runs`: immutable headless run arms.
- `comparisons`: paired aggregate metric jobs referencing run IDs.
- `submission`: base branch, `advisor-results/...` branch, title, commit
  message, and an automatically opened draft pull request.

## Run arm

Each run needs:

```json
{
  "id": "kimi-text-baseline",
  "engine": "kimi",
  "model": "kimi-code/k3",
  "input_mode": "text-only",
  "condition": "baseline",
  "packet": "Data/.../G1-dev-r1",
  "output": "Data/.../kimi-text-baseline",
  "max_retries": 2,
  "timeout_seconds": 600
}
```

Run IDs, packet paths, and output paths must be unique. Outputs must stay under
`Data/`. `timeout_seconds` is a positive per-student CLI deadline; keep the
default unless the frozen task is known to require longer. Do not put API keys,
tokens, passwords, or raw prompt text in this file.

## Packet build

Each multimodal packet build needs:

```json
{
  "id": "baseline-image-dev",
  "source_text_packet": "Data/.../baseline.../G1-dev-r1",
  "input_root": "Data/.../anonymized",
  "privacy_review": "Data/.../manifest/privacy_review.csv",
  "output_root": "Data/.../image_packets/<experiment>-baseline"
}
```

`prepare` obtains the anonymous student set and packet metadata from
`source_text_packet`; it does not accept a hand-entered student list.

## Comparison

Each comparison needs:

```json
{
  "id": "kimi-text-baseline-vs-candidate",
  "baseline_run": "kimi-text-baseline",
  "candidate_run": "kimi-text-candidate",
  "output_json": "Data/.../metrics/kimi-text.json",
  "output_md": "Data/.../metrics/kimi-text.md"
}
```

The labels `baseline_run` and `candidate_run` describe subtraction order. They
may also represent text-versus-image or Kimi-versus-Claude comparisons when the
ID states that axis clearly.

## Retry rule

Never point a retry at an existing failed directory. Copy the private config
and append `-r2`, `-r3`, and so on to:

- `experiment_id` when the whole experiment is retried, or
- the affected run `id` and `output` when only one immutable arm is retried.

Keep the original failure record available for the final retrospective.
