# DSAA3071 Week 5 Development Transcript Production

Status: **text_transcripts_ready_pending_human_spot_check**

This note records how the local transcript source for DSAA3071 week 5 development model runs was produced. It intentionally contains no student answer text. The actual transcript JSON files live under ignored `Data/` and are not tracked by GitHub.

## Source

- Course: `DSAA3071`
- Assessment: `week5_test`
- Split: `development`
- Student set: `S017`, `S021`, `S002`, `S015`, `S020`, `S016`, `S022`
- Transcript source: `Data/DSAA3071/week5-benchmark-redaction-v3/transcripts/T1-dev-r1`
- Source PDFs: `Data/DSAA3071/week5-benchmark-redaction-v3/anonymized/<student_id>/week5.pdf`
- Packet generation base commit: `c9a56c4`
- Model-run commit policy: record `git rev-parse --short HEAD` at run time

## Method

1. Rendered each 3-page anonymized student PDF locally with Poppler `pdftoppm` for visual inspection.
2. Transcribed only visible student answers into one JSON file per anonymous student.
3. Excluded teacher scores, check marks, cross marks, and margin feedback from the transcript text.
4. Used `unclear: true` when handwriting, edits, or page-edge text made the transcription uncertain.
5. Ran `validate-transcripts` against `experiments/course_specs/DSAA3071_week5_test.json` and the development student list.

No external API was used to produce these transcripts.

## QA Summary

- Transcript files written: 7
- Expected questions per transcript: 10
- Schema readiness: `ready`
- Unclear-answer counts:
  - `S002`: 4 / 10
  - `S015`: 5 / 10
  - `S016`: 2 / 10
  - `S017`: 1 / 10
  - `S020`: 1 / 10
  - `S021`: 0 / 10
  - `S022`: 4 / 10

## Privacy Finding

During visual inspection, `S016` page 1 in `week5-benchmark-redaction-v3` still showed a residual handwritten identity string near the top margin. The transcript excludes it, so the text-only dev packets do not contain that identity string.

Until a corrected PDF redaction is generated, PDF-based grading packets from `week5-benchmark-redaction-v3` should be treated as privacy-blocked for model calls. The DSAA3071 week 5 development experiment should proceed only with the text-only transcript packets recorded in `text-packet-readiness-dev.json`.

## Reproduction Commands

Validate transcript structure:

```powershell
python -m benchmark.core.cli validate-transcripts `
  --course experiments\course_specs\DSAA3071_week5_test.json `
  --transcript-source Data\DSAA3071\week5-benchmark-redaction-v3\transcripts\T1-dev-r1 `
  --students-file experiments\records\DSAA3071-week5-test-plan\students-development.txt `
  --output experiments\records\DSAA3071-week5-dev-model-run\transcript-readiness-dev.json
```

See `RUN-PROTOCOL.md` for text packet generation and DeepSeek model-run commands.
