import io
import json
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
