import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.anonymization import ANONYMIZATION_REVIEW_COLUMNS, sha256_file, write_json
from benchmark.core.submission_scope_workflow import (
    SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SubmissionScopeError,
    apply_submission_scope_decisions,
    build_anonymous_submission_image_snapshot,
    initialize_submission_scope_resolution,
    validate_submission_scope_resolution,
)


class SubmissionScopeWorkflowTests(unittest.TestCase):
    def test_human_resolution_can_exclude_duplicate_and_preserve_missing_question_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_approved_artifact(Path(tmp))
            template = paths["private_root"] / "scope-template.json"
            initialize_submission_scope_resolution(**_common(paths), resolution_path=template)
            draft = json.loads(template.read_text(encoding="utf-8"))
            automatic = {item["anonymous_id"]: item for item in draft["submissions"]}
            self.assertEqual(automatic["S001"]["scope_status"], "automatic_include_all")
            self.assertEqual(automatic["S002"]["scope_status"], "pending_human_resolution")

            decisions = paths["private_root"] / "scope-decisions.json"
            write_json(
                decisions,
                {
                    "schema_version": 1,
                    "record_type": "private_anonymous_submission_scope_decisions",
                    "template_resolution_sha256": sha256_file(template),
                    "decisions": [
                        {
                            "anonymous_id": "S002",
                            "included_source_pages": [1, 2, 3, 4],
                            "missing_question_ids": ["Q3"],
                            "reviewer": "course_owner",
                            "reviewed_at": "2026-08-08T10:00:00Z",
                            "notes": "duplicate final page excluded; Q3 source page is absent",
                        }
                    ],
                },
            )
            resolution = paths["private_root"] / "scope-resolution.json"
            result = apply_submission_scope_decisions(
                **_common(paths),
                template_resolution_path=template,
                decisions_path=decisions,
                resolved_resolution_path=resolution,
            )
            self.assertEqual(result["status"], "resolved")
            readiness = validate_submission_scope_resolution(
                **_common(paths), resolution_path=resolution
            )
            self.assertEqual(readiness["status"], "ready_scope_only")
            self.assertFalse(readiness["model_run_allowed"])

            output = paths["private_root"] / "snapshot"
            snapshot = build_anonymous_submission_image_snapshot(
                **_common(paths),
                resolution_path=resolution,
                scope_id="all-questions",
                output_root=output,
            )
            self.assertEqual(snapshot["status"], "built")
            manifest = json.loads(
                (output / SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["grading_unit"], "anonymous_submission")
            by_student = {item["anonymous_id"]: item for item in manifest["submissions"]}
            self.assertEqual(len(by_student["S001"]["images"]), 4)
            self.assertEqual(len(by_student["S002"]["images"]), 4)
            self.assertEqual(by_student["S002"]["missing_question_ids"], ["Q3"])
            self.assertFalse(manifest["model_run_allowed"])

    def test_refuses_out_of_order_human_page_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_approved_artifact(Path(tmp))
            template = paths["private_root"] / "scope-template.json"
            initialize_submission_scope_resolution(**_common(paths), resolution_path=template)
            decisions = paths["private_root"] / "scope-decisions.json"
            write_json(
                decisions,
                {
                    "schema_version": 1,
                    "record_type": "private_anonymous_submission_scope_decisions",
                    "template_resolution_sha256": sha256_file(template),
                    "decisions": [
                        {
                            "anonymous_id": "S002",
                            "included_source_pages": [2, 1, 3, 4, 5],
                            "missing_question_ids": [],
                            "reviewer": "course_owner",
                            "reviewed_at": "2026-08-08T10:00:00Z",
                            "notes": "reviewed",
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(SubmissionScopeError, "preserve approved rendered-page order"):
                apply_submission_scope_decisions(
                    **_common(paths),
                    template_resolution_path=template,
                    decisions_path=decisions,
                    resolved_resolution_path=paths["private_root"] / "scope-resolution.json",
                )


def _common(paths: dict[str, Path]) -> dict[str, object]:
    return {
        "artifact_root": paths["artifact_root"],
        "final_review_path": paths["review_path"],
        "final_review_validation_path": paths["validation_path"],
        "private_assembly_manifest_path": paths["assembly_path"],
        "expected_pages_per_submission": 4,
    }


def _make_approved_artifact(root: Path) -> dict[str, Path]:
    private_root = root / "Data" / "synthetic"
    artifact_root = private_root / "anonymized"
    manifest_root = artifact_root / "manifest"
    rows: list[dict[str, str]] = []
    groups = []
    for anonymous_id, page_count in (("S001", 4), ("S002", 5)):
        source_pages = list(range(1, page_count + 1))
        groups.append(
            {
                "anonymous_id": anonymous_id,
                "status": "converted_pending_page_review",
                "rendered_page_count": page_count,
            }
        )
        for source_page in source_pages:
            image = artifact_root / "anonymized_pages" / anonymous_id / f"{anonymous_id}-p{source_page:02d}.png"
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(f"image:{anonymous_id}:{source_page}".encode("ascii"))
            rows.append(
                {
                    "anonymous_id": anonymous_id,
                    "source_page": str(source_page),
                    "output_image": image.relative_to(artifact_root).as_posix(),
                    "output_pdf": f"anonymized_pdfs/{anonymous_id}.pdf",
                }
            )
        pdf = artifact_root / "anonymized_pdfs" / f"{anonymous_id}.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(f"pdf:{anonymous_id}".encode("ascii"))

    render_hash = "a" * 64
    artifact_paths = sorted([row["output_image"] for row in rows] + list({row["output_pdf"] for row in rows}))
    artifact_manifest = {
        "schema_version": 1,
        "record_type": "anonymized_assessment_output_artifacts",
        "render_spec_sha256": render_hash,
        "artifacts": [
            {
                "path": relative,
                "sha256": sha256_file(artifact_root / relative),
                "bytes": (artifact_root / relative).stat().st_size,
            }
            for relative in artifact_paths
        ],
    }
    artifact_manifest_path = manifest_root / "output-artifacts.json"
    write_json(artifact_manifest_path, artifact_manifest)
    artifact_manifest_hash = sha256_file(artifact_manifest_path)
    review_path = manifest_root / "anonymization_review.csv"
    with review_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANONYMIZATION_REVIEW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "render_spec_sha256": render_hash,
                    "artifact_manifest_sha256": artifact_manifest_hash,
                    **row,
                    "identity_redaction_rectangles": "[]",
                    "grading_mark_mask_rectangles": "[]",
                    "privacy_review_status": "approved",
                    "privacy_reviewer": "reviewer",
                    "privacy_reviewed_at": "2026-08-08T00:00:00Z",
                    "privacy_notes": "approved",
                    "blindness_review_status": "approved",
                    "blindness_reviewer": "reviewer",
                    "blindness_reviewed_at": "2026-08-08T00:00:00Z",
                    "blindness_notes": "approved",
                    "answer_content_status": "approved",
                    "answer_content_reviewer": "reviewer",
                    "answer_content_reviewed_at": "2026-08-08T00:00:00Z",
                    "answer_content_notes": "approved",
                }
            )
    write_json(
        manifest_root / "prep-metadata.json",
        {
            "schema_version": 2,
            "record_type": "anonymized_assessment_preparation",
            "assessment_id": "synthetic_variable_scope",
            "review_path": "manifest/anonymization_review.csv",
            "artifact_manifest_path": "manifest/output-artifacts.json",
            "artifact_manifest_sha256": artifact_manifest_hash,
            "render_spec_sha256": render_hash,
        },
    )
    validation_path = manifest_root / "final-review-validation.json"
    write_json(
        validation_path,
        {
            "schema_version": 1,
            "report_type": "anonymization_review_readiness",
            "status": "ready",
            "failed_checks": [],
            "expected_page_count": len(rows),
            "review_row_count": len(rows),
            "checks": [
                {"id": check, "status": "passed", "detail": "synthetic"}
                for check in (
                    "required_columns_present",
                    "review_pairs_match_layout",
                    "review_output_paths_match_layout",
                    "review_render_spec_matches_preparation",
                    "review_artifact_manifest_matches_preparation",
                    "review_status_values_valid",
                    "privacy_review_approved",
                    "blindness_review_approved",
                    "answer_content_review_approved",
                    "approved_reviews_have_audit_trail",
                    "layout_hash_matches_preparation",
                    "review_path_matches_preparation_metadata",
                    "render_spec_matches_preparation",
                    "artifact_manifest_hash_matches_preparation",
                    "artifact_manifest_covers_expected_outputs",
                    "prepared_output_tree_matches_expected_paths",
                    "prepared_output_hashes_match",
                )
            ],
        },
    )
    assembly_path = private_root / "assembly.json"
    write_json(
        assembly_path,
        {"record_type": "private_mixed_submission_assembly", "groups": groups},
    )
    return {
        "private_root": private_root,
        "artifact_root": artifact_root,
        "review_path": review_path,
        "validation_path": validation_path,
        "assembly_path": assembly_path,
    }


if __name__ == "__main__":
    unittest.main()
