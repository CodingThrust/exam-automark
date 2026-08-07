import tempfile
import unittest
from pathlib import Path

import fitz
from PIL import Image

from scripts.prepare_anonymized_assessment import (
    _effective_render_scale,
    _write_pdf,
)


class AdaptiveRenderScaleTests(unittest.TestCase):
    def test_requested_scale_is_preserved_below_the_pixel_cap(self):
        self.assertEqual(
            _effective_render_scale(
                page_width=600,
                page_height=800,
                requested_scale=2.0,
                max_render_pixels=12_000_000,
            ),
            2.0,
        )

    def test_large_page_is_deterministically_reduced_to_the_pixel_cap(self):
        scale = _effective_render_scale(
            page_width=12_000,
            page_height=8_000,
            requested_scale=2.0,
            max_render_pixels=12_000_000,
        )

        self.assertGreater(scale, 0)
        self.assertLess(scale, 2.0)
        self.assertAlmostEqual(12_000 * 8_000 * scale * scale, 12_000_000)

    def test_invalid_page_geometry_or_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "dimensions"):
            _effective_render_scale(
                page_width=0,
                page_height=800,
                requested_scale=2.0,
                max_render_pixels=12_000_000,
            )
        with self.assertRaisesRegex(ValueError, "positive"):
            _effective_render_scale(
                page_width=600,
                page_height=800,
                requested_scale=2.0,
                max_render_pixels=0,
            )

    def test_pdf_assembly_streams_existing_page_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.png"
            second = root / "second.png"
            output = root / "submission.pdf"
            Image.new("RGB", (100, 200), "white").save(first)
            Image.new("RGB", (200, 100), "white").save(second)

            _write_pdf(output, [first, second])

            with fitz.open(output) as document:
                self.assertEqual(len(document), 2)
                self.assertEqual((document[0].rect.width, document[0].rect.height), (100.0, 200.0))
                self.assertEqual((document[1].rect.width, document[1].rect.height), (200.0, 100.0))


if __name__ == "__main__":
    unittest.main()
