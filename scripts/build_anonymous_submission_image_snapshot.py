from __future__ import annotations

"""Build a private variable-page snapshot whose unit is one submission."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.submission_scope_workflow import (  # noqa: E402
    SubmissionScopeError,
    build_anonymous_submission_image_snapshot,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a private anonymous-submission image snapshot; no model is called.")
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--final-review", type=Path, required=True)
    parser.add_argument("--final-review-validation", type=Path, required=True)
    parser.add_argument("--private-assembly-manifest", type=Path, required=True)
    parser.add_argument("--expected-pages-per-submission", type=int, required=True)
    parser.add_argument("--resolution", type=Path, required=True)
    parser.add_argument("--scope-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--private-output-acknowledged", action="store_true")
    args = parser.parse_args(argv)
    if args.expected_pages_per_submission < 1:
        parser.error("--expected-pages-per-submission must be positive")
    if not args.private_output_acknowledged:
        parser.error("--private-output-acknowledged is required")
    try:
        result = build_anonymous_submission_image_snapshot(
            artifact_root=args.artifact_root,
            final_review_path=args.final_review,
            final_review_validation_path=args.final_review_validation,
            private_assembly_manifest_path=args.private_assembly_manifest,
            expected_pages_per_submission=args.expected_pages_per_submission,
            resolution_path=args.resolution,
            scope_id=args.scope_id,
            output_root=args.output_root,
        )
    except (OSError, ValueError, SubmissionScopeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
