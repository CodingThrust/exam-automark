import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.anonymization import (
    ANONYMIZATION_REVIEW_COLUMNS,
    expected_review_pairs,
    expected_review_outputs,
    review_rows_for_layout,
    validate_anonymization_review,
    validate_page_layout,
)
from benchmark.core.schema import CourseSpec


REPO_ROOT = Path(__file__).parents[3]
RENDER_SPEC_SHA256 = "b" * 64
ARTIFACT_MANIFEST_SHA256 = "c" * 64


class AnonymousPageLayoutTests(unittest.TestCase):
    def test_fragment_layout_can_cover_source_with_documented_exclusion(self):
        layout = _layout()

        report = validate_page_layout(
            layout,
            source_page_count=4,
            source_sha256="a" * 64,
        )

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["anonymous_group_count"], 2)
        self.assertEqual(report["covered_page_count"], 3)
        self.assertEqual(report["excluded_page_count"], 1)
        self.assertEqual(report["failed_checks"], [])

    def test_duplicate_or_uncovered_source_page_blocks_layout(self):
        layout = _layout()
        layout["page_groups"][1]["source_pages"] = [2]
        layout["excluded_pages"] = []

        report = validate_page_layout(
            layout,
            source_page_count=4,
            source_sha256="a" * 64,
        )

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("all_pages_covered_once", report["failed_checks"])


class AnonymizationReviewTests(unittest.TestCase):
    def test_identity_masks_are_recorded_separately_from_grading_masks(self):
        layout = _layout()
        layout["page_groups"][0]["page_masks"] = [
            {
                "source_page": 1,
                "reason": "identity_mask_review",
                "rectangles": [
                    {"left": 0.0, "top": 0.0, "right": 0.2, "bottom": 0.1}
                ],
            }
        ]
        rows = review_rows_for_layout(
            layout,
            identity_rectangles=[],
            render_spec_sha256=RENDER_SPEC_SHA256,
            artifact_manifest_sha256=ARTIFACT_MANIFEST_SHA256,
        )

        row = next(item for item in rows if item["source_page"] == "1")
        self.assertIn('"right":0.2', row["identity_redaction_rectangles"])
        self.assertEqual(row["grading_mark_mask_rectangles"], "[]")

    def test_all_three_human_approvals_are_required(self):
        layout = _layout()
        with tempfile.TemporaryDirectory() as tmp:
            review_path = Path(tmp) / "anonymization_review.csv"
            _write_review(review_path, expected_review_pairs(layout), layout)

            ready = validate_anonymization_review(
                review_path,
                expected_pairs=expected_review_pairs(layout),
                expected_outputs=expected_review_outputs(layout),
                expected_render_spec_sha256=RENDER_SPEC_SHA256,
                expected_artifact_manifest_sha256=ARTIFACT_MANIFEST_SHA256,
            )

            with review_path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["blindness_review_status"] = "pending"
            _write_rows(review_path, rows)
            blocked = validate_anonymization_review(
                review_path,
                expected_pairs=expected_review_pairs(layout),
                expected_outputs=expected_review_outputs(layout),
                expected_render_spec_sha256=RENDER_SPEC_SHA256,
                expected_artifact_manifest_sha256=ARTIFACT_MANIFEST_SHA256,
            )

        self.assertEqual(ready["status"], "ready")
        self.assertEqual(blocked["status"], "not_ready")
        self.assertIn("blindness_review_approved", blocked["failed_checks"])

    def test_old_approval_cannot_be_reused_for_different_rendered_artifacts(self):
        layout = _layout()
        with tempfile.TemporaryDirectory() as tmp:
            review_path = Path(tmp) / "anonymization_review.csv"
            _write_review(review_path, expected_review_pairs(layout), layout)

            report = validate_anonymization_review(
                review_path,
                expected_pairs=expected_review_pairs(layout),
                expected_outputs=expected_review_outputs(layout),
                expected_render_spec_sha256="d" * 64,
                expected_artifact_manifest_sha256="e" * 64,
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "review_render_spec_matches_preparation", report["failed_checks"]
        )
        self.assertIn(
            "review_artifact_manifest_matches_preparation", report["failed_checks"]
        )

    def test_review_output_paths_must_match_layout(self):
        layout = _layout()
        with tempfile.TemporaryDirectory() as tmp:
            review_path = Path(tmp) / "anonymization_review.csv"
            _write_review(review_path, expected_review_pairs(layout), layout)
            with review_path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["output_image"] = "anonymized_pages/S002/S002-p01.png"
            _write_rows(review_path, rows)

            report = validate_anonymization_review(
                review_path,
                expected_pairs=expected_review_pairs(layout),
                expected_outputs=expected_review_outputs(layout),
                expected_render_spec_sha256=RENDER_SPEC_SHA256,
                expected_artifact_manifest_sha256=ARTIFACT_MANIFEST_SHA256,
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("review_output_paths_match_layout", report["failed_checks"])

    def test_partial_week3_course_spec_is_explicitly_seventy_points(self):
        course = CourseSpec.from_json_path(
            REPO_ROOT
            / "experiments"
            / "course_specs"
            / "DSAA3071_week3_partial_pages_1_and_3.json"
        )

        self.assertEqual(course.question_ids, ("Q1", "Q2", "Q3", "Q4", "Q9", "Q10"))
        self.assertEqual(course.max_total, 70.0)
        self.assertEqual(course.input_modes, ("image", "pdf", "transcript", "text"))


def _layout() -> dict[str, object]:
    return {
        "schema_version": 1,
        "assessment_id": "synthetic_partial",
        "source_sha256": "a" * 64,
        "expected_page_count": 4,
        "page_groups": [
            {
                "anonymous_id": "S001",
                "source_pages": [1, 3],
                "page_masks": [
                    {
                        "source_page": 3,
                        "reason": "synthetic_grading_mark",
                        "rectangles": [
                            {"left": 0.8, "top": 0.0, "right": 1.0, "bottom": 0.1}
                        ],
                    }
                ],
            },
            {
                "anonymous_id": "S002",
                "source_pages": [2],
                "page_masks": [],
            },
        ],
        "excluded_pages": [
            {
                "source_page": 4,
                "reason": "synthetic_blank_separator",
            }
        ],
    }


def _write_review(
    path: Path, pairs: set[tuple[str, int]], layout: dict[str, object]
) -> None:
    outputs = expected_review_outputs(layout)
    rows = []
    for anonymous_id, source_page in sorted(pairs):
        row = {column: "" for column in ANONYMIZATION_REVIEW_COLUMNS}
        row.update(
            {
                "anonymous_id": anonymous_id,
                "source_page": str(source_page),
                "render_spec_sha256": RENDER_SPEC_SHA256,
                "artifact_manifest_sha256": ARTIFACT_MANIFEST_SHA256,
                "output_image": outputs[(anonymous_id, source_page)][0],
                "output_pdf": outputs[(anonymous_id, source_page)][1],
                "privacy_review_status": "approved",
                "privacy_reviewer": "reviewer",
                "privacy_reviewed_at": "2026-08-02T00:00:00Z",
                "blindness_review_status": "approved",
                "blindness_reviewer": "reviewer",
                "blindness_reviewed_at": "2026-08-02T00:00:00Z",
                "answer_content_status": "approved",
                "answer_content_reviewer": "reviewer",
                "answer_content_reviewed_at": "2026-08-02T00:00:00Z",
            }
        )
        rows.append(row)
    _write_rows(path, rows)


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANONYMIZATION_REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
