#set document(title: "DSAA3071 Week 5 Candidate-v3.2 Development Note")
#set page(margin: (x: 1.45cm, y: 1.15cm), numbering: "1")
#set text(font: "New Computer Modern", size: 9pt)
#import "@preview/cetz:0.5.2"

#let ink = rgb("#17212b")
#let accent = rgb("#256d85")
#let accent2 = rgb("#7a5c00")
#let good = rgb("#2d7a5b")
#let soft = rgb("#edf5f7")
#let line = rgb("#d8e4e8")
#let danger = rgb("#a33b2f")
#let muted = rgb("#63707a")
#let card(fill, body) = box(fill: fill, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[#body]
#let pill(body) = box(fill: soft, stroke: line, inset: (x: 7pt, y: 4pt), radius: 3pt, body)
#let metric-card(label, value, detail) = box(fill: soft, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[#text(size: 8pt, fill: accent)[#label]\ #text(size: 16pt, weight: "bold")[#value]\ #text(size: 7.6pt)[#detail]]

#align(center)[#text(size: 20pt, weight: "bold", fill: ink)[DSAA3071 Week 5 Candidate-v3.2 Development Note]]
#align(center)[#pill[Development split only. held-out not run; not a final accuracy claim.]]

#card(soft)[#strong[Technical summary.] C32 is the strongest development condition so far on aggregate MAE: question MAE improves from `R1=2.614` to `C32=2.557`, and total MAE improves from `R1=20.143` to `C32=14.429`. The result is promising but not final: Q8 remains the main unresolved error source, Q6 worsens versus R1, and C32 still has slightly higher severe-error rate than R1.]

== What Was Tested

#grid(columns: (1fr, 1fr, 1fr), gutter: 8pt,
  card(soft)[#strong[1. Same data] Seven anonymous development students from the reviewed DSAA3071 Week 5 transcript snapshot.],
  card(soft)[#strong[2. Same gold] Official per-question scores from `primary_scores.csv`; no official rationales are available.],
  card(soft)[#strong[3. New package] C32 uses `candidate-v3.2` plus `rubric_v2.json` to reduce over-harsh grading on Q7-Q9.],
)

This note covers `DSAA3071` / `week5_test` on branch `codex/dsaa3071-week5-dev-transcripts` at analysis commit `7f4e06a`.

== Reproducibility Anchors

#table(columns: (auto, 1fr), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Anchor]], [#strong[Value]],
  [Metric record], [`experiments/records/DSAA3071-week5-candidate-v31-dev-plan/dev-metrics-deepseek-c32.json`],
  [Run protocol], [`experiments/records/DSAA3071-week5-candidate-v31-dev-plan/RUN-PROTOCOL-C32.md`],
  [Prompt snapshot], [`experiments/records/DSAA3071-week5-candidate-v31-dev-plan/prompts/grade_candidate_v3_2_strict_schema.txt`],
  [Rubric], [`experiments/records/DSAA3071-week5-prep/rubric_v2.json`],
  [Skill snapshot], [`experiments/skill_versions/skill_candidate_v3_2.json`],
  [Data snapshot], [`95e744f5811d...`],
  [Text source hash], [`9f9be72bf088...`],
)

#pagebreak()

== Prompt And Skill Evolution

#card(soft)[#strong[Why this matters.] The DSAA3071 experiment is not only a model benchmark. It is a grading-skill development experiment for concept-heavy short-answer and proof questions. The conditions below show how the prompt/skill moved from standard-answer matching toward evidence-first, type-aware, and open-ended grading.]

#table(columns: (auto, 1.25fr, 1.65fr, 1.35fr), stroke: line, inset: (x: 5pt, y: 3.7pt),
  [#strong[Cond.]], [#strong[Prompt / skill package]], [#strong[Main grading behavior]], [#strong[Why it was tested]],
  [B0], [baseline prompt + `rubric_v0.json`], [Simple frozen-rubric grading from the extracted official solution. It mainly checks whether the answer matches the expected solution and point criteria.], [Reference starting point. Shows how the uncalibrated framework behaves on DSAA3071.],
  [R1], [same baseline prompt + `rubric_v1.json`], [Keeps the prompt constant but upgrades the rubric into concept/key-term elements, score bands, full-credit rules, and material-error caps.], [Isolates whether a better rubric helps before changing the grading skill.],
  [C3], [`candidate-v3` prompt + `rubric_v1.json`], [Adds a type-aware grading algorithm: multiple choice, short answer, calculation, algorithm, proof, and essay are scored by different rules. It uses evidence before score and separates key-term, concept, and relation evidence.], [Tests whether the grading skill itself improves over the baseline prompt under the same rubric.],
  [C31-r2], [`candidate-v3.1` open-ended prompt + `rubric_v1.json`], [Adds open-ended adequacy: the standard answer is an anchor, not an exhaustive whitelist. Valid, relevant, non-contradictory constructions or explanations can receive credit even when phrased differently.], [Addresses over-harsh scoring on open-ended answers, especially Q8 and Q9.],
  [C32], [`candidate-v3.2` prompt + `rubric_v2.json`], [Adds official-style adequacy and "avoid being overly harsh" rules. It also adds targeted policies for Q7 proof locality, Q8 power-of-two enumerators, and Q9 Church-Turing conceptual evidence.], [Current calibrated package. Tests whether targeted prompt plus targeted rubric reduce aggregate error.],
)

#v(4pt)
#grid(columns: (1fr, 1fr), gutter: 8pt,
  card(white)[#strong[What changed from C3 to C31-r2]
  C31-r2 keeps the core candidate-v3 algorithm but adds an explicit open-ended adequacy rule. This tells the grader not to reject a valid answer merely because it is not listed in the official solution.],
  card(white)[#strong[What changed from C31-r2 to C32]
  C32 adds official-style tolerance plus question-specific policies. It is less ideal-answer-completeness driven, but still requires the answer to satisfy the actual task and avoids giving credit for material contradictions.],
)

#card(white)[#strong[Important experimental interpretation.] R1 is close to a rubric-only comparison against B0. C3 is closer to a skill-prompt comparison against R1. C32 is a calibrated package-level comparison because both the prompt and rubric changed. Therefore C32 should be read as the best current grading package on dev, not as a pure one-factor ablation.]

#pagebreak()

== Rubric Evolution

#table(columns: (auto, 1.25fr, 1.65fr, 1.35fr), stroke: line, inset: (x: 5pt, y: 3.7pt),
  [#strong[Rubric]], [#strong[Used by]], [#strong[Design]], [#strong[Main limitation / improvement]],
  [`rubric_v0`], [B0], [Draft rubric extracted from the solution PDF. Most questions are represented as point criteria tied closely to the expected answer.], [Good enough to start the benchmark, but weak for concept answers because it gives little guidance about semantic equivalents, partial understanding, or local mistakes.],
  [`rubric_v1`], [R1, C3, C31-r2], [Concept/key-term rubric. Adds scoring elements, evidence levels, score bands, full-credit rules, and material-error caps. It distinguishes absent, mentioned-only, partial understanding, demonstrated, and misused evidence.], [Improves structure and partial-credit behavior, but Q8/Q9 still showed over-harsh or unstable behavior in dev.],
  [`rubric_v2`], [C32], [Targeted calibration from C31-r2 error diagnosis. Adds official-style tolerance and specific rules for Q7 proof locality, Q8 `0^(2^n)` enumerator behavior, and Q9 broad Church-Turing evidence.], [Best aggregate dev MAE so far, but Q8 remains unresolved and Q6 worsens versus R1.],
)

#v(4pt)
#table(columns: (1fr, 1fr, 1fr), stroke: line, inset: (x: 5pt, y: 3.7pt),
  [#strong[Q7 proof locality]], [#strong[Q8 enumerator policy]], [#strong[Q9 conceptual essay policy]],
  [Preserve credit for each correctly demonstrated proof direction. A local nonmembership/rejection mistake should not erase unrelated construction credit.],
  [The target language is `0^(2^n)`. Distinguish powers of two from linear even lengths `2n`, invalid extra outputs, wrong base cases, and vague loop mechanisms.],
  [Accept broad valid evidence for the Church-Turing thesis when it supports effective computability. Do not require exact labels such as lambda calculus if the explanation is equivalent and non-contradictory.],
)

#card(soft)[#strong[Data discipline.] These rubric changes were calibrated from aggregate development errors and official solutions. The report does not copy raw student answer text, and official scores provide per-question gold scores but not detailed official rationales.]

#pagebreak()
== Key Findings With Visual Evidence

#grid(columns: 4, gutter: 8pt,
  metric-card("Best question MAE", "2.557", "C32, lower is better"),
  metric-card("Best total MAE", "14.429", "C32, lower is better"),
  metric-card("Exact agreement", "52.9%", "C32 ties C31-r2"),
  metric-card("Severe error", "22.9%", "C32, still above R1"),
)

#v(5pt)
#grid(columns: (1fr, 1fr), gutter: 8pt,
  card(white)[
    #strong[Aggregate MAE comparison]
    #v(4pt)
    #cetz.canvas({
      import cetz.draw: *
      content((1.05, 5.28), text(size: 7pt, fill: rgb("#63707a"))[Question MAE])
      content((5.35, 5.28), text(size: 7pt, fill: rgb("#63707a"))[Total MAE])
      rect((1.05, 0.75), (4.25, 5.05), fill: rgb("#fbfdfe"), stroke: rgb("#d8e4e8"))
      rect((5.35, 0.75), (8.55, 5.05), fill: rgb("#fbfdfe"), stroke: rgb("#d8e4e8"))
  content((0.25, 4.80), text(size: 7pt, weight: "bold")[B0])
  rect((1.05, 4.71), (4.25, 4.89), fill: rgb("#8a98a5"), stroke: none)
  content((4.53, 4.80), text(size: 6.5pt)[3.343])
  rect((5.35, 4.71), (8.55, 4.89), fill: rgb("#8a98a5"), stroke: none)
  content((8.02, 4.80), text(size: 6.5pt)[27.429])
  content((0.25, 4.08), text(size: 7pt, weight: "bold")[R1])
  rect((1.05, 3.99), (3.55, 4.17), fill: rgb("#256d85"), stroke: none)
  content((3.83, 4.08), text(size: 6.5pt)[2.614])
  rect((5.35, 3.99), (7.70, 4.17), fill: rgb("#256d85"), stroke: none)
  content((8.02, 4.08), text(size: 6.5pt)[20.143])
  content((0.25, 3.36), text(size: 7pt, weight: "bold")[C3])
  rect((1.05, 3.27), (3.74, 3.45), fill: rgb("#b9822f"), stroke: none)
  content((4.02, 3.36), text(size: 6.5pt)[2.814])
  rect((5.35, 3.27), (7.70, 3.45), fill: rgb("#b9822f"), stroke: none)
  content((8.02, 3.36), text(size: 6.5pt)[20.143])
  content((0.25, 2.64), text(size: 7pt, weight: "bold")[C31-r2])
  rect((1.05, 2.55), (3.85, 2.73), fill: rgb("#7a5c00"), stroke: none)
  content((4.13, 2.64), text(size: 6.5pt)[2.929])
  rect((5.35, 2.55), (7.50, 2.73), fill: rgb("#7a5c00"), stroke: none)
  content((7.82, 2.64), text(size: 6.5pt)[18.429])
  content((0.25, 1.92), text(size: 7pt, weight: "bold")[C32])
  rect((1.05, 1.83), (3.50, 2.01), fill: rgb("#2d7a5b"), stroke: none)
  content((3.78, 1.92), text(size: 6.5pt)[2.557])
  rect((5.35, 1.83), (7.03, 2.01), fill: rgb("#2d7a5b"), stroke: none)
  content((7.35, 1.92), text(size: 6.5pt)[14.429])
    })
    #text(size: 7.5pt, fill: muted)[Shorter bars are better. C32 has the lowest question MAE and total MAE on the development split.]
  ],
  card(white)[
    #strong[Accuracy-risk map]
    #v(4pt)
    #cetz.canvas({
      import cetz.draw: *
      rect((0.75, 0.55), (7.15, 4.35), fill: rgb("#fbfdfe"), stroke: rgb("#d8e4e8"))
      line((0.95, 0.75), (6.95, 0.75), stroke: rgb("#63707a"))
      line((0.95, 0.75), (0.95, 4.15), stroke: rgb("#63707a"))
      content((0.95, 4.42), text(size: 7pt, fill: rgb("#63707a"))[Severe])
      content((6.55, 0.38), text(size: 7pt, fill: rgb("#63707a"))[Question MAE])
      rect((0.98, 0.82), (2.70, 1.72), fill: rgb("#e8f3ed"), stroke: none)
      content((1.84, 1.27), text(size: 6.5pt, fill: rgb("#316a4d"))[target zone])
  circle((6.80, 3.82), radius: 0.10, fill: rgb("#8a98a5"), stroke: white)
  content((7.15, 3.92), text(size: 7pt, weight: "bold")[B0])
  circle((5.54, 3.47), radius: 0.10, fill: rgb("#256d85"), stroke: white)
  content((5.89, 3.57), text(size: 7pt, weight: "bold")[R1])
  circle((5.88, 3.82), radius: 0.10, fill: rgb("#b9822f"), stroke: white)
  content((6.23, 3.92), text(size: 7pt, weight: "bold")[C3])
  circle((6.08, 4.00), radius: 0.10, fill: rgb("#7a5c00"), stroke: white)
  content((6.43, 4.10), text(size: 7pt, weight: "bold")[C31-r2])
  circle((5.44, 3.64), radius: 0.10, fill: rgb("#2d7a5b"), stroke: white)
  content((5.79, 3.74), text(size: 7pt, weight: "bold")[C32])
    })
    #text(size: 7.5pt, fill: muted)[Lower left is better. C32 moves left versus R1 but remains slightly above R1 on severe-error rate.]
  ],
)

#pagebreak()

== Condition Details

#table(columns: (auto, 1.45fr, auto, auto, auto, auto, auto), stroke: line, inset: (x: 5pt, y: 3.8pt),
  [#strong[Cond.]], [#strong[Description]], [#strong[Validation]], [#strong[Tokens]], [#strong[Q MAE]], [#strong[Total MAE]], [#strong[Severe]],
  [B0], [baseline prompt + rubric v0], [passed (7/7)], [63448], [3.343], [27.429], [24.3%],
  [R1], [baseline prompt + rubric v1], [passed (7/7)], [92633], [2.614], [20.143], [21.4%],
  [C3], [candidate-v3 prompt + rubric v1], [passed (7/7)], [104803], [2.814], [20.143], [24.3%],
  [C31-r2], [candidate-v3.1 r2 open-ended adequacy prompt + rubric v1], [passed_after_recovery (7/7)], [107658], [2.929], [18.429], [25.7%],
  [C32], [candidate-v3.2 prompt + rubric v2], [passed (7/7)], [116758], [2.557], [14.429], [22.9%],
)

C32 improves aggregate MAE while preserving the same seven-student development split. This table should be read as calibration evidence, not as a final leaderboard.

== Per-Question Error Concentration

#table(columns: (auto, auto, auto, auto, auto, auto, 1fr), stroke: line, inset: (x: 5pt, y: 3.8pt),
  [#strong[Question]], [#strong[B0]], [#strong[R1]], [#strong[C3]], [#strong[C31-r2]], [#strong[C32]], [#strong[Best]],
  [Q5],
  table.cell(fill: rgb("#e7a39b"))[7.000],
  table.cell(fill: rgb("#edc37a"))[4.857],
  table.cell(fill: rgb("#e7a39b"))[5.857],
  table.cell(fill: rgb("#f2e7bd"))[2.571],
  table.cell(fill: rgb("#f2e7bd"))[2.714],
  [C31-r2],
  [Q6],
  table.cell(fill: rgb("#f2e7bd"))[2.143],
  table.cell(fill: rgb("#f2e7bd"))[1.714],
  table.cell(fill: rgb("#f2e7bd"))[1.857],
  table.cell(fill: rgb("#edc37a"))[2.714],
  table.cell(fill: rgb("#e7a39b"))[4.429],
  [R1],
  [Q7],
  table.cell(fill: rgb("#e7a39b"))[4.429],
  table.cell(fill: rgb("#f2e7bd"))[2.429],
  table.cell(fill: rgb("#e7a39b"))[4.429],
  table.cell(fill: rgb("#e7a39b"))[5.000],
  table.cell(fill: rgb("#f2e7bd"))[2.429],
  [R1, C32],
  [Q8],
  table.cell(fill: rgb("#edc37a"))[3.857],
  table.cell(fill: rgb("#e7a39b"))[5.714],
  table.cell(fill: rgb("#e7a39b"))[4.857],
  table.cell(fill: rgb("#e7a39b"))[5.000],
  table.cell(fill: rgb("#e7a39b"))[5.571],
  [B0],
  [Q9],
  table.cell(fill: rgb("#e7a39b"))[14.857],
  table.cell(fill: rgb("#edc37a"))[9.714],
  table.cell(fill: rgb("#edc37a"))[9.714],
  table.cell(fill: rgb("#e7a39b"))[11.714],
  table.cell(fill: rgb("#edc37a"))[9.000],
  [C32],
  [Q10],
  table.cell(fill: rgb("#f2e7bd"))[1.143],
  table.cell(fill: rgb("#e7a39b"))[1.714],
  table.cell(fill: rgb("#edc37a"))[1.429],
  table.cell(fill: rgb("#e7a39b"))[2.286],
  table.cell(fill: rgb("#edc37a"))[1.429],
  [B0],
)

The strongest C32 improvements are Q7 and Q9 relative to C31-r2. The biggest blocker is still Q8: C32 Q8 MAE is `5.571`, almost unchanged from R1 and worse than B0.

#v(5pt)
#card(white)[
  #strong[Exact agreement and severe-error bars]
  #v(4pt)
  #cetz.canvas({
    import cetz.draw: *
    content((1.05, 4.18), text(size: 6.5pt, fill: rgb("#63707a"))[Exact agreement])
    content((7.98, 4.18), text(size: 6.5pt, fill: rgb("#a33b2f"))[Severe])
  content((0.25, 3.70), text(size: 7pt, weight: "bold")[B0])
  rect((1.05, 3.62), (6.65, 3.78), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 3.62), (6.35, 3.78), fill: rgb("#8a98a5"), stroke: none)
  rect((6.34, 3.52), (6.39, 3.88), fill: rgb("#a33b2f"), stroke: none)
  content((7.15, 3.70), text(size: 6.5pt)[50.0%])
  content((8.08, 3.70), text(size: 6.2pt, fill: rgb("#a33b2f"))[24.3%])
  content((0.25, 3.15), text(size: 7pt, weight: "bold")[R1])
  rect((1.05, 3.07), (6.65, 3.23), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 3.07), (6.50, 3.23), fill: rgb("#256d85"), stroke: none)
  rect((5.72, 2.97), (5.77, 3.33), fill: rgb("#a33b2f"), stroke: none)
  content((7.15, 3.15), text(size: 6.5pt)[51.4%])
  content((8.08, 3.15), text(size: 6.2pt, fill: rgb("#a33b2f"))[21.4%])
  content((0.25, 2.60), text(size: 7pt, weight: "bold")[C3])
  rect((1.05, 2.52), (6.65, 2.68), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 2.52), (6.35, 2.68), fill: rgb("#b9822f"), stroke: none)
  rect((6.34, 2.42), (6.39, 2.78), fill: rgb("#a33b2f"), stroke: none)
  content((7.15, 2.60), text(size: 6.5pt)[50.0%])
  content((8.08, 2.60), text(size: 6.2pt, fill: rgb("#a33b2f"))[24.3%])
  content((0.25, 2.05), text(size: 7pt, weight: "bold")[C31-r2])
  rect((1.05, 1.97), (6.65, 2.13), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 1.97), (6.65, 2.13), fill: rgb("#7a5c00"), stroke: none)
  rect((6.65, 1.87), (6.70, 2.23), fill: rgb("#a33b2f"), stroke: none)
  content((7.15, 2.05), text(size: 6.5pt)[52.9%])
  content((8.08, 2.05), text(size: 6.2pt, fill: rgb("#a33b2f"))[25.7%])
  content((0.25, 1.50), text(size: 7pt, weight: "bold")[C32])
  rect((1.05, 1.42), (6.65, 1.58), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 1.42), (6.65, 1.58), fill: rgb("#2d7a5b"), stroke: none)
  rect((6.03, 1.32), (6.08, 1.68), fill: rgb("#a33b2f"), stroke: none)
  content((7.15, 1.50), text(size: 6.5pt)[52.9%])
  content((8.08, 1.50), text(size: 6.2pt, fill: rgb("#a33b2f"))[22.9%])
  })
  #text(size: 7.5pt, fill: muted)[Colored bars show exact agreement. Red ticks and red labels show severe-error rate.]
]

#pagebreak()

== C32 Q7-Q9 Development Error Table

#table(columns: (auto, auto, auto, auto, auto), stroke: line, inset: (x: 5pt, y: 3.6pt),
  [#strong[Student]], [#strong[Question]], [#strong[Gold]], [#strong[C32]], [#strong[Error]],
  [`S017`], [Q7], [20.000], [17.000], table.cell(fill: rgb("#dfeee7"))[-3.000],
  [`S017`], [Q8], [9.000], [5.000], table.cell(fill: rgb("#dfeee7"))[-4.000],
  [`S017`], [Q9], [25.000], [12.000], table.cell(fill: rgb("#e7a39b"))[-13.000],
  [`S021`], [Q7], [15.000], [16.000], table.cell(fill: rgb("#dfeee7"))[1.000],
  [`S021`], [Q8], [0.000], [5.000], table.cell(fill: rgb("#f2e7bd"))[5.000],
  [`S021`], [Q9], [12.000], [10.000], table.cell(fill: rgb("#dfeee7"))[-2.000],
  [`S002`], [Q7], [10.000], [15.000], table.cell(fill: rgb("#f2e7bd"))[5.000],
  [`S002`], [Q8], [10.000], [3.000], table.cell(fill: rgb("#f2e7bd"))[-7.000],
  [`S002`], [Q9], [25.000], [25.000], table.cell(fill: rgb("#dfeee7"))[0.000],
  [`S015`], [Q7], [10.000], [13.000], table.cell(fill: rgb("#dfeee7"))[3.000],
  [`S015`], [Q8], [10.000], [4.000], table.cell(fill: rgb("#f2e7bd"))[-6.000],
  [`S015`], [Q9], [25.000], [17.000], table.cell(fill: rgb("#f2e7bd"))[-8.000],
  [`S020`], [Q7], [18.000], [18.000], table.cell(fill: rgb("#dfeee7"))[0.000],
  [`S020`], [Q8], [10.000], [1.000], table.cell(fill: rgb("#f2e7bd"))[-9.000],
  [`S020`], [Q9], [10.000], [2.000], table.cell(fill: rgb("#f2e7bd"))[-8.000],
  [`S016`], [Q7], [0.000], [0.000], table.cell(fill: rgb("#dfeee7"))[0.000],
  [`S016`], [Q8], [8.000], [5.000], table.cell(fill: rgb("#dfeee7"))[-3.000],
  [`S016`], [Q9], [25.000], [5.000], table.cell(fill: rgb("#e7a39b"))[-20.000],
  [`S022`], [Q7], [10.000], [5.000], table.cell(fill: rgb("#f2e7bd"))[-5.000],
  [`S022`], [Q8], [10.000], [5.000], table.cell(fill: rgb("#f2e7bd"))[-5.000],
  [`S022`], [Q9], [25.000], [13.000], table.cell(fill: rgb("#e7a39b"))[-12.000],
)

This table uses anonymous IDs only and does not copy student answer text. It shows why the result is still mixed: Q7 is mostly controlled, Q9 improved but remains under-scored for several students, and Q8 remains unstable.

== Metric Definitions And Method

- `question_score_mae`: mean absolute error over all student-question pairs. Lower is better.
- `normalized_question_score_mae`: mean absolute error divided by question max score. Lower is better.
- `question_exact_agreement`: fraction of student-question pairs where model score exactly equals official score. Higher is better.
- `severe_error_rate_abs_ge_5`: fraction of student-question pairs with absolute error at least 5 points. Lower is better.
- `total_score_mae`: mean absolute error between model total and official total per student. Lower is better.

The model run used DeepSeek public API, `deepseek-v4-pro`, text-only inputs, the reviewed transcript snapshot, and packet `C32-dev-reviewed-r1`. The model output schema validation passed for all seven development students.

== Limitations And Next Step

- held-out not run; this is not a final accuracy claim.
- The development split has only seven anonymous students.
- Official scores provide per-question numbers but not detailed official rationales.
- C32 changes rubric, prompt, and skill together by design, so it evaluates the calibrated package rather than one isolated factor.
- Next step: diagnose Q8 specifically before freezing the skill or running a held-out test.
