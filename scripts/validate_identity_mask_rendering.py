"""Verify that reviewed identity masks were applied to rendered anonymous PNGs.

This local-only checker samples pixels strictly inside each approved identity
rectangle. It never performs OCR or semantic identity detection: the human
reviewer remains responsible for deciding which regions contain personal data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymization import load_page_layout  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify reviewed identity rectangles are white in anonymous PNGs."
    )
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args(argv)
    report = validate_identity_mask_rendering(
        layout_path=args.layout,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "ready" else 1


def validate_identity_mask_rendering(
    *,
    layout_path: Path,
    artifact_root: Path,
) -> dict[str, Any]:
    layout = load_page_layout(layout_path)
    image_root = artifact_root / "anonymized_pages"
    checks = 0
    failed = 0
    missing_images = 0
    masked_pages = 0

    for group in layout["page_groups"]:
        anonymous_id = str(group["anonymous_id"])
        for local_page, source_page in enumerate(group["source_pages"], start=1):
            rectangles = _identity_rectangles_for_page(
                group=group,
                source_page=int(source_page),
            )
            if not rectangles:
                continue
            masked_pages += 1
            image_path = (
                image_root
                / anonymous_id
                / f"{anonymous_id}-p{local_page:02d}.png"
            )
            if not image_path.is_file():
                missing_images += 1
                failed += len(rectangles)
                continue
            with Image.open(image_path) as image:
                rgb = image.convert("RGB")
                for rectangle in rectangles:
                    checks += 1
                    if not _rectangle_is_white(rgb, rectangle):
                        failed += 1

    return {
        "schema_version": 1,
        "record_type": "identity_mask_render_validation",
        "status": "ready" if not failed and not missing_images else "not_ready",
        "masked_page_count": masked_pages,
        "identity_rectangle_count": checks,
        "failed_rectangle_count": failed,
        "missing_image_count": missing_images,
        "model_run_allowed": False,
        "note": (
            "Checks only that approved rectangles rendered as white; it does not "
            "perform OCR or detect personal information outside reviewed regions."
        ),
    }


def _identity_rectangles_for_page(
    *,
    group: Mapping[str, Any],
    source_page: int,
) -> list[dict[str, float]]:
    rectangles: list[dict[str, float]] = []
    for page_mask in group.get("page_masks", []):
        if (
            page_mask.get("reason") == "identity_mask_review"
            and int(page_mask.get("source_page", -1)) == source_page
        ):
            for rectangle in page_mask.get("rectangles", []):
                rectangles.append(
                    {
                        key: float(rectangle[key])
                        for key in ("left", "top", "right", "bottom")
                    }
                )
    return rectangles


def _rectangle_is_white(
    image: Image.Image,
    rectangle: Mapping[str, float],
) -> bool:
    width, height = image.size
    left = int(width * float(rectangle["left"]))
    top = int(height * float(rectangle["top"]))
    right = int(width * float(rectangle["right"]))
    bottom = int(height * float(rectangle["bottom"]))
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        return False
    xs = _interior_samples(left, right)
    ys = _interior_samples(top, bottom)
    return all(
        min(image.getpixel((x, y))) >= 250
        for x in xs
        for y in ys
    )


def _interior_samples(start: int, end: int) -> tuple[int, ...]:
    span = end - start
    return tuple(
        min(end - 1, max(start, start + int(span * fraction)))
        for fraction in (0.25, 0.5, 0.75)
    )


if __name__ == "__main__":
    raise SystemExit(main())
