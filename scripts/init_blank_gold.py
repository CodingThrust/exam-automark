from __future__ import annotations

"""Create an idempotent, blank question-level gold CSV without running a model."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.readiness_scaffolding import (  # noqa: E402
    ReadinessScaffoldError,
    collect_anonymous_student_ids,
    initialize_blank_gold,
)
from benchmark.core.schema import CourseSpec  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a blank question-level gold CSV from a course spec and anonymous "
            "student IDs. This command never reads submissions or calls a model."
        )
    )
    parser.add_argument("--course", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--student-id", action="append", dest="student_ids")
    parser.add_argument(
        "--students-file",
        type=Path,
        help="UTF-8 one-anonymous-ID-per-line file; blank lines and # comments are ignored",
    )
    parser.add_argument(
        "--students-dir",
        type=Path,
        help=(
            "directory whose direct child names matching the course anonymous-ID "
            "pattern are used; it is not scanned recursively"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        course = CourseSpec.from_json_path(args.course)
        student_ids = collect_anonymous_student_ids(
            course,
            student_ids=args.student_ids,
            students_file=args.students_file,
            students_dir=args.students_dir,
        )
        result = initialize_blank_gold(course, student_ids, args.output)
    except (OSError, ReadinessScaffoldError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
