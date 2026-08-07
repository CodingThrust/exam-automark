from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from benchmark.core.page_scope_workflow import (
    PAGE_SCOPE_REVIEW_COLUMNS,
    PageScopeReviewError,
    build_page_scope_review_metadata,
    initialize_page_scope_review,
    page_scope_review_rows,
    sha256_file,
    validate_page_scope_review,
)


REPO_ROOT = Path(__file__).parents[3]


class PageScopeWorkflowTests(unittest.TestCase):
    def test_rows_and_metadata_do_not_copy_raw_group_data(self):
        manifest = _manifest()

        rows = page_scope_review_rows(manifest, expected_pages_per_group=4)
        metadata = build_page_scope_review_metadata(
            private_manifest=manifest,
            private_manifest_sha256="a" * 64,
            expected_pages_per_group=4,
        )
        serialized = json.dumps({"rows": rows, "metadata": metadata})

        self.assertEqual(len(rows), 1)
        self.assertEqual(tuple(rows[0]), PAGE_SCOPE_REVIEW_COLUMNS)
        self.assertNotIn("student-name", serialized)
        self.assertNotIn("raw-answer-file", serialized)
        self.assertFalse(metadata["model_run_allowed"])

    def test_initialization_is_idempotent_and_validation_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = _write_manifest(root)
            review_path = root / "review.csv"
            metadata_path = root / "metadata.json"

            created = initialize_page_scope_review(
                private_manifest_path=manifest_path,
                expected_pages_per_group=4,
                review_csv_path=review_path,
                metadata_path=metadata_path,
            )
            repeated = initialize_page_scope_review(
                private_manifest_path=manifest_path,
                expected_pages_per_group=4,
                review_csv_path=review_path,
                metadata_path=metadata_path,
            )
            pending = validate_page_scope_review(
                private_manifest_path=manifest_path,
                expected_pages_per_group=4,
                review_csv_path=review_path,
                metadata_path=metadata_path,
            )
            rows = _read_csv(review_path)
            rows[0].update(
                {
                    "scope_review_status": "approved_include_all",
                    "reviewer": "course_owner",
                    "reviewed_at": "2026-08-07T00:00:00Z",
                    "notes": "all rendered pages belong to this submission",
                }
            )
            _write_csv(review_path, rows)
            approved = validate_page_scope_review(
                private_manifest_path=manifest_path,
                expected_pages_per_group=4,
                review_csv_path=review_path,
                metadata_path=metadata_path,
            )

        self.assertEqual(created["status"], "created")
        self.assertEqual(repeated["status"], "already_matches_template")
        self.assertEqual(pending["status"], "not_ready")
        self.assertIn("all_page_scope_decisions_completed", pending["failed_checks"])
        self.assertEqual(approved["status"], "ready")
        self.assertFalse(approved["model_run_allowed"])

    def test_correction_blocks_cohort_freeze_and_needs_explanation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = _write_manifest(root)
            review_path = root / "review.csv"
            metadata_path = root / "metadata.json"
            initialize_page_scope_review(
                private_manifest_path=manifest_path,
                expected_pages_per_group=4,
                review_csv_path=review_path,
                metadata_path=metadata_path,
            )
            rows = _read_csv(review_path)
            rows[0].update(
                {
                    "scope_review_status": "requires_correction",
                    "reviewer": "course_owner",
                    "reviewed_at": "2026-08-07T00:00:00Z",
                    "notes": "page must be reassessed",
                }
            )
            _write_csv(review_path, rows)
            report = validate_page_scope_review(
                private_manifest_path=manifest_path,
                expected_pages_per_group=4,
                review_csv_path=review_path,
                metadata_path=metadata_path,
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("all_anomalies_approved_include_all", report["failed_checks"])

    def test_refuses_manifest_with_inconsistent_page_count_status(self):
        manifest = _manifest()
        manifest["groups"][1]["page_count_status"] = "matches_expected"

        with self.assertRaisesRegex(PageScopeReviewError, "page_count_status"):
            page_scope_review_rows(manifest, expected_pages_per_group=4)

    def test_cli_initializes_private_template_without_ids_in_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = _write_manifest(root)
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(REPO_ROOT / "scripts" / "review_page_scope.py"),
                    "initialize",
                    "--private-manifest",
                    str(manifest_path),
                    "--expected-pages-per-group",
                    "4",
                    "--review-csv",
                    str(root / "review.csv"),
                    "--metadata",
                    str(root / "metadata.json"),
                    "--private-output-acknowledged",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("S002", result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["anomaly_group_count"], 1)
        self.assertFalse(payload["model_run_allowed"])


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_type": "private_mixed_submission_assembly",
        "assessment_id": "synthetic-assessment",
        "groups": [
            {
                "anonymous_id": "S001",
                "raw_group_key": "student-name-one",
                "status": "converted_pending_page_review",
                "source_files": [{"raw_relative_path": "raw-answer-file-one.jpg"}],
                "rendered_page_count": 4,
                "page_count_status": "matches_expected",
            },
            {
                "anonymous_id": "S002",
                "raw_group_key": "student-name-two",
                "status": "converted_pending_page_review",
                "source_files": [{"raw_relative_path": "raw-answer-file-two.jpg"}],
                "rendered_page_count": 5,
                "page_count_status": "requires_page_scope_review",
            },
            {
                "anonymous_id": "S003",
                "raw_group_key": "student-name-three",
                "status": "blocked",
                "reason": "synthetic",
            },
        ],
    }


def _write_manifest(root: Path) -> Path:
    path = root / "private-source-manifest.json"
    path.write_text(json.dumps(_manifest()), encoding="utf-8")
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAGE_SCOPE_REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
