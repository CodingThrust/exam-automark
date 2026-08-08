from __future__ import annotations

"""Merge final-approved anonymous submission snapshots without model access."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymous_cohort_snapshot import (  # noqa: E402
    merge_anonymous_submission_image_snapshots,
)
from benchmark.core.submission_scope_workflow import SubmissionScopeError  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Merge final-approved anonymous submission snapshots into one private cohort. "
            "This never invokes or authorizes a grading model."
        )
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        action="append",
        required=True,
        help="one private submission-snapshot root; repeat for every source",
    )
    parser.add_argument("--cohort-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--private-output-acknowledged", action="store_true")
    args = parser.parse_args(argv)
    if not args.private_output_acknowledged:
        parser.error("--private-output-acknowledged is required")
    try:
        result = merge_anonymous_submission_image_snapshots(
            snapshot_roots=args.snapshot_root,
            cohort_id=args.cohort_id,
            output_root=args.output_root,
        )
    except (OSError, ValueError, SubmissionScopeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
