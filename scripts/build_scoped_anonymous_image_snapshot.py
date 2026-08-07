from __future__ import annotations

"""Create a local image-only snapshot from final-approved anonymous artifacts.

This command never invokes a model.  It copies only the explicitly selected
anonymous PNG pages after checking the schema-v2 preparation metadata, final
approval CSV, final-review-validation report, and source artifact hashes.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.scoped_anonymous_images import (  # noqa: E402
    ScopedSnapshotError,
    build_scoped_anonymous_image_snapshot,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a local, image-only scoped snapshot from an approved anonymous "
            "artifact version. This does not run a grading model."
        )
    )
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument(
        "--final-review",
        type=Path,
        required=True,
        help="must be artifact_root/manifest/anonymization_review.csv",
    )
    parser.add_argument(
        "--final-review-validation",
        type=Path,
        required=True,
        help="must be artifact_root/manifest/final-review-validation.json and status=ready",
    )
    parser.add_argument(
        "--page-suffix",
        action="append",
        required=True,
        metavar="pNN",
        help="one rendered page suffix to include for every S###; repeat for each suffix",
    )
    parser.add_argument(
        "--scope-id",
        required=True,
        help="stable local label for the declared question/page scope",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--cohort-preflight",
        type=Path,
        help=(
            "optional ready private cohort-preflight report; when supplied, its "
            "final-approval and page-scope bindings are verified and recorded"
        ),
    )
    args = parser.parse_args(argv)
    try:
        result = build_scoped_anonymous_image_snapshot(
            artifact_root=args.artifact_root,
            final_review_path=args.final_review,
            final_review_validation_path=args.final_review_validation,
            page_suffixes=args.page_suffix,
            scope_id=args.scope_id,
            output_root=args.output_root,
            cohort_preflight_path=args.cohort_preflight,
        )
    except ScopedSnapshotError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
