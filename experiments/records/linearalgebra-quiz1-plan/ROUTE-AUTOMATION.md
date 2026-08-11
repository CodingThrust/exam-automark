# Linear Algebra Quiz 1 route automation / 线路自动化

Status: the anonymous cohort and development/held-out split are frozen. The
snapshot-level `model_run_allowed` marker remains `false`; it is not mutated by
route execution. This document contains no student work, gold scores, or
private filenames.

## Authorized blinded parallel development run

The default gate order below requires completed development gold before a model
run. A course owner may explicitly authorize one blinded development execution
while human gold entry is still in progress only when all of the following are
recorded: the exact frozen development roster, course/rubric/reference/skill
contract, matched M1/T1 packet lineage, provider/model configuration, and the
owner's scope-limited approval. This exception does not authorize held-out work
or any metric, accuracy, agreement, or route-comparison claim. Those remain
locked until the corresponding human gold subset is complete and validated.

For Linear Algebra Quiz 1 v2, the course owner authorized this exception on
2026-08-11 for the frozen 30-submission development roster and the four M1,
T1, Codex-G1, and DeepSeek-G1 routes only. Legacy v1 outputs and any partial
v5.1 route outputs are excluded from comparison and must not be resumed.

## What is automated / 已自动化内容

`build-matched-image-route-packets` creates M1 and T1 together from one
final-approved anonymous submission snapshot and one split roster. It checks
that both packets have the same anonymous IDs, the same per-student input
hashes, and the same immutable snapshot binding. The snapshot manifest, not a
directory naming convention, supplies every submission's ordered pages.

`run-model-packet` accepts both grade and transcription packets. For a
snapshot-derived T1 packet it reads `submission.json` only as page-order and
scope metadata, attaches every listed image in that order, and validates a
transcription-shaped output. It does not score T1 output.

The source-page number, attachment index, and image filename are locators only:
they never identify a question and are not a question-to-page mapping. Every
route must review the full ordered submission and find each declared leaf from
visible question labels, stems, and answer content. A page may contain several
answers, an answer may span pages, and scan order may differ across students.

`build-text-grading-packet` detects a completed adjacent T1 `outputs/` folder.
It inherits and verifies that run's T1 packet hash and frozen snapshot hash, so
G1 cannot silently point at another transcription run. `check-route-lineage`
then validates the full M1 → T1 → G1 chain without a model call.

## Required gate order / 必须的门槛顺序

1. The course owner finishes the private development-set question gold.
2. Validate that development gold; unfinished held-out rows are allowed at
   this stage.
3. Build matched M1/T1 development packets and check their image-route
   lineage.
4. Obtain a separate, explicit development-run approval with a pinned provider
   and model. Only then run T1 and M1.
5. Validate T1 transcripts, build G1 from those exact outputs, and check full
   route lineage.
6. Run M1 and G1 under the same controlled configuration; compare them only
   against development gold. Review typical cases using the W5 categories:
   clear model error, representation loss, rubric/gold conflict, reasonable
   strictness difference, or insufficient evidence.
7. Freeze any skill/prompt decision. A held-out packet and run require a new,
   explicit approval; held-out gold stays sealed until that stage.

## Development commands / 开发集命令

Use private paths appropriate to the local `Data/` tree. Do not use the raw
submission tree and do not put command output in Git.

```powershell
# 1. Human gold must be complete for the frozen development roster.
python -m benchmark.core.cli validate-gold-subset `
  --course experiments/course_specs/linearalgebra_quiz1_v2.json `
  --gold Data/<course>/<private-gold>/question-gold.csv `
  --students-file Data/<course>/<private-split>/development-students.txt `
  --output Data/<course>/<private-gold>/development-gold-readiness.json

# 2. Build byte-matched M1 and T1 image packets. This does not call a model.
python -m benchmark.core.cli build-matched-image-route-packets `
  --course experiments/course_specs/linearalgebra_quiz1_v2.json `
  --snapshot-root Data/<course>/<final-approved-cohort> `
  --output-root Data/<course>/<private-packets>/development `
  --split development `
  --students-file Data/<course>/<private-split>/development-students.txt `
  --m1-packet-id M1-dev-r1 `
  --t1-packet-id T1-dev-r1 `
  --grade-prompt experiments/prompt_templates/grade_candidate_v5_2.txt `
  --transcribe-prompt experiments/prompt_templates/transcribe_standard_v2.txt `
  --rubric experiments/records/linearalgebra-quiz1-plan/rubric_v2.json `
  --metadata skill_version_id=skill_candidate_v5_2 `
  --metadata grade_prompt_template_id=grade_candidate_v5_2 `
  --metadata transcribe_prompt_template_id=transcribe_standard_v2

# 3. This must be ready before any provider call. It never grants approval.
python -m benchmark.core.cli check-route-lineage `
  --m1-packet Data/<course>/<private-packets>/development/M1-dev-r1 `
  --t1-packet Data/<course>/<private-packets>/development/T1-dev-r1 `
  --output Data/<course>/<private-packets>/development/m1-t1-lineage.json
```

After the separate development-run approval, run T1 in `multimodal` mode and
give it a stable `--run-id T1-dev-r1`. Build G1 from the completed T1
`outputs/` directory; the command below rejects a failed or mismatched adjacent
T1 run and automatically inherits its run ID, packet hash, and snapshot hash.

```powershell
# Provider/model values are intentionally omitted until the explicit approval.
python -m benchmark.core.cli build-text-grading-packet `
  --course experiments/course_specs/linearalgebra_quiz1_v2.json `
  --packet-id G1-dev-r1 `
  --condition G1 `
  --prompt experiments/prompt_templates/grade_candidate_v5_2.txt `
  --rubric experiments/records/linearalgebra-quiz1-plan/rubric_v2.json `
  --students-file Data/<course>/<private-split>/development-students.txt `
  --transcript-source Data/<course>/<private-runs>/T1-dev-r1/outputs `
  --output-root Data/<course>/<private-packets>/development `
  --text-source-kind automatic_transcript `
  --metadata split=development `
  --metadata skill_version_id=skill_candidate_v5_2

python -m benchmark.core.cli check-route-lineage `
  --m1-packet Data/<course>/<private-packets>/development/M1-dev-r1 `
  --t1-packet Data/<course>/<private-packets>/development/T1-dev-r1 `
  --g1-packet Data/<course>/<private-packets>/development/G1-dev-r1 `
  --t1-run Data/<course>/<private-runs>/T1-dev-r1 `
  --output Data/<course>/<private-packets>/development/m1-t1-g1-lineage.json
```

The last lineage report must be `ready`; it still reports
`model_run_allowed: false`. It proves data lineage only. Provider execution and
later held-out use remain separately authorized decisions.
