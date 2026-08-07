import csv
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.review_identity_masks import (
    IdentityMaskReviewStore,
    REVIEW_COLUMNS,
    compile_review,
    initialize_review,
)


class IdentityMaskReviewTests(unittest.TestCase):
    def test_initialize_review_and_compile_approved_masks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout_path = _write_layout(root)
            source_root = root / "source_pages"
            source_root.mkdir()
            _write_source_page(source_root / "source-p0001.jpg")
            review_path = root / "review.csv"

            summary = initialize_review(
                layout_path=layout_path,
                source_pages_root=source_root,
                review_path=review_path,
                private_output_acknowledged=True,
            )
            store = IdentityMaskReviewStore(
                layout_path=layout_path,
                source_pages_root=source_root,
                review_path=review_path,
            )
            page = store.state()["pages"][0]
            compiled_path = root / "compiled-layout.json"

            self.assertEqual(summary["status"], "identity_mask_review_pending")
            self.assertEqual(page["review_status"], "pending")
            self.assertTrue(page["proposed_rectangles"])
            with self.assertRaisesRegex(ValueError, "at least one identity rectangle"):
                store.save(
                    {
                        "anonymous_id": "S001",
                        "source_page": 1,
                        "review_status": "approved",
                        "approved_rectangles": [],
                        "reviewer": "reviewer",
                        "reviewed_at": "2026-08-06T00:00:00Z",
                    }
                )
            store.save(
                {
                    "anonymous_id": "S001",
                    "source_page": 1,
                    "review_status": "approved",
                    "approved_rectangles": [
                        {"left": 0.1, "top": 0.1, "right": 0.4, "bottom": 0.2}
                    ],
                    "reviewer": "reviewer",
                    "reviewed_at": "2026-08-06T00:00:00Z",
                }
            )
            compiled = compile_review(
                layout_path=layout_path,
                review_path=review_path,
                output_layout=compiled_path,
                private_output_acknowledged=True,
            )
            layout = json.loads(compiled_path.read_text())

        self.assertEqual(compiled["status"], "identity_masks_compiled_pending_render")
        self.assertEqual(layout["identity_mask_review"]["status"], "all_pages_approved")
        self.assertEqual(layout["page_groups"][0]["page_masks"][0]["reason"], "identity_mask_review")

    def test_review_csv_columns_are_fixed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout_path = _write_layout(root)
            source_root = root / "source_pages"
            source_root.mkdir()
            _write_source_page(source_root / "source-p0001.jpg")
            review_path = root / "review.csv"
            initialize_review(
                layout_path=layout_path,
                source_pages_root=source_root,
                review_path=review_path,
                private_output_acknowledged=True,
            )
            with review_path.open(newline="", encoding="utf-8") as handle:
                columns = csv.DictReader(handle).fieldnames

        self.assertEqual(tuple(columns or ()), REVIEW_COLUMNS)

    def test_compile_allows_explicit_no_identity_page_without_a_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout_path = _write_layout(root)
            source_root = root / "source_pages"
            source_root.mkdir()
            _write_source_page(source_root / "source-p0001.jpg")
            review_path = root / "review.csv"
            compiled_path = root / "compiled-layout.json"
            initialize_review(
                layout_path=layout_path,
                source_pages_root=source_root,
                review_path=review_path,
                private_output_acknowledged=True,
            )
            store = IdentityMaskReviewStore(
                layout_path=layout_path,
                source_pages_root=source_root,
                review_path=review_path,
            )

            store.save(
                {
                    "anonymous_id": "S001",
                    "source_page": 1,
                    "review_status": "approved_no_identity",
                    "approved_rectangles": [],
                    "reviewer": "reviewer",
                    "reviewed_at": "2026-08-07T00:00:00Z",
                }
            )
            compiled = compile_review(
                layout_path=layout_path,
                review_path=review_path,
                output_layout=compiled_path,
                private_output_acknowledged=True,
            )
            layout = json.loads(compiled_path.read_text())

        self.assertEqual(compiled["status"], "identity_masks_compiled_pending_render")
        self.assertEqual(layout["page_groups"][0]["page_masks"], [])
        self.assertEqual(layout["identity_mask_review"]["masked_page_count"], 0)
        self.assertEqual(layout["identity_mask_review"]["no_identity_page_count"], 1)


def _write_layout(root: Path) -> Path:
    path = root / "layout.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assessment_id": "synthetic",
                "source_sha256": "a" * 64,
                "expected_page_count": 1,
                "page_groups": [
                    {"anonymous_id": "S001", "source_pages": [1], "page_masks": []}
                ],
                "excluded_pages": [],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_source_page(path: Path) -> None:
    image = Image.new("L", (200, 300), 255)
    ImageDraw.Draw(image).rectangle((20, 20, 150, 45), fill=0)
    image.save(path)


if __name__ == "__main__":
    unittest.main()
