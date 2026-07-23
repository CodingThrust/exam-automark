# Benchmark decision table

Use this table at every consequential choice. Do not ask the user to choose
when the evidence already determines the answer.

| Situation | Required action | Forbidden shortcut |
| --- | --- | --- |
| Frozen transcript packet with source provenance and approved anonymous images both exist | Run matched `text-only` and `multimodal` development arms | Picking only the cheaper route |
| Transcript source is automatic/OCR and provenance is complete | Run it as `automatic-transcript`; separate transcription errors from grading errors | Calling it human-reviewed |
| Transcript exists but source kind/path/run ID is absent | Mark text arm blocked; repair provenance | Guessing whether it was automatic or reviewed |
| Images exist but privacy review is absent, false, or incomplete | Mark multimodal arm blocked; request privacy review | Inferring anonymity from `Sxxx` filenames |
| One input route is ready and the other is blocked | The ready route may run as partial evidence; package the blocked gate | Calling it a two-route comparison |
| Text and image packets contain different student IDs | Repair packet pairing before model calls | Comparing unmatched aggregates |
| Kimi Code is available but `MOONSHOT_API_KEY` is absent | Continue with the Kimi CLI route after Kimi Code auth | Requesting a platform API key |
| CLI is installed but login is unknown | Ask permission for a zero-data probe, then run it | Discovering auth with student data |
| Development arms have not all passed | Stay on development and package failures | Unlocking test |
| Development arms pass and the user already authorized the full campaign or explicitly approves test | Freeze config/commit, then run all 18 test students | Changing prompt, rubric, model, or skill mid-test |
| Existing run directory has passed matching metadata | Resume by reusing it | Paying to rerun it |
| Existing run directory is failed, incomplete, or mismatched | Preserve it and create a new `-rN` run/output | Deleting or overwriting evidence |
| CLI exits before valid output | Record a technical failure | Reporting zero accuracy |
| Valid output disagrees with gold | Record a scoring/accuracy error | Calling it a runtime failure |
| Any experiment fails | Package and submit failure status plus aggregated cause | Returning only a chat message |
| GitHub PR authentication is absent | Configure `gh` or environment-only token before the expensive run | Asking the user to private-message results |
| Privacy scan finds student IDs, raw text, images, logs, or a secret | Block submission and remove the unsafe artifact | Force-adding or bypassing the scan |

## Comparison invariants

A meaningful comparison changes only the named axis:

- baseline versus candidate: same engine, model, mode, split, student IDs, and
  run commit;
- text versus multimodal: same engine, model, condition, split, student IDs,
  rubric target, and run commit;
- Kimi versus Claude: same condition, input mode, split, student IDs, packet
  semantics, and run commit.

Report a comparison as unmatched if an invariant cannot be established.

## Default run order

1. Kimi text baseline/candidate.
2. Kimi multimodal baseline/candidate.
3. Claude text baseline/candidate.
4. Claude multimodal baseline/candidate.
5. Baseline/candidate metrics within each engine and mode.
6. Text/multimodal comparisons within each engine.
7. Kimi/Claude comparisons within each mode.
8. After development passes, repeat steps 1-7 on the sealed test split without
   changing the frozen workflow.

The order gives an early Kimi result, exercises both routes before the second
engine, and still produces useful partial evidence if a later subscription or
runtime limit is reached.
