from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print(json.dumps({"status": "error", "error": "usage: to_images.py <input> <output_dir>"}))
        return 2

    source = Path(args[0])
    output_dir = Path(args[1])
    output_dir.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        print(json.dumps({"status": "error", "error": f"missing file: {source}"}))
        return 2

    suffix = source.suffix.lower()
    try:
        if suffix in IMAGE_SUFFIXES:
            pages = [_convert_image(source, output_dir)]
            return _ok(source, pages)
        if suffix == ".pdf":
            pages = _convert_pdf(source, output_dir)
            return _ok(source, pages)
        if suffix == ".docx":
            pages = _convert_docx(source, output_dir)
            return _ok(source, pages)
    except MissingPdfRenderer as error:
        return _error("pdf_renderer_missing", str(error), code=2)
    except MissingDocxConverter as error:
        return _error("docx_unsupported", str(error), code=3)
    except Exception as error:
        return _error("conversion_failed", str(error), code=2)

    return _error("unsupported_file_type", suffix, code=2)


def _convert_image(source: Path, output_dir: Path) -> Path:
    target = output_dir / "page-001.png"
    with Image.open(source) as image:
        ImageOps.exif_transpose(image).convert("RGB").save(target)
    return target


def _convert_pdf(source: Path, output_dir: Path) -> list[Path]:
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
        target = output_dir / f"page-{index:03d}.png"
        pixmap.save(target)
        pages.append(target)
    return pages


def _convert_docx(source: Path, output_dir: Path) -> list[Path]:
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
        return _convert_pdf(pdf, output_dir)


def _ok(source: Path, pages: list[Path]) -> int:
    print(
        json.dumps(
            {
                "status": "ok",
                "source": source.as_posix(),
                "pages": [page.as_posix() for page in pages],
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
