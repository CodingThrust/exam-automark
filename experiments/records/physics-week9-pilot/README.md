# Physics Week 9 Pilot Record

This is an after-the-fact reproducibility record for the legacy Physics Week 9
pilot data copied from the old TDAA-Go workspace.

Status: pilot only. Do not use this record as a final accuracy conclusion.

The private data snapshot is expected at:

```text
Data/physics/benchmark
```

The prompt packets for the Codex-mediated transcript and grading conditions are
expected at:

```text
Data/physics/benchmark/blind_packets
```

Offline validation command:

```bash
python -m benchmark.physics.cli validate --root Data/physics/benchmark
```

Regenerate legacy metrics from completed runs:

```bash
python -m benchmark.physics.cli evaluate --root Data/physics/benchmark --split dev
python -m benchmark.physics.cli evaluate --root Data/physics/benchmark --split test
python -m benchmark.physics.cli evaluate --root Data/physics/benchmark --split all
```

Known limitations:

- The pilot was produced before the generalized `benchmark.core` framework.
- G0 is a historical direct workflow, not a controlled rerun.
- GPT/Codex interactive conditions are not pinned API snapshots.
- The reference is primarily a single-rater grading standard.
- Physics Week 9 error patterns must not be generalized to DSAA3073, DSAA3071,
  or linear algebra.
