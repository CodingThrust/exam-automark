# DSAA3071 week5_test Run Readiness

Status: **ready**

No model calls are recorded by this checklist.

## Anchors

- Course: `DSAA3071`
- Assessment: `week5_test`
- Data snapshot: `cf87b373395e381d9d07bbd370c1faa772372b760557b0581dcf9e8a93c04c28`
- Course spec: `experiments/course_specs/DSAA3071_week5_test.json`
- Data inventory: `experiments/data_inventory/DSAA3071.json`
- Git: `codex/multi-course-pilot-inventory @ ca8954b`
- Current Git: `codex/multi-course-pilot-inventory @ 428f0175bac26c89db9a811374f6a63ea61b29d1`
- Baseline skill: `skill_baseline_v1`
- Candidate skill: `skill_candidate_v2`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `plans_are_packetized` | passed | baseline=packets_built; candidate=packets_built |
| `same_course_and_assessment` | passed | DSAA3071/week5_test vs DSAA3071/week5_test |
| `same_data_snapshot` | passed | cf87b373395e... vs cf87b373395e... |
| `same_data_inventory_and_course_spec` | passed | inventory=experiments/data_inventory/DSAA3071.json; course_spec=experiments/course_specs/DSAA3071_week5_test.json |
| `same_git_anchor` | passed | codex/multi-course-pilot-inventory@ca8954b vs codex/multi-course-pilot-inventory@ca8954b |
| `different_skill_versions` | passed | skill_baseline_v1 vs skill_candidate_v2 |
| `different_skill_hashes` | passed | candidate skill hash must differ from baseline skill hash |
| `same_planned_packet_ids` | passed | G1-dev-r1, G1-test-r1, T1-dev-r1, T1-test-r1 |
| `same_built_packet_ids` | passed | G1-dev-r1, G1-test-r1, T1-dev-r1, T1-test-r1 |
| `all_packets_audit_recorded_passed` | passed | all built packet records must have audit_status=passed |
| `grade_prompt_differs` | passed | ['grade_standard_v1_strict_schema'] vs ['grade_candidate_v2_strict_schema'] |
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
| `current_git_branch_matches_plan` | passed | current=codex/multi-course-pilot-inventory; planned=codex/multi-course-pilot-inventory |
| `planned_git_commit_exists` | passed | planned=ca8954b; resolved=ca8954b4be01233aa4abfec306605bd4bc2b8b3a |
| `current_git_head_contains_plan_commit` | passed | HEAD=428f0175bac26c89db9a811374f6a63ea61b29d1; planned=ca8954b4be01233aa4abfec306605bd4bc2b8b3a |
| `post_anchor_changes_are_record_only` | passed | post-anchor commits only touch experiment records |
| `git_worktree_clean` | passed | working tree clean |
| `data_ignored_by_git` | passed | Data/ is ignored and has no tracked files |

## Next Actions

- Ready to run only after the researcher explicitly starts model calls.
