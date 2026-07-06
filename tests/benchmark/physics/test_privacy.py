import tempfile
import unittest
from pathlib import Path

from PIL import Image

from benchmark.physics.privacy import apply_redactions, assert_privacy_approved


class PrivacyTests(unittest.TestCase):
    def test_redaction_masks_configured_rectangle(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.jpg"
            output = Path(tmp) / "S001-p01.jpg"
            Image.new("RGB", (20, 20), "white").save(source)
            apply_redactions(source, output, [(0, 0, 10, 10)])
            with Image.open(output) as image:
                self.assertEqual(image.getpixel((5, 5)), (0, 0, 0))

    def test_unapproved_page_blocks_upload(self):
        rows = [{"page": "S001-p01.jpg", "approved": "false"}]
        with self.assertRaisesRegex(ValueError, "privacy approval"):
            assert_privacy_approved(rows)


if __name__ == "__main__":
    unittest.main()
