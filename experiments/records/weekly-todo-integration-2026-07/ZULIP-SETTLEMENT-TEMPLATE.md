# Zulip TODO Settlement Template

Use one settlement per TODO. Keep case-level student evidence and raw model
outputs in private storage; link only public-safe aggregate records.

```text
Topic: [exam-automark] TODO<N> - <short title>

Status:
completed | negative_result | blocked | implemented_waiting_external_validation

Goal:
<What decision or capability this TODO was meant to support.>

What was done:
- <Concrete action or implementation.>
- <Concrete action or experiment.>

Evidence:
- <Repository record, structured result, report, commit, or PR.>

Key result:
<The result, including a negative result or technical failure when applicable.>

Failure causes:
- <Observed cause with evidence.>
- <Separate environment/runtime/schema failures from scoring accuracy.>

What improved:
- <What became more reliable, automated, measurable, or accurate.>

How this helps the project:
<Connection to reproducibility, grading quality, privacy, iteration speed, or
decision quality.>

Limitations / prohibited claims:
- <What this evidence does not establish.>

Decision needed:
<A/B/C options with benefit, cost, and risk, or "none".>

Next action:
<One concrete follow-up and its gate.>
```

## Posting checklist

- No student IDs, answers, page images, private paths, credentials, or raw
  provider responses.
- Metrics identify development versus sealed test.
- Negative results remain negative.
- Technical failure counts are not reported as accuracy.
- Every claim links to a durable artifact.
- Failure and meaningful negative-result reports provide complete Chinese and
  English versions; a bilingual title alone is insufficient.
