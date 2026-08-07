from __future__ import annotations

"""Initialize or validate a private review of anomalous page-count groups.

The output contains only anonymous IDs, rendered counts, and review status.
It must remain under the private data boundary and does not authorize model use.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.page_scope_workflow import (  # noqa: E402
    PageScopeReviewError,
    initialize_page_scope_review,
    validate_page_scope_review,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create or validate a local-only page-scope review for anomalous "
            "submission page counts. No model is called."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("initialize", "validate"):
        child = subparsers.add_parser(command)
        child.add_argument("--private-manifest", type=Path, required=True)
        child.add_argument("--expected-pages-per-group", type=int, required=True)
        child.add_argument("--review-csv", type=Path, required=True)
        child.add_argument("--metadata", type=Path, required=True)
        child.add_argument(
            "--private-output-acknowledged",
            action="store_true",
            help="required acknowledgement that the review remains private local data",
        )
    args = parser.parse_args(argv)
    if args.expected_pages_per_group < 1:
        parser.error("--expected-pages-per-group must be positive")
    if not args.private_output_acknowledged:
        parser.error("--private-output-acknowledged is required")
    try:
        if args.command == "initialize":
            result = initialize_page_scope_review(
                private_manifest_path=args.private_manifest,
                expected_pages_per_group=args.expected_pages_per_group,
                review_csv_path=args.review_csv,
                metadata_path=args.metadata,
            )
        else:
            result = validate_page_scope_review(
                private_manifest_path=args.private_manifest,
                expected_pages_per_group=args.expected_pages_per_group,
                review_csv_path=args.review_csv,
                metadata_path=args.metadata,
            )
    except (OSError, PageScopeReviewError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
