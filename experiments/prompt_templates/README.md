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

When an experiment is planned, each template file is hashed into `plan.json`.
When an experiment is run, the exact prompt text is copied into each prompt
packet as `prompt.txt`; the packet manifest records the prompt hash.

Do not place answer keys, reference scores, identity maps, previous model
outputs, or raw student files in this directory.
