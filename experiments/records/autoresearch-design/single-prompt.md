# Single-Prompt Autoresearch Dry-Run

You are running the minimal exam-automark autoresearch MVP. Do not read raw
student submissions, identity maps, raw model responses, or files under
`Data/`. This run is a deterministic dry-run of the experiment-control loop,
not a full model-driven SkillOpt run.

Goal:

1. Use tracked course, inventory, and skill snapshot files only.
2. Build one autoresearch experiment record.
3. Compare a baseline metric and a candidate metric.
4. Accept the candidate if the primary metric improves.
5. Reject the candidate otherwise.
6. Write the result to the requested output JSON file.

Run from the repository root:

```powershell
python experiments/records/autoresearch-design/run_experiment.py `
  --mode dry-run `
  --record-id physics-week9-autoresearch-mvp-dry-run `
  --prompt experiments/records/autoresearch-design/single-prompt.md `
  --course-spec experiments/course_specs/physics_week9.json `
  --data-inventory experiments/data_inventory/physics.json `
  --baseline-skill experiments/skill_versions/skill_baseline_v1.json `
  --candidate-skill experiments/skill_versions/skill_candidate_v2.json `
  --baseline-metric 2.2639 `
  --candidate-metric 2.0833 `
  --generated-at 2026-07-21T00:00:00Z `
  --output experiments/records/autoresearch-design/dry-run-result.json
```

Expected result:

- The output JSON has `record_type = ai_grading_autoresearch_experiment`.
- `single_prompt.path` points to this file.
- `decision.status` is `accept` because candidate total-score MAE is lower.
- `mode` is `dry-run`.

Stop conditions:

- If any command tries to read `Data/`, stop.
- If the candidate sees gold scores, previous predictions, or held-out results,
  stop.
- If the output path already contains a real model-run result, stop and choose a
  new dry-run output path.
