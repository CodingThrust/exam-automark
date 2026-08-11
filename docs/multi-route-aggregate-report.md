---
title: Aggregate Multi-route Typst Report
---

# Aggregate multi-route Typst report

`render-multi-route-report` assembles a privacy-safe Typst dashboard only
after the complete M1/T1/G1 experiment gates have passed. It is generic across
courses; all question policy, score rules, and answer content stay in the
frozen course specification and rubric.

The route roles are:

- `M1`: direct multimodal grading.
- `T1`: multimodal transcription readiness only, not a scoring-accuracy row.
- `G1-Codex`: text-only grading of the frozen T1 transcripts with Codex.
- `G1-DeepSeek`: text-only grading of the same frozen T1 transcripts with DeepSeek.

## Privacy and output boundary

Raw submissions, gold scores, transcripts, packet manifests, individual model
outputs, and run validation rows remain in local `Data/`. The public artifacts
below contain only aggregate counts, safe route metadata, and opaque SHA-256
commitments. The renderer rejects student IDs, raw content, private paths,
unknown fields, mismatched routes, and incomplete T1-to-G1 lineage.

The dashboard is supplementary to the three pairwise aggregate metric reports:
those reports retain the score unit, threshold definitions, bootstrap confidence
intervals, and per-question aggregate metrics. A development result does not
authorize held-out or production grading.

## Required completed-run gates

Before producing any public metric or dashboard artifact:

1. Validate the selected human gold subset locally with `validate-gold-subset`.
2. Validate T1 locally with `validate-transcripts`.
3. Require complete, non-dry, structurally passed M1, G1-Codex, and G1-DeepSeek
   runs on the same frozen development roster.
4. Run every `compare-course-runs` invocation with
   `--require-same-data-snapshot`.
5. Produce one ready full-route lineage report and one public binding for each
   G1 route. Each binding proves the same M1/T1 snapshot and roster, the exact
   T1 run and packet, and byte-identical T1 transcript sources.

## Project the two local readiness artifacts

The T1 projection deliberately reads the local validation and run-metadata
files, then writes only aggregate status/counts plus opaque source commitments:

```powershell
python -m benchmark.core.cli summarize-t1-readiness `
  --validation <local-t1-validation.json> `
  --run-metadata <local-t1-run-metadata.json> `
  --output experiments/records/<experiment>/t1-readiness.aggregate.json
```

For each G1 packet, check the full private lineage locally and then project its
canonical public binding. The private report may remain in `Data/`; only the
binding is an input to the public dashboard.

```powershell
python -m benchmark.core.cli check-route-lineage `
  --m1-packet <local-m1-packet> `
  --t1-packet <local-t1-packet> `
  --g1-packet <local-g1-codex-packet> `
  --t1-run <local-t1-run> `
  --output <local-g1-codex-lineage.json>

python -m benchmark.core.cli project-route-lineage-binding `
  --lineage <local-g1-codex-lineage.json> `
  --output experiments/records/<experiment>/g1-codex-lineage.aggregate.json
```

Repeat the two commands for G1-DeepSeek. The two G1 packets/prompts may differ;
their shared snapshot, T1 run, T1 packet, and transcript-source commitments must
match.

## Pairwise aggregate metrics

Keep all inputs under `Data/`, but write only the privacy-checked aggregate
reports under `experiments/records/<experiment>/metrics/`.

```powershell
python -m benchmark.core.cli compare-course-runs `
  --course <public-course.json> --gold <local-gold.csv> --students-file <local-development-roster.txt> `
  --baseline-run <local-m1-run> --candidate-run <local-g1-codex-run> `
  --require-same-data-snapshot `
  --output-json experiments/records/<experiment>/metrics/m1-vs-g1-codex.json `
  --output-md experiments/records/<experiment>/metrics/m1-vs-g1-codex.md

python -m benchmark.core.cli compare-course-runs `
  --course <public-course.json> --gold <local-gold.csv> --students-file <local-development-roster.txt> `
  --baseline-run <local-m1-run> --candidate-run <local-g1-deepseek-run> `
  --require-same-data-snapshot `
  --output-json experiments/records/<experiment>/metrics/m1-vs-g1-deepseek.json `
  --output-md experiments/records/<experiment>/metrics/m1-vs-g1-deepseek.md

python -m benchmark.core.cli compare-course-runs `
  --course <public-course.json> --gold <local-gold.csv> --students-file <local-development-roster.txt> `
  --baseline-run <local-g1-codex-run> --candidate-run <local-g1-deepseek-run> `
  --require-same-data-snapshot `
  --output-json experiments/records/<experiment>/metrics/g1-codex-vs-g1-deepseek.json `
  --output-md experiments/records/<experiment>/metrics/g1-codex-vs-g1-deepseek.md
```

## Render the dashboard

Create a public route contract containing only course IDs, the named split,
provider/model/route roles, and the opaque snapshot hash. It must accurately
match the frozen run metadata; it contains no roster or individual result.

```json
{
  "schema_version": 1,
  "record_type": "public_multi_route_contract",
  "privacy": {
    "aggregate_only": true,
    "student_ids_included": false,
    "per_student_scores_included": false,
    "raw_answers_included": false,
    "model_evidence_included": false,
    "private_paths_included": false
  },
  "course": {"course_id": "<course>", "assessment_id": "<assessment>"},
  "scope": {"split": "development", "data_snapshot_hash": "<sha256>"},
  "routes": {
    "M1": {"declared_route": "M1", "provider": "<provider>", "model": "<model>", "condition": "M1", "task": "grade", "input_mode": "multimodal"},
    "G1-Codex": {"declared_route": "G1-Codex", "provider": "<provider>", "model": "<model>", "condition": "G1", "task": "grade", "input_mode": "text-only"},
    "G1-DeepSeek": {"declared_route": "G1-DeepSeek", "provider": "<provider>", "model": "<model>", "condition": "G1", "task": "grade", "input_mode": "text-only"}
  }
}
```

```powershell
python -m benchmark.core.cli render-multi-route-report `
  --m1-metrics experiments/records/<experiment>/metrics/m1-vs-g1-codex.json `
  --m1-side baseline `
  --g1-codex-metrics experiments/records/<experiment>/metrics/m1-vs-g1-codex.json `
  --g1-codex-side candidate `
  --g1-deepseek-metrics experiments/records/<experiment>/metrics/m1-vs-g1-deepseek.json `
  --g1-deepseek-side candidate `
  --t1-readiness experiments/records/<experiment>/t1-readiness.aggregate.json `
  --route-contract experiments/records/<experiment>/route-contract.json `
  --g1-codex-lineage experiments/records/<experiment>/g1-codex-lineage.aggregate.json `
  --g1-deepseek-lineage experiments/records/<experiment>/g1-deepseek-lineage.aggregate.json `
  --output-json experiments/records/<experiment>/multi-route.aggregate.json `
  --output-typst experiments/records/<experiment>/multi-route-dashboard.typ

& 'C:\Tools\typst\typst.exe' compile `
  experiments/records/<experiment>/multi-route-dashboard.typ `
  experiments/records/<experiment>/multi-route-dashboard.pdf
```

`--output-json` and `--output-typst` must be distinct, previously nonexistent
paths. The renderer validates and renders first, then publishes an all-or-clean
pair; it never overwrites an existing report.
