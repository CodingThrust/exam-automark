#set document(
  title: "LLM-Based Paper Marking and Automated Grading",
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
#let red = rgb("#a33b2f")

#let pill(body) = box(fill: soft, stroke: line, inset: (x: 7pt, y: 4pt), radius: 3pt, body)
#let callout(title, body, fill-color: soft) = box(fill: fill-color, stroke: line, inset: 9pt, radius: 4pt, width: 100%)[
  #strong[#title] #body
]
#let verdict(label, fill-color) = box(fill: fill-color, stroke: line, inset: (x: 5pt, y: 2.5pt), radius: 3pt)[#text(size: 7.4pt)[#label]]

#align(center)[
  #text(size: 19pt, weight: "bold", fill: ink)[LLM-Based Paper Marking and Automated Grading]
]

#align(center)[
  #pill[Research background for exam-automark evaluation design]
]

#v(4pt)

#callout("Scope.", [
  This survey covers automated grading of constructed responses: essays, short
  answers, programming submissions, mathematical work, and handwritten exam
  responses. Multiple-choice benchmark scoring is out of scope except where it
  informs evaluation methodology.
])

#callout("sci-brain run.", [
  Source set built on 2026-07-19 with the installed sci-brain `/survey` and
  `/download-ref` workflow. The active KB is `.knowledge/`: 18 grading-focused
  references in this report, 32 total BibTeX entries across both surveys,
  32 downloaded arXiv PDFs, and 32 rendered local markdown files. No grading
  model calls were run.
], fill-color: green)

= Abstract

Automated grading has evolved from feature-based essay scoring to transformer
models, short-answer grading benchmarks, LLM-as-a-judge protocols, and
vision-capable LLMs for handwritten mathematical work
@haller_2022_survey @meyer_2024_asag @liu_2023_g @caraeni_2024_evaluating.
The strongest recent theme is not full replacement of human graders; it is
carefully constrained human-in-the-loop automation
@schneider_2023_towards @vanhoyweghen_2026_human. LLMs can reduce workload,
draft feedback, expose rubric ambiguity, and support consistency checks, but
the literature repeatedly raises concerns about calibration, bias, grading
difficulty, prompt sensitivity, OCR or transcription failure, and high-stakes
validity @wang_2023_large @lundgren_2024_large @levine_2026_automated. For exam-automark, the
most useful pattern is a reproducible, rubric-item-level framework with
anonymized data boundaries, strict output schemas, severe-error metrics, and
teacher review gates.

= Background

Automated essay scoring (AES) is often traced to Ellis B. Page's Project Essay
Grade work in the 1960s, but this historical citation should be rechecked before
use in a formal paper. Modern AES has moved through feature engineering,
statistical models, neural architectures, transformers, and feedback-oriented
systems @jong_2023_review. A parallel line, automatic short-answer grading
(ASAG), focuses on short constructed responses where semantic equivalence,
partial credit, and rubric granularity matter more than global writing quality
@suzen_2018_automatic @haller_2022_survey.

LLMs change the design space because the same model can read a rubric, compare a
student answer with reference material, produce a score, and explain a decision.
That flexibility is also the main risk. LLM grading is prompt-sensitive,
non-deterministic unless tightly configured, prone to surface fluency effects,
and often hard to calibrate against human raters. Several recent studies find
promising performance in constrained formative settings, while others report
that direct replacement of human grading is not yet reliable.

exam-automark sits in the practical middle. It does not need a grand claim that
LLMs can grade all papers. It needs a reproducible framework for testing whether
a specific grading skill, rubric, model, and data preparation pipeline can match
teacher marks on a bounded assessment while flagging cases that require human
review.

= Taxonomy Of Method Categories

== Classical Automated Essay Scoring

Classical AES systems score longer essays using features such as length,
grammar, syntax, vocabulary, organization, and prompt relevance. Recent surveys
on AES feedback and argumentative writing show a shift from holistic scores
toward diagnostic feedback and trait-level evaluation
@wang_2022_automated @jong_2023_review. The lesson for
exam-automark is caution: surface-quality features can correlate with marks but
may miss conceptual correctness, originality, and domain-specific reasoning.

== Automatic Short-Answer Grading

ASAG systems grade brief natural-language answers. Older approaches use word
overlap, semantic similarity, clustering, textual entailment, and supervised
classifiers @suzen_2018_automatic. Deep-learning surveys organize recent work
around embeddings, sequential models, and attention-based transformer methods
@haller_2022_survey. Several papers emphasize that hand-engineered features
still complement neural representations, especially when datasets are small.
Feedback-oriented ASAG work also treats the explanation of a mark as part of the
grading output rather than a separate afterthought @aggarwal_2024_i.

This is highly relevant to exam-automark because many exam subquestions are
short constructed responses with partial-credit rubrics. It suggests that a
grading skill should not rely only on an LLM's generic judgment; it should also
use rubric clauses, reference solutions, item-level labels, and deterministic
post-checks.

== LLM Rubric Graders

LLM grading studies ask models such as GPT-4, GPT-4o, ChatGPT, or Llama to score
student answers or essays from rubrics. Some work reports near-human agreement
in narrow formative contexts; other work finds weak reliability, conservative or
harsh grade distributions, and poor alignment with nuanced human grading
criteria @schneider_2023_towards @henkel_2023_can @mansour_2024_can
@lundgren_2024_large. Multi-trait specialization for AES decomposes writing
quality into separate traits, which is analogous to rubric-item grading
@lee_2024_unleashing.

For exam-automark, direct LLM graders should be treated as candidate graders
whose outputs must be validated, not as authoritative scorers.

== LLM-as-a-Judge And Evaluation Bias

LLM-as-a-judge work is not education-specific, but it supplies useful warnings.
G-Eval and MT-Bench show that strong LLM judges can approximate human
preferences on some open-ended tasks @liu_2023_g @zheng_2023_judging. FairEval
and related work document position bias, verbosity bias, and self-enhancement
bias @wang_2023_large. In grading, analogous biases could appear as preference
for longer solutions, polished language, or answers that resemble the model's
own reasoning style.

== Human-In-The-Loop And Guideline Optimization

Recent grading frameworks increasingly include human review. GradeOpt uses
additional LLM agents to reflect on grading errors and optimize guidelines
@chu_2024_llm. Human-in-the-loop handwritten-math workflows combine scanning,
anonymization, multi-pass scoring, consistency checks, and mandatory human
verification @vanhoyweghen_2026_human. These
are the closest cousins to exam-automark: they optimize workload and consistency
without pretending that model output is final in all cases.

== Multimodal And Handwritten Exam Grading

Vision-capable LLMs make handwritten exam marking possible in principle, but the
literature is still early. Studies on handwritten mathematics identify
transcription failures, image quality, equivalent-expression handling, and
rubric misapplication as major error modes @caraeni_2024_evaluating
@levine_2026_automated. This matches exam-automark's need to
separate document parsing quality from grading-skill quality.

= Representative Work

#table(
  columns: (1.15fr, 0.7fr, 1.25fr, 1.55fr, 1.6fr),
  stroke: line,
  inset: (x: 5pt, y: 4pt),
  [#strong[Work]], [#strong[Year]], [#strong[Setting]], [#strong[Finding or role]], [#strong[Implication]],
  [Project Essay Grade / Page], [1960s], [Essay scoring], [Early AES history; #text(fill: red)[needs verification] for exact bibliographic details], [Useful historical context, not direct design evidence.],
  [Suzen et al. @suzen_2018_automatic], [2018], [Short-answer grading], [Text mining and clustering for short answers and feedback], [Simple similarity features can remain useful baselines.],
  [Haller et al. @haller_2022_survey], [2022], [ASAG survey], [Deep-learning ASAG from embeddings to transformers], [Combine learned representations with engineered features and rubric context.],
  [Wang et al. @wang_2022_automated], [2022], [Argumentative writing survey], [Trait-focused evaluation beyond holistic score], [Rubric-item feedback is more useful than only total marks.],
  [Jong et al. @jong_2023_review], [2023], [AES feedback review], [Feedback is central for AES as a learning tool], [Feedback quality needs separate evaluation.],
  [Henkel et al. @henkel_2023_can], [2023], [LLM short-answer reading comprehension], [GPT-4 reached high agreement on a novel formative dataset], [Promising under constrained settings with expert labels.],
  [Schneider et al. @schneider_2023_towards], [2023], [LLM short textual answers], [LLMs can support validation but need human oversight], [Use LLM graders as complementary evidence, not final authority.],
  [Lee et al. @lee_2024_unleashing], [2024], [Zero-shot essay scoring], [Multi Trait Specialization decomposes scoring into traits], [Map essay traits to rubric-item scoring.],
  [Mansour et al. @mansour_2024_can], [2024], [LLM AES], [Prompt choice is model- and task-dependent; feedback may be useful], [Prompt experiments need frozen metrics and held-out tests.],
  [Aggarwal et al. @aggarwal_2024_i], [2024], [Short-answer feedback], [Automatic grading is paired with student-facing feedback], [Feedback quality needs its own review target.],
  [GradeOpt @chu_2024_llm], [2024], [LLM short-answer grading], [Multi-agent guideline optimization improves behavior alignment], [Relevant to automated grading-skill improvement.],
  [ASAG2024 @meyer_2024_asag], [2024], [Combined ASAG benchmark], [LLM methods reach high scores but remain below human performance], [Benchmark generalization remains unresolved.],
  [Caraeni et al. @caraeni_2024_evaluating], [2024], [Handwritten math exams], [Rubrics improve GPT-4o alignment, but accuracy remains too low for deployment], [Multimodal grading needs review gates.],
  [Vanhoyweghen et al. @vanhoyweghen_2026_human], [2026], [Handwritten math, human-in-loop], [Workflow reduced grading time while requiring verification], [Closest operational pattern for exam-automark.],
  [Levine et al. @levine_2026_automated], [2026], [Vision-capable LLM handwritten math], [Many errors attributed to transcription rather than rubric application], [Separate OCR/transcription evaluation from grading evaluation.],
)

= Comparison Table

#table(
  columns: (1fr, 1.15fr, 1.15fr, 1.35fr, 1.35fr),
  stroke: line,
  inset: (x: 5pt, y: 4pt),
  [#strong[Approach]], [#strong[Best fit]], [#strong[Required data]], [#strong[Strengths]], [#strong[Risks]],
  [Classical AES], [Long essays and writing traits], [Large scored essay sets], [Efficient, stable, interpretable features @jong_2023_review], [Can reward length or fluency over content.],
  [Traditional ASAG], [Short typed answers], [Reference answers and scored examples], [Strong baselines; transparent similarity features @suzen_2018_automatic], [Question-specific; struggles with rare valid paraphrases.],
  [Transformer ASAG], [Short answer datasets], [Labeled responses per task], [Better semantic representations @haller_2022_survey], [Small-data overfitting and domain transfer issues.],
  [Direct LLM rubric grader], [Low-stakes formative or pilot grading], [Rubric, reference solution, examples], [Fast to prototype; can produce feedback @henkel_2023_can @mansour_2024_can], [Prompt sensitivity, bias, hallucination, calibration drift.],
  [LLM-as-a-judge protocol], [Comparing outputs or feedback variants], [Human preferences or rubrics], [Scalable evaluation aid @liu_2023_g @zheng_2023_judging], [Position, verbosity, and self-preference biases @wang_2023_large.],
  [Guideline optimizer], [Improving grading instructions], [Error traces and human labels], [Can discover rubric ambiguity and revise criteria @chu_2024_llm], [Needs strict audit trail to avoid self-justifying rules.],
  [Multimodal LLM grader], [Scanned handwritten exams], [Images, transcriptions, rubric labels], [Can unify reading and marking @caraeni_2024_evaluating @levine_2026_automated], [Image quality, OCR, formula equivalence, and review burden.],
)

= Relevance To exam-automark

#grid(
  columns: (1fr, 1fr),
  gutter: 8pt,
  callout("Design direction.", [
    exam-automark should evaluate grading as a pipeline: document preparation,
    evidence extraction, rubric-item scoring, schema validation, feedback, and
    audit. Each stage needs its own failure categories.
  ], fill-color: green),
  callout("Deployment stance.", [
    The literature supports LLM-assisted grading with human verification more
    strongly than fully autonomous high-stakes grading. Severe-error flags and
    manual review are design requirements, not optional polish.
  ], fill-color: redsoft),
)

Concrete lessons for the repository:

- Store only anonymized, reproducible experiment metadata in Git; keep raw
  submissions outside the public repo.
- Use item-level metrics, not just total-score correlation. Exact agreement,
  adjacent agreement, total MAE, severe-error rate, bias, and per-question
  deltas should all be reported.
- Separate parsing/OCR errors from rubric errors. A vision model can fail before
  the grading skill has a fair chance.
- Require strict output schemas and validation before using any model output in
  metrics.
- Compare against human-human agreement when possible. A model-human mismatch is
  more meaningful when human rater reliability is known.
- Use teacher review for ambiguous or high-impact cases, especially where a
  partial-credit decision changes the pass/fail or letter-grade boundary.
- Evaluate feedback separately from marks. A correct score with misleading
  feedback is still unsafe for learners.

= Open Problems

- #strong[Validity.] Agreement with historical marks does not prove the system
  measures the intended construct, especially for open-ended reasoning.
- #strong[Fairness.] LLMs may favor fluent writing, standard dialects, longer
  answers, or model-like reasoning even when a rubric should reward substance.
- #strong[Human label noise.] Single-rater grades can be inconsistent. Automated
  systems should not be trained to reproduce unexamined noise.
- #strong[Ambiguous partial credit.] Rubrics often leave edge cases unresolved.
  These cases should become teacher-review flags and rubric revisions.
- #strong[Benchmark generalization.] ASAG2024-style combined benchmarks help,
  but course-specific rubrics and handwriting still challenge transfer.
- #strong[Multimodal robustness.] Image capture, cropping, handwriting, formulas,
  tables, diagrams, and units all create non-text failure modes.
- #strong[Feedback safety.] LLMs can generate confident explanations for wrong
  scores. Feedback needs factual checks against the submitted work.
- #strong[Operational audit.] Every grade should be traceable to model version,
  prompt packet, rubric version, input hash, validation result, and reviewer
  decision.

= References

Generated from the sci-brain KB BibTeX file copied from
`.knowledge/references.bib`.
Historical Page/PEG context remains `needs verification` because it is not part
of the verified arXiv/Semantic Scholar KB.

#bibliography(bib-path, style: "ieee")
