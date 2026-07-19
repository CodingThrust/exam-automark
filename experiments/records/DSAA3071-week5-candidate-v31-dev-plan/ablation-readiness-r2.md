# Three-Condition Ablation Readiness

Status: **ready**

No model calls are recorded by this checklist.

## Shared Run Settings

- Provider: `deepseek`
- Model: `deepseek-v4-pro`
- Input mode: `text-only`
- Repetition: `1`

## Declared Differences

- B0/R1: rubric only; prompt and skill must match.
- R1/C3: prompt and skill only; rubric must match.

## Packet Hashes

- B0: `7acbfba40fb0542ccebbc45727f6b259f59c759d39b71dc6f56acfb254f01538`
- R1: `9daaa68706c10d3871e2503e8e588e092e3c5c27bb2f6060d69dfbda24983827`
- C3: `d30d5366d8386f6fdbe4621d428e8b739c0b4f0f95b5f7d69941046a6f5e7173`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `same_course` | passed | B0={"course_hash": "ec88c329127550cf283912d85dcd9a6316edfc588e2f8aba6fe1080d24ce69f7", "course_id": "DSAA3071"}; R1={"course_hash": "ec88c329127550cf283912d85dcd9a6316edfc588e2f8aba6fe1080d24ce69f7", "course_id": "DSAA3071"}; C3={"course_hash": "ec88c329127550cf283912d85dcd9a6316edfc588e2f8aba6fe1080d24ce69f7", "course_id": "DSAA3071"} |
| `same_assessment` | passed | B0="week5_test"; R1="week5_test"; C3="week5_test" |
| `same_students` | passed | B0=["S017", "S021", "S002", "S015", "S020", "S016", "S022"]; R1=["S017", "S021", "S002", "S015", "S020", "S016", "S022"]; C3=["S017", "S021", "S002", "S015", "S020", "S016", "S022"] |
| `same_split` | passed | B0="development"; R1="development"; C3="development" |
| `same_task` | passed | B0="grade"; R1="grade"; C3="grade" |
| `same_output_schema` | passed | B0="b5fe4ab6c03b967c6ded896e05c494c86a6ba8912cc587c5f23f87da5eb3ea77"; R1="b5fe4ab6c03b967c6ded896e05c494c86a6ba8912cc587c5f23f87da5eb3ea77"; C3="b5fe4ab6c03b967c6ded896e05c494c86a6ba8912cc587c5f23f87da5eb3ea77" |
| `same_text_source` | passed | B0="9f9be72bf088f211a3b5fc35db1439b3e965059ff55d5c0563e2880bdc7f4a00"; R1="9f9be72bf088f211a3b5fc35db1439b3e965059ff55d5c0563e2880bdc7f4a00"; C3="9f9be72bf088f211a3b5fc35db1439b3e965059ff55d5c0563e2880bdc7f4a00" |
| `same_data_snapshot` | passed | B0="95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37"; R1="95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37"; C3="95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37" |
| `packet_audits_pass` | passed | B0=passed; R1=passed; C3=passed |
| `b0_r1_prompt_and_skill_match` | passed | prompt=8fe0b9bb69d5/8fe0b9bb69d5; skill=('skill_baseline_v1', '23ce24c83d68a1bcae1fa66738c8e4ad5e4db8ed79325e72ac710622effc8b27')/('skill_baseline_v1', '23ce24c83d68a1bcae1fa66738c8e4ad5e4db8ed79325e72ac710622effc8b27') |
| `b0_r1_rubric_differs` | passed | B0=432dc6ea0461; R1=6798e56675bc |
| `r1_c3_rubric_matches` | passed | R1=6798e56675bc; C3=6798e56675bc |
| `r1_c3_prompt_and_skill_differ` | passed | prompt=8fe0b9bb69d5/ba5113e1dec1; skill=('skill_baseline_v1', '23ce24c83d68a1bcae1fa66738c8e4ad5e4db8ed79325e72ac710622effc8b27')/('skill_candidate_v3_1_r2', 'f3c3fbe8ecb856d30cc950f7a252d1e6efa7463e3a59ad8261c760819e0d6e27') |
