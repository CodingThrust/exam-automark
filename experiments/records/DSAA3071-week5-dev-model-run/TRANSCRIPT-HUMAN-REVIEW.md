# DSAA3071 Week 5 Development Transcript Human Review

Status: **ready**

This record freezes the question-by-question human review of the seven
DSAA3071 week 5 development transcripts. It contains no student answer text.
The transcript JSON files remain under ignored `Data/` and are not tracked by
GitHub.

## Frozen Sources

- Historical pre-review source: `Data/DSAA3071/week5-benchmark-redaction-v3/transcripts/T1-dev-r1`
- Historical source directory hash: `3e2e804049b4c70fd2e3c3252cef121ad90b049e4b9fec3454be069772ebaf2d`
- Historical packet `text_source_hash`: `163e919ed6995d789e6cb785a1bd172567a4baf8b2751cbe789f01126660e39e`
- Human-reviewed source: `Data/DSAA3071/week5-benchmark-redaction-v3/transcripts/T1-dev-human-reviewed-r1`
- Human-reviewed directory hash: `95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37`
- Human-reviewed readiness: `ready`, 7 / 7 transcripts

The pre-review source was restored byte-for-byte from the baseline packet used
by the completed DeepSeek run. Baseline and candidate-v2 packet transcript
copies were verified to be identical before restoration. This preserves the
input lineage of the existing metrics while giving future runs a separate,
immutable human-reviewed source.

## Review Method

1. The user compared every transcript question against its anonymized PDF.
2. Transcript text was corrected only when the visible student answer differed.
3. `unclear` was set to `false` only when the PDF evidence was sufficiently
   clear after manual review.
4. Remaining genuinely ambiguous content kept `unclear: true`.
5. The edited transcripts were validated against the frozen course schema and
   development student list.

## Change Summary

- Students reviewed: 7
- Question records reviewed: 70
- Question records changed: 14
- Transcript text changes: 9
- `unclear` flag changes: 11
- Students with at least one change: 5
- Remaining `unclear: true` records: 6

Changed question IDs are recorded without answer text in
`transcript-human-review.json`.

During validation, `S020` Q5 contained unescaped quotation marks introduced by
manual editing. The quotation marks were normalized without changing the answer
meaning, and the full reviewed snapshot then passed schema validation.

## Experimental Consequence

The existing DeepSeek baseline and candidate-v2 metrics remain valid only for
the historical pre-review packets. They must not be described as results on the
human-reviewed snapshot.

Any new baseline, candidate-v2, or candidate-v3 comparison must build new packet
directories from `T1-dev-human-reviewed-r1`, record the reviewed directory hash,
and write new model-run outputs. Existing packet and run directories must not be
overwritten.

## Reproduction

Windows PowerShell:

```powershell
python -m benchmark.core.cli validate-transcripts `
  --course experiments\course_specs\DSAA3071_week5_test.json `
  --transcript-source Data\DSAA3071\week5-benchmark-redaction-v3\transcripts\T1-dev-human-reviewed-r1 `
  --students-file experiments\records\DSAA3071-week5-test-plan\students-development.txt

python -c "from pathlib import Path; from benchmark.core.inventory import directory_digest; print(directory_digest(Path(r'Data\DSAA3071\week5-benchmark-redaction-v3\transcripts\T1-dev-human-reviewed-r1')))"
```

macOS/Linux:

```bash
python -m benchmark.core.cli validate-transcripts \
  --course experiments/course_specs/DSAA3071_week5_test.json \
  --transcript-source Data/DSAA3071/week5-benchmark-redaction-v3/transcripts/T1-dev-human-reviewed-r1 \
  --students-file experiments/records/DSAA3071-week5-test-plan/students-development.txt

python -c "from pathlib import Path; from benchmark.core.inventory import directory_digest; print(directory_digest(Path('Data/DSAA3071/week5-benchmark-redaction-v3/transcripts/T1-dev-human-reviewed-r1')))"
```

Expected reviewed directory hash:

`95e744f5811d9d869e86229f5a5177fe69d75104940989a09e9ebba8fc211c37`
