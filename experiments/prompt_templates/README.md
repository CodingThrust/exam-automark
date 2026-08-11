# Prompt Templates

This directory stores reusable model-facing prompt text for reproducible
grading experiments.

- `transcribe_standard_v1.txt`: converts visible multimodal or text inputs into
  per-question transcripts.
- `grade_standard_v1.txt`: grades anonymous work against `course.json` and
  `rubric.json`.
- `grade_candidate_v2.txt`: candidate grading prompt aligned with
  `skill_candidate_v2`; keeps evidence-first grading, frozen rubric discipline,
  confidence/flags, second-pass review, and total checks while using the
  teacher-confirmed partial-credit rule: no 0.25-point scores; correct answer
  plus roughly correct process receives full credit; wrong answers receive
  careful process-credit review.
- `grade_candidate_v3.txt`: generic, concept-aware candidate prompt aligned
  with `skill_candidate_v3`; records key-term, concept, and relation evidence;
  assigns one evidence state per rubric element; permits limited keyword-only
  credit and semantic equivalents; prevents duplicate credit; and applies score
  bands and material-error caps only as upper bounds.
- `grade_candidate_v3_1.txt`: minimal development calibration aligned with
  `skill_candidate_v3_1_r2`; keeps candidate-v3 and calculation behavior while
  adding cap-locality, contradiction-locality, key-term semantics, and
  indirect-construction rules. The current r2 prompt also adds open-ended
  adequacy so open-ended answers are scored against the task requirement rather
  than a closed standard-answer whitelist.
- `grade_candidate_v4.txt`: historical cross-course candidate. It preserves the
  evidence-first, locality, semantic-equivalence, official-style-adequacy, and
  second-pass safeguards from the candidate line while removing inherited
  named-question and subject-specific rules. It begins with question-type
  classification, including true/false, mixed calculation-and-short-answer,
  proof, construction, and diagram/representation work. Course-specific point
  values, answer-only credit, and calibration rules must remain in the frozen
  course rubric and packet.
- `grade_candidate_v5.txt`: current cross-course candidate. It retains v4's
  evidence-first, question-type, locality, alternative-method, and second-pass
  safeguards while explicitly making the complete anonymous submission the
  scoring unit: all ordered pages for one student are assembled before any
  question is scored; a page is never graded or summed independently. Missing
  page/question flags remain course-frozen evidence, not a license to infer
  unseen work.
- `grade_candidate_v5_1.txt`: successor to v5. It retains whole-submission
  assembly while making each declared `question_id` the smallest independently
  scoreable leaf: separately allocated subparts are scored separately across
  all ordered pages, while undeclared subparts are never invented.

When an experiment is planned, each template file is hashed into `plan.json`.
When an experiment is run, the exact prompt text is copied into each prompt
packet as `prompt.txt`; the packet manifest records the prompt hash.

Do not place answer keys, reference scores, identity maps, previous model
outputs, or raw student files in this directory.
