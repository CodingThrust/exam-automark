from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from roster import RosterError, SAFE_SUBMISSION_ID, require_private_path
import to_images


SUPPORTED_SUFFIXES = to_images.IMAGE_SUFFIXES | {".pdf", ".docx"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render one complete private submission without page overwrites."
    )
    parser.add_argument("submission_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--submission-id")
    namespace = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    source_dir = namespace.submission_dir
    output_dir = namespace.output_dir
    submission_id = (namespace.submission_id or source_dir.name).strip()
    if not SAFE_SUBMISSION_ID.fullmatch(submission_id):
        print("invalid submission_id", file=sys.stderr)
        return 2
    if not source_dir.is_dir():
        print("submission directory is missing", file=sys.stderr)
        return 2
    if output_dir.exists() and any(output_dir.iterdir()):
        print("refusing to overwrite an existing rendered submission", file=sys.stderr)
        return 4
    try:
        require_private_path(source_dir, label="submission directory")
        require_private_path(output_dir, label="rendered submission output")
    except RosterError as error:
        print(f"private-output check failed: {error}", file=sys.stderr)
        return 2

    sources = _source_files(source_dir)
    if not sources:
        print("submission directory contains no supported scan files", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    pages: list[dict[str, object]] = []
    page_order = 0
    try:
        for source_order, source in enumerate(sources, start=1):
            prefix = f"source-{source_order:03d}"
            rendered = to_images.render_file(source, output_dir, prefix=prefix)
            for source_page_order, page in enumerate(rendered, start=1):
                page_order += 1
                pages.append(
                    {
                        "page_id": page.stem,
                        "path": page.name,
                        "source_id": f"source-{source_order:03d}",
                        "source_order": source_order,
                        "source_page_order": source_page_order,
                        "page_order": page_order,
                    }
                )
    except Exception as error:
        print(f"render failed: {error}", file=sys.stderr)
        return 2

    manifest = {
        "schema_version": 1,
        "submission_id": submission_id,
        "page_count": len(pages),
        "pages": pages,
    }
    manifest_path = output_dir / "pages.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "submission_id": submission_id,
                "page_count": len(pages),
                "manifest": manifest_path.name,
            },
            sort_keys=True,
        )
    )
    return 0


def _source_files(source_dir: Path) -> list[Path]:
    files = []
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_dir)
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
            continue
        if path.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(path)
    return sorted(files, key=lambda path: _natural_key(path.relative_to(source_dir).as_posix()))


def _natural_key(value: str) -> tuple[object, ...]:
    return tuple(
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", value.casefold())
    )


if __name__ == "__main__":
    raise SystemExit(main())
