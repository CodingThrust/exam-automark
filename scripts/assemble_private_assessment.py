"""Assemble mixed private submissions into anonymous-ready page inputs.

This is an ingestion step, not an anonymization approval and not a grader.
It converts supported local files to sequential PNG pages, creates a combined
private PDF plus a source-page layout with anonymous IDs, and keeps the raw
filename mapping solely in a private manifest under the caller's output root.
No source filename or answer content is printed to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import fitz
from PIL import Image, ImageOps


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
HEIF_SUFFIXES = {".heic", ".heif"}
SUPPORTED_SUFFIXES = IMAGE_SUFFIXES | HEIF_SUFFIXES | {".pdf", ".docx"}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.input_root.is_dir():
        raise FileNotFoundError(args.input_root)
    if args.output_root.exists() and any(args.output_root.iterdir()):
        raise FileExistsError(
            f"output root is not empty: {args.output_root}; create a new versioned root"
        )
    if not args.group_separator:
        raise ValueError("--group-separator must not be empty")
    if args.expected_pages_per_group < 1:
        raise ValueError("--expected-pages-per-group must be positive")
    if not args.private_output_acknowledged:
        raise ValueError(
            "--private-output-acknowledged is required because the output manifest contains raw filenames"
        )

    sources = _discover_sources(args.input_root)
    if not sources:
        raise ValueError("no supported source files found")
    grouped = _group_sources(sources, args.input_root, args.group_separator)
    assignment_seed = secrets.token_hex(32)
    anonymous_groups = _assign_anonymous_ids(
        grouped, prefix=args.anonymous_id_prefix, seed=assignment_seed
    )

    args.output_root.mkdir(parents=True, exist_ok=True)
    source_pages_root = args.output_root / "source_pages"
    source_pages_root.mkdir(parents=True, exist_ok=True)

    next_source_page = 1
    layout_groups: list[dict[str, Any]] = []
    private_groups: list[dict[str, Any]] = []
    blocked_groups: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="assemble-private-assessment-") as temp:
        staging_root = Path(temp)
        for anonymous_id, raw_group_key, group_sources in anonymous_groups:
            conversion = _convert_group(
                group_sources,
                input_root=args.input_root,
                staging_root=staging_root / anonymous_id,
                docx_policy=args.docx_policy,
            )
            if conversion["status"] != "ok":
                blocked_groups.append(
                    {
                        "anonymous_id": anonymous_id,
                        "source_file_count": len(group_sources),
                        "reason": conversion["reason"],
                    }
                )
                private_groups.append(
                    {
                        "anonymous_id": anonymous_id,
                        "raw_group_key": raw_group_key,
                        "status": "blocked",
                        "reason": conversion["reason"],
                        "source_files": _private_source_file_rows(
                            group_sources, args.input_root
                        ),
                    }
                )
                continue

            converted_pages = conversion["pages"]
            source_pages: list[int] = []
            page_rows: list[dict[str, Any]] = []
            for page in converted_pages:
                source_page = next_source_page
                next_source_page += 1
                suffix = page["path"].suffix.lower()
                target = source_pages_root / f"source-p{source_page:04d}{suffix}"
                shutil.copy2(page["path"], target)
                source_pages.append(source_page)
                page_rows.append(
                    {
                        "source_page": source_page,
                        "raw_relative_path": page["raw_relative_path"],
                        "source_file_page": page["source_file_page"],
                    }
                )

            layout_groups.append(
                {
                    "anonymous_id": anonymous_id,
                    "source_pages": source_pages,
                    "page_masks": [],
                }
            )
            private_groups.append(
                {
                    "anonymous_id": anonymous_id,
                    "raw_group_key": raw_group_key,
                    "status": "converted_pending_page_review",
                    "source_files": _private_source_file_rows(
                        group_sources, args.input_root
                    ),
                    "page_map": page_rows,
                    "rendered_page_count": len(source_pages),
                    "page_count_status": (
                        "matches_expected"
                        if len(source_pages) == args.expected_pages_per_group
                        else "requires_page_scope_review"
                    ),
                }
            )

    if not layout_groups:
        raise ValueError("no submission groups were converted; no private source PDF was written")

    source_pdf = args.output_root / "source.pdf"
    _write_combined_pdf(source_pdf, source_pages_root)
    source_sha256 = _sha256_file(source_pdf)
    layout = {
        "schema_version": 1,
        "assessment_id": args.assessment_id,
        "source_sha256": source_sha256,
        "expected_page_count": next_source_page - 1,
        "page_groups": layout_groups,
        "excluded_pages": [],
    }
    _write_json(args.output_root / "page-layout.json", layout)
    private_manifest = {
        "schema_version": 1,
        "record_type": "private_mixed_submission_assembly",
        "assessment_id": args.assessment_id,
        "input_root": str(args.input_root.resolve()),
        "assignment_seed": assignment_seed,
        "grouping": {
            "rule": "filename_stem_prefix_before_separator",
            "separator": args.group_separator,
            "source_file_count": len(sources),
            "raw_group_count": len(anonymous_groups),
        },
        "source_pdf": source_pdf.name,
        "source_sha256": source_sha256,
        "source_page_count": next_source_page - 1,
        "groups": private_groups,
        "blocked_groups": blocked_groups,
        "model_run_allowed": False,
        "model_run_blockers": [
            "Visible identity, grading-mark, page-order, and answer-preservation review is pending.",
            "This assembly keeps private source pages and is not anonymized model input.",
        ],
    }
    _write_json(args.output_root / "private-source-manifest.json", private_manifest)
    anomaly_count = sum(
        group["status"] == "converted_pending_page_review"
        and group["page_count_status"] == "requires_page_scope_review"
        for group in private_groups
    )
    print(
        json.dumps(
            {
                "status": "assembled_pending_anonymization",
                "anonymous_group_count": len(layout_groups),
                "blocked_group_count": len(blocked_groups),
                "page_count_anomaly_group_count": anomaly_count,
                "source_page_count": next_source_page - 1,
                "model_run_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble mixed private submissions into a source PDF and anonymous page layout. "
            "This does not create approved anonymized model inputs."
        )
    )
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--assessment-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--group-separator",
        required=True,
        help="Files sharing the filename-stem prefix before this separator form one group.",
    )
    parser.add_argument("--anonymous-id-prefix", default="S")
    parser.add_argument("--expected-pages-per-group", type=int, default=4)
    parser.add_argument(
        "--private-output-acknowledged",
        action="store_true",
        help="Required acknowledgement that output contains private source-page and raw-filename mapping data.",
    )
    parser.add_argument(
        "--docx-policy",
        choices=("manual_review",),
        default="manual_review",
        help="DOCX conversion is deliberately blocked pending an explicit converter decision.",
    )
    return parser


def _discover_sources(input_root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in input_root.rglob("*")
            if path.is_file()
            and not any(part.startswith(".") for part in path.relative_to(input_root).parts)
            and path.suffix.lower() in SUPPORTED_SUFFIXES
        ),
        key=lambda path: _natural_key(path.relative_to(input_root).as_posix()),
    )


def _group_sources(
    sources: Sequence[Path], input_root: Path, separator: str
) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = {}
    for source in sources:
        stem = source.stem
        group_key, delimiter, _ = stem.partition(separator)
        if not delimiter or not group_key:
            raise ValueError(
                "every supported source filename must contain the configured group separator"
            )
        grouped.setdefault(group_key, []).append(source)
    return {
        key: sorted(
            paths,
            key=lambda path: _natural_key(path.relative_to(input_root).as_posix()),
        )
        for key, paths in grouped.items()
    }


def _assign_anonymous_ids(
    grouped: dict[str, list[Path]], *, prefix: str, seed: str
) -> list[tuple[str, str, list[Path]]]:
    if not re.fullmatch(r"[A-Za-z]+", prefix):
        raise ValueError("--anonymous-id-prefix must contain only letters")
    ordered = sorted(
        grouped,
        key=lambda key: hashlib.sha256(f"{seed}|{key}".encode("utf-8")).hexdigest(),
    )
    width = max(3, len(str(len(ordered))))
    return [
        (f"{prefix}{index:0{width}d}", key, grouped[key])
        for index, key in enumerate(ordered, start=1)
    ]


def _convert_group(
    sources: Sequence[Path],
    *,
    input_root: Path,
    staging_root: Path,
    docx_policy: str,
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    staging_root.mkdir(parents=True, exist_ok=True)
    for source_index, source in enumerate(sources, start=1):
        suffix = source.suffix.lower()
        if suffix == ".docx":
            if docx_policy == "manual_review":
                return {"status": "blocked", "reason": "docx_requires_manual_conversion_review"}
            raise ValueError(f"unsupported DOCX policy: {docx_policy}")
        try:
            converted = _convert_source(source, staging_root, source_index)
        except Exception as error:
            return {
                "status": "blocked",
                "reason": f"conversion_failed_{suffix.lstrip('.') or 'unknown'}",
                "detail": type(error).__name__,
            }
        raw_relative_path = source.relative_to(input_root).as_posix()
        for source_file_page, page in enumerate(converted, start=1):
            pages.append(
                {
                    "path": page,
                    "raw_relative_path": raw_relative_path,
                    "source_file_page": source_file_page,
                }
            )
    return {"status": "ok", "pages": pages}


def _convert_source(source: Path, staging_root: Path, source_index: int) -> list[Path]:
    suffix = source.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        with Image.open(source) as image:
            orientation = image.getexif().get(274, 1)
            if orientation == 1:
                return [source]
            target = staging_root / f"file-{source_index:03d}-p001.png"
            ImageOps.exif_transpose(image).convert("RGB").save(target, format="PNG")
            return [target]
    if suffix in HEIF_SUFFIXES:
        converter = shutil.which("heif-convert")
        if converter is None:
            raise RuntimeError("heif_converter_unavailable")
        target = staging_root / f"file-{source_index:03d}-p001.jpg"
        result = subprocess.run(
            [converter, "--quiet", str(source), str(target)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0 or not target.is_file():
            raise RuntimeError("heif_conversion_failed")
        return [target]
    if suffix == ".pdf":
        document = fitz.open(source)
        if document.needs_pass:
            raise RuntimeError("encrypted_pdf")
        pages: list[Path] = []
        try:
            for page_index, page in enumerate(document, start=1):
                target = staging_root / f"file-{source_index:03d}-p{page_index:03d}.png"
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                pixmap.save(target)
                pages.append(target)
        finally:
            document.close()
        if not pages:
            raise RuntimeError("empty_pdf")
        return pages
    raise ValueError(f"unsupported source suffix: {suffix}")


def _private_source_file_rows(sources: Sequence[Path], input_root: Path) -> list[dict[str, str]]:
    return [
        {
            "raw_relative_path": source.relative_to(input_root).as_posix(),
            "sha256": _sha256_file(source),
            "extension": source.suffix.lower(),
        }
        for source in sources
    ]


def _write_combined_pdf(path: Path, source_pages_root: Path) -> None:
    page_paths = sorted(source_pages_root.glob("source-p*.*"), key=lambda item: item.name)
    if not page_paths:
        raise ValueError("no normalized pages available for source PDF")
    document = fitz.open()
    try:
        for image_path in page_paths:
            with Image.open(image_path) as image:
                page = document.new_page(width=image.width, height=image.height)
            page.insert_image(page.rect, filename=str(image_path), keep_proportion=False)
        document.save(path, deflate=True, garbage=4)
    finally:
        document.close()


def _natural_key(value: str) -> list[object]:
    return [int(token) if token.isdigit() else token.casefold() for token in re.split(r"(\d+)", value)]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
