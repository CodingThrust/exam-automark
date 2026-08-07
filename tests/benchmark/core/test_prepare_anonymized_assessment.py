import json
import tempfile
import unittest
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

from scripts.prepare_anonymized_assessment import (
    _effective_render_scale,
    _write_pdf,
    main,
)
from benchmark.core.grading_mask_workflow import (
    build_artifact_manifest,
    canonical_json_sha256,
    sha256_file,
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

    def test_candidate_detection_uses_verified_anonymous_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout = {
                "schema_version": 1,
                "assessment_id": "synthetic-anonymous-artifact",
                "source_sha256": "a" * 64,
                "expected_page_count": 1,
                "page_groups": [
                    {"anonymous_id": "S001", "source_pages": [1], "page_masks": []}
                ],
                "excluded_pages": [],
            }
            layout_path = root / "layout.json"
            layout_path.write_text(json.dumps(layout), encoding="utf-8")
            artifact_root = root / "anonymous-artifacts"
            image_path = artifact_root / "anonymized_pages" / "S001" / "S001-p01.png"
            pdf_path = artifact_root / "anonymized_pdfs" / "S001.pdf"
            image_path.parent.mkdir(parents=True)
            pdf_path.parent.mkdir(parents=True)
            image = Image.new("RGB", (200, 100), "white")
            ImageDraw.Draw(image).line((150, 50, 175, 70), fill=(220, 10, 10), width=4)
            image.save(image_path)
            pdf_path.write_bytes(b"synthetic pdf")

            layout_hash = sha256_file(layout_path)
            render_spec = {"layout_sha256": layout_hash, "render_scale": 1.0}
            render_spec_sha256 = canonical_json_sha256(render_spec)
            artifact_manifest = build_artifact_manifest(
                output_root=artifact_root,
                layout=layout,
                render_spec_sha256=render_spec_sha256,
            )
            manifest_path = artifact_root / "manifest" / "output-artifacts.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(json.dumps(artifact_manifest), encoding="utf-8")
            prep_metadata = {
                "schema_version": 2,
                "record_type": "anonymized_assessment_preparation",
                "assessment_id": layout["assessment_id"],
                "layout_sha256": layout_hash,
                "render_spec": render_spec,
                "render_spec_sha256": render_spec_sha256,
                "artifact_manifest_path": "manifest/output-artifacts.json",
                "artifact_manifest_sha256": sha256_file(manifest_path),
            }
            (artifact_root / "manifest" / "prep-metadata.json").write_text(
                json.dumps(prep_metadata), encoding="utf-8"
            )

            review_root = root / "candidate-review"
            self.assertEqual(
                0,
                main(
                    [
                        "propose-grading-masks-from-artifacts",
                        "--layout",
                        str(layout_path),
                        "--artifact-root",
                        str(artifact_root),
                        "--output-root",
                        str(review_root),
                    ]
                ),
            )

            candidate_manifest = json.loads(
                (review_root / "candidate-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                "post_identity_anonymous_render",
                candidate_manifest["detector"]["input_mode"],
            )
            self.assertEqual(1, len(candidate_manifest["candidates"]))
            self.assertTrue((review_root / "candidate-decisions.csv").is_file())
            self.assertTrue((review_root / "page-sweeps.csv").is_file())


if __name__ == "__main__":
    unittest.main()
