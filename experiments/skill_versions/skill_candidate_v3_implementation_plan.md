# Candidate v3 and Rubric v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and freeze an English candidate-v3 grading policy and a calibrated DSAA3071 week 5 rubric v1, then prepare a no-model-call B0/R1/C3 development ablation on the human-reviewed transcript snapshot.

**Architecture:** Keep the grading procedure course-independent in the prompt and mirrored `grade-homework` skill. Keep DSAA3071 content and scoring calibration in `rubric_v1.json`. Add a generic concept-rubric validator and a three-packet controlled-difference readiness checker so invalid rubrics, privacy leakage, and unintended experimental drift fail before model execution.

**Tech Stack:** Python 3.12 standard library, `unittest`, existing `benchmark.core` CLI and packet APIs, JSON experiment assets, Markdown skill resources, Git SHA-256 snapshots.

## Global Constraints

- Preserve `rubric_v0.json`, candidate-v2 prompts, skill snapshot, packets, runs, and metrics unchanged.
- Use only `S017`, `S021`, `S002`, `S015`, `S020`, `S016`, and `S022` for calibration.
- Do not inspect held-out gold rows during implementation.
- Do not place student answer text, PDFs, gold scores, or identifiable data in tracked artifacts.
- Keep all model-facing text in English.
- Allow integer scores only; do not use 0.25-point increments.
- Use transcript snapshot `T1-dev-human-reviewed-r1` with hash `95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37`.
- Never overwrite existing packet or run directories.
- Do not call a model in this implementation plan.

---

## File Map

- `benchmark/core/rubrics.py`: validate the optional `concept_keyterm_v1` rubric format.
- `benchmark/core/packets.py`: invoke rubric validation before writing grade packets.
- `benchmark/core/comparisons.py`: validate controlled differences across B0/R1/C3 packet manifests.
- `benchmark/core/cli.py`: expose `validate-rubric` and `check-ablation-readiness`.
- `experiments/records/DSAA3071-week5-prep/rubric_v1.json`: course-specific calibrated scoring contract.
- `experiments/prompt_templates/grade_candidate_v3.txt`: reusable candidate-v3 model prompt.
- `.agents/skills/grade-homework/`: canonical candidate-v3 skill implementation.
- `.claude/skills/grade-homework/`: byte-synchronized mirror.
- `experiments/skill_versions/skill_candidate_v3.json`: generated skill hash snapshot.
- `experiments/records/DSAA3071-week5-candidate-v3-dev-plan/`: strict prompt snapshot, ablation plan, readiness outputs, and reproduction protocol.
- `tests/benchmark/core/test_rubrics.py`: rubric validation and tracked-asset tests.
- `tests/benchmark/core/test_candidate_v3_assets.py`: prompt, skill, mirror, and privacy tests.
- `tests/benchmark/core/test_comparisons.py`: controlled-difference readiness tests.

---

### Task 1: Validate Concept-Keyterm Rubrics Before Packet Creation

**Files:**
- Create: `benchmark/core/rubrics.py`
- Modify: `benchmark/core/packets.py`
- Modify: `benchmark/core/cli.py`
- Create: `tests/benchmark/core/test_rubrics.py`
- Modify: `tests/benchmark/core/test_cli.py`

**Interfaces:**
- Produces: `validate_concept_rubric(rubric: dict[str, Any], course: CourseSpec) -> list[str]`
- Produces: `require_valid_rubric(rubric: dict[str, Any], course: CourseSpec) -> None`
- Produces CLI: `validate-rubric --course PATH --rubric PATH [--output PATH]`
- Consumed by: `build_prompt_packet` and `build_text_grading_packet` when `rubric_format == "concept_keyterm_v1"`.

- [ ] **Step 1: Write failing validator tests**

Add tests that construct a two-question synthetic rubric and assert:

```python
errors = validate_concept_rubric(valid_rubric, course)
self.assertEqual(errors, [])

invalid = copy.deepcopy(valid_rubric)
invalid["questions"][1]["scoring_elements"][0]["levels"]["mentioned_only"] = 1.5
errors = validate_concept_rubric(invalid, course)
self.assertIn("Q2 mentioned_only credit must use the 1.0 score step", errors)
```

Cover missing/extra question IDs, mismatched maxima, duplicate element IDs,
non-integer or descending level credit, demonstrated-credit totals above the
question maximum, missing five score bands, invalid band bounds, material-error
caps outside the score range, and forbidden keys such as `student_id`,
`gold_score`, and `example_student_answer`.

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```powershell
python -m unittest tests.benchmark.core.test_rubrics -v
```

Expected: import failure for `benchmark.core.rubrics`.

- [ ] **Step 3: Implement the minimal validator**

Implement stable sorted findings. The entry point skips legacy rubrics unless:

```python
if rubric.get("rubric_format") != "concept_keyterm_v1":
    return []
```

For concept questions require `scoring_elements`, `score_bands`,
`material_errors`, and `full_credit_rule`. Require each scoring element to use
exactly these states:

```python
REQUIRED_LEVELS = (
    "mentioned_only",
    "partial_understanding",
    "demonstrated",
)
REQUIRED_BANDS = (
    "full",
    "substantially_correct",
    "partially_correct",
    "minimal_relevant",
    "no_credit",
)
```

Use `QuestionSpec.allows_score()` for every level point and band boundary.
Reject any recursively discovered forbidden key from:

```python
FORBIDDEN_RUBRIC_KEYS = {
    "student_id",
    "student_ids",
    "gold_score",
    "gold_scores",
    "primary_scores",
    "example_student_answer",
}
```

`require_valid_rubric` raises one `ValueError` containing all findings. Call it
before either packet builder creates its output directory.

- [ ] **Step 4: Add and test the CLI command**

The command loads `CourseSpec`, parses the rubric JSON object, writes this shape,
and exits `0` only for `ready`:

```json
{
  "course_id": "DSAA3071",
  "failed_checks": [],
  "rubric_format": "concept_keyterm_v1",
  "status": "ready"
}
```

Run:

```powershell
python -m unittest tests.benchmark.core.test_rubrics tests.benchmark.core.test_cli -v
```

Expected: PASS.

- [ ] **Step 5: Run packet regressions and commit**

Run:

```powershell
python -m unittest tests.benchmark.core.test_packets tests.benchmark.core.test_transcripts -v
```

Expected: PASS with legacy rubrics unchanged.

Commit:

```powershell
git add benchmark/core/rubrics.py benchmark/core/packets.py benchmark/core/cli.py tests/benchmark/core/test_rubrics.py tests/benchmark/core/test_cli.py
git commit -m "Validate concept-keyterm grading rubrics"
```

---

### Task 2: Create and Validate DSAA3071 Rubric v1

**Files:**
- Create: `experiments/records/DSAA3071-week5-prep/rubric_v1.json`
- Modify: `tests/benchmark/core/test_rubrics.py`
- Modify: `experiments/records/DSAA3071-week5-prep/README.md`

**Interfaces:**
- Consumes: `validate_concept_rubric` from Task 1.
- Produces: model-facing rubric with `rubric_format = "concept_keyterm_v1"`, `rubric_version = "DSAA3071-week5-v1"`, and total points `130`.

- [ ] **Step 1: Write a failing tracked-asset test**

Load the course and rubric paths and assert:

```python
self.assertEqual(rubric["rubric_format"], "concept_keyterm_v1")
self.assertEqual(validate_concept_rubric(rubric, course), [])
self.assertEqual(sum(q["max_score"] for q in rubric["questions"]), 130)
for question in rubric["questions"][4:]:
    self.assertTrue(question["scoring_elements"])
    self.assertTrue(any(e["levels"]["mentioned_only"] > 0 for e in question["scoring_elements"]))
```

Serialize the tracked rubric and assert it contains no anonymous ID matching
`S[0-9]{3}`, no `primary_scores`, and no student answer text fields.

- [ ] **Step 2: Run the asset test and confirm RED**

Run:

```powershell
python -m unittest tests.benchmark.core.test_rubrics -v
```

Expected: failure because `rubric_v1.json` does not exist.

- [ ] **Step 3: Create the exact scoring-element allocation**

Retain Q1-Q4 as 5-point exact multiple-choice questions. Create these
non-overlapping demonstrated-credit allocations for Q5-Q10:

| Question | Element IDs and demonstrated points | Total |
|---|---|---:|
| Q5 | `virtual_tape_encoding` 6, `virtual_head_tracking` 6, `simulated_step` 8 | 20 |
| Q6 | `branch_address` 5, `systematic_exploration` 6, `branch_simulation_and_acceptance` 6, `resource_or_overhead_awareness` 3 | 20 |
| Q7 | `recognizer_to_enumerator` 9, `enumerator_to_recognizer` 8, `correctness_and_nonmembership` 3 | 20 |
| Q8 | `power_of_two_outputs` 5, `enumerator_loop_or_doubling` 5 | 10 |
| Q9 | `equivalent_computation_models` 8, `tm_variant_robustness` 8, `absence_of_counterexamples` 9 | 25 |
| Q10 | `stay_put_simulation` 5, `finite_tape_restriction` 5, `one_way_restriction` 5 | 15 |

For each element set integer levels satisfying:

```text
0 < mentioned_only < partial_understanding < demonstrated
```

Use `mentioned_only = 1` for 5-6 point elements, `2` for 8-9 point elements;
use a midpoint integer for `partial_understanding`. Include accepted keywords,
abbreviations, semantic equivalents, meaning, importance, and
`required_for_full_credit`.

Use these band boundaries:

| Max | no_credit | minimal | partial | substantial | full |
|---:|---:|---:|---:|---:|---:|
| 10 | 0 | 1-2 | 3-5 | 6-9 | 10 |
| 15 | 0 | 1-4 | 5-9 | 10-14 | 15 |
| 20 | 0 | 1-5 | 6-12 | 13-19 | 20 |
| 25 | 0 | 1-7 | 8-16 | 17-24 | 25 |

Use these requirements consistently: `full` requires every
`required_for_full_credit` element at `demonstrated` and no active material
error; `substantially_correct` requires the central conclusion and a majority
of essential demonstrated credit; `partially_correct` requires at least one
partially understood essential element; `minimal_relevant` requires at least
one correctly relevant keyword or idea; `no_credit` requires blank, irrelevant,
or wholly contradicted evidence.

Encode these question-specific material errors and caps:

| Question | Material error | Cap |
|---|---|---:|
| Q5 | Does not preserve both virtual tape configurations or supplies no coherent simulation mechanism | 9 |
| Q6 | Explores only one nondeterministic branch with no fair/systematic exploration | 10 |
| Q7 | Claims nonmembers can be rejected merely because an enumerator or recognizer has not produced an answer | 16 |
| Q8 | Generates lengths `2n` rather than `2^n` | 4 |
| Q9 | Treats a computational speedup alone as evidence of computing an uncomputable function | 16 |

Q10 errors are local to their corresponding 5-point elements and do not impose
an additional whole-question cap.

Q9 v1 must score the three requested evidence families and must not add the v0
`thesis_not_a_theorem` item as a fourth point-bearing requirement. It may appear
only as optional explanatory context.

- [ ] **Step 4: Validate the rubric and update its provenance note**

Run:

```powershell
python -m benchmark.core.cli validate-rubric --course experiments\course_specs\DSAA3071_week5_test.json --rubric experiments\records\DSAA3071-week5-prep\rubric_v1.json
```

Expected: `"status": "ready"` and no failed checks.

Update the prep README to state that v1 was calibrated from the official
solution and development score discrepancies, contains no student examples,
and leaves v0 frozen for historical runs.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m unittest tests.benchmark.core.test_rubrics tests.benchmark.core.test_experiment_records -v
```

Expected: PASS.

Commit:

```powershell
git add experiments/records/DSAA3071-week5-prep/rubric_v1.json experiments/records/DSAA3071-week5-prep/README.md tests/benchmark/core/test_rubrics.py
git commit -m "Add calibrated DSAA3071 concept rubric v1"
```

---

### Task 3: Implement Candidate-v3 Prompt and Mirrored Grading Skill

**Files:**
- Create: `experiments/prompt_templates/grade_candidate_v3.txt`
- Modify: `experiments/prompt_templates/README.md`
- Modify: `.agents/skills/grade-homework/SKILL.md`
- Modify: `.agents/skills/grade-homework/references/grading-prompt.md`
- Modify: `.claude/skills/grade-homework/SKILL.md`
- Modify: `.claude/skills/grade-homework/references/grading-prompt.md`
- Create: `experiments/records/DSAA3071-week5-candidate-v3-dev-plan/prompts/grade_candidate_v3_strict_schema.txt`
- Create: `experiments/skill_versions/skill_candidate_v3.json`
- Create: `tests/benchmark/core/test_candidate_v3_assets.py`
- Modify: `tests/benchmark/core/test_grade_homework_candidate_skill.py`
- Modify: `tests/benchmark/core/test_skill_snapshots.py`

**Interfaces:**
- Produces: generic candidate-v3 grading contract shared by prompt and skill.
- Produces: strict-schema prompt snapshot for C3 packet construction.
- Produces: synchronized `skill_candidate_v3` SHA-256 snapshot.

- [ ] **Step 1: Write failing prompt and skill tests**

Assert that the generic prompt, strict snapshot, canonical skill, and grading
reference all include the exact concepts:

```python
required = (
    "key_term_evidence",
    "concept_evidence",
    "relation_evidence",
    "mentioned_only",
    "partial_understanding",
    "demonstrated",
    "misused_or_contradicted",
    "Do not award duplicate credit",
    "semantic equivalent",
    "question type",
)
```

Assert that prompt and skill explicitly preserve integer scoring, wrong-answer
process credit, evidence-first scoring, confidence enum values, second-pass
review, and exact total recomputation. Assert Codex and Claude mirrors match for
every bundled file. Assert no DSAA-specific answer terms or `S[0-9]{3}` IDs are
present in the generic prompt or skill.

Update the checked-in snapshot test so the current skill directories must match
`skill_candidate_v3.json`. Keep a separate assertion that
`skill_candidate_v2.json` remains loadable, synchronized as recorded, and
different from both baseline v1 and candidate v3; do not require historical v2
hashes to match the newly updated current directories.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```powershell
python -m unittest tests.benchmark.core.test_candidate_v3_assets tests.benchmark.core.test_grade_homework_candidate_skill -v
```

Expected: failure because candidate-v3 artifacts are missing.

- [ ] **Step 3: Write the candidate-v3 contract**

Implement the ten-step algorithm from
`experiments/skill_versions/skill_candidate_v3_design.md` in English. The
contract must:

```text
extract key-term, concept, and relation evidence
map each scoring element to exactly one state
award limited keyword-only credit
sum non-overlapping element credit
apply score-band and material-error caps without raising the subtotal
apply question-type rules
review missed equivalents, missed keyword credit, duplicate credit, and misuse
```

Keep v2's valid evidence, privacy, confidence, flag, score-step, and total rules.
Do not add course answers or student examples.

- [ ] **Step 4: Synchronize mirrors and generate the skill snapshot**

Copy only the changed `SKILL.md` and `references/grading-prompt.md` from
`.agents` to `.claude`; leave scripts unchanged and verify every bundled file is
identical.

Run:

```powershell
python -m benchmark.core.cli snapshot-skill --skill-version-id skill_candidate_v3 --source agents=.agents\skills\grade-homework --source claude=.claude\skills\grade-homework --output experiments\skill_versions\skill_candidate_v3.json
```

Expected: `"mirror_synchronized": true`.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m unittest tests.benchmark.core.test_candidate_v3_assets tests.benchmark.core.test_grade_homework_candidate_skill tests.benchmark.core.test_skill_snapshots tests.benchmark.physics.test_skill_sync -v
```

Expected: PASS.

Commit:

```powershell
git add experiments/prompt_templates .agents/skills/grade-homework .claude/skills/grade-homework experiments/records/DSAA3071-week5-candidate-v3-dev-plan/prompts experiments/skill_versions/skill_candidate_v3.json tests/benchmark/core/test_candidate_v3_assets.py tests/benchmark/core/test_grade_homework_candidate_skill.py tests/benchmark/core/test_skill_snapshots.py
git commit -m "Add concept-aware candidate v3 grading skill"
```

---

### Task 4: Add Controlled B0/R1/C3 Ablation Readiness

**Files:**
- Create: `benchmark/core/comparisons.py`
- Modify: `benchmark/core/cli.py`
- Create: `tests/benchmark/core/test_comparisons.py`

**Interfaces:**
- Produces: `check_three_condition_ablation(b0: Path, r1: Path, c3: Path, *, provider: str, model: str, input_mode: str, repetition: int) -> dict[str, Any]`
- Produces CLI: `check-ablation-readiness --b0-packet PATH --r1-packet PATH --c3-packet PATH --provider deepseek --model deepseek-v4-pro --input-mode text-only --repetition 1 --output PATH --markdown-output PATH`.

- [ ] **Step 1: Write failing controlled-difference tests**

Build three synthetic packet directories with manifests. Assert `ready` only
when:

```text
all: same course, assessment, students, split, task, output schema,
     text source hash, data snapshot hash
B0/R1: same prompt and skill; different rubric
R1/C3: same rubric; different prompt and skill
all packet audits: no findings
```

Add one test per unexpected drift: different student order, transcript hash,
output schema, or undeclared prompt/rubric relationship. Each must return
`status = "not_ready"` with a stable failed-check ID.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```powershell
python -m unittest tests.benchmark.core.test_comparisons -v
```

Expected: import failure for `benchmark.core.comparisons`.

- [ ] **Step 3: Implement readiness and Markdown rendering**

Return a JSON report containing shared run settings, packet hashes, expected
differences, checks, failed checks, and status. Use check IDs:

```python
COMMON_CHECKS = (
    "same_course",
    "same_assessment",
    "same_students",
    "same_split",
    "same_task",
    "same_output_schema",
    "same_text_source",
    "same_data_snapshot",
    "packet_audits_pass",
    "b0_r1_prompt_and_skill_match",
    "b0_r1_rubric_differs",
    "r1_c3_rubric_matches",
    "r1_c3_prompt_and_skill_differ",
)
```

Reject `repetition < 1` and any input mode other than `text-only`. Keep the
provider/model values as one shared anchor so they cannot drift by condition.

- [ ] **Step 4: Add CLI tests and run GREEN**

Run:

```powershell
python -m unittest tests.benchmark.core.test_comparisons tests.benchmark.core.test_cli -v
```

Expected: PASS, including JSON and Markdown output creation.

- [ ] **Step 5: Run readiness regressions and commit**

Run:

```powershell
python -m unittest tests.benchmark.core.test_readiness tests.benchmark.core.test_comparisons -v
```

Expected: PASS.

Commit:

```powershell
git add benchmark/core/comparisons.py benchmark/core/cli.py tests/benchmark/core/test_comparisons.py tests/benchmark/core/test_cli.py
git commit -m "Add controlled three-condition readiness gate"
```

---

### Task 5: Build Reviewed Dev Packets and Freeze the No-Call Experiment Record

**Files:**
- Create under ignored `Data/`: three new text packet directories.
- Create: `experiments/records/DSAA3071-week5-candidate-v3-dev-plan/ablation-plan.json`
- Create: `experiments/records/DSAA3071-week5-candidate-v3-dev-plan/ablation-readiness.json`
- Create: `experiments/records/DSAA3071-week5-candidate-v3-dev-plan/ablation-readiness.md`
- Create: `experiments/records/DSAA3071-week5-candidate-v3-dev-plan/RUN-PROTOCOL.md`
- Modify: `tests/benchmark/core/test_experiment_records.py`

**Interfaces:**
- Consumes: reviewed transcript hash, rubric v0/v1, baseline/candidate-v3 prompts, and skill snapshots.
- Produces: packet-ready B0/R1/C3 experiment with no model outputs.

- [ ] **Step 1: Write a failing experiment-record test**

Assert that `ablation-plan.json` declares exactly B0/R1/C3, the reviewed source
hash, development-only student list, shared DeepSeek model settings, controlled
differences, packet paths, prompt/rubric/skill hashes, and `model_calls = 0`.
Assert the readiness JSON is `ready` and the run protocol contains Windows and
macOS/Linux reproduction commands without API keys.

- [ ] **Step 2: Run the record test and confirm RED**

Run:

```powershell
python -m unittest tests.benchmark.core.test_experiment_records -v
```

Expected: failure because the candidate-v3 dev-plan record does not exist.

- [ ] **Step 3: Build three new packets without overwriting old paths**

Use packet IDs `B0-dev-reviewed-r1`, `R1-dev-reviewed-r1`, and
`C3-dev-reviewed-r1`, condition values B0/R1/C3, and source run ID
`T1-dev-human-reviewed-r1`.

Use these output roots:

```text
Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-B0-v0-reviewed-dev
Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-R1-v1-reviewed-dev
Data/DSAA3071/week5-benchmark-redaction-v3/text_grading_packets/DSAA3071-week5-C3-v1-reviewed-dev
```

B0 uses baseline strict prompt + rubric v0 + `skill_baseline_v1`.
R1 uses the same baseline strict prompt + rubric v1 + `skill_baseline_v1`.
C3 uses candidate-v3 strict prompt + rubric v1 + `skill_candidate_v3`.
Every packet records
`data_snapshot_hash=95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37`,
split development, and the shared transcript source.

- [ ] **Step 4: Generate and run the controlled readiness gate**

Run:

```powershell
python -m benchmark.core.cli check-ablation-readiness --b0-packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-B0-v0-reviewed-dev\B0-dev-reviewed-r1 --r1-packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-R1-v1-reviewed-dev\R1-dev-reviewed-r1 --c3-packet Data\DSAA3071\week5-benchmark-redaction-v3\text_grading_packets\DSAA3071-week5-C3-v1-reviewed-dev\C3-dev-reviewed-r1 --provider deepseek --model deepseek-v4-pro --input-mode text-only --repetition 1 --output experiments\records\DSAA3071-week5-candidate-v3-dev-plan\ablation-readiness.json --markdown-output experiments\records\DSAA3071-week5-candidate-v3-dev-plan\ablation-readiness.md
```

Expected: `"status": "ready"`, no failed checks, and no model call.

- [ ] **Step 5: Write the safe plan and reproduction protocol**

Record exact packet, prompt, rubric, skill, transcript, data, course, output
schema, and Git commit hashes. Include packet build commands and future run
command templates for Windows and macOS/Linux, but state that execution is
blocked until user approval. Do not include an API key, answer text, gold rows,
or model outputs.

- [ ] **Step 6: Run full verification and commit**

Run:

```powershell
python -m unittest discover -s tests\benchmark\core -p "test*.py" -v
python -m unittest discover -s tests\benchmark\physics -p "test*.py" -v
python -m benchmark.core.cli validate-rubric --course experiments\course_specs\DSAA3071_week5_test.json --rubric experiments\records\DSAA3071-week5-prep\rubric_v1.json
python -m benchmark.core.cli validate-transcripts --course experiments\course_specs\DSAA3071_week5_test.json --transcript-source Data\DSAA3071\week5-benchmark-redaction-v3\transcripts\T1-dev-human-reviewed-r1 --students-file experiments\records\DSAA3071-week5-test-plan\students-development.txt
git diff --check
git ls-files -- Data
```

Expected: all tests pass; rubric and transcripts are `ready`; no diff errors;
`git ls-files -- Data` prints nothing.

Commit:

```powershell
git add experiments/records/DSAA3071-week5-candidate-v3-dev-plan tests/benchmark/core/test_experiment_records.py
git commit -m "Prepare DSAA3071 candidate v3 dev ablation"
```

Do not push, open a PR, or call DeepSeek in this task.
