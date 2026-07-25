# Tooling survey records

External-repository reviews in this directory must record a fixed source
snapshot in `sources.json`.

Run the local health check with:

```powershell
python -m benchmark.core.research_records
```

The check rejects:

- records that are not readable UTF-8;
- common mojibake markers;
- missing repository URLs or 40-character commit SHAs;
- source records that do not cite their declared repository and commit;
- GitHub evidence links that point to a floating `main` branch.

Repository home-page links may remain unpinned for navigation. Evidence links
to files or trees must use the recorded commit.
