from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import fitz
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymization import (
    expected_review_pairs,
    load_page_layout,
    masks_for_group_page,
    review_rows_for_layout,
    sha256_file,
    validate_anonymization_review,
    validate_page_layout,
    write_json,
    write_review_csv,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "validate-review":
        return _validate_review(args)
    raise ValueError(f"unsupported command: {args.command}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare anonymous, blind-scoring image inputs from a combined scanned "
            "assessment PDF. This tool never marks the result model-ready."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser(
        "prepare",
        help="render a private page-layout manifest into anonymous PNG and PDF inputs",
    )
    prepare.add_argument("--source-pdf", type=Path, required=True)
    prepare.add_argument(
        "--layout",
        type=Path,
        required=True,
        help="private JSON layout with anonymous page groups and page-specific masks",
    )
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument(
        "--identity-redaction-rect",
        action="append",
        required=True,
        metavar="LEFT,TOP,RIGHT,BOTTOM",
        help="normalized identity rectangle; provide every required header mask",
    )
    prepare.add_argument("--scale", type=float, default=2.0)

    review = commands.add_parser(
        "validate-review",
        help="check that every prepared page has human privacy, blindness, and content approval",
    )
    review.add_argument("--layout", type=Path, required=True)
    review.add_argument(
        "--prep-metadata",
        type=Path,
        required=True,
        help="prep-metadata.json emitted by the matching prepare command",
    )
    review.add_argument("--review", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)
    return parser


def _prepare(args: argparse.Namespace) -> int:
    source_pdf = args.source_pdf
    if not source_pdf.is_file():
        raise FileNotFoundError(source_pdf)
    if args.scale <= 0:
        raise ValueError("--scale must be positive")
    if args.output_root.exists() and any(args.output_root.iterdir()):
        raise FileExistsError(
            f"output root is not empty: {args.output_root}; create a new versioned root"
        )

    identity_rectangles = [_parse_rectangle(value) for value in args.identity_redaction_rect]
    layout = load_page_layout(args.layout)
    source_hash = sha256_file(source_pdf)
    with fitz.open(source_pdf) as document:
        layout_report = validate_page_layout(
            layout,
            source_page_count=len(document),
            source_sha256=source_hash,
        )
        if layout_report["status"] != "ready":
            raise ValueError(
                "private page layout is not ready: "
                + json.dumps(layout_report["failed_checks"], sort_keys=True)
            )

        args.output_root.mkdir(parents=True, exist_ok=True)
        image_root = args.output_root / "anonymized_pages"
        pdf_root = args.output_root / "anonymized_pdfs"
        manifest_root = args.output_root / "manifest"
        image_root.mkdir(parents=True, exist_ok=True)
        pdf_root.mkdir(parents=True, exist_ok=True)
        manifest_root.mkdir(parents=True, exist_ok=True)

        for group in layout["page_groups"]:
            anonymous_id = group["anonymous_id"]
            source_pages = group["source_pages"]
            student_image_root = image_root / anonymous_id
            student_image_root.mkdir(parents=True, exist_ok=True)
            images: list[Image.Image] = []
            for local_page, source_page in enumerate(source_pages, start=1):
                pixmap = document.load_page(source_page - 1).get_pixmap(
                    matrix=fitz.Matrix(args.scale, args.scale),
                    alpha=False,
                )
                image = Image.frombytes(
                    "RGB",
                    (pixmap.width, pixmap.height),
                    pixmap.samples,
                )
                rectangles = [
                    *identity_rectangles,
                    *masks_for_group_page(group, source_page),
                ]
                _apply_rectangles(image, rectangles)
                image_path = student_image_root / f"{anonymous_id}-p{local_page:02d}.png"
                image.save(image_path, format="PNG")
                images.append(image)
            _write_pdf(pdf_root / f"{anonymous_id}.pdf", images)

    review_rows = review_rows_for_layout(
        layout,
        identity_rectangles=identity_rectangles,
    )
    review_path = manifest_root / "anonymization_review.csv"
    write_review_csv(review_path, review_rows)
    layout_hash = sha256_file(args.layout)
    metadata = {
        "schema_version": 1,
        "record_type": "anonymized_assessment_preparation",
        "assessment_id": layout["assessment_id"],
        "source_pdf": source_pdf.name,
        "source_sha256": source_hash,
        "source_page_count": layout_report["source_page_count"],
        "anonymous_group_count": layout_report["anonymous_group_count"],
        "layout_sha256": layout_hash,
        "layout_validation_path": "manifest/page-layout-validation.json",
        "review_path": "manifest/anonymization_review.csv",
        "identity_redaction_rectangles": identity_rectangles,
        "render_scale": args.scale,
        "outputs": {
            "images": "anonymized_pages/S###/S###-pNN.png",
            "pdfs": "anonymized_pdfs/S###.pdf",
        },
        "privacy_review_status": "pending",
        "blindness_review_status": "pending",
        "answer_content_review_status": "pending",
        "model_run_allowed": False,
        "model_run_blockers": [
            "Every prepared page requires privacy approval.",
            "Every prepared page requires blindness approval: no score, tick/cross, total, or grader comment may leak gold.",
            "Every prepared page requires content-preservation approval for the declared question scope.",
            "A frozen split, reviewed transcripts, question-level gold, rubric, packet audit, and separate run-readiness approval are still required.",
        ],
    }
    write_json(manifest_root / "page-layout-validation.json", layout_report)
    write_json(manifest_root / "prep-metadata.json", metadata)
    print(
        json.dumps(
            {
                "status": "prepared_pending_human_review",
                "anonymous_group_count": layout_report["anonymous_group_count"],
                "review_rows": len(review_rows),
                "output_root": str(args.output_root),
                "model_run_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _validate_review(args: argparse.Namespace) -> int:
    layout = load_page_layout(args.layout)
    metadata = _load_json_object(args.prep_metadata)
    current_layout_hash = sha256_file(args.layout)
    report = validate_anonymization_review(
        args.review,
        expected_pairs=expected_review_pairs(layout),
    )
    metadata_layout_hash = metadata.get("layout_sha256")
    layout_hash_matches = metadata_layout_hash == current_layout_hash
    report["preparation_metadata_path"] = str(args.prep_metadata)
    report["layout_hash_matches_preparation"] = layout_hash_matches
    report["checks"].append(
        {
            "id": "layout_hash_matches_preparation",
            "status": "passed" if layout_hash_matches else "failed",
            "detail": (
                "private layout matches the layout used to render anonymous inputs"
                if layout_hash_matches
                else "layout changed after anonymous inputs were rendered"
            ),
        }
    )
    if not layout_hash_matches:
        report["failed_checks"].append("layout_hash_matches_preparation")
        report["status"] = "not_ready"
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "failed_checks": report["failed_checks"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "ready" else 1


def _parse_rectangle(value: str) -> dict[str, float]:
    try:
        left, top, right, bottom = [float(part.strip()) for part in value.split(",")]
    except ValueError as error:
        raise ValueError(
            "redaction rectangle must use LEFT,TOP,RIGHT,BOTTOM"
        ) from error
    rectangle = {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
    }
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError(f"redaction rectangle is outside normalized page bounds: {value}")
    return rectangle


def _apply_rectangles(
    image: Image.Image,
    rectangles: Sequence[Mapping[str, float]],
) -> None:
    draw = ImageDraw.Draw(image)
    for rectangle in rectangles:
        draw.rectangle(
            (
                int(image.width * float(rectangle["left"])),
                int(image.height * float(rectangle["top"])),
                int(image.width * float(rectangle["right"])),
                int(image.height * float(rectangle["bottom"])),
            ),
            fill="white",
        )


def _write_pdf(path: Path, images: Sequence[Image.Image]) -> None:
    if not images:
        raise ValueError(f"no pages were rendered for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        path,
        "PDF",
        save_all=True,
        append_images=list(images[1:]),
        resolution=144,
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
