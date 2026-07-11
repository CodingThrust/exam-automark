# Data Inventories

The JSON files in this directory summarize local `Data/<course>` folders without
recording raw filenames. They are safe to review in Git because they contain
only hashes, counts, extension distributions, layout flags, and policy notes.

The actual data remains outside Git. Final reproducible experiments should use
anonymous snapshots from the private HKUST-GZ GitLab data repository and record
the matching snapshot hash in `plan.json` or `experiment.json`.
