#set document(
  title: "Automated Skill Optimization for LLM Grading Systems",
  author: "exam-automark research background survey",
)
#set page(paper: "a4", margin: (x: 1.45cm, y: 1.25cm), numbering: "1")
#set text(font: "New Computer Modern", size: 9.2pt, fill: rgb("#17212b"))
#set heading(numbering: "1.")
#let bib-path = "references.bib"

#let ink = rgb("#17212b")
#let muted = rgb("#5f6c76")
#let line = rgb("#d8e4e8")
#let soft = rgb("#eef6f7")
#let soft2 = rgb("#fff7e3")
#let green = rgb("#edf5ef")
#let redsoft = rgb("#f9eeee")
#let blue = rgb("#256d85")
#let gold = rgb("#8a6500")
#let red = rgb("#a33b2f")

#let pill(body) = box(fill: soft, stroke: line, inset: (x: 7pt, y: 4pt), radius: 3pt, body)
#let callout(title, body, fill-color: soft) = box(fill: fill-color, stroke: line, inset: 9pt, radius: 4pt, width: 100%)[
  #strong[#title] #body
]
#let status(label, fill-color) = box(fill: fill-color, stroke: line, inset: (x: 5pt, y: 2.5pt), radius: 3pt)[#text(size: 7.4pt)[#label]]

#align(center)[
  #text(size: 19pt, weight: "bold", fill: ink)[Automated Skill Optimization for LLM Grading Systems]
]

#align(center)[
  #pill[Research background for exam-automark grading-skill improvement]
]

#v(4pt)

#callout("Scope.", [
  This survey treats a grading skill as a versioned, executable instruction
  artifact: rubric text, prompt template, schema, examples, feedback rules,
  evaluation scripts, and release gates. The practical question is how much of
  skill improvement can be automated while preserving reproducibility,
  auditability, and teacher review.
])

#callout("sci-brain run.", [
  Source set built on 2026-07-19 with the installed sci-brain `/survey` and
  `/download-ref` workflow. The active KB is `.knowledge/`: 14 optimization
  references in this report, 32 total BibTeX entries across both surveys,
  32 downloaded arXiv PDFs, and 32 rendered local markdown files. No grading
  model calls were run.
], fill-color: green)

= Abstract

Automated skill optimization sits between prompt engineering, program synthesis,
and evaluation-driven software engineering. The relevant literature does not yet
use one stable vocabulary: papers speak about automatic prompt engineering,
prompt optimization, language-model programs, textual gradients, reflection,
self-refinement, lifelong skill libraries, and multi-agent optimization
@shin_2020_eliciting @zhou_2022_large @pryzant_2023_automatic
@khattab_2023_dspy @yuksekgonul_2024_textgrad. For
exam-automark, the useful abstraction is an optimization loop over a frozen
grading artifact. The loop proposes a change, evaluates it on a development
split with rubric-level metrics, records the trace, and promotes the change only
through a human-readable review gate. This report organizes automated approaches
into five method families and identifies how they can inform future grading-skill
work without running models in this survey.

= Background

LLM application behavior is highly sensitive to instructions, examples,
schemas, retrieval context, tool use, and output validation. Manual prompt
engineering can produce strong local improvements, but it is hard to reproduce:
small prompt edits are rarely tied to testable hypotheses, and improvements on
one batch can regress on another batch. Grading makes this problem sharper
because a "better" skill must satisfy several objectives at once: exact
agreement with reference marks, low severe-error rate, stable feedback, strict
JSON validity, fairness across questions and student groups, and interpretable
partial-credit decisions.

The optimization literature offers a useful shift: prompts and skills can be
treated as artifacts to search, compile, critique, and version. Early work such
as AutoPrompt searched token triggers for masked language models
@shin_2020_eliciting. Later systems such as APE, ProTeGi/APO, and OPRO use LLMs
to propose or edit natural-language instructions and select candidates with task
metrics @zhou_2022_large @pryzant_2023_automatic @yang_2023_large. DSPy and
MIPRO generalize this from one prompt to multi-stage language-model programs
@khattab_2023_dspy @opsahlong_2024_optimizing. TextGrad and GEPA push the idea
further by using natural-language feedback as an optimization signal over
components of compound AI systems @yuksekgonul_2024_textgrad
@agrawal_2025_gepa.

For exam-automark, this is not simply a way to "make a prompt better." It is a
way to make skill revisions empirical. A grading-skill optimizer should leave a
record of what changed, which rubric failures motivated the change, which
development examples improved or regressed, and why a teacher or researcher
accepted the update.

= Taxonomy Of Method Categories

== Discrete Prompt And Instruction Search

These methods search over natural-language strings. A generator proposes
candidate instructions, a target model applies them, and a metric ranks the
results. The main strength is accessibility: the optimized artifact remains
readable by humans. APE frames instructions as programs and asks an LLM to
propose candidate instructions, then evaluates candidates on task examples
@zhou_2022_large. ProTeGi/APO uses natural-language "gradients" derived from
errors and edits the prompt in the opposite semantic direction
@pryzant_2023_automatic. OPRO treats the LLM itself as an optimizer that sees
previous solutions and scores, then proposes new solutions @yang_2023_large.

For grading skills, this family maps naturally to prompt-template edits, rubric
wording, allowed evidence types, and output-schema instructions. The core risk
is overfitting to a small development set or optimizing a superficial metric
while making feedback worse.

== Continuous And Soft Prompt Optimization

Soft prompt methods learn embeddings or prefix vectors while keeping the base
model frozen. Prefix-tuning and prompt tuning are parameter-efficient, scalable
alternatives to full fine-tuning @li_2021_prefix @lester_2021_power. They are less attractive for exam-automark's
current skill work because the resulting artifact is not easily inspectable by a
teacher and is model-specific. They are still useful as a conceptual baseline:
they show that prompt-like adaptation can be optimized directly when labels and
model access are available.

== Language-Model Program Optimizers

DSPy treats LM applications as programs made from declarative modules and
optimizes those modules against a metric @khattab_2023_dspy. MIPRO extends this
to multi-stage programs by optimizing both instructions and demonstrations under
downstream metrics, even when module-level labels are absent
@opsahlong_2024_optimizing. DSPy Assertions adds computational constraints that
can be used at compile time and inference time @singhvi_2023_dspy.

This is the most directly relevant family for exam-automark once grading is
expressed as a pipeline: parse submission, extract evidence, apply rubric,
validate schema, generate feedback, and audit high-risk cases. The optimizer can
target the whole pipeline while still recording which module changed.

== Textual Gradients And Reflective Evolution

TextGrad uses natural-language feedback as a form of automatic differentiation
over variables in a computation graph @yuksekgonul_2024_textgrad. GEPA uses
reflection over trajectories, prompt mutation, and Pareto-style selection to
improve compound systems with fewer rollouts than reinforcement learning
baselines @agrawal_2025_gepa. These methods are
especially relevant when failures are easier to explain in language than to
encode as scalar gradients.

For grading, textual feedback can encode why an item was wrong: hallucinated
student work, ignored rubric clause, over-penalized equivalent expression, or
invalid JSON. The optimizer can then propose targeted prompt edits. The danger
is black-box reflection: if the optimizer's critique is not tied to concrete
examples and metrics, it can create persuasive but ungrounded changes.

== Self-Refinement, Agent Memory, And Skill Libraries

Self-Refine shows how a model can iteratively critique and refine its own output
without additional training @madaan_2023_self. Reflexion stores verbal lessons
from prior trials @shinn_2023_reflexion. Voyager uses an ever-growing skill
library of executable code, an automatic curriculum, and feedback-driven repair
in Minecraft @wang_2023_voyager. These systems are not
grading optimizers, but they show a pattern exam-automark can borrow: convert
successful tactics into reusable, versioned skills.

For exam-automark, the analogous artifact is a skill library of rubric-handling
patterns, evidence extraction patterns, schema repair patterns, and known
failure-mode mitigations. The library should be curated and tested rather than
allowed to grow automatically without review.

= Representative Work

#table(
  columns: (1.15fr, 0.7fr, 1.35fr, 1.55fr, 1.55fr),
  stroke: line,
  inset: (x: 5pt, y: 4pt),
  [#strong[Work]], [#strong[Year]], [#strong[Optimized artifact]], [#strong[Signal]], [#strong[Use for grading skills]],
  [AutoPrompt @shin_2020_eliciting], [2020], [Discrete trigger tokens for masked language models], [Gradient-guided search], [Historical baseline for automatic prompt construction; less suitable for readable teacher-facing skills.],
  [Prefix-tuning @li_2021_prefix], [2021], [Continuous prefix vectors], [Backpropagation on labeled data], [Useful conceptually, but weak auditability for teacher review.],
  [Prompt tuning @lester_2021_power], [2021], [Soft prompt embeddings], [Backpropagation on labeled examples], [Model-specific adaptation; not ideal for repo-stored skill text.],
  [APE @zhou_2022_large], [2022], [Natural-language instructions], [Candidate generation and task scoring], [Direct analogue for searching rubric prompts and output instructions.],
  [Self-Refine @madaan_2023_self], [2023], [Generated output at inference time], [Self-feedback and iterative revision], [Can repair feedback or scoring rationales, but must be bounded by schema checks.],
  [Reflexion @shinn_2023_reflexion], [2023], [Agent memory and future behavior], [Verbal reinforcement from task feedback], [Useful for storing failure-mode lessons across grading trials.],
  [ProTeGi/APO @pryzant_2023_automatic], [2023], [Natural-language prompts], [Textual gradients, beam search, bandits], [Strong fit for dev-set prompt revision with severe-error metrics.],
  [OPRO @yang_2023_large], [2023], [Prompt or solution candidates], [LLM proposes new candidates from prior scores], [Simple optimizer loop, but vulnerable to metric gaming.],
  [DSPy @khattab_2023_dspy], [2023], [LM pipeline modules], [Compiler optimizes toward metrics], [Best architectural fit for reproducible grading pipelines.],
  [MIPRO @opsahlong_2024_optimizing], [2024], [Instructions and demonstrations for LM programs], [Downstream metric with surrogate optimization], [Promising for multi-stage rubric/evidence/feedback pipelines.],
  [TextGrad @yuksekgonul_2024_textgrad], [2024], [Variables in compound AI systems], [Natural-language feedback as gradient], [Can turn rubric-item errors into targeted prompt updates.],
  [GEPA @agrawal_2025_gepa], [2025], [Prompts in compound systems], [Reflective trajectory analysis and Pareto search], [Relevant future direction; needs careful trace auditing in grading.],
)

= Comparison Table

#table(
  columns: (1.1fr, 1.15fr, 1.15fr, 1.4fr, 1.4fr),
  stroke: line,
  inset: (x: 5pt, y: 4pt),
  [#strong[Category]], [#strong[Required assets]], [#strong[What changes]], [#strong[Strengths]], [#strong[Risks]],
  [Discrete instruction search], [Dev examples, metric, model API], [Prompt text, rubric wording, examples], [Readable diffs; easy to version; fast experiments @zhou_2022_large @pryzant_2023_automatic], [Overfits dev set; may optimize for score while harming explanation quality.],
  [Soft prompt tuning], [Labeled data and model training access], [Embedding vectors or prefix parameters], [Parameter-efficient; strong when labels are abundant @li_2021_prefix @lester_2021_power], [Opaque artifact; model lock-in; hard to inspect or merge as a skill.],
  [Program optimizers], [Pipeline modules, dev metric, validation scripts], [Module prompts, demos, sometimes control flow], [Optimizes end-to-end behavior; matches exam-automark architecture @khattab_2023_dspy @opsahlong_2024_optimizing], [Credit assignment is hard; costs can grow quickly.],
  [Textual gradients], [Failure traces, critique prompt, candidate evaluator], [Natural-language prompt/code variables], [Turns qualitative errors into actionable edits @yuksekgonul_2024_textgrad @agrawal_2025_gepa], [Critiques may hallucinate; requires example-grounded evidence.],
  [Reflection and skill libraries], [Episode traces, success criteria, retrieval scheme], [Memory, reusable skills, repair tactics], [Accumulates reusable know-how; supports lifelong improvement @madaan_2023_self @shinn_2023_reflexion @wang_2023_voyager], [Uncurated memory can amplify stale or wrong tactics.],
)

= Relevance To exam-automark

#grid(
  columns: (1fr, 1fr),
  gutter: 8pt,
  callout("Immediate use.", [
    Treat every grading skill as a versioned artifact with a frozen development
    split, an evaluation command, and a release note. Candidate changes should
    be judged by exact agreement, total-score MAE, within-tolerance rate,
    severe-error rate, per-question deltas, schema validity, and feedback
    quality.
  ], fill-color: green),
  callout("Do not automate yet.", [
    Do not let an optimizer update production skill text from private data
    without a recorded prompt packet, anonymized examples, human review, and
    held-out evaluation. Automatic proposals can draft changes; promotion must
    remain auditable.
  ], fill-color: redsoft),
)

The repo already has useful anchors: experiment records under
`experiments/records/`, frozen skill snapshots under `experiments/skill_versions/`,
prompt templates, data inventories, and Typst notes. The optimization loop can
reuse those anchors:

- Build a small public or anonymized development set with rubric-item labels.
- Record each candidate skill revision as a patch against a skill snapshot.
- Run a deterministic evaluator that reports aggregate and per-item metrics.
- Generate a compact failure report showing which rubric clauses changed.
- Require a teacher or researcher to accept, reject, or edit the candidate.
- Only then freeze a new skill version and test on held-out data.

In this framing, automated skill optimization becomes less like ad hoc prompt
tuning and more like CI for grading behavior. The metric is not "did the prompt
look better?" but "did this version reduce validated grading errors without
introducing unacceptable regressions?"

= Open Problems

- #strong[Reward design.] A scalar score can hide dangerous behavior. A skill
  that raises exact agreement but increases severe errors should not be promoted.
- #strong[Small and noisy data.] Real course data is scarce, private, and often
  single-rater. Optimizers need uncertainty estimates and teacher adjudication.
- #strong[Rubric ambiguity.] Some failures reveal ambiguous rubrics, not model
  errors. The optimizer should flag these rather than silently patching around
  them.
- #strong[Generalization.] A prompt optimized for Physics Week 9 may not transfer
  to DSAA, linear algebra, or multimodal submissions.
- #strong[Multimodal evidence.] Image quality, OCR, formula parsing, and diagram
  interpretation create failure modes that text-only prompt optimizers do not
  cover.
- #strong[Traceability.] Every proposed change needs a source: examples,
  failures, metric deltas, and the exact model/tool configuration that produced
  the proposal.
- #strong[Cost and reproducibility.] Search loops can consume many model calls.
  A reproducible framework needs budgets, cached traces, and stable evaluation
  commands.

= References

Generated from the sci-brain KB BibTeX file copied from
`.knowledge/references.bib`.

#bibliography(bib-path, style: "ieee")
