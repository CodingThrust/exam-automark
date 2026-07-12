#set document(title: "Physics Week 9 Development Run Note")
#set page(paper: "a4", margin: (x: 1.45cm, y: 1.2cm))
#set text(font: "New Computer Modern", size: 9.2pt, fill: rgb("#17212b"))
#import "@preview/cetz:0.5.2"

#let ink = rgb("#17212b")
#let muted = rgb("#63707a")
#let line = rgb("#d8e4e8")
#let soft = rgb("#eef6f7")
#let soft2 = rgb("#fff7e3")
#let blue = rgb("#256d85")
#let gold = rgb("#b9822f")
#let olive = rgb("#4e7d5a")
#let red = rgb("#a33b2f")
#let pale = rgb("#f7fafb")

#let pill(body) = box(fill: soft, stroke: line, inset: (x: 7pt, y: 4pt), radius: 3pt, body)
#let note-box(body) = box(fill: soft, stroke: line, inset: 9pt, radius: 4pt, width: 100%, body)
#let warning-box(body) = box(fill: soft2, stroke: rgb("#ead59b"), inset: 9pt, radius: 4pt, width: 100%, body)
#let metric-card(label, value, detail, fill_color: soft) = box(fill: fill_color, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[
  #text(size: 7.5pt, fill: muted)[#label]\
  #text(size: 17pt, weight: "bold", fill: ink)[#value]\
  #text(size: 7.5pt, fill: muted)[#detail]
]

#align(center)[
  #text(size: 20pt, weight: "bold", fill: ink)[Physics Week 9 Development Run Note]
]

#align(center)[
  #pill[Baseline vs candidate v2, text-only, DeepSeek dev split]
]

#warning-box[
  #strong[Reading guide.] This note records development evidence only. Candidate v2 improved over the baseline on the 8-student development split and is now frozen for held-out evaluation. The held-out test split has not been run, so this is not a final accuracy claim.
]

== Experiment State

#grid(columns: (1fr, 1fr, 1fr, 1fr), gutter: 7pt,
  metric-card("Validation", "8/8 + 8/8", "baseline and candidate passed"),
  metric-card("Exact agreement", "85.4%", "candidate v2 dev split", fill_color: rgb("#edf5ef")),
  metric-card("Total MAE", "0.75", "candidate v2, points", fill_color: rgb("#fff7e3")),
  metric-card("Held-out test", "Not run", "candidate frozen", fill_color: rgb("#f9eeee")),
)

#grid(columns: (1fr, 1fr), gutter: 8pt,
  note-box[
    #strong[Protocol decision.] Candidate v2 is frozen in `CANDIDATE-V2-FREEZE.md`. The next step is held-out packet preparation without changing prompts.
  ],
  note-box[
    #strong[Data boundary.] Student data and model outputs remain under ignored `Data/`. This Git record stores paths, hashes, commands, and aggregate metrics only.
  ],
)

== Reproducibility Anchors

#table(columns: (auto, 1fr), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Anchor]], [#strong[Value]],
  [Record directory], [`experiments/records/physics-week9-baseline-candidate-v2-run`],
  [Branch], [`codex/physics-week9-baseline-candidate-v2-run`],
  [Model-run commit], [`95622f0aead87187c6410ec0a38ba94cb2866dee`],
  [Report input record], [`DEV-METRICS-STRICT-SCHEMA.md`],
  [Course / assessment], [`physics` / `week9`],
  [Split], [`development`, 8 anonymous students],
  [Provider / model], [`deepseek` / `deepseek-v4-pro`],
  [Endpoint], [`https://api.deepseek.com`],
  [Input mode], [`text-only`, pilot-derived automatic transcript],
  [Temperature / response format], [`0` / `json_object`],
  [Typst], [`0.15.0`],
)

== Prompt Packet Lineage

#cetz.canvas({
  import cetz.draw: *
  rect((0.40, 2.72), (2.45, 3.42), fill: rgb("#eef6f7"), stroke: rgb("#d8e4e8"))
  content((1.425, 3.18), text(size: 7.2pt, weight: "bold")[Transcript source])
  content((1.425, 2.92), text(size: 6.3pt, fill: rgb("#63707a"))[T1-dev-r1])

  rect((3.10, 3.38), (5.45, 4.08), fill: rgb("#eef6f7"), stroke: rgb("#d8e4e8"))
  content((4.275, 3.84), text(size: 7.2pt, weight: "bold")[Baseline packet])
  content((4.275, 3.58), text(size: 6.3pt, fill: rgb("#63707a"))[prompt 8fe0...fa5e])

  rect((3.10, 2.08), (5.45, 2.78), fill: rgb("#fff7e3"), stroke: rgb("#ead59b"))
  content((4.275, 2.54), text(size: 7.2pt, weight: "bold")[Candidate v2 packet])
  content((4.275, 2.28), text(size: 6.3pt, fill: rgb("#63707a"))[prompt 1eb9...2c3f])

  rect((6.15, 3.38), (8.15, 4.08), fill: rgb("#f7fafb"), stroke: rgb("#d8e4e8"))
  content((7.15, 3.84), text(size: 7.2pt, weight: "bold")[DeepSeek run])
  content((7.15, 3.58), text(size: 6.3pt, fill: rgb("#63707a"))[baseline 8/8])

  rect((6.15, 2.08), (8.15, 2.78), fill: rgb("#f7fafb"), stroke: rgb("#d8e4e8"))
  content((7.15, 2.54), text(size: 7.2pt, weight: "bold")[DeepSeek run])
  content((7.15, 2.28), text(size: 6.3pt, fill: rgb("#63707a"))[candidate 8/8])

  rect((8.88, 2.72), (10.80, 3.42), fill: rgb("#edf5ef"), stroke: rgb("#c8dfce"))
  content((9.84, 3.18), text(size: 7.2pt, weight: "bold")[Dev metrics])
  content((9.84, 2.92), text(size: 6.3pt, fill: rgb("#63707a"))[compare, then test])

  line((2.45, 3.07), (3.10, 3.73), stroke: (paint: rgb("#63707a"), thickness: 0.8pt), mark: (end: ">"))
  line((2.45, 3.07), (3.10, 2.43), stroke: (paint: rgb("#63707a"), thickness: 0.8pt), mark: (end: ">"))
  line((5.45, 3.73), (6.15, 3.73), stroke: (paint: rgb("#63707a"), thickness: 0.8pt), mark: (end: ">"))
  line((5.45, 2.43), (6.15, 2.43), stroke: (paint: rgb("#63707a"), thickness: 0.8pt), mark: (end: ">"))
  line((8.15, 3.73), (8.88, 3.22), stroke: (paint: rgb("#63707a"), thickness: 0.8pt), mark: (end: ">"))
  line((8.15, 2.43), (8.88, 2.92), stroke: (paint: rgb("#63707a"), thickness: 0.8pt), mark: (end: ">"))
})

#v(3pt)
#text(size: 7.6pt, fill: muted)[Both packets use the same transcript hash `30e45836b26f6c05d0a55c2e436d5ace7078d01ae86932c3c64b27ad14e24cf8` and rubric hash `a02e0531b3d78590c66d32e76eba170d2e0400e3e4a1c60436f4f5c2c8e93b21`.]

#pagebreak()

== Development Results

#table(columns: (1.35fr, auto, auto, auto), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Metric]], [#strong[Baseline]], [#strong[Candidate v2]], [#strong[Direction]],
  [exact agreement], [0.7917], [0.8542], [candidate better],
  [macro accuracy], [0.7917], [0.8542], [candidate better],
  [subquestion MAE], [0.2214], [0.1042], [candidate better],
  [total score MAE], [2.1563], [0.7500], [candidate better],
  [within 1 point rate], [0.3750], [0.7500], [candidate better],
  [severe error rate], [0.3750], [0.1250], [candidate better],
  [mean signed error], [-0.1797], [-0.0625], [candidate less biased],
)

#grid(columns: (1fr, 1fr), gutter: 8pt,
  box(fill: white, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[
#strong[Higher-is-better metrics]
#v(4pt)
#cetz.canvas({
  import cetz.draw: *
  line((1.25, 0.70), (7.25, 0.70), stroke: rgb("#63707a"))
  content((1.25, 0.38), text(size: 6.3pt, fill: rgb("#63707a"))[0%])
  content((4.25, 0.38), text(size: 6.3pt, fill: rgb("#63707a"))[50%])
  content((7.25, 0.38), text(size: 6.3pt, fill: rgb("#63707a"))[100%])

  content((0.34, 3.38), text(size: 7pt, weight: "bold")[Exact])
  rect((1.25, 3.18), (7.25, 3.34), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.25, 3.18), (6.00, 3.34), fill: rgb("#256d85"), stroke: none)
  content((7.55, 3.31), text(size: 6.5pt)[79.2%])
  rect((1.25, 2.88), (7.25, 3.04), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.25, 2.88), (6.38, 3.04), fill: rgb("#b9822f"), stroke: none)
  content((7.55, 3.01), text(size: 6.5pt)[85.4%])

  content((0.34, 2.08), text(size: 7pt, weight: "bold")[Within 1])
  rect((1.25, 1.88), (7.25, 2.04), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.25, 1.88), (3.50, 2.04), fill: rgb("#256d85"), stroke: none)
  content((7.55, 2.01), text(size: 6.5pt)[37.5%])
  rect((1.25, 1.58), (7.25, 1.74), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.25, 1.58), (5.75, 1.74), fill: rgb("#b9822f"), stroke: none)
  content((7.55, 1.71), text(size: 6.5pt)[75.0%])

  rect((1.25, 4.00), (1.45, 4.14), fill: rgb("#256d85"), stroke: none)
  content((1.78, 4.08), text(size: 6.5pt, fill: rgb("#63707a"))[baseline])
  rect((3.05, 4.00), (3.25, 4.14), fill: rgb("#b9822f"), stroke: none)
  content((3.58, 4.08), text(size: 6.5pt, fill: rgb("#63707a"))[candidate v2])
})
#v(3pt)
#text(size: 7.3pt, fill: muted)[The candidate improves both exact agreement and total-score tolerance on the dev split.]
],
  box(fill: white, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[
#strong[Error and risk reduction vs baseline]
#v(4pt)
#cetz.canvas({
  import cetz.draw: *
  line((2.40, 0.70), (7.25, 0.70), stroke: rgb("#63707a"))
  content((2.40, 0.38), text(size: 6.3pt, fill: rgb("#63707a"))[0%])
  content((4.82, 0.38), text(size: 6.3pt, fill: rgb("#63707a"))[35%])
  content((7.25, 0.38), text(size: 6.3pt, fill: rgb("#63707a"))[70%])

  content((0.30, 3.45), text(size: 6.6pt, weight: "bold")[Subquestion MAE])
  rect((2.40, 3.25), (7.25, 3.43), fill: rgb("#d8e4e8"), stroke: none)
  rect((2.40, 3.25), (6.06, 3.43), fill: rgb("#4e7d5a"), stroke: none)
  content((7.48, 3.39), text(size: 6.5pt)[52.9%])

  content((0.30, 2.65), text(size: 6.6pt, weight: "bold")[Total MAE])
  rect((2.40, 2.45), (7.25, 2.63), fill: rgb("#d8e4e8"), stroke: none)
  rect((2.40, 2.45), (6.92, 2.63), fill: rgb("#4e7d5a"), stroke: none)
  content((7.48, 2.59), text(size: 6.5pt)[65.2%])

  content((0.30, 1.85), text(size: 6.6pt, weight: "bold")[Severe errors])
  rect((2.40, 1.65), (7.25, 1.83), fill: rgb("#d8e4e8"), stroke: none)
  rect((2.40, 1.65), (7.02, 1.83), fill: rgb("#4e7d5a"), stroke: none)
  content((7.48, 1.79), text(size: 6.5pt)[66.7%])

  content((0.30, 1.05), text(size: 6.6pt, weight: "bold")[Bias magnitude])
  rect((2.40, 0.85), (7.25, 1.03), fill: rgb("#d8e4e8"), stroke: none)
  rect((2.40, 0.85), (6.92, 1.03), fill: rgb("#4e7d5a"), stroke: none)
  content((7.48, 0.99), text(size: 6.5pt)[65.2%])
})
#v(3pt)
#text(size: 7.3pt, fill: muted)[Positive bars mean candidate v2 reduced the baseline error or risk metric.]
],
)

== Where Candidate v2 Changed The Most

#box(fill: white, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[
#strong[Per-question exact-agreement gain, candidate minus baseline]
#v(4pt)
#cetz.canvas({
  import cetz.draw: *
  line((1.25, 0.65), (9.25, 0.65), stroke: rgb("#63707a"))
  content((1.25, 0.34), text(size: 6.2pt, fill: rgb("#63707a"))[0 pp])
  content((3.25, 0.34), text(size: 6.2pt, fill: rgb("#63707a"))[10])
  content((5.25, 0.34), text(size: 6.2pt, fill: rgb("#63707a"))[20])
  content((7.25, 0.34), text(size: 6.2pt, fill: rgb("#63707a"))[30])
  content((9.25, 0.34), text(size: 6.2pt, fill: rgb("#63707a"))[40])

  content((0.35, 4.72), text(size: 6.5pt, weight: "bold")[Q1a])
  line((1.25, 4.72), (1.35, 4.72), stroke: rgb("#b9822f"))
  content((9.55, 4.72), text(size: 6.2pt)[0.0])
  content((0.35, 4.37), text(size: 6.5pt, weight: "bold")[Q1b])
  line((1.25, 4.37), (1.35, 4.37), stroke: rgb("#b9822f"))
  content((9.55, 4.37), text(size: 6.2pt)[0.0])
  content((0.35, 4.02), text(size: 6.5pt, weight: "bold")[Q1c])
  line((1.25, 4.02), (1.35, 4.02), stroke: rgb("#b9822f"))
  content((9.55, 4.02), text(size: 6.2pt)[0.0])
  content((0.35, 3.67), text(size: 6.5pt, weight: "bold")[Q1d])
  line((1.25, 3.67), (1.35, 3.67), stroke: rgb("#b9822f"))
  content((9.55, 3.67), text(size: 6.2pt)[0.0])
  content((0.35, 3.32), text(size: 6.5pt, weight: "bold")[Q2a])
  rect((1.25, 3.24), (3.75, 3.40), fill: rgb("#b9822f"), stroke: none)
  content((9.55, 3.32), text(size: 6.2pt)[+12.5])
  content((0.35, 2.97), text(size: 6.5pt, weight: "bold")[Q2b])
  line((1.25, 2.97), (1.35, 2.97), stroke: rgb("#b9822f"))
  content((9.55, 2.97), text(size: 6.2pt)[0.0])
  content((0.35, 2.62), text(size: 6.5pt, weight: "bold")[Q3a])
  line((1.25, 2.62), (1.35, 2.62), stroke: rgb("#b9822f"))
  content((9.55, 2.62), text(size: 6.2pt)[0.0])
  content((0.35, 2.27), text(size: 6.5pt, weight: "bold")[Q3b])
  line((1.25, 2.27), (1.35, 2.27), stroke: rgb("#b9822f"))
  content((9.55, 2.27), text(size: 6.2pt)[0.0])
  content((0.35, 1.92), text(size: 6.5pt, weight: "bold")[Q3c])
  line((1.25, 1.92), (1.35, 1.92), stroke: rgb("#b9822f"))
  content((9.55, 1.92), text(size: 6.2pt)[0.0])
  content((0.35, 1.57), text(size: 6.5pt, weight: "bold")[Q3d])
  rect((1.25, 1.49), (3.75, 1.65), fill: rgb("#b9822f"), stroke: none)
  content((9.55, 1.57), text(size: 6.2pt)[+12.5])
  content((0.35, 1.22), text(size: 6.5pt, weight: "bold")[Q3e])
  rect((1.25, 1.14), (3.75, 1.30), fill: rgb("#b9822f"), stroke: none)
  content((9.55, 1.22), text(size: 6.2pt)[+12.5])
  content((0.35, 0.87), text(size: 6.5pt, weight: "bold")[Q3f])
  rect((1.25, 0.79), (8.75, 0.95), fill: rgb("#b9822f"), stroke: none)
  content((9.55, 0.87), text(size: 6.2pt)[+37.5])
})
#v(3pt)
#text(size: 7.4pt, fill: muted)[The largest development gain is Q3f. Questions with zero bars were unchanged on this split.]
]

#pagebreak()

== Prompt And Packet Registry

#text(size: 7.5pt, fill: muted)[This PDF uses short hashes for layout. Full SHA-256 values are recorded in `DEV-METRICS-STRICT-SCHEMA.md`.]

#table(columns: (auto, 1.75fr, auto), stroke: line, inset: (x: 5pt, y: 3.6pt),
  [#strong[Role]], [#strong[Prompt source]], [#strong[Prompt hash]],
  [baseline], [`experiments/records/.../prompts/grade_standard_v1_strict_schema.txt`], [`8fe0...fa5e`],
  [candidate v2], [`experiments/records/.../prompts/grade_candidate_v2_strict_schema.txt`], [`1eb9...2c3f`],
)

#table(columns: (auto, 1.75fr, auto), stroke: line, inset: (x: 5pt, y: 3.6pt),
  [#strong[Role]], [#strong[Packet path]], [#strong[Packet hash]],
  [baseline], [`Data/physics/benchmark/text_packets/physics-week9-baseline-text-strict-schema/G1-dev-r1`], [`e556...2601`],
  [candidate v2], [`Data/physics/benchmark/text_packets/physics-week9-candidate-v2-text-strict-schema/G1-dev-r1`], [`8987...ed6d`],
)

== Run Outputs Used For Metrics

#table(columns: (auto, 1fr, auto), stroke: line, inset: (x: 5pt, y: 3.6pt),
  [#strong[Role]], [#strong[Run directory]], [#strong[Validation]],
  [baseline], [`Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-baseline-text-G1-dev-r1-strict-schema`], [passed, 8/8],
  [candidate v2], [`Data/physics/benchmark/runs/physics-week9-baseline-candidate-v2/deepseek-candidate-text-G1-dev-r1-strict-schema`], [passed, 8/8],
)

#table(columns: (1fr, auto), stroke: line, inset: (x: 5pt, y: 3.6pt),
  [#strong[Local artifact]], [#strong[Hash]],
  [`dev-metrics-strict-schema.json`], [`68d4...e613`],
  [`dev-student-total-errors-strict-schema.csv`], [`3e11...b176`],
)

== Reproduction Commands

Run from the repository root. The API key must be supplied through `DEEPSEEK_API_KEY`; never write the key value into Git, reports, or shell history.

#table(columns: (auto, 1fr), stroke: line, inset: (x: 5pt, y: 3.6pt),
  [#strong[Step]], [#strong[Command record]],
  [1], [`python -m benchmark.core.cli check-run-readiness ...` using `baseline-plan.json` and `candidate-v2-plan.json`],
  [2], [`python -m benchmark.core.cli run-model-packet ...` with the baseline strict-schema packet],
  [3], [`python -m benchmark.core.cli run-model-packet ...` with the candidate v2 strict-schema packet],
)

The exact multiline commands are stored in `STRICT-SCHEMA-RERUN.md`, and the user-facing DeepSeek key setup instructions are stored in `EXTERNAL-API-DATA-GATE.md`.

== Freeze Gate Before Held-Out Test

#table(columns: (1fr, auto, 1.6fr), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Gate]], [#strong[Status]], [#strong[Evidence]],
  [Development validation], [passed], [both strict-schema runs validated 8/8],
  [Prompt packet record], [passed], [prompt, packet, text-source, and rubric hashes are recorded],
  [Candidate v2 freeze], [passed], [`CANDIDATE-V2-FREEZE.md` records the frozen prompt],
  [English rubric rule], [passed], [model-facing prompts and rubrics are English],
  [External API data gate], [passed], [anonymous data approved for DeepSeek public API by supervisor],
  [Held-out test], [not run], [build and dry-run held-out packets first],
)

== Limitations

- Development split only; 8 anonymous students.
- Text-only input; this run does not test multimodal image grading.
- Text source is a pilot-derived automatic transcript.
- Gold reference status is single primary rater, not adjudicated.
- The failed baseline attempts are retained under ignored `Data/` for audit, but are not used for metrics.
- This note supports held-out preparation for frozen candidate v2; it is not a final cross-course conclusion.
