#set document(title: "linearalgebra quiz1 Multi-route Grading Report")
#set page(margin: (x: 1.65cm, y: 1.30cm))
#set text(font: "New Computer Modern", size: 9pt)
#let ink = rgb("#17212b")
#let accent = rgb("#256d85")
#let green = rgb("#2d7a5b")
#let soft = rgb("#edf5f7")
#let line = rgb("#d8e4e8")
#let muted = rgb("#63707a")

#align(center)[
  #text(size: 18pt, weight: "bold", fill: ink)[linearalgebra quiz1 Multi-route Grading Report]
]
#align(center)[
  #text(size: 7.5pt, fill: muted)[Aggregate-only supplementary dashboard; detailed thresholds and confidence intervals remain in the pairwise reports.]
]

== Scope, question, and T1 gate

#grid(columns: (1fr, 1fr), gutter: 8pt,
  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[
    #strong[Course / assessment] #text(fill: muted)[linearalgebra / quiz1]
    #linebreak()
    #strong[Scope] #text(fill: muted)[development; 6c7bf60f199a...]
    #linebreak()
    #strong[Population] #text(fill: muted)[30 submissions; 300 score rows; points]
    #linebreak()
    #strong[Research question] #text(size: 7.5pt, fill: muted)[On this frozen, matched split, how closely do direct multimodal and transcription-to-text grading routes agree with the same frozen reference scores?]
  ],
  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[
    #strong[T1 readiness] #text(fill: green)[passed]
    #linebreak()
    #text(fill: muted)[30 / 30 complete; 0 failed]
    #linebreak()
    #text(size: 8pt, fill: muted)[T1 packet 3112779297d1...; run LA-v2-T1-codex-dev-30-v5_2-r2]
    #linebreak()
    #text(size: 7.5pt, fill: muted)[A complete T1 route is required before either text-only G1 route can be reported.]
  ],
)

== Exact-agreement comparison

#grid(columns: (29mm, 1fr, 17mm), column-gutter: 6pt, row-gutter: 5pt,
  [#strong[Route]], [#strong[Exact agreement]], [#align(right)[#strong[Value]]],
  [M1],
  [#box(width: 54mm, height: 7pt, fill: line, radius: 3pt)[#box(width: 48.06mm, height: 7pt, fill: accent, radius: 3pt)[]]],
  [#align(right)[89.0%]],
  [G1-Codex],
  [#box(width: 54mm, height: 7pt, fill: line, radius: 3pt)[#box(width: 47.16mm, height: 7pt, fill: accent, radius: 3pt)[]]],
  [#align(right)[87.3%]],
  [G1-DeepSeek],
  [#box(width: 54mm, height: 7pt, fill: line, radius: 3pt)[#box(width: 45.72mm, height: 7pt, fill: accent, radius: 3pt)[]]],
  [#align(right)[84.7%]],
)

== Error and risk metrics

#table(
  columns: (29mm, 22mm, 22mm, 22mm, 22mm),
  inset: 5pt, stroke: line, align: (left, right, right, right, right),
  table.header([#strong[Route]], [#strong[Total MAE]], [#strong[Within 1]], [#strong[Severe]], [#strong[Bias]]),
  [M1], [2.53], [50.0%], [46.7%], [+0.16],
  [G1-Codex], [3.03], [50.0%], [40.0%], [+0.00],
  [G1-DeepSeek], [8.63], [26.7%], [66.7%], [-0.95],
)

#text(size: 7.4pt, fill: muted)[Metric definitions: exact agreement = an exact score-row match; Total MAE = mean absolute error of submission totals; Within 1 = total error at most 1 point; Severe = total error above 2 points; Bias = mean signed score-row error (route minus reference).]

== Reproducibility commitments

#table(
  columns: (25mm, 23mm, 30mm, 30mm, 1fr),
  inset: 4pt, stroke: line, align: (left, left, left, left, left),
  table.header([#strong[Route]], [#strong[Mode]], [#strong[Packet]], [#strong[Prompt]], [#strong[Model]]),
  [M1], [multimodal], [d70093ab5bd4...], [29123e7cd9ce...], [codex_cli / gpt-5.6-sol],
  [G1-Codex], [text-only], [271588f95aee...], [29123e7cd9ce...], [codex_cli / gpt-5.6-sol],
  [G1-DeepSeek], [text-only], [271588f95aee...], [29123e7cd9ce...], [deepseek / deepseek-v4-pro],
)

#grid(columns: (1fr, 1fr), gutter: 7pt,
  box(fill: soft, stroke: line, inset: 6pt, radius: 4pt)[
    #strong[Canonical commitments]
    #linebreak()
    #text(size: 7.1pt, fill: muted)[Snapshot SHA-256: #raw("6c7bf60f199a80eb27bad6cde854ce2d60eacd1fbe6995305a22226cd2797c54")]
    #linebreak()
    #text(size: 7.1pt, fill: muted)[Full packet and prompt SHA-256 commitments remain in canonical public JSON at #raw("routes[*].run.packet_hash") and #raw("routes[*].run.prompt_hash"). The short hashes above are display locators.]
  ],
  box(fill: soft, stroke: line, inset: 6pt, radius: 4pt)[
    #strong[Reproduce / verify]
    #linebreak()
    #text(size: 7.1pt, fill: muted)[Rebuild from the seven aggregate-only inputs; the CLI flag reference is:]
    #linebreak()
    #text(font: "Cascadia Mono", size: 6.8pt)[python -m benchmark.core.cli render-multi-route-report --help]
    #linebreak()
    #text(font: "Cascadia Mono", size: 6.8pt)[typst compile report.typ report.pdf]
  ],
)

#text(size: 8pt, fill: muted)[Shared roster commitment: 0fe82cddead4.... Shared G1 transcript source: aec0507b6f25.... M1 and the two G1 packet hashes are intentionally retained per route rather than forced equal.]

== Limitations, safeguards, and operating rules

- M1 and T1 may execute in parallel because both independently consume the same frozen images; G1 begins only after T1 passes validation.
- The route contract, snapshot commitment, and full T1-to-G1 lineage binding must all match before this dashboard can be rendered.
- This report is aggregate-only and contains no student identifiers, individual scores, answers, transcripts, evidence, prompts, responses, or private paths.
- Development or calibration evidence does not by itself authorize held-out or production grading.

#text(size: 8pt, fill: muted)[This dashboard is supplementary to the aggregate pairwise metric reports. Those reports retain the score unit, metric thresholds, and paired bootstrap confidence intervals for each comparison.]
