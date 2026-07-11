#set document(title: "Physics Week 9 Pilot Reproducibility Note")
#set page(margin: (x: 1.6cm, y: 1.25cm))
#set text(font: "New Computer Modern", size: 9.25pt)
#import "@preview/cetz:0.5.2"
#let ink = rgb("#17212b")
#let accent = rgb("#256d85")
#let accent2 = rgb("#7a5c00")
#let soft = rgb("#edf5f7")
#let line = rgb("#d8e4e8")
#let danger = rgb("#a33b2f")
#let muted = rgb("#63707a")
#let pill(body) = box(fill: soft, stroke: line, inset: (x: 7pt, y: 4pt), radius: 3pt, body)
#let metric-card(label, value, detail) = box(fill: soft, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[#text(size: 8pt, fill: accent)[#label]\ #text(size: 17pt, weight: "bold")[#value]\ #text(size: 8pt)[#detail]]

#align(center)[
  #text(size: 20pt, weight: "bold", fill: ink)[Physics Week 9 Pilot Reproducibility Note]
]

#align(center)[
  #pill[Pilot record. Use for protocol design, not final accuracy claims.]
]

#box(fill: soft, stroke: line, inset: 10pt, radius: 4pt)[#strong[Reading guide.] This is a reproducibility note, not a leaderboard. G0 has the highest exact agreement in this metrics file (91.3%). The historical G0 baseline is retained for context at 91.3% exact agreement. #text(fill: danger)[Because this is a legacy pilot, these numbers guide protocol design and should not be presented as final cross-course evidence.]]

== What Is Being Reproduced

#grid(columns: (1fr, 1fr, 1fr), gutter: 8pt,
  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[#strong[1. Freeze]\ Anonymous data snapshot and rubric are identified by hash.],
  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[#strong[2. Packetize]\ Model-facing work happens only inside prompt packets with `prompt.txt`.],
  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[#strong[3. Evaluate]\ Predictions are compared with the same metrics script and recorded here.],
)

This record covers `physics` / `week9` on branch `codex/repro-experiment-framework`.

== Reproducibility Anchors

#table(columns: (auto, auto), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Anchor]], [#strong[Value]],
  [Experiment], [physics-week9-pilot],
  [Git], [codex/repro-experiment-framework @ 9e1c7c018268],
  [Data snapshot], [d134f9127adc...],
  [Metrics], [Data/physics/benchmark/metrics-all.json],
  [Typst source], [experiments/records/physics-week9-pilot/note.typ],
)

== Prompt Packet Registry

#table(columns: (auto, auto), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Condition]], [#strong[Packet SHA-256]],
  [G2-dev-r1], [752bf779d5fb...],
  [G2-test-r1], [02d067965bfb...],
  [G3-dev-r1], [6738cb00a40d...],
  [G3-test-r1], [87103669cc7b...],
  [T1-dev-r1], [7763fc740353...],
  [T1-test-r1], [b63aadd3cf33...],
)

== Key Findings

- G0 is the highest exact-agreement condition in this file at 91.3%.
- The historical G0 baseline remains the top exact-agreement condition, so this pilot does not show a workflow improvement over G0.
- D2 has the highest severe-error rate (40.0%), which is the clearest operational risk signal in this pilot.
- DeepSeek transcript subset: D1 to D2 changed exact agreement from 78.3% to 79.2%; human-minus-automatic interval -10.0% to 15.8%.
- GPT transcript subset: G2 to G3 changed exact agreement from 87.5% to 78.3%; human-minus-automatic interval -11.7% to -6.7%.
- Interpret all findings as protocol guidance only; this pilot is not evidence that one workflow generalizes across courses.

#pagebreak()

== Results At A Glance

#grid(columns: 3, gutter: 8pt, metric-card("Best exact", "91.3%", "G0"), metric-card("G0 exact", "91.3%", "historical baseline"), metric-card("Highest severe", "40.0%", "D2"))

#grid(columns: (1.05fr, 0.95fr), gutter: 8pt,
  box(fill: white, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[
#strong[Accuracy vs severe-error risk]
#v(4pt)
#cetz.canvas({
  import cetz.draw: *
  rect((0.55, 0.45), (7.25, 4.45), fill: rgb("#fbfdfe"), stroke: rgb("#d8e4e8"))
  line((0.8, 0.6), (6.9, 0.6), stroke: rgb("#63707a"))
  line((0.8, 0.6), (0.8, 4.1), stroke: rgb("#63707a"))
  content((0.75, 4.32), text(size: 7pt, fill: rgb("#63707a"))[Exact])
  content((6.95, 0.35), text(size: 7pt, fill: rgb("#63707a"))[Severe])
  line((0.80, 0.54), (0.80, 0.66), stroke: rgb("#63707a"))
  content((0.80, 0.24), text(size: 6.5pt, fill: rgb("#63707a"))[0.0%])
  line((3.70, 0.54), (3.70, 0.66), stroke: rgb("#63707a"))
  content((3.70, 0.24), text(size: 6.5pt, fill: rgb("#63707a"))[20.0%])
  line((6.61, 0.54), (6.61, 0.66), stroke: rgb("#63707a"))
  content((6.61, 0.24), text(size: 6.5pt, fill: rgb("#63707a"))[40.0%])
  line((0.74, 1.48), (0.86, 1.48), stroke: rgb("#63707a"))
  content((0.38, 1.48), text(size: 6.5pt, fill: rgb("#63707a"))[80.0%])
  line((0.74, 3.23), (0.86, 3.23), stroke: rgb("#63707a"))
  content((0.38, 3.23), text(size: 6.5pt, fill: rgb("#63707a"))[90.0%])
  rect((6.29, 1.45), (6.49, 1.65), fill: rgb("#a33b2f"), stroke: white)
  content((6.71, 1.73), text(size: 7pt, weight: "bold", fill: rgb("#17212b"))[D1])
  rect((6.51, 1.23), (6.71, 1.43), fill: rgb("#a33b2f"), stroke: white)
  content((6.89, 1.15), text(size: 7pt, weight: "bold", fill: rgb("#17212b"))[D2])
  rect((1.26, 3.36), (1.46, 3.56), fill: rgb("#2d7a5b"), stroke: white)
  content((1.66, 3.61), text(size: 7pt, weight: "bold", fill: rgb("#17212b"))[G0])
  rect((4.61, 2.86), (4.81, 3.06), fill: rgb("#b9822f"), stroke: white)
  content((4.99, 3.14), text(size: 7pt, weight: "bold", fill: rgb("#17212b"))[G2])
  rect((5.06, 1.08), (5.26, 1.28), fill: rgb("#b9822f"), stroke: white)
  content((5.46, 1.00), text(size: 7pt, weight: "bold", fill: rgb("#17212b"))[G3])
  rect((0.90, 3.62), (2.30, 3.98), fill: rgb("#e8f3ed"), stroke: none)
  content((1.60, 3.80), text(size: 6.5pt, fill: rgb("#316a4d"))[target zone])
})
#v(3pt)
#text(size: 7.5pt, fill: muted)[Upper left is better: high exact agreement and low severe-error rate.]
],
  box(fill: white, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[
#strong[Ranked condition bars]
#v(4pt)
#cetz.canvas({
  import cetz.draw: *
  content((1.05, 4.72), text(size: 6.5pt, fill: rgb("#63707a"))[0])
  content((4.20, 4.72), text(size: 6.5pt, fill: rgb("#63707a"))[50%])
  content((7.25, 4.72), text(size: 6.5pt, fill: rgb("#63707a"))[100%])
  content((0.34, 4.27), text(size: 7.5pt, weight: "bold")[G0])
  rect((1.05, 4.12), (7.25, 4.28), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 4.12), (6.71, 4.28), fill: rgb("#256d85"), stroke: none)
  rect((1.26, 4.01), (1.31, 4.39), fill: rgb("#a33b2f"), stroke: none)
  content((7.72, 4.27), text(size: 7pt)[91.3%])
  content((8.58, 4.27), text(size: 6.5pt, fill: rgb("#a33b2f"))[3.8%])
  content((0.34, 3.52), text(size: 7.5pt, weight: "bold")[G2])
  rect((1.05, 3.37), (7.25, 3.53), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 3.37), (6.53, 3.53), fill: rgb("#256d85"), stroke: none)
  rect((2.69, 3.26), (2.74, 3.64), fill: rgb("#a33b2f"), stroke: none)
  content((7.72, 3.52), text(size: 7pt)[88.5%])
  content((8.58, 3.52), text(size: 6.5pt, fill: rgb("#a33b2f"))[26.9%])
  content((0.34, 2.77), text(size: 7.5pt, weight: "bold")[D1])
  rect((1.05, 2.62), (7.25, 2.78), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 2.62), (6.04, 2.78), fill: rgb("#256d85"), stroke: none)
  rect((3.41, 2.51), (3.46, 2.89), fill: rgb("#a33b2f"), stroke: none)
  content((7.72, 2.77), text(size: 7pt)[80.4%])
  content((8.58, 2.77), text(size: 6.5pt, fill: rgb("#a33b2f"))[38.5%])
  content((0.34, 2.02), text(size: 7.5pt, weight: "bold")[D2])
  rect((1.05, 1.87), (7.25, 2.03), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 1.87), (5.96, 2.03), fill: rgb("#256d85"), stroke: none)
  rect((3.51, 1.76), (3.56, 2.14), fill: rgb("#a33b2f"), stroke: none)
  content((7.72, 2.02), text(size: 7pt)[79.2%])
  content((8.58, 2.02), text(size: 6.5pt, fill: rgb("#a33b2f"))[40.0%])
  content((0.34, 1.27), text(size: 7.5pt, weight: "bold")[G3])
  rect((1.05, 1.12), (7.25, 1.28), fill: rgb("#d8e4e8"), stroke: none)
  rect((1.05, 1.12), (5.91, 1.28), fill: rgb("#256d85"), stroke: none)
  rect((2.89, 1.01), (2.94, 1.39), fill: rgb("#a33b2f"), stroke: none)
  content((7.72, 1.27), text(size: 7pt)[78.3%])
  content((8.58, 1.27), text(size: 6.5pt, fill: rgb("#a33b2f"))[30.0%])
})
#v(3pt)
#text(size: 7.5pt, fill: muted)[Blue bars show exact agreement. Red ticks show severe-error rate.]
],
)
#v(6pt)
#box(fill: white, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[
#strong[Transcript-path delta]
#v(4pt)
#cetz.canvas({
  import cetz.draw: *
  line((1.0, 0.55), (10.0, 0.55), stroke: rgb("#63707a"))
  content((1.0, 0.25), text(size: 6.5pt, fill: rgb("#63707a"))[75%])
  content((4.0, 0.25), text(size: 6.5pt, fill: rgb("#63707a"))[80%])
  content((7.0, 0.25), text(size: 6.5pt, fill: rgb("#63707a"))[85%])
  content((10.0, 0.25), text(size: 6.5pt, fill: rgb("#63707a"))[90%])
  content((0.35, 2.05), text(size: 7.5pt, weight: "bold")[DeepSeek])
  line((3.00, 2.05), (3.50, 2.05), stroke: (paint: rgb("#7a5c00"), thickness: 1.2pt))
  rect((2.92, 1.97), (3.08, 2.13), fill: rgb("#256d85"), stroke: white)
  rect((3.42, 1.97), (3.58, 2.13), fill: rgb("#7a5c00"), stroke: white)
  content((3.00, 2.37), text(size: 6.5pt, fill: rgb("#256d85"))[D1 78.3%])
  content((3.50, 1.73), text(size: 6.5pt, fill: rgb("#7a5c00"))[D2 79.2%])
  content((0.35, 1.10), text(size: 7.5pt, weight: "bold")[GPT])
  line((8.50, 1.10), (3.00, 1.10), stroke: (paint: rgb("#7a5c00"), thickness: 1.2pt))
  rect((8.42, 1.02), (8.58, 1.18), fill: rgb("#256d85"), stroke: white)
  rect((2.92, 1.02), (3.08, 1.18), fill: rgb("#7a5c00"), stroke: white)
  content((8.50, 1.42), text(size: 6.5pt, fill: rgb("#256d85"))[G2 87.5%])
  content((3.00, 0.78), text(size: 6.5pt, fill: rgb("#7a5c00"))[G3 78.3%])
})
#v(3pt)
#text(size: 7.5pt, fill: muted)[Same-student subset comparison: automatic transcript versus human transcript.]
]
#v(6pt)
#box(fill: white, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[
#strong[Question-level agreement heatmap]
#v(4pt)
#cetz.canvas({
  import cetz.draw: *
  content((0.35, 2.59), text(size: 6.5pt, fill: rgb("#63707a"))[Cond.])
  content((1.31, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q1a])
  content((1.83, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q1b])
  content((2.35, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q1c])
  content((2.87, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q1d])
  content((3.39, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q2a])
  content((3.91, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q2b])
  content((4.43, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q3a])
  content((4.95, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q3b])
  content((5.47, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q3c])
  content((5.99, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q3d])
  content((6.51, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q3e])
  content((7.03, 2.59), text(size: 5.8pt, fill: rgb("#63707a"))[Q3f])
  content((0.35, 2.19), text(size: 6.5pt, weight: "bold")[G0])
  rect((1.05, 2.02), (1.57, 2.37), fill: rgb("#2d7a5b"), stroke: white)
  rect((1.57, 2.02), (2.09, 2.37), fill: rgb("#2d7a5b"), stroke: white)
  rect((2.09, 2.02), (2.61, 2.37), fill: rgb("#2d7a5b"), stroke: white)
  rect((2.61, 2.02), (3.13, 2.37), fill: rgb("#2d7a5b"), stroke: white)
  rect((3.13, 2.02), (3.65, 2.37), fill: rgb("#7ba989"), stroke: white)
  rect((3.65, 2.02), (4.17, 2.37), fill: rgb("#7ba989"), stroke: white)
  rect((4.17, 2.02), (4.69, 2.37), fill: rgb("#d6b15b"), stroke: white)
  rect((4.69, 2.02), (5.21, 2.37), fill: rgb("#2d7a5b"), stroke: white)
  rect((5.21, 2.02), (5.73, 2.37), fill: rgb("#d6b15b"), stroke: white)
  rect((5.73, 2.02), (6.25, 2.37), fill: rgb("#7ba989"), stroke: white)
  rect((6.25, 2.02), (6.77, 2.37), fill: rgb("#d6b15b"), stroke: white)
  rect((6.77, 2.02), (7.29, 2.37), fill: rgb("#7ba989"), stroke: white)
  content((0.35, 1.85), text(size: 6.5pt, weight: "bold")[G2])
  rect((1.05, 1.67), (1.57, 2.02), fill: rgb("#2d7a5b"), stroke: white)
  rect((1.57, 1.67), (2.09, 2.02), fill: rgb("#2d7a5b"), stroke: white)
  rect((2.09, 1.67), (2.61, 2.02), fill: rgb("#7ba989"), stroke: white)
  rect((2.61, 1.67), (3.13, 2.02), fill: rgb("#d6b15b"), stroke: white)
  rect((3.13, 1.67), (3.65, 2.02), fill: rgb("#b9822f"), stroke: white)
  rect((3.65, 1.67), (4.17, 2.02), fill: rgb("#7ba989"), stroke: white)
  rect((4.17, 1.67), (4.69, 2.02), fill: rgb("#7ba989"), stroke: white)
  rect((4.69, 1.67), (5.21, 2.02), fill: rgb("#2d7a5b"), stroke: white)
  rect((5.21, 1.67), (5.73, 2.02), fill: rgb("#7ba989"), stroke: white)
  rect((5.73, 1.67), (6.25, 2.02), fill: rgb("#7ba989"), stroke: white)
  rect((6.25, 1.67), (6.77, 2.02), fill: rgb("#b9822f"), stroke: white)
  rect((6.77, 1.67), (7.29, 2.02), fill: rgb("#7ba989"), stroke: white)
  content((0.35, 1.50), text(size: 6.5pt, weight: "bold")[D1])
  rect((1.05, 1.32), (1.57, 1.67), fill: rgb("#7ba989"), stroke: white)
  rect((1.57, 1.32), (2.09, 1.67), fill: rgb("#2d7a5b"), stroke: white)
  rect((2.09, 1.32), (2.61, 1.67), fill: rgb("#b9822f"), stroke: white)
  rect((2.61, 1.32), (3.13, 1.67), fill: rgb("#d6b15b"), stroke: white)
  rect((3.13, 1.32), (3.65, 1.67), fill: rgb("#b9822f"), stroke: white)
  rect((3.65, 1.32), (4.17, 1.67), fill: rgb("#7ba989"), stroke: white)
  rect((4.17, 1.32), (4.69, 1.67), fill: rgb("#7ba989"), stroke: white)
  rect((4.69, 1.32), (5.21, 1.67), fill: rgb("#d6b15b"), stroke: white)
  rect((5.21, 1.32), (5.73, 1.67), fill: rgb("#d6b15b"), stroke: white)
  rect((5.73, 1.32), (6.25, 1.67), fill: rgb("#b9822f"), stroke: white)
  rect((6.25, 1.32), (6.77, 1.67), fill: rgb("#b9822f"), stroke: white)
  rect((6.77, 1.32), (7.29, 1.67), fill: rgb("#d6b15b"), stroke: white)
  content((0.35, 1.15), text(size: 6.5pt, weight: "bold")[D2])
  rect((1.05, 0.97), (1.57, 1.32), fill: rgb("#2d7a5b"), stroke: white)
  rect((1.57, 0.97), (2.09, 1.32), fill: rgb("#2d7a5b"), stroke: white)
  rect((2.09, 0.97), (2.61, 1.32), fill: rgb("#a33b2f"), stroke: white)
  rect((2.61, 0.97), (3.13, 1.32), fill: rgb("#d6b15b"), stroke: white)
  rect((3.13, 0.97), (3.65, 1.32), fill: rgb("#b9822f"), stroke: white)
  rect((3.65, 0.97), (4.17, 1.32), fill: rgb("#2d7a5b"), stroke: white)
  rect((4.17, 0.97), (4.69, 1.32), fill: rgb("#7ba989"), stroke: white)
  rect((4.69, 0.97), (5.21, 1.32), fill: rgb("#2d7a5b"), stroke: white)
  rect((5.21, 0.97), (5.73, 1.32), fill: rgb("#7ba989"), stroke: white)
  rect((5.73, 0.97), (6.25, 1.32), fill: rgb("#b9822f"), stroke: white)
  rect((6.25, 0.97), (6.77, 1.32), fill: rgb("#b9822f"), stroke: white)
  rect((6.77, 0.97), (7.29, 1.32), fill: rgb("#a33b2f"), stroke: white)
  content((0.35, 0.80), text(size: 6.5pt, weight: "bold")[G3])
  rect((1.05, 0.62), (1.57, 0.97), fill: rgb("#2d7a5b"), stroke: white)
  rect((1.57, 0.62), (2.09, 0.97), fill: rgb("#2d7a5b"), stroke: white)
  rect((2.09, 0.62), (2.61, 0.97), fill: rgb("#a33b2f"), stroke: white)
  rect((2.61, 0.62), (3.13, 0.97), fill: rgb("#d6b15b"), stroke: white)
  rect((3.13, 0.62), (3.65, 0.97), fill: rgb("#a33b2f"), stroke: white)
  rect((3.65, 0.62), (4.17, 0.97), fill: rgb("#2d7a5b"), stroke: white)
  rect((4.17, 0.62), (4.69, 0.97), fill: rgb("#2d7a5b"), stroke: white)
  rect((4.69, 0.62), (5.21, 0.97), fill: rgb("#7ba989"), stroke: white)
  rect((5.21, 0.62), (5.73, 0.97), fill: rgb("#2d7a5b"), stroke: white)
  rect((5.73, 0.62), (6.25, 0.97), fill: rgb("#d6b15b"), stroke: white)
  rect((6.25, 0.62), (6.77, 0.97), fill: rgb("#b9822f"), stroke: white)
  rect((6.77, 0.62), (7.29, 0.97), fill: rgb("#b9822f"), stroke: white)
  rect((7.94, 1.67), (8.19, 1.85), fill: rgb("#a33b2f"), stroke: none)
  content((8.56, 1.76), text(size: 6.3pt, fill: rgb("#63707a"))[low])
  rect((7.94, 2.02), (8.19, 2.20), fill: rgb("#b9822f"), stroke: none)
  content((8.56, 2.11), text(size: 6.3pt, fill: rgb("#63707a"))[mid])
  rect((7.94, 2.37), (8.19, 2.55), fill: rgb("#2d7a5b"), stroke: none)
  content((8.56, 2.46), text(size: 6.3pt, fill: rgb("#63707a"))[high])
})
#v(3pt)
#text(size: 7.5pt, fill: muted)[Cells show per-question exact agreement. Red and amber cells are review targets.]
]

#pagebreak()

== Condition Details

#table(columns: (auto, auto, auto, auto, auto, auto, auto, auto), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Cond.]], [#strong[N]], [#strong[Population]], [#strong[Exact]], [#strong[Total MAE]], [#strong[Within 1]], [#strong[Severe]], [#strong[Bias]],
  [D1], [26], [full_split], [80.4%], [2.452], [38.5%], [38.5%], [-0.169],
  [D2], [10], [transcript_subset], [79.2%], [1.950], [30.0%], [40.0%], [-0.154],
  [G0], [26], [full_split], [91.3%], [0.413], [88.5%], [3.8%], [+0.030],
  [G2], [26], [full_split], [88.5%], [1.135], [61.5%], [26.9%], [-0.027],
  [G3], [10], [transcript_subset], [78.3%], [1.575], [40.0%], [30.0%], [-0.119],
)

== Where Errors Concentrate

#table(columns: (auto, auto), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Condition]], [#strong[Lowest-agreement questions]],
  [D1], [Q1c: 69.2%, Q2a: 69.2%, Q3d: 69.2%],
  [D2], [Q1c: 40.0%, Q3f: 50.0%, Q2a: 60.0%],
  [G0], [Q3e: 76.9%, Q3a: 80.8%, Q3c: 84.6%],
  [G2], [Q2a: 69.2%, Q3e: 73.1%, Q1d: 84.6%],
  [G3], [Q2a: 30.0%, Q1c: 40.0%, Q3e: 60.0%],
)

== Paired And Transcript Comparisons

#strong[Paired exact-agreement differences versus G0]

#table(columns: (auto, auto, auto), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Condition]], [#strong[Mean diff.]], [#strong[95% interval]],
  [D1], [-10.9%], [-18.3% to -4.2%],
  [G2], [-2.9%], [-6.4% to 0.6%],
)

#strong[Transcript subset comparisons]

#table(columns: (auto, auto, auto, auto, auto), stroke: line, inset: (x: 6pt, y: 4pt),
  [#strong[Model]], [#strong[Conditions]], [#strong[Auto exact]], [#strong[Human exact]], [#strong[Interval]],
  [DeepSeek], [D1 -> D2], [78.3%], [79.2%], [-10.0% to 15.8%],
  [GPT], [G2 -> G3], [87.5%], [78.3%], [-11.7% to -6.7%],
)

== Reproduction Commands

```bash
python -m benchmark.core.cli audit-packet --packet <packet-path>
python -m benchmark.physics.cli validate --root Data/physics/benchmark
python -m benchmark.physics.cli evaluate --root Data/physics/benchmark --split dev
python -m benchmark.physics.cli evaluate --root Data/physics/benchmark --split test
python -m benchmark.physics.cli evaluate --root Data/physics/benchmark --split all
```

== Limitations

- after-the-fact record for the legacy Physics Week 9 pilot
- pilot only; not a final accuracy conclusion
- private data is excluded from Git and must come from the private data snapshot
- reference scores are single-primary-rater, not adjudicated
- Physics Week 9 is a pilot and must not be generalized to other courses
- historical baselines and interactive model runs are not controlled reruns
