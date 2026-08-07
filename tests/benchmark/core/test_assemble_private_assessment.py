import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import fitz
from PIL import Image

from benchmark.core.anonymization import validate_page_layout
from scripts.assemble_private_assessment import main


class AssemblePrivateAssessmentTests(unittest.TestCase):
    def test_builds_private_layout_without_raw_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "submissions"
            input_root.mkdir()
            _write_image(input_root / "alice_1.jpg", (255, 0, 0))
            _write_image(input_root / "alice_2.jpg", (0, 255, 0))
            _write_two_page_pdf(input_root / "bob_scan.pdf")
            output_root = root / "private-output"

            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "--input-root",
                        str(input_root),
                        "--assessment-id",
                        "synthetic_quiz",
                        "--output-root",
                        str(output_root),
                        "--group-separator",
                        "_",
                        "--private-output-acknowledged",
                        "--expected-pages-per-group",
                        "2",
                    ]
                )

            layout = json.loads((output_root / "page-layout.json").read_text())
            private_manifest = json.loads(
                (output_root / "private-source-manifest.json").read_text()
            )
            report = validate_page_layout(
                layout,
                source_page_count=4,
                source_sha256=layout["source_sha256"],
            )
            page_count = len(list((output_root / "source_pages").glob("source-p*.*")))

        self.assertEqual(result, 0)
        self.assertEqual(report["status"], "ready")
        self.assertEqual({group["anonymous_id"] for group in layout["page_groups"]}, {"S001", "S002"})
        self.assertNotIn("alice", json.dumps(layout))
        self.assertNotIn("bob", json.dumps(layout))
        self.assertEqual(private_manifest["model_run_allowed"], False)
        self.assertEqual(page_count, 4)

    def test_docx_group_is_blocked_without_stopping_other_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "submissions"
            input_root.mkdir()
            _write_image(input_root / "alice_1.jpg", (255, 0, 0))
            (input_root / "bob_1.docx").write_bytes(b"synthetic")
            output_root = root / "private-output"

            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "--input-root",
                        str(input_root),
                        "--assessment-id",
                        "synthetic_quiz",
                        "--output-root",
                        str(output_root),
                        "--group-separator",
                        "_",
                        "--private-output-acknowledged",
                    ]
                )
            layout = json.loads((output_root / "page-layout.json").read_text())
            private_manifest = json.loads(
                (output_root / "private-source-manifest.json").read_text()
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(layout["page_groups"]), 1)
        self.assertEqual(len(private_manifest["blocked_groups"]), 1)
        self.assertEqual(
            private_manifest["blocked_groups"][0]["reason"],
            "docx_requires_manual_conversion_review",
        )

    def test_image_only_docx_is_extracted_in_embedded_drawing_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "submissions"
            input_root.mkdir()
            _write_image_only_docx(input_root / "alice_1.docx", [(255, 0, 0), (0, 255, 0)])
            output_root = root / "private-output"

            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "--input-root",
                        str(input_root),
                        "--assessment-id",
                        "synthetic_quiz",
                        "--output-root",
                        str(output_root),
                        "--group-separator",
                        "_",
                        "--private-output-acknowledged",
                        "--docx-policy",
                        "embedded_images",
                    ]
                )

            layout = json.loads((output_root / "page-layout.json").read_text())
            pages = sorted((output_root / "source_pages").glob("source-p*.png"))
            colors = [Image.open(page).getpixel((0, 0)) for page in pages]

        self.assertEqual(result, 0)
        self.assertEqual(layout["expected_page_count"], 2)
        self.assertEqual(colors, [(255, 0, 0), (0, 255, 0)])

    def test_docx_with_text_remains_blocked_under_embedded_image_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "submissions"
            input_root.mkdir()
            _write_image(input_root / "bob_1.jpg", (0, 255, 0))
            _write_image_only_docx(
                input_root / "alice_1.docx",
                [(255, 0, 0)],
                include_text=True,
            )
            output_root = root / "private-output"

            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "--input-root",
                        str(input_root),
                        "--assessment-id",
                        "synthetic_quiz",
                        "--output-root",
                        str(output_root),
                        "--group-separator",
                        "_",
                        "--private-output-acknowledged",
                        "--docx-policy",
                        "embedded_images",
                    ]
                )
            private_manifest = json.loads(
                (output_root / "private-source-manifest.json").read_text()
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            private_manifest["blocked_groups"][0]["reason"], "conversion_failed_docx"
        )

    def test_docx_supplement_can_use_an_isolated_source_filter_and_id_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "submissions"
            input_root.mkdir()
            _write_image(input_root / "alice_1.jpg", (255, 0, 0))
            _write_image_only_docx(input_root / "bob_1.docx", [(0, 255, 0)])
            output_root = root / "private-output"

            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "--input-root",
                        str(input_root),
                        "--assessment-id",
                        "synthetic_quiz",
                        "--output-root",
                        str(output_root),
                        "--group-separator",
                        "_",
                        "--private-output-acknowledged",
                        "--docx-policy",
                        "embedded_images",
                        "--include-suffix",
                        ".docx",
                        "--anonymous-id-start",
                        "43",
                    ]
                )

            layout = json.loads((output_root / "page-layout.json").read_text())
            private_manifest = json.loads(
                (output_root / "private-source-manifest.json").read_text()
            )

        self.assertEqual(result, 0)
        self.assertEqual([group["anonymous_id"] for group in layout["page_groups"]], ["S043"])
        self.assertEqual(layout["expected_page_count"], 1)
        self.assertEqual(private_manifest["grouping"]["included_suffixes"], [".docx"])

    def test_requires_explicit_private_output_acknowledgement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "submissions"
            input_root.mkdir()
            _write_image(input_root / "alice_1.jpg", (255, 0, 0))

            with self.assertRaisesRegex(ValueError, "private-output-acknowledged"):
                main(
                    [
                        "--input-root",
                        str(input_root),
                        "--assessment-id",
                        "synthetic_quiz",
                        "--output-root",
                        str(root / "output"),
                        "--group-separator",
                        "_",
                    ]
                )


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (30, 20), color).save(path)


def _write_two_page_pdf(path: Path) -> None:
    document = fitz.open()
    try:
        for _ in range(2):
            document.new_page(width=30, height=20)
        document.save(path)
    finally:
        document.close()


def _write_image_only_docx(
    path: Path,
    colors: list[tuple[int, int, int]],
    *,
    include_text: bool = False,
) -> None:
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<w:body>"
        + "".join(
            f'<w:p><w:r><w:drawing><a:blip r:embed="rId{index}" />'
            "</w:drawing></w:r></w:p>"
            for index, _color in enumerate(colors, start=1)
        )
        + ("<w:p><w:r><w:t>not allowed</w:t></w:r></w:p>" if include_text else "")
        + "</w:body></w:document>"
    )
    relationships = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{index}" Target="media/image{index}.png" />'
            for index, _color in enumerate(colors, start=1)
        )
        + "</Relationships>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", relationships)
        for index, color in enumerate(colors, start=1):
            image_bytes = io.BytesIO()
            Image.new("RGB", (30, 20), color).save(image_bytes, format="PNG")
            archive.writestr(f"word/media/image{index}.png", image_bytes.getvalue())


if __name__ == "__main__":
    unittest.main()
