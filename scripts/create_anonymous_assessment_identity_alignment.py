from __future__ import annotations

"""Create a hash-bound private assessment-identity alignment decision."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymous_cohort_snapshot import (  # noqa: E402
    create_assessment_identity_alignment,
)
from benchmark.core.submission_scope_workflow import SubmissionScopeError  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record a private, hash-bound course-owner confirmation that independently "
            "frozen submission snapshots belong to one assessment. This never invokes "
            "or authorizes a grading model."
        )
    )
    parser.add_argument("--snapshot-root", type=Path, action="append", required=True)
    parser.add_argument(
        "--canonical-snapshot-root",
        type=Path,
        required=True,
        help="declared source whose assessment_id becomes the cohort target",
    )
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-output-acknowledged", action="store_true")
    args = parser.parse_args(argv)
    if not args.private_output_acknowledged:
        parser.error("--private-output-acknowledged is required")
    try:
        result = create_assessment_identity_alignment(
            snapshot_roots=args.snapshot_root,
            canonical_snapshot_root=args.canonical_snapshot_root,
            reviewer=args.reviewer,
            reviewed_at=args.reviewed_at,
            reason=args.reason,
            output_path=args.output,
        )
    except (OSError, ValueError, SubmissionScopeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
