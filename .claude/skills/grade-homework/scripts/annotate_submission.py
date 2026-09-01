from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from roster import RosterError, SAFE_SUBMISSION_ID, require_private_path


ANNOTATION_KINDS = {"deduction", "praise", "review"}
COLORS = {
    "deduction": (196, 46, 46),
    "praise": (35, 130, 72),
    "review": (206, 129, 25),
}
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?:^|\s)[A-Za-z]:[\\/]")
PRIVATE_DATA_PATH = re.compile(r"(?:^|[\\/])Data[\\/]", re.IGNORECASE)
FILE_URI = re.compile(r"\bfile://", re.IGNORECASE)
EMAIL_ADDRESS = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
IDENTITY_LABEL = re.compile(
    "\\b(?:student[ _-]?(?:id|number|name)|name)\\s*[:=]|(?:\\u59d3\\u540d|\\u5b66\\u53f7)\\s*[:\\uff1a]",
    re.IGNORECASE,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render validated praise, deduction, and review annotations."
    )
    parser.add_argument("pages_manifest", type=Path)
    parser.add_argument("annotations_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    namespace = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    output_dir = namespace.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        print("refusing to overwrite an existing marked submission", file=sys.stderr)
        return 4
    try:
        require_private_path(output_dir, label="marked submission output")
        manifest = _load_object(namespace.pages_manifest, "pages manifest")
        annotations_record = _load_object(namespace.annotations_json, "annotation record")
        pages, submission_id = _validated_pages(manifest, namespace.pages_manifest.parent)
        annotations = _validated_annotations(annotations_record, submission_id, set(pages))
    except (OSError, ValueError, RosterError) as error:
        print(f"invalid annotation input: {error}", file=sys.stderr)
        return 2

    by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for annotation in annotations:
        by_page[annotation["page_id"]].append(annotation)

    output_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    rendered_images: list[Image.Image] = []
    try:
        for page_id, page_path in pages.items():
            with Image.open(page_path) as source:
                image = source.convert("RGB")
            _draw_annotations(image, by_page[page_id], font)
            target = output_dir / page_path.name
            image.save(target)
            rendered_images.append(image)
        pdf_path = output_dir / "marked.pdf"
        rendered_images[0].save(
            pdf_path,
            save_all=True,
            append_images=rendered_images[1:],
            resolution=150.0,
        )
    except Exception as error:
        print(f"annotation rendering failed: {error}", file=sys.stderr)
        return 2
    finally:
        for image in rendered_images:
            image.close()

    print(
        json.dumps(
            {
                "status": "ok",
                "submission_id": submission_id,
                "page_count": len(pages),
                "marked_pdf": "marked.pdf",
            },
            sort_keys=True,
        )
    )
    return 0


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} could not be read") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _validated_pages(
    manifest: dict[str, Any], manifest_dir: Path
) -> tuple[dict[str, Path], str]:
    submission_id = str(manifest.get("submission_id", "")).strip()
    if not SAFE_SUBMISSION_ID.fullmatch(submission_id):
        raise ValueError("pages manifest submission_id is invalid")
    raw_pages = manifest.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise ValueError("pages manifest requires non-empty pages")
    pages: dict[str, Path] = {}
    for page in raw_pages:
        if not isinstance(page, dict):
            raise ValueError("pages manifest page must be an object")
        page_id = str(page.get("page_id", "")).strip()
        raw_path = str(page.get("path", "")).strip()
        if not SAFE_SUBMISSION_ID.fullmatch(page_id):
            raise ValueError("pages manifest page_id is invalid")
        if not raw_path or Path(raw_path).name != raw_path:
            raise ValueError("pages manifest page path must be a filename")
        source = manifest_dir / raw_path
        if page_id in pages or not source.is_file():
            raise ValueError("pages manifest has duplicate or missing page")
        pages[page_id] = source
    return pages, submission_id


def _validated_annotations(
    record: dict[str, Any], submission_id: str, page_ids: set[str]
) -> list[dict[str, Any]]:
    if str(record.get("student_id", "")).strip() != submission_id:
        raise ValueError("annotation record does not match the pages manifest")
    raw_annotations = record.get("annotations")
    if not isinstance(raw_annotations, list):
        raise ValueError("annotation record requires annotations")
    required = {"question_id", "page_id", "box", "kind", "label"}
    result = []
    for annotation in raw_annotations:
        if not isinstance(annotation, dict) or set(annotation) != required:
            raise ValueError("annotation fields are invalid")
        question_id = str(annotation["question_id"]).strip()
        if not question_id:
            raise ValueError("annotation question_id is invalid")
        page_id = str(annotation["page_id"]).strip()
        if page_id not in page_ids:
            raise ValueError("annotation references an unknown page")
        kind = annotation["kind"]
        if kind not in ANNOTATION_KINDS:
            raise ValueError("annotation kind is invalid")
        box = annotation["box"]
        if (
            not isinstance(box, list)
            or len(box) != 4
            or any(isinstance(part, bool) or not isinstance(part, (int, float)) for part in box)
        ):
            raise ValueError("annotation box is invalid")
        x, y, width, height = (float(part) for part in box)
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            raise ValueError("annotation box is outside the page")
        result.append(
            {
                "question_id": question_id,
                "page_id": page_id,
                "box": [x, y, width, height],
                "kind": kind,
                "label": _safe_label(annotation["label"], submission_id),
            }
        )
    return result


def _safe_label(value: Any, submission_id: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError("annotation label is invalid")
    if (
        WINDOWS_ABSOLUTE_PATH.search(value)
        or PRIVATE_DATA_PATH.search(value)
        or FILE_URI.search(value)
        or EMAIL_ADDRESS.search(value)
        or IDENTITY_LABEL.search(value)
        or submission_id.casefold() in value.casefold()
    ):
        raise ValueError("annotation label contains private information")
    return value.strip()


def _draw_annotations(
    image: Image.Image, annotations: list[dict[str, Any]], font: ImageFont.ImageFont
) -> None:
    draw = ImageDraw.Draw(image)
    width, height = image.size
    stroke = max(2, min(width, height) // 400)
    for annotation in annotations:
        x, y, box_width, box_height = annotation["box"]
        left = round(x * width)
        top = round(y * height)
        right = round((x + box_width) * width)
        bottom = round((y + box_height) * height)
        color = COLORS[annotation["kind"]]
        draw.rectangle((left, top, right, bottom), outline=color, width=stroke)
        label = annotation["label"]
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_width = text_bbox[2] - text_bbox[0] + 6
        text_height = text_bbox[3] - text_bbox[1] + 4
        label_left = min(max(0, left), max(0, width - text_width))
        label_top = top - text_height if top >= text_height else min(height - text_height, bottom)
        draw.rectangle(
            (label_left, label_top, label_left + text_width, label_top + text_height),
            fill=color,
        )
        draw.text((label_left + 3, label_top + 2), label, fill=(255, 255, 255), font=font)


if __name__ == "__main__":
    raise SystemExit(main())
