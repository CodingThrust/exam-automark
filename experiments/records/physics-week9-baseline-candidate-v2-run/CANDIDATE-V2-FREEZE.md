# Candidate v2 Freeze Record

Status: candidate v2 is frozen for held-out evaluation.

Captured date: 2026-07-13, Asia/Shanghai.

## Decision

Freeze the Physics Week 9 candidate v2 strict-schema grading prompt for the next
held-out text-only evaluation.

This decision means:

- the candidate v2 prompt must not be edited before the held-out test run
- the held-out test split must not be used to tune candidate v2
- if a later prompt change is needed, it must become a new candidate version
  such as candidate v3
- the held-out test can only evaluate the frozen candidate v2 against the frozen
  baseline under the same packet and runner protocol

## Frozen Candidate Artifact

| Field | Value |
| --- | --- |
| course | `physics` |
| assessment | `week9` |
| input mode | `text-only` |
| candidate version | `candidate v2 strict-schema` |
| skill version id | `skill_candidate_v2` |
| prompt template id | `grade_candidate_v2_strict_schema` |
| prompt source | `experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_candidate_v2_strict_schema.txt` |
| prompt SHA-256 | `1eb905236e6f4e4623399e4dc5cd77b80c69fa7a5ea3a2d6a2777f2dcc902c3f` |
| development packet | `Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1` |
| development packet SHA-256 | `8987ce06f54a46ba242703df0d028ffb8de56143a00a312b289e1f39fc7aed6d` |
| text source hash | `30e45836b26f6c05d0a55c2e436d5ace7078d01ae86932c3c64b27ad14e24cf8` |
| rubric hash | `a02e0531b3d78590c66d32e76eba170d2e0400e3e4a1c60436f4f5c2c8e93b21` |
| model-run commit | `95622f0aead87187c6410ec0a38ba94cb2866dee` |
| freeze basis commit | `9d292221b0cdefa1d433d7c821d219d1c246581e` |

## Frozen Baseline Comparator

The held-out test must also use the strict-schema baseline comparator.

| Field | Value |
| --- | --- |
| baseline version | `baseline strict-schema` |
| skill version id | `skill_baseline_v1` |
| prompt template id | `grade_standard_v1_strict_schema` |
| prompt source | `experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_standard_v1_strict_schema.txt` |
| prompt SHA-256 | `8fe0b9bb69d56109b2bbecfcdd6ca05ebe2ae9dff76efe610ecfde0d831cfa5e` |
| development packet | `Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1` |
| development packet SHA-256 | `e556b8f12cc32e975c6a27545efeddb2891cb85fa6d3060f57dec3d6abf92601` |

## Development Evidence

The freeze decision is based only on the development split, not the held-out test
split.

| Metric | Baseline | Candidate v2 | Decision signal |
| --- | ---: | ---: | --- |
| exact agreement | 0.7917 | 0.8542 | candidate better |
| macro accuracy | 0.7917 | 0.8542 | candidate better |
| subquestion MAE | 0.2214 | 0.1042 | candidate better |
| total score MAE | 2.1563 | 0.7500 | candidate better |
| within 1 point rate | 0.3750 | 0.7500 | candidate better |
| severe error rate | 0.3750 | 0.1250 | candidate better |
| mean signed error | -0.1797 | -0.0625 | candidate less biased |

Paired student bootstrap for candidate minus baseline exact agreement:

- mean difference: `0.0625`
- 95% interval: `[0.0104, 0.1458]`

Development evidence files:

- `DEV-METRICS-STRICT-SCHEMA.md`
- `note.typ`
- `note.pdf`

## Freeze Rules

After this freeze record:

1. Do not edit
   `experiments/records/physics-week9-baseline-candidate-v2-run/prompts/grade_candidate_v2_strict_schema.txt`
   before held-out evaluation.
2. Do not edit the strict-schema baseline prompt before held-out evaluation.
3. Do not inspect held-out model outputs for the purpose of revising candidate
   v2.
4. If held-out results reveal a problem, record the result first, then create a
   new branch and candidate version for later work.
5. Keep all real student data and model outputs under ignored `Data/` or the
   approved private data repository.

## Allowed Next Steps

The next work can prepare the held-out test run without changing prompts:

1. Build strict-schema baseline held-out text packet. Done in
   `HELD-OUT-PREFLIGHT.md`.
2. Build strict-schema candidate v2 held-out text packet. Done in
   `HELD-OUT-PREFLIGHT.md`.
3. Dry-run both held-out packets with `deepseek-test`. Passed, 18/18 for both
   packets.
4. Record packet hashes and dry-run validation. Done in
   `HELD-OUT-PREFLIGHT.md`.
5. Ask the project user to execute the real DeepSeek held-out runs from
   PowerShell with `DEEPSEEK_API_KEY` set locally.
6. Evaluate held-out metrics and update the Typst/PDF note.

Do not evaluate held-out metrics unless both real held-out runs pass validation.

## Limitations

- The freeze decision is based on only 8 development students.
- This is a text-only workflow and does not evaluate multimodal image grading.
- The transcript source is pilot-derived automatic text.
- The gold reference is a single primary-rater reference, not an adjudicated
  multi-rater gold standard.
- Physics Week 9 remains a pilot and does not prove cross-course generalization.
