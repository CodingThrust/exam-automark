from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

from roster import RosterError, require_private_path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic"}


def _validated_prefix(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}", normalized):
        raise ValueError("prefix must contain only letters, digits, dot, underscore, or dash")
    return normalized


def _page_target(output_dir: Path, prefix: str, index: int) -> Path:
    stem = f"{prefix}-page" if prefix else "page"
    return output_dir / f"{stem}-{index:03d}.png"


def _ensure_new_target(target: Path) -> None:
    if target.exists():
        raise FileExistsError(f"refusing to overwrite rendered page: {target.name}")


def render_file(source: Path, output_dir: Path, *, prefix: str = "") -> list[Path]:
    """Render one supported submission source without overwriting pages."""

    suffix = source.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return [_convert_image(source, output_dir, prefix=prefix)]
    if suffix == ".pdf":
        return _convert_pdf(source, output_dir, prefix=prefix)
    if suffix == ".docx":
        return _convert_docx(source, output_dir, prefix=prefix)
    raise ValueError(f"unsupported file type: {suffix}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render one source file to PNG pages.")
    parser.add_argument("input")
    parser.add_argument("output_dir")
    parser.add_argument("--prefix", default="")
    namespace = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    source = Path(namespace.input)
    output_dir = Path(namespace.output_dir)
    try:
        prefix = _validated_prefix(namespace.prefix)
    except ValueError as error:
        parser.error(str(error))
    if not source.is_file():
        print(json.dumps({"status": "error", "error": "missing_input_file"}))
        return 2

    try:
        require_private_path(output_dir, label="rendered-page output")
        output_dir.mkdir(parents=True, exist_ok=True)
        pages = render_file(source, output_dir, prefix=prefix)
        return _ok(source, pages)
    except RosterError as error:
        return _error("private_output_required", str(error), code=2)
    except MissingPdfRenderer as error:
        return _error("pdf_renderer_missing", str(error), code=2)
    except MissingDocxConverter as error:
        return _error("docx_unsupported", str(error), code=3)
    except Exception as error:
        return _error("conversion_failed", str(error), code=2)



def _convert_image(source: Path, output_dir: Path, *, prefix: str) -> Path:
    target = _page_target(output_dir, prefix, 1)
    _ensure_new_target(target)
    with Image.open(source) as image:
        ImageOps.exif_transpose(image).convert("RGB").save(target)
    return target


def _convert_pdf(source: Path, output_dir: Path, *, prefix: str) -> list[Path]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise MissingPdfRenderer(
            "Install PyMuPDF to render PDF submissions in Python."
        ) from exc

    pages = []
    document = fitz.open(str(source))
    for index, page in enumerate(document, start=1):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        target = _page_target(output_dir, prefix, index)
        _ensure_new_target(target)
        pixmap.save(target)
        pages.append(target)
    return pages


def _convert_docx(source: Path, output_dir: Path, *, prefix: str) -> list[Path]:
    converter = shutil.which("soffice") or shutil.which("libreoffice")
    if converter is None:
        raise MissingDocxConverter("LibreOffice or soffice is required for DOCX files.")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        result = subprocess.run(
            [
                converter,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmpdir),
                str(source),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise MissingDocxConverter(result.stderr.strip() or result.stdout.strip())
        pdf = tmpdir / f"{source.stem}.pdf"
        if not pdf.is_file():
            matches = list(tmpdir.glob("*.pdf"))
            if not matches:
                raise MissingDocxConverter("DOCX converter did not produce a PDF.")
            pdf = matches[0]
        return _convert_pdf(pdf, output_dir, prefix=prefix)


def _ok(source: Path, pages: list[Path]) -> int:
    print(
        json.dumps(
            {
                "status": "ok",
                "page_count": len(pages),
                "pages": [page.name for page in pages],
            },
            sort_keys=True,
        )
    )
    return 0


def _error(error: str, detail: str, *, code: int) -> int:
    print(json.dumps({"status": "error", "error": error, "detail": detail}, sort_keys=True))
    return code


class MissingPdfRenderer(Exception):
    pass


class MissingDocxConverter(Exception):
    pass


if __name__ == "__main__":
    raise SystemExit(main())
