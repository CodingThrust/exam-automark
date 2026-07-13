from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

try:
    import pypdfium2 as pdfium
except ImportError as error:  # pragma: no cover - dependency gate
    raise SystemExit(
        "pypdfium2 is required. Install it with `python -m pip install pypdfium2`."
    ) from error


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_pdf = args.source_pdf
    output_root = args.output_root
    anonymized_root = output_root / "anonymized"
    manifest_root = output_root / "manifest"
    preview_root = output_root / "privacy_review" / "previews"

    if not source_pdf.exists():
        raise FileNotFoundError(source_pdf)
    if output_root.exists() and any(output_root.iterdir()) and not args.force:
        raise FileExistsError(f"output root is not empty: {output_root}")

    output_root.mkdir(parents=True, exist_ok=True)
    anonymized_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)
    if args.preview_first_pages:
        preview_root.mkdir(parents=True, exist_ok=True)

    doc = pdfium.PdfDocument(str(source_pdf))
    expected_pages = args.student_count * args.pages_per_student
    if len(doc) != expected_pages:
        raise ValueError(
            f"expected {expected_pages} pages for "
            f"{args.student_count} students x {args.pages_per_student} pages, "
            f"got {len(doc)}"
        )

    generated_at = _utc_now()
    index_rows = []
    review_rows = []
    for offset in range(args.student_count):
        student_id = f"S{offset + 1:03d}"
        start = offset * args.pages_per_student
        end = start + args.pages_per_student
        student_dir = anonymized_root / student_id
        student_dir.mkdir(parents=True, exist_ok=True)
        output_pdf = student_dir / "week5.pdf"

        pages = [
            _render_redacted_page(
                doc,
                page_index,
                student_id=student_id,
                source_start=start + 1,
                source_end=end,
                scale=args.scale,
                redaction_top_fraction=args.redaction_top_fraction,
            )
            for page_index in range(start, end)
        ]
        _write_pdf_from_images(output_pdf, pages)

        if args.preview_first_pages:
            pages[0].save(preview_root / f"{student_id}-p01.png")

        relative_output = output_pdf.relative_to(output_root).as_posix()
        index_rows.append(
            {
                "student_id": student_id,
                "source_pdf": source_pdf.name,
                "source_start_page": start + 1,
                "source_end_page": end,
                "page_count": args.pages_per_student,
                "output_pdf": relative_output,
            }
        )
        for page_number, source_page in enumerate(range(start + 1, end + 1), start=1):
            review_rows.append(
                {
                    "student_id": student_id,
                    "source_pdf": source_pdf.name,
                    "source_page": source_page,
                    "output_pdf": relative_output,
                    "output_page": page_number,
                    "redaction_method": "rasterize_and_top_band_whiten",
                    "redaction_top_fraction": args.redaction_top_fraction,
                    "privacy_review_status": "pending",
                    "reviewer": "",
                    "reviewed_at": "",
                    "notes": "verify no name, student id, or other direct identifier remains visible",
                }
            )

    _write_csv(manifest_root / "student_index.csv", index_rows)
    _write_csv(manifest_root / "privacy_review.csv", review_rows)
    metadata = {
        "record_type": "dsaa3071_week5_anonymization_prep",
        "generated_at": generated_at,
        "source_pdf": source_pdf.name,
        "source_sha256": _sha256(source_pdf),
        "student_count": args.student_count,
        "pages_per_student": args.pages_per_student,
        "page_count": len(doc),
        "anonymous_id_pattern": "S###",
        "output_root": str(output_root),
        "anonymized_root": str(anonymized_root),
        "redaction_method": "render each page to raster image, whiten top identity band, write new PDF",
        "redaction_top_fraction": args.redaction_top_fraction,
        "scale": args.scale,
        "privacy_review_status": "pending",
        "model_run_allowed": False,
        "notes": [
            "The generated PDFs are not approved for model runs until privacy_review.csv is reviewed.",
            "The source PDF is a combined 22-student answer file confirmed by the user.",
            "The top-band redaction assumes direct identifiers are in the page header; human review is required.",
        ],
    }
    (manifest_root / "prep-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(metadata, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare DSAA3071 Week 5 anonymized inputs from a combined PDF."
    )
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--student-count", type=int, default=22)
    parser.add_argument("--pages-per-student", type=int, default=3)
    parser.add_argument("--redaction-top-fraction", type=float, default=0.18)
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument("--preview-first-pages", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def _render_redacted_page(
    doc: pdfium.PdfDocument,
    page_index: int,
    *,
    student_id: str,
    source_start: int,
    source_end: int,
    scale: float,
    redaction_top_fraction: float,
):
    page = doc[page_index]
    image = page.render(scale=scale).to_pil().convert("RGB")
    draw = ImageDraw.Draw(image)
    band_height = int(image.height * redaction_top_fraction)
    draw.rectangle((0, 0, image.width, band_height), fill="white")
    label = (
        f"Anonymous ID: {student_id} | source pages {source_start}-{source_end} "
        "| identity header redacted"
    )
    draw.text((24, 24), label, fill="black")
    return image


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_pdf_from_images(path: Path, images: list) -> None:
    if not images:
        raise ValueError(f"no images for {path}")
    pdf = canvas.Canvas(str(path), pagesize=(images[0].width, images[0].height))
    for image in images:
        pdf.setPageSize((image.width, image.height))
        pdf.drawImage(
            ImageReader(image),
            0,
            0,
            width=image.width,
            height=image.height,
        )
        pdf.showPage()
    pdf.save()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
