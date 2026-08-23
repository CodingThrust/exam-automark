from __future__ import annotations

"""Prepare a private development-only human-gold revision without model calls."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.gold_revision import GoldRevisionError, prepare_gold_revision  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a hash-bound private revision of a complete human gold table. "
            "Only selected frozen development cells are cleared; no submission content "
            "is opened and no model is called."
        )
    )
    parser.add_argument("--course", type=Path, required=True)
    parser.add_argument("--candidate-plan", type=Path, required=True)
    parser.add_argument("--rubric", type=Path, required=True)
    parser.add_argument("--calibration-decisions", type=Path, required=True)
    parser.add_argument("--source-gold", type=Path, required=True)
    parser.add_argument("--source-binding", type=Path, required=True)
    parser.add_argument("--frozen-split", type=Path, required=True)
    parser.add_argument(
        "--reset-question",
        action="append",
        dest="reset_questions",
        required=True,
        help="course leaf whose development gold and review metadata are cleared",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--private-output-acknowledged", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.private_output_acknowledged:
        parser.error("--private-output-acknowledged is required")
    try:
        result = prepare_gold_revision(
            course_path=args.course,
            candidate_plan_path=args.candidate_plan,
            rubric_path=args.rubric,
            calibration_decisions_path=args.calibration_decisions,
            source_gold_path=args.source_gold,
            source_binding_path=args.source_binding,
            frozen_split_path=args.frozen_split,
            reset_question_ids=args.reset_questions,
            output_root=args.output_root,
        )
    except (GoldRevisionError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
