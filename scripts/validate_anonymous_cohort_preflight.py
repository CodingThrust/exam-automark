from __future__ import annotations

"""Validate final anonymization plus anomalous page-scope decisions for a cohort."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.cohort_preflight import (  # noqa: E402
    CohortPreflightError,
    build_anonymous_cohort_preflight,
    canonical_report_bytes,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a private anonymous cohort's final anonymization and anomalous "
            "page-scope decisions. No model is called or authorized."
        )
    )
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--final-review-validation", type=Path, required=True)
    parser.add_argument("--private-manifest", type=Path, required=True)
    parser.add_argument("--expected-pages-per-group", type=int, required=True)
    parser.add_argument("--page-scope-review-csv", type=Path, required=True)
    parser.add_argument("--page-scope-review-metadata", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        help="optional fresh private report path; refuses to overwrite divergent content",
    )
    parser.add_argument("--private-output-acknowledged", action="store_true")
    args = parser.parse_args(argv)
    if args.expected_pages_per_group < 1:
        parser.error("--expected-pages-per-group must be positive")
    if args.output is not None and not args.private_output_acknowledged:
        parser.error("--private-output-acknowledged is required when writing a private report")
    try:
        report = build_anonymous_cohort_preflight(
            artifact_root=args.artifact_root,
            layout_path=args.layout,
            final_review_validation_path=args.final_review_validation,
            private_manifest_path=args.private_manifest,
            expected_pages_per_group=args.expected_pages_per_group,
            page_scope_review_csv_path=args.page_scope_review_csv,
            page_scope_review_metadata_path=args.page_scope_review_metadata,
        )
        if args.output is not None:
            _write_only_if_empty_or_identical(args.output, canonical_report_bytes(report))
    except (OSError, CohortPreflightError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(report, sort_keys=True))
    return 0


def _write_only_if_empty_or_identical(path: Path, expected: bytes) -> None:
    if path.exists():
        if not path.is_file():
            raise CohortPreflightError(f"preflight output must be a file: {path}")
        if path.read_bytes() != expected:
            raise CohortPreflightError(
                f"refusing to overwrite divergent cohort preflight report: {path}"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)


if __name__ == "__main__":
    raise SystemExit(main())
