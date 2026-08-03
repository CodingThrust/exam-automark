"""Validate direct-multimodal versus transcript-first packet lineage.

This is a receipt-only safety check.  It does not invoke a model or create a
packet.  It verifies that matched grading routes begin with the same approved
anonymous image hashes and that the text route is bound to the intended T1 run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.modality_lineage import (  # noqa: E402
    ModalityLineageError,
    validate_modality_lineage,
    write_lineage_report,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the immutable image-to-transcript lineage for one matched "
            "direct-multimodal and transcript-first grading comparison. This does "
            "not run a model."
        )
    )
    parser.add_argument("--direct-multimodal-packet", type=Path, required=True)
    parser.add_argument("--transcription-packet", type=Path, required=True)
    parser.add_argument("--transcript-first-packet", type=Path, required=True)
    parser.add_argument(
        "--transcription-run-output",
        type=Path,
        required=True,
        help="directory containing run-metadata.json, validation.json, and outputs/",
    )
    parser.add_argument(
        "--transcription-run-id",
        required=True,
        help="the frozen workflow-config ID that built the transcript-first packet",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "optional deterministic readiness report; a different existing report "
            "is never overwritten"
        ),
    )
    args = parser.parse_args(argv)

    try:
        report = validate_modality_lineage(
            direct_multimodal_packet=args.direct_multimodal_packet,
            transcription_packet=args.transcription_packet,
            transcript_first_packet=args.transcript_first_packet,
            transcription_run_output=args.transcription_run_output,
            transcription_run_id=args.transcription_run_id,
        )
        if args.output is not None:
            report["report_write_status"] = write_lineage_report(args.output, report)
    except ModalityLineageError as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
