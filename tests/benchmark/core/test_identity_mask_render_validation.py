import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.validate_identity_mask_rendering import validate_identity_mask_rendering


class IdentityMaskRenderValidationTests(unittest.TestCase):
    def test_accepts_white_rendered_identity_rectangle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout_path, image_path = _fixture(root)
            image = Image.new("RGB", (100, 100), "white")
            image.save(image_path)

            report = validate_identity_mask_rendering(
                layout_path=layout_path,
                artifact_root=root / "artifacts",
            )

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["identity_rectangle_count"], 1)
        self.assertEqual(report["failed_rectangle_count"], 0)

    def test_rejects_nonwhite_pixel_inside_rendered_identity_rectangle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout_path, image_path = _fixture(root)
            image = Image.new("RGB", (100, 100), "white")
            ImageDraw.Draw(image).rectangle((40, 40, 60, 60), fill="black")
            image.save(image_path)

            report = validate_identity_mask_rendering(
                layout_path=layout_path,
                artifact_root=root / "artifacts",
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(report["failed_rectangle_count"], 1)


def _fixture(root: Path) -> tuple[Path, Path]:
    layout_path = root / "layout.json"
    layout_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assessment_id": "synthetic",
                "source_sha256": "a" * 64,
                "expected_page_count": 1,
                "page_groups": [
                    {
                        "anonymous_id": "S001",
                        "source_pages": [1],
                        "page_masks": [
                            {
                                "source_page": 1,
                                "reason": "identity_mask_review",
                                "rectangles": [
                                    {
                                        "left": 0.2,
                                        "top": 0.2,
                                        "right": 0.8,
                                        "bottom": 0.8,
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "excluded_pages": [],
            }
        ),
        encoding="utf-8",
    )
    image_path = (
        root
        / "artifacts"
        / "anonymized_pages"
        / "S001"
        / "S001-p01.png"
    )
    image_path.parent.mkdir(parents=True)
    return layout_path, image_path


if __name__ == "__main__":
    unittest.main()
