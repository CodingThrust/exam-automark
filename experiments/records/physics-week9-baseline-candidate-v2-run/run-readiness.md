# Physics Week 9 Run Readiness

Status: **ready**

No model calls are recorded by this checklist.

## Anchors

- Course: `physics`
- Assessment: `week9`
- Data snapshot: `e0b47a06a3ec12417a70a773ac8d5728ebbbd40c8991ac7ec7a11c2a92d2a6f3`
- Course spec: `experiments/course_specs/physics_week9.json`
- Data inventory: `experiments/data_inventory/physics.json`
- Git: `codex/physics-week9-baseline-candidate-v2-run @ 36e7201`
- Current Git: `codex/physics-week9-baseline-candidate-v2-run @ 51c22c644b1819c1aafb04549147f6c28fd4f7dc`
- Baseline skill: `skill_baseline_v1`
- Candidate skill: `skill_candidate_v2`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `plans_are_packetized` | passed | baseline=packets_built; candidate=packets_built |
| `same_course_and_assessment` | passed | physics/week9 vs physics/week9 |
| `same_data_snapshot` | passed | e0b47a06a3ec... vs e0b47a06a3ec... |
| `same_data_inventory_and_course_spec` | passed | inventory=experiments/data_inventory/physics.json; course_spec=experiments/course_specs/physics_week9.json |
| `same_git_anchor` | passed | codex/physics-week9-baseline-candidate-v2-run@36e7201 vs codex/physics-week9-baseline-candidate-v2-run@36e7201 |
| `different_skill_versions` | passed | skill_baseline_v1 vs skill_candidate_v2 |
| `different_skill_hashes` | passed | candidate skill hash must differ from baseline skill hash |
| `same_planned_packet_ids` | passed | G1-dev-r1, G1-test-r1, T1-dev-r1, T1-test-r1 |
| `same_built_packet_ids` | passed | G1-dev-r1, G1-test-r1, T1-dev-r1, T1-test-r1 |
| `all_packets_audit_recorded_passed` | passed | all built packet records must have audit_status=passed |
| `grade_prompt_differs` | passed | ['grade_standard_v1'] vs ['grade_candidate_v2'] |
| `transcribe_prompt_held_constant` | passed | ['transcribe_standard_v1'] vs ['transcribe_standard_v1'] |
| `packet_manifests_exist` | passed | all packet manifests are present |
| `packet_paths_are_local_data` | passed | all packet paths should be under ignored Data/ |
| `packet_directories_exist` | passed | all packet directories exist |
| `packet_hashes_match_local_files` | passed | all packet hashes match |
| `packet_audits_pass_now` | passed | all packet audits pass |
| `manifest_prompt_hashes_match_plan` | passed | all manifest prompt hashes match plan templates |
| `manifest_metadata_matches_plan` | passed | all packet metadata matches plan |
| `same_students_and_inputs_per_packet` | passed | matching packet ids use the same student ids and input hashes |
| `same_rubric_for_grade_packets` | passed | grade packets use the same rubric hash |
| `no_model_result_artifacts_in_plan_dirs` | passed | no experiment, metrics, or prediction artifacts found |
| `current_git_branch_matches_plan` | passed | current=codex/physics-week9-baseline-candidate-v2-run; planned=codex/physics-week9-baseline-candidate-v2-run |
| `planned_git_commit_exists` | passed | planned=36e7201; resolved=36e720107e7c8f02586cf53956fb8bd1319391de |
| `current_git_head_contains_plan_commit` | passed | HEAD=51c22c644b1819c1aafb04549147f6c28fd4f7dc; planned=36e720107e7c8f02586cf53956fb8bd1319391de |
| `post_anchor_changes_are_record_only` | passed | post-anchor commits only touch experiment records |
| `git_worktree_clean` | passed | working tree clean |
| `data_ignored_by_git` | passed | Data/ is ignored and has no tracked files |

## Next Actions

- Ready to run only after the researcher explicitly starts model calls.
