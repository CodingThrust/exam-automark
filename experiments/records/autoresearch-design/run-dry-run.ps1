Set-Location "D:\AI-Grading-Platform\exam-automark-multicourse"

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

$exit = $LASTEXITCODE
"Autoresearch dry-run exit=$exit"
exit $exit
