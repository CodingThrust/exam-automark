# exam-automark sci-brain literature surveys

Built by `/survey` on 2026-07-19, using WebSearch-style discovery because no
arXiv, Semantic Scholar, CrossRef, paper-search, or Sci-Hub MCP server was
available in this Codex session. Metadata, BibTeX, arXiv PDFs, and rendered
markdown were then populated by the installed sci-brain `download-ref` helpers.

## Field landscape: automated skill and prompt optimization

### Discrete prompt and instruction search

Automatic prompt construction begins with discrete search over tokens or
instructions. AutoPrompt searches trigger tokens for masked language models
[@shin_2020_eliciting]. APE reframes natural-language instructions as programs
that can be proposed and evaluated by language models [@zhou_2022_large].
ProTeGi/APO introduces natural-language gradients, beam search, and bandit
selection for prompt edits [@pryzant_2023_automatic]. OPRO treats language
models themselves as optimizers that propose new candidates from prior scores
[@yang_2023_large].

### Continuous prompt adaptation

Prefix-tuning and prompt tuning show that prompt-like adaptation can be learned
as continuous vectors while freezing most model weights [@li_2021_prefix;
@lester_2021_power]. These methods are important historically, but they are less
aligned with exam-automark's need for teacher-readable, version-controlled
grading skills.

### Language-model program optimization

DSPy treats LM applications as declarative pipelines that can be compiled
against metrics [@khattab_2023_dspy]. DSPy Assertions adds constraints for
self-refining pipelines [@singhvi_2023_dspy]. MIPRO optimizes instructions and
demonstrations for multi-stage language-model programs [@opsahlong_2024_optimizing].
This family is closest to exam-automark's likely architecture: evidence
extraction, rubric-item scoring, schema validation, feedback, and audit can be
optimized as separate but coupled modules.

### Textual gradients, reflection, and skill libraries

Self-Refine and Reflexion show how language feedback and memory can improve
future generations without parameter updates [@madaan_2023_self;
@shinn_2023_reflexion]. Voyager demonstrates an executable skill library that
grows through environment feedback [@wang_2023_voyager]. TextGrad generalizes
textual feedback as gradients over variables in compound AI systems
[@yuksekgonul_2024_textgrad]. GEPA uses reflective trajectory analysis and
Pareto-style selection to evolve prompts in compound systems [@agrawal_2025_gepa].

## Field landscape: paper marking, exam marking, and LLM grading

### Essay and short-answer grading

Automatic short-answer grading combines text mining, semantic similarity, and
feedback generation [@suzen_2018_automatic]. Deep-learning ASAG work spans word
embeddings, sequence models, attention, and transformer representations
[@haller_2022_survey]. Automated argumentative-writing evaluation emphasizes
trait-level scoring and feedback, not only holistic marks [@wang_2022_automated;
@jong_2023_review].

### LLM rubric graders and short-answer scoring

LLM grading work tests whether rubric-conditioned models can grade short textual
answers and reading-comprehension responses [@schneider_2023_towards;
@henkel_2023_can]. Essay-scoring studies explore zero-shot and trait-specialized
LLM grading [@mansour_2024_can; @lee_2024_unleashing]. Recent short-answer
grading with feedback and combined ASAG benchmarks make evaluation more
standardized [@aggarwal_2024_i; @meyer_2024_asag]. GradeOpt explicitly optimizes
human-level grading guidelines with LLM agents [@chu_2024_llm].

### LLM-as-a-judge, bias, and human review

G-Eval and MT-Bench establish LLM-as-a-judge as a broad evaluation pattern
[@liu_2023_g; @zheng_2023_judging], but FairEval-style work documents evaluator
biases that are directly relevant to grading, such as positional or
presentation bias [@wang_2023_large]. Empirical comparisons between ChatGPT and
human graders underscore the need for human oversight and calibration
[@lundgren_2024_large].

### Multimodal and handwritten exam grading

Handwritten mathematical grading with GPT-4-class or vision-capable LLMs is a
newer branch. The most relevant studies for exam-automark evaluate rubrics,
image/transcription failures, and human-in-the-loop verification for handwritten
math assessments [@caraeni_2024_evaluating; @vanhoyweghen_2026_human;
@levine_2026_automated].

## Key open problems

1. **Metric design for grading-skill optimization.** Exact agreement alone can
   hide severe errors, invalid feedback, or question-level regressions. A useful
   optimizer must jointly track exact agreement, total-score error, severe-error
   rate, schema validity, and per-question deltas [@pryzant_2023_automatic;
   @opsahlong_2024_optimizing; @meyer_2024_asag].
2. **Grounded natural-language feedback.** Textual gradients and reflection are
   attractive for rubric errors, but they must be tied to concrete submissions,
   rubric clauses, and metric deltas rather than free-form self-justification
   [@yuksekgonul_2024_textgrad; @agrawal_2025_gepa].
3. **Human-review boundaries.** The literature supports LLM-assisted grading
   more strongly than fully autonomous high-stakes grading. Review gates are
   especially important for ambiguous partial credit, severe total-score errors,
   and handwritten/image failures [@schneider_2023_towards;
   @caraeni_2024_evaluating; @vanhoyweghen_2026_human].
4. **Generalization across courses and modalities.** Prompt and skill changes
   optimized for one course or text-only transcript may not transfer to DSAA,
   linear algebra, physics diagrams, or handwritten mathematics
   [@khattab_2023_dspy; @levine_2026_automated].
5. **Bias and calibration.** LLM graders may reward fluency, length, position,
   or model-like reasoning instead of rubric-grounded correctness
   [@wang_2023_large; @lundgren_2024_large].

## Key bottlenecks

1. **Small, private, noisy labels.** Course data is limited, sensitive, and often
   single-rater. Optimizers need uncertainty estimates and teacher adjudication.
2. **Reproducibility cost.** Search-based optimization and LLM grading both
   require many model calls unless the experiment framework caches prompts,
   traces, outputs, and metrics.
3. **Copyright and storage policy.** sci-brain can render full paper markdown,
   but exam-automark should not commit raw PDFs or full rendered paper text into
   the public repo. This run keeps those as local ignored caches.
4. **Multimodal preprocessing.** Image capture, OCR, formula parsing, and
   diagram interpretation create failures that must be separated from grading
   skill failures.
5. **Citation verification.** The active KB contains 32 Semantic Scholar/arXiv
   verified entries. Historical non-arXiv citations, such as Page/PEG, still
   require manual bibliographic verification before formal use.

