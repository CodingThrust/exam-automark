# C32 Joint Calibration Readiness

Status: **ready**

No model calls are recorded by this checklist.

## Purpose

C32 is a deliberately joint calibration of the DSAA3071 Week 5 grading rubric, prompt, and skill after the development-set diagnosis of C31-r2. The goal is to reduce over-harsh grading on Q7, Q8, and Q9 while preserving official-style adequacy, keyword partial-credit, and severe-error discipline.

## Shared Run Settings

- Provider: `deepseek`
- Model: `deepseek-v4-pro`
- Input mode: `text-only`
- Repetition: `1`
- Split: `development`
- Model run status: `not_started`

## Declared Differences

- B0/R1: rubric only; prompt and skill must match.
- R1/C32-v3.2-rubric-v2: rubric, prompt, and skill jointly differ by design.

The old three-condition gate expects R1/C3 to share the same rubric, so it is expected to fail on `r1_c3_rubric_matches` for C32. This C32-specific gate treats that rubric difference as intentional and records it explicitly.

## Packet Hashes

- B0: `7acbfba40fb0542ccebbc45727f6b259f59c759d39b71dc6f56acfb254f01538`
- R1: `9daaa68706c10d3871e2503e8e588e092e3c5c27bb2f6060d69dfbda24983827`
- C32-v3.2-rubric-v2: `b9146715f6b0dc014f079e07625d98cef62e1954d3e6d0e76bedcc464f4b8439`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `same_course` | passed | B0, R1, and C32 all target DSAA3071 week5_test using the same course hash. |
| `same_students` | passed | All packets contain the same seven development students. |
| `same_split` | passed | All packets declare `development`. |
| `same_task_and_schema` | passed | All packets are text-only grade packets using the same output schema. |
| `same_text_source_and_snapshot` | passed | All packets use the same reviewed transcript hash and data snapshot hash. |
| `packet_audits_pass` | passed | B0, R1, and C32 packet audits pass. |
| `b0_r1_controlled_difference` | passed | B0/R1 isolate rubric change only. |
| `r1_c32_joint_calibration_declared` | passed | R1/C32 intentionally changes rubric, prompt, and skill together. |
| `no_data_committed` | passed | GitHub tracks only safe metadata and reproducibility records, not Data. |
