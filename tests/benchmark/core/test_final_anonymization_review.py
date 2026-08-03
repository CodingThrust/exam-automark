import tempfile
import unittest
from pathlib import Path

from benchmark.core.anonymization import (
    expected_review_outputs,
    expected_review_pairs,
    review_rows_for_layout,
    sha256_file,
    validate_anonymization_review,
    write_json,
    write_review_csv,
)
from benchmark.core.grading_mask_workflow import (
    build_artifact_manifest,
    build_render_spec,
    canonical_json_sha256,
)
from scripts.review_final_anonymization import FinalApprovalStore


class FinalAnonymizationReviewTests(unittest.TestCase):
    def test_approve_all_writes_all_three_bound_final_approvals(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_prepared_artifact(Path(tmp))
            store = _store(paths)

            self.assertEqual(store.state()["summary"]["fully_approved"], 0)
            store.approve_all(
                {
                    "anonymous_id": "S001",
                    "source_page": 1,
                    "reviewer": "reviewer",
                    "reviewed_at": "2026-08-03T00:00:00Z",
                }
            )

            report = validate_anonymization_review(
                paths["review_path"],
                expected_pairs=expected_review_pairs(_layout()),
                expected_outputs=expected_review_outputs(_layout()),
                expected_render_spec_sha256=paths["render_spec_sha256"],
                expected_artifact_manifest_sha256=paths["artifact_manifest_sha256"],
            )

        self.assertEqual(store.state()["summary"]["fully_approved"], 1)
        self.assertEqual(report["status"], "ready")

    def test_reject_keeps_page_out_of_final_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_prepared_artifact(Path(tmp))
            store = _store(paths)
            store.reject(
                {
                    "anonymous_id": "S001",
                    "source_page": 1,
                    "reviewer": "reviewer",
                    "reviewed_at": "2026-08-03T00:00:00Z",
                    "note": "synthetic remaining grader mark",
                }
            )

            report = validate_anonymization_review(
                paths["review_path"],
                expected_pairs=expected_review_pairs(_layout()),
                expected_outputs=expected_review_outputs(_layout()),
                expected_render_spec_sha256=paths["render_spec_sha256"],
                expected_artifact_manifest_sha256=paths["artifact_manifest_sha256"],
            )

        self.assertEqual(store.state()["summary"]["needs_correction"], 1)
        self.assertEqual(report["status"], "not_ready")
        self.assertIn("privacy_review_approved", report["failed_checks"])


def _layout() -> dict[str, object]:
    return {
        "schema_version": 1,
        "assessment_id": "synthetic_final_review",
        "source_sha256": "a" * 64,
        "expected_page_count": 1,
        "page_groups": [
            {"anonymous_id": "S001", "source_pages": [1], "page_masks": []}
        ],
        "excluded_pages": [],
    }


def _make_prepared_artifact(root: Path) -> dict[str, object]:
    layout = _layout()
    layout_path = root / "layout.json"
    write_json(layout_path, layout)
    artifact_root = root / "artifacts"
    image_path = artifact_root / "anonymized_pages" / "S001" / "S001-p01.png"
    pdf_path = artifact_root / "anonymized_pdfs" / "S001.pdf"
    image_path.parent.mkdir(parents=True)
    pdf_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"synthetic image")
    pdf_path.write_bytes(b"synthetic pdf")

    render_spec = build_render_spec(
        layout=layout,
        layout_sha256=sha256_file(layout_path),
        identity_rectangles=[{"left": 0.0, "top": 0.0, "right": 0.1, "bottom": 0.1}],
        render_scale=2.0,
    )
    render_spec_sha256 = canonical_json_sha256(render_spec)
    artifact_manifest = build_artifact_manifest(
        output_root=artifact_root,
        layout=layout,
        render_spec_sha256=render_spec_sha256,
    )
    artifact_manifest_path = artifact_root / "manifest" / "output-artifacts.json"
    write_json(artifact_manifest_path, artifact_manifest)
    artifact_manifest_sha256 = sha256_file(artifact_manifest_path)
    review_path = artifact_root / "manifest" / "anonymization_review.csv"
    write_review_csv(
        review_path,
        review_rows_for_layout(
            layout,
            identity_rectangles=render_spec["identity_redaction_rectangles"],
            render_spec_sha256=render_spec_sha256,
            artifact_manifest_sha256=artifact_manifest_sha256,
        ),
    )
    write_json(
        artifact_root / "manifest" / "prep-metadata.json",
        {
            "schema_version": 2,
            "record_type": "anonymized_assessment_preparation",
            "assessment_id": layout["assessment_id"],
            "layout_sha256": sha256_file(layout_path),
            "render_spec": render_spec,
            "render_spec_sha256": render_spec_sha256,
            "artifact_manifest_path": "manifest/output-artifacts.json",
            "artifact_manifest_sha256": artifact_manifest_sha256,
            "review_path": "manifest/anonymization_review.csv",
        },
    )
    return {
        "layout_path": layout_path,
        "artifact_root": artifact_root,
        "prep_metadata_path": artifact_root / "manifest" / "prep-metadata.json",
        "review_path": review_path,
        "render_spec_sha256": render_spec_sha256,
        "artifact_manifest_sha256": artifact_manifest_sha256,
    }


def _store(paths: dict[str, object]) -> FinalApprovalStore:
    return FinalApprovalStore(
        layout_path=paths["layout_path"],  # type: ignore[arg-type]
        artifact_root=paths["artifact_root"],  # type: ignore[arg-type]
        prep_metadata_path=paths["prep_metadata_path"],  # type: ignore[arg-type]
        review_path=paths["review_path"],  # type: ignore[arg-type]
    )


if __name__ == "__main__":
    unittest.main()
