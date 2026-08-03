from __future__ import annotations

"""Build a private, representative root-cause review queue.

This is a local data-preparation command only.  It reads existing private
development error books, calls no model, and refuses to write outside a
gitignored private-data location when invoked from this repository.
"""

import argparse
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.error_review_queue import (  # noqa: E402
    build_root_cause_review_queue,
    load_page_suffix_by_question,
    load_rubric_review_context,
    write_root_cause_review_queue,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a private representative root-cause review queue from "
            "development error books. No model is called."
        )
    )
    parser.add_argument(
        "--course",
        type=Path,
        required=True,
        help="tracked course specification with the approved question-to-page mapping",
    )
    parser.add_argument(
        "--condition",
        action="append",
        required=True,
        metavar="ID=PRIVATE_ERROR_BOOK",
        help=(
            "condition ID and private error-book JSON; repeat for every "
            "comparable condition (for example codex_m1=...json)"
        ),
    )
    parser.add_argument(
        "--rubric",
        type=Path,
        required=True,
        help=(
            "frozen rubric JSON used by the source packets; its SHA-256 must "
            "match every source error book"
        ),
    )
    parser.add_argument(
        "--question",
        action="append",
        required=True,
        metavar="QID",
        help="in-scope question to cover; repeat in the desired review order",
    )
    parser.add_argument(
        "--items-per-question",
        type=int,
        default=2,
        help="representative cases selected per requested question (default: 2)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new, gitignored private root-cause-review-queue JSON",
    )
    args = parser.parse_args(argv)

    try:
        sources = _parse_sources(args.condition)
        queue = build_root_cause_review_queue(
            sources=sources,
            question_ids=args.question,
            page_suffix_by_question=load_page_suffix_by_question(args.course),
            rubric_context=load_rubric_review_context(
                args.rubric, question_ids=args.question
            ),
            items_per_question=args.items_per_question,
        )
        queue_sha256 = write_root_cause_review_queue(
            output_path=args.output,
            queue=queue,
            private_root=REPO_ROOT / "Data",
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(
        "Private root-cause review queue ready: "
        f"{len(queue['items'])} representative development cases across "
        f"{len(queue['provenance']['source_books'])} conditions."
    )
    print(f"Queue ID: {queue['queue_id']}; queue SHA-256: {queue_sha256}")
    print("No model was called. Open it only through the local reviewer tool.")
    return 0


def _parse_sources(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        condition_id, separator, raw_path = value.partition("=")
        condition_id = condition_id.strip()
        raw_path = raw_path.strip()
        if not separator or not condition_id or not raw_path:
            raise ValueError("--condition must use ID=PRIVATE_ERROR_BOOK")
        if condition_id in result:
            raise ValueError("each --condition ID may appear only once")
        result[condition_id] = Path(raw_path)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
