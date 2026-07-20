#set page(paper: "a4", margin: (x: 15mm, y: 14mm))
#set text(font: "Arial", size: 9.2pt, lang: "en")
#set heading(numbering: "1.")
#set par(justify: false, leading: 0.56em)

#let navy = rgb("#17324d")
#let ink = rgb("#17212b")
#let muted = rgb("#5e6a76")
#let gridline = rgb("#d8e0e8")
#let panel = rgb("#f6f8fb")
#let deepseek = rgb("#c95f4a")
#let codex = rgb("#1e7c86")
#let base = rgb("#7a8794")
#let good = rgb("#2f855a")
#let warn = rgb("#b7791f")

#let metric-card(title, value, note, color) = block(
  width: 100%,
  inset: 7pt,
  radius: 4pt,
  stroke: (paint: gridline, thickness: 0.6pt),
  fill: panel,
)[
  #text(size: 7.2pt, fill: muted, weight: "bold")[#title]
  #linebreak()
  #text(size: 18pt, fill: color, weight: "bold")[#value]
  #linebreak()
  #text(size: 7pt, fill: muted)[#note]
]

#let bar(label, value, width, color) = grid(
  columns: (30mm, 38mm, 15mm),
  gutter: 3pt,
  align: horizon,
)[
  #text(size: 7.6pt, fill: ink)[#label]
][
  #rect(width: width, height: 5.5pt, fill: color, radius: 2pt)
][
  #text(size: 7.6pt, fill: muted)[#value]
]

#align(center)[
  #text(size: 19pt, weight: "bold", fill: navy)[Physics Week 9 Model Benchmark v1]
  #linebreak()
  #text(size: 10pt, fill: muted)[DeepSeek API vs Codex CLI headless on the text-only held-out split]
]

#v(5pt)
#grid(columns: (1fr, 1fr, 1fr), gutter: 7pt)[
  #metric-card("Best completed condition", "Codex CLI + C2", "candidate-v2, held-out test", codex)
][
  #metric-card("Held-out exact agreement", "89.8%", "Codex C2 vs gold scores", codex)
][
  #metric-card("Held-out total MAE", "1.08", "lower is better", good)
]

#v(5pt)
#block(width: 100%, inset: 8pt, radius: 4pt, stroke: (paint: gridline, thickness: 0.6pt), fill: rgb("#fbfcfe"))[
  #text(weight: "bold", fill: navy)[Executive readout.] This v1 report compares the two completed physics Week 9 text-only model families: DeepSeek public API and Codex CLI headless. Both providers were run with the same baseline packet and candidate-v2 packet on the development split and on the held-out test split. The strongest completed result is #text(weight: "bold")[Codex CLI + candidate-v2] on held-out test: exact agreement 0.898, total-score MAE 1.083, within-1-point rate 0.667, and severe-error rate 0.333.
]

== What Is Being Compared

#table(
  columns: (22mm, 38mm, 30mm, 1fr),
  inset: 4.4pt,
  stroke: gridline,
  table.header([Condition], [Provider / model], [Input], [Purpose]),
  [B0], [DeepSeek v4-pro or Codex gpt-5.5], [text-only transcript], [Original baseline grading packet.],
  [C2], [same provider / model], [text-only transcript], [Candidate-v2 grading skill packet: more explicit scoring rules, stricter schema, and process-aware handling for calculation answers.],
  [Dev split], [8 students], [96 subquestion rows], [Used for debugging/calibration. Not the final evidence split.],
  [Held-out split], [18 students], [216 subquestion rows], [Primary comparison split. It was kept separate from prompt tuning.],
)

== Held-out Test: Main Evidence

#grid(columns: (1fr, 1fr), gutter: 10pt)[
  #block(width: 100%, inset: 8pt, radius: 4pt, stroke: (paint: gridline, thickness: 0.6pt), fill: panel)[
    #text(weight: "bold", fill: navy)[Exact agreement, higher is better]
    #v(4pt)
    #bar("DeepSeek B0", "81.0%", 30.8mm, base)
    #v(2.5pt)
    #bar("DeepSeek C2", "84.3%", 32.0mm, deepseek)
    #v(2.5pt)
    #bar("Codex B0", "86.6%", 32.9mm, base)
    #v(2.5pt)
    #bar("Codex C2", "89.8%", 34.1mm, codex)
  ]
][
  #block(width: 100%, inset: 8pt, radius: 4pt, stroke: (paint: gridline, thickness: 0.6pt), fill: panel)[
    #text(weight: "bold", fill: navy)[Total-score MAE, lower is better]
    #v(4pt)
    #bar("DeepSeek B0", "2.26", 35.8mm, base)
    #v(2.5pt)
    #bar("DeepSeek C2", "2.08", 33.0mm, deepseek)
    #v(2.5pt)
    #bar("Codex B0", "1.32", 20.9mm, base)
    #v(2.5pt)
    #bar("Codex C2", "1.08", 17.2mm, codex)
  ]
]

#v(4pt)
#table(
  columns: (31mm, 23mm, 23mm, 23mm, 24mm, 24mm),
  inset: 4pt,
  stroke: gridline,
  table.header([Held-out condition], [Exact], [SubQ MAE], [Total MAE], [Within 1 pt], [Severe err.]),
  [DeepSeek B0], [0.810], [0.200], [2.264], [0.333], [0.444],
  [DeepSeek C2], [0.843], [0.185], [2.083], [0.500], [0.444],
  [Codex B0], [0.866], [0.126], [1.319], [0.667], [0.333],
  [Codex C2], [#text(weight: "bold")[0.898]], [#text(weight: "bold")[0.100]], [#text(weight: "bold")[1.083]], [#text(weight: "bold")[0.667]], [#text(weight: "bold")[0.333]],
)

#v(3pt)
#block(width: 100%, inset: 7pt, radius: 4pt, stroke: (paint: rgb("#eed9ac"), thickness: 0.6pt), fill: rgb("#fffaf0"))[
  #text(weight: "bold", fill: warn)[Interpretation.] Candidate-v2 improves exact agreement and MAE for both completed providers. Codex CLI is stronger than DeepSeek on every held-out metric in this v1 comparison. However, severe-error rate remains non-trivial, so this is a benchmark result rather than a production-ready grading claim.
]

#pagebreak()

== Baseline vs Candidate-v2 Deltas

Positive exact-agreement deltas mean candidate-v2 matched the gold score more often. Negative MAE deltas mean candidate-v2 reduced scoring error.

#table(
  columns: (34mm, 31mm, 31mm, 1fr),
  inset: 4.4pt,
  stroke: gridline,
  table.header([Held-out delta], [DeepSeek C2-B0], [Codex C2-B0], [Readout]),
  [Exact agreement], [+0.032], [+0.032], [Both providers gain the same absolute exact-agreement lift on held-out test.],
  [Subquestion MAE], [-0.015], [-0.027], [Codex shows a larger reduction in subquestion-level error.],
  [Total-score MAE], [-0.181], [-0.236], [Both improve; Codex reaches the lower final error.],
  [Within-1-point rate], [+0.167], [+0.000], [DeepSeek improves proximity; Codex was already higher and stays stable.],
  [Severe-error rate], [+0.000], [+0.000], [No held-out improvement. This is the main remaining weakness.],
)

#v(5pt)
#grid(columns: (1fr, 1fr), gutter: 10pt)[
  #block(width: 100%, inset: 8pt, radius: 4pt, stroke: (paint: gridline, thickness: 0.6pt), fill: panel)[
    #text(weight: "bold", fill: navy)[Candidate-v2 exact agreement]
    #v(4pt)
    #bar("DeepSeek dev", "85.4%", 17.2mm, deepseek)
    #v(2.5pt)
    #bar("DeepSeek held-out", "84.3%", 32.0mm, deepseek)
    #v(2.5pt)
    #bar("Codex dev", "89.6%", 34.0mm, codex)
    #v(2.5pt)
    #bar("Codex held-out", "89.8%", 34.1mm, codex)
  ]
][
  #block(width: 100%, inset: 8pt, radius: 4pt, stroke: (paint: gridline, thickness: 0.6pt), fill: panel)[
    #text(weight: "bold", fill: navy)[Candidate-v2 severe-error rate]
    #v(4pt)
    #bar("DeepSeek dev", "12.5%", 9.5mm, deepseek)
    #v(2.5pt)
    #bar("DeepSeek held-out", "44.4%", 33.8mm, deepseek)
    #v(2.5pt)
    #bar("Codex dev", "12.5%", 9.5mm, codex)
    #v(2.5pt)
    #bar("Codex held-out", "33.3%", 25.3mm, codex)
  ]
]

== Development Split Sanity Check

The development split is useful for detecting obvious packet failures, schema failures, or candidate regressions before spending more runs on held-out data. It should not be used as the final conclusion because the prompt packet was calibrated using development feedback.

#table(
  columns: (31mm, 23mm, 23mm, 23mm, 24mm, 24mm),
  inset: 4pt,
  stroke: gridline,
  table.header([Dev condition], [Exact], [SubQ MAE], [Total MAE], [Within 1 pt], [Severe err.]),
  [DeepSeek B0], [0.792], [0.221], [2.156], [0.375], [0.375],
  [DeepSeek C2], [0.854], [0.104], [0.750], [0.750], [0.125],
  [Codex B0], [0.875], [0.099], [0.438], [0.875], [0.125],
  [Codex C2], [0.896], [0.081], [0.594], [0.875], [0.125],
)

#v(3pt)
#block(width: 100%, inset: 7pt, radius: 4pt, stroke: (paint: gridline, thickness: 0.6pt), fill: rgb("#fbfcfe"))[
  #text(weight: "bold")[Development caveat.] Codex candidate-v2 improves exact agreement on dev, but its dev total-score MAE is slightly worse than Codex baseline. Held-out test reverses that concern: Codex candidate-v2 lowers total-score MAE from 1.319 to 1.083. This is why the held-out split is the primary evidence.
]

#pagebreak()

== Good-enough Gate

#table(
  columns: (56mm, 20mm, 1fr),
  inset: 4.5pt,
  stroke: gridline,
  table.header([Gate], [Status], [Evidence]),
  [All expected students pass schema validation], [Pass], [DeepSeek and Codex held-out runs passed validation.],
  [Held-out exact agreement at least 0.84], [Pass], [DeepSeek C2 = 0.843; Codex C2 = 0.898.],
  [Held-out exact agreement improves over baseline], [Pass], [Both providers improve by +0.032.],
  [Held-out total-score MAE at most 2.10 and improves], [Pass], [DeepSeek C2 = 2.083; Codex C2 = 1.083.],
  [Held-out within-1-point rate at least 0.50], [Pass], [DeepSeek C2 = 0.500; Codex C2 = 0.667.],
  [Severe-error rate not worsened], [Pass with caveat], [No worsening, but rates remain high: DeepSeek 0.444, Codex 0.333.],
)

== Reproducibility Notes

#table(
  columns: (34mm, 1fr),
  inset: 4.4pt,
  stroke: gridline,
  [Code version], [Report summary: 780e75a. DeepSeek held-out: 9cce18378abb19d817040cb56599457108d7d575. Codex held-out: 780e75a.],
  [Data policy], [Raw Data/ and model outputs are private/ignored. This report contains only aggregate metrics and reproducibility pointers.],
  [DeepSeek source], [Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/held-out-metrics-strict-schema.json],
  [Codex source], [Data/physics/benchmark/runs/physics-week9-codex-headless/codex-heldout-G1-baseline-vs-candidate.metrics.json],
  [Codex engine], [Codex CLI 0.133.0, headless mode, model label gpt-5.5.],
  [Current missing runs], [Kimi and Claude are not included in this v1 report. They should be added in v2 after mentor-side runs return complete outputs.],
)

== Conclusion for v1

For the completed physics Week 9 text-only benchmark, #text(weight: "bold")[Codex CLI + candidate-v2] is the current best-supported condition. It clears the pre-set good-enough bar on held-out exact agreement, total-score MAE, and within-1-point rate, and it outperforms DeepSeek candidate-v2 on the held-out split.

This is still not the final model-selection report. The next report version should add Kimi and Claude Code runs, include the same held-out metrics, and keep severe-error analysis as a first-class criterion rather than treating exact agreement alone as sufficient.