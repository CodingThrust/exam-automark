# DSAA3071 Week 5 S016 Redaction Correction

Status: **corrected_and_synced**

Date: 2026-07-18

This record contains no student answer text and no identity text. It records why the DSAA3071 week 5 development PDF packet hashes changed after the original dry run.

## What Changed

- A residual handwritten identity string was found on `S016` page 1 in `week5-benchmark-redaction-v3` during transcript production.
- The user manually erased the residual identity area in the anonymized `S016` PDF.
- The corrected PDF was rendered for pages 1-3 with Poppler for visual QA.
- The corrected PDF was copied into the development T1/G1 packet inputs for baseline and candidate-v2.
- Held-out packets were not changed because `S016` is not in the held-out split.

## Correction Anchors

- Correction ID: `DSAA3071-week5-S016-redaction-2026-07-18`
- Corrected source PDF: `Data/DSAA3071/week5-benchmark-redaction-v3/anonymized/S016/week5.pdf`
- Corrected source PDF SHA-256: `385782d3f0ab1192a40af5743fb005cada550f7132bbea1f039ad7fb434fd40a`
- Corrected `inputs/S016` directory hash: `948b8fbd7f8a1f6251bd7d70fca47c49b8a0161aa7c51686a8f0d6f10076e440`

## Updated Development Packet Hashes

| Condition | Packet | Task | Packet hash |
| --- | --- | --- | --- |
| baseline-v1 | `T1-dev-r1` | transcribe | `f3954dfa147467b564cf8c7d7d5f669587f4e64a57aa645b07a217360df621ad` |
| baseline-v1 | `G1-dev-r1` | grade | `0814dc999791cc8a6521cdfa6eb6aaeabfbea22523ca59d79bcec8442ae3343e` |
| candidate-v2 | `T1-dev-r1` | transcribe | `a9a965ed019dcbbd3d67db564d532eec29a2aff1e100d326a270d8a0fea6d463` |
| candidate-v2 | `G1-dev-r1` | grade | `7a51e58eb55960405cfd145cbe41a862f3d5a8505ceec73d7e0b60ac9f76ebba` |

## Reproduction Notes

Render-check pattern:

```powershell
pdftoppm -f 1 -l 3 -png -r 120 Data\DSAA3071\week5-benchmark-redaction-v3\anonymized\S016\week5.pdf tmp\S016-page
```

After correction, rerun or refresh packet records so `manifest.json` and plan `packet_hash` values match the corrected local files.

## Impact On Existing Metrics

The recorded DeepSeek development metrics used text-only transcript packets, not PDF packets. Therefore this PDF correction does not change those metrics. It does matter for any future multimodal or headless PDF grading run.

The transcript text still needs human spot-check before final accuracy claims.
