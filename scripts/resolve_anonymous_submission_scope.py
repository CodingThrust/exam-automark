from __future__ import annotations

"""Create, resolve, or validate private variable-page submission scope."""

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
    apply_submission_scope_decisions,
    initialize_submission_scope_resolution,
    validate_submission_scope_resolution,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage private anonymous submission scope; no model is called.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("initialize", "validate", "apply"):
        child = subparsers.add_parser(command)
        child.add_argument("--artifact-root", type=Path, required=True)
        child.add_argument("--final-review", type=Path, required=True)
        child.add_argument("--final-review-validation", type=Path, required=True)
        child.add_argument("--private-assembly-manifest", type=Path, required=True)
        child.add_argument("--expected-pages-per-submission", type=int, required=True)
        child.add_argument("--private-output-acknowledged", action="store_true")
        if command == "initialize":
            child.add_argument("--resolution", type=Path, required=True)
        elif command == "validate":
            child.add_argument("--resolution", type=Path, required=True)
        else:
            child.add_argument("--template-resolution", type=Path, required=True)
            child.add_argument("--decisions", type=Path, required=True)
            child.add_argument("--resolved-resolution", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.expected_pages_per_submission < 1:
        parser.error("--expected-pages-per-submission must be positive")
    if not args.private_output_acknowledged:
        parser.error("--private-output-acknowledged is required")
    common = {
        "artifact_root": args.artifact_root,
        "final_review_path": args.final_review,
        "final_review_validation_path": args.final_review_validation,
        "private_assembly_manifest_path": args.private_assembly_manifest,
        "expected_pages_per_submission": args.expected_pages_per_submission,
    }
    try:
        if args.command == "initialize":
            result = initialize_submission_scope_resolution(**common, resolution_path=args.resolution)
        elif args.command == "validate":
            result = validate_submission_scope_resolution(**common, resolution_path=args.resolution)
        else:
            result = apply_submission_scope_decisions(
                **common,
                template_resolution_path=args.template_resolution,
                decisions_path=args.decisions,
                resolved_resolution_path=args.resolved_resolution,
            )
    except (OSError, ValueError, SubmissionScopeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
