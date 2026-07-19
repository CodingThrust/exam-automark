# DSAA3071 Candidate-v3.2 Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a development-only DSAA3071 Week 5 candidate-v3.2 packet that adds official-style tolerance and targeted Q7/Q8/Q9 calibration.

**Architecture:** Keep the existing experiment framework. Candidate-v3.2 is represented by a new prompt template, updated mirrored grading skill directories, a new skill snapshot, a new `rubric_v2.json`, and a packet/readiness record under the existing DSAA3071 v3.1 experiment directory.

**Tech Stack:** Python `unittest`, `benchmark.core.cli`, JSON rubrics, Markdown experiment records, ignored local `Data` packets.

## Global Constraints

- Do not run model calls while preparing the packet.
- Keep all model-facing scoring rules in English.
- Do not track `Data` in GitHub.
- Do not copy raw student answer text or identity information into tracked records.
- Preserve integer-only scoring and do not introduce quarter-point scores.
- Preserve calculation-question logic so physics-style tasks still retain method/process credit.

---

### Task 1: Add Failing Asset Tests

**Files:**
- Modify: `tests/benchmark/core/test_candidate_v3_assets.py`
- Modify: `tests/benchmark/core/test_skill_snapshots.py`

**Interfaces:**
- Consumes: existing prompt, strict snapshot, skill, reference, and snapshot paths.
- Produces: tests that require `grade_candidate_v3_2.txt`, `rubric_v2.json`, `skill_candidate_v3_2.json`, and model-facing v3.2 calibration phrases.

- [ ] Add tests for official-style tolerance, Q7 proof-locality, Q8 enumerator policy, Q9 conceptual essay policy, and current skill snapshot v3.2.
- [ ] Run the targeted tests and verify they fail because v3.2 assets do not exist yet.

### Task 2: Implement Rubric and Prompt Assets

**Files:**
- Create: `experiments/records/DSAA3071-week5-prep/rubric_v2.json`
- Create: `experiments/prompt_templates/grade_candidate_v3_2.txt`
- Create: `experiments/records/DSAA3071-week5-candidate-v31-dev-plan/prompts/grade_candidate_v3_2_strict_schema.txt`
- Modify: `.agents/skills/grade-homework/SKILL.md`
- Modify: `.agents/skills/grade-homework/references/grading-prompt.md`
- Modify: `.claude/skills/grade-homework/SKILL.md`
- Modify: `.claude/skills/grade-homework/references/grading-prompt.md`

**Interfaces:**
- Consumes: candidate-v3.1 prompt and `rubric_v1.json`.
- Produces: v3.2 model-facing text and rubric rules with official-style tolerance.

- [ ] Copy v3.1 prompt structure and add v3.2 calibration rules.
- [ ] Copy rubric v1 and change only Q7/Q8/Q9 calibration fields.
- [ ] Mirror the updated skill text in `.agents` and `.claude`.
- [ ] Run the targeted tests and verify the v3.2 asset tests pass.

### Task 3: Snapshot and Packet Records

**Files:**
- Create: `experiments/skill_versions/skill_candidate_v3_2.json`
- Create: `experiments/records/DSAA3071-week5-candidate-v31-dev-plan/ablation-plan-c32.json`
- Create: `experiments/records/DSAA3071-week5-candidate-v31-dev-plan/ablation-readiness-c32.json`
- Create: `experiments/records/DSAA3071-week5-candidate-v31-dev-plan/ablation-readiness-c32.md`
- Create: `experiments/records/DSAA3071-week5-candidate-v31-dev-plan/RUN-PROTOCOL-C32.md`
- Create ignored packet under `Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C32-v2-reviewed-dev/C32-dev-reviewed-r1`

**Interfaces:**
- Consumes: new prompt, rubric, skill snapshot, existing B0/R1 packets, and human-reviewed transcripts.
- Produces: reproducible packet and run commands for C32 development only.

- [ ] Build and audit the C32 packet.
- [ ] Generate/readiness-check B0/R1/C32 comparison.
- [ ] Record packet hashes, prompt hashes, rubric hashes, skill hashes, and PowerShell/macOS/Linux run commands.
- [ ] Run tests, packet audit, and `git ls-files -- Data`.

### Task 4: Commit and Handoff

**Files:**
- Commit all tracked v3.2 assets and records.

**Interfaces:**
- Consumes: all outputs from Tasks 1-3.
- Produces: a clean Git commit and user-facing run command.

- [ ] Run final verification.
- [ ] Commit with a message describing candidate-v3.2 packet preparation.
- [ ] Summarize what changed, limitations, and the next PowerShell command to run.
