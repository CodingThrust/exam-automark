from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.anonymization import sha256_file
from benchmark.core.cohort_preflight import build_anonymous_cohort_preflight
from benchmark.core.page_scope_workflow import (
    PAGE_SCOPE_REVIEW_COLUMNS,
    initialize_page_scope_review,
)


class CohortPreflightTests(unittest.TestCase):
    def test_pending_page_scope_blocks_otherwise_final_approved_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            report = _build(paths)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("anomalous_page_scope_review_ready", report["failed_checks"])
        self.assertFalse(report["model_run_allowed"])

    def test_approved_page_scope_enables_preflight_but_not_model_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            _approve_scope(paths["review_csv"])
            report = _build(paths)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["anonymous_page_count"], 5)
        self.assertFalse(report["model_run_allowed"])
        self.assertIn("private_manifest_sha256", report["bindings"])

    def test_changed_layout_breaks_preparation_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            _approve_scope(paths["review_csv"])
            layout = json.loads(paths["layout"].read_text(encoding="utf-8"))
            layout["assessment_id"] = "tampered"
            paths["layout"].write_text(json.dumps(layout), encoding="utf-8")
            report = _build(paths)

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "preparation_metadata_schema_and_layout_binding", report["failed_checks"]
        )


def _build(paths: dict[str, Path]) -> dict[str, object]:
    return build_anonymous_cohort_preflight(
        artifact_root=paths["artifact_root"],
        layout_path=paths["layout"],
        final_review_validation_path=paths["final_validation"],
        private_manifest_path=paths["private_manifest"],
        expected_pages_per_group=4,
        page_scope_review_csv_path=paths["review_csv"],
        page_scope_review_metadata_path=paths["review_metadata"],
    )


def _make_inputs(root: Path) -> dict[str, Path]:
    manifest = {
        "schema_version": 1,
        "record_type": "private_mixed_submission_assembly",
        "assessment_id": "synthetic",
        "groups": [
            {
                "anonymous_id": "S001",
                "status": "converted_pending_page_review",
                "rendered_page_count": 5,
                "page_count_status": "requires_page_scope_review",
            }
        ],
    }
    private_manifest = root / "private-manifest.json"
    private_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    review_csv = root / "scope-review.csv"
    review_metadata = root / "scope-review-metadata.json"
    initialize_page_scope_review(
        private_manifest_path=private_manifest,
        expected_pages_per_group=4,
        review_csv_path=review_csv,
        metadata_path=review_metadata,
    )
    layout = {
        "schema_version": 1,
        "assessment_id": "synthetic",
        "source_sha256": "a" * 64,
        "expected_page_count": 5,
        "page_groups": [
            {"anonymous_id": "S001", "source_pages": [1, 2, 3, 4, 5], "page_masks": []}
        ],
        "excluded_pages": [],
    }
    layout_path = root / "page-layout.json"
    layout_path.write_text(json.dumps(layout), encoding="utf-8")
    artifact_root = root / "anonymous-artifact"
    manifest_root = artifact_root / "manifest"
    manifest_root.mkdir(parents=True)
    (manifest_root / "prep-metadata.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "anonymized_assessment_preparation",
                "assessment_id": "synthetic",
                "layout_sha256": sha256_file(layout_path),
            }
        ),
        encoding="utf-8",
    )
    final_validation = manifest_root / "final-review-validation.json"
    final_validation.write_text(
        json.dumps(
            {
                "status": "ready",
                "failed_checks": [],
                "expected_page_count": 5,
                "review_row_count": 5,
            }
        ),
        encoding="utf-8",
    )
    return {
        "artifact_root": artifact_root,
        "layout": layout_path,
        "final_validation": final_validation,
        "private_manifest": private_manifest,
        "review_csv": review_csv,
        "review_metadata": review_metadata,
    }


def _approve_scope(path: Path) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0].update(
        {
            "scope_review_status": "approved_include_all",
            "reviewer": "course_owner",
            "reviewed_at": "2026-08-08T00:00:00Z",
            "notes": "synthetic approval",
        }
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAGE_SCOPE_REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
