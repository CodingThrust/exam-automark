import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.anonymization import (
    ANONYMIZATION_REVIEW_COLUMNS,
    sha256_file,
    write_json,
)
from benchmark.core.scoped_anonymous_images import (
    SNAPSHOT_MANIFEST_RELATIVE_PATH,
    ScopedSnapshotError,
    build_scoped_anonymous_image_snapshot,
)


class ScopedAnonymousImageSnapshotTests(unittest.TestCase):
    def test_builds_selected_approved_images_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _make_approved_artifact(root)
            target = root / "private" / "artifacts" / "scoped" / "mcq-q9-q10"

            result = _build(paths, target)

            self.assertEqual(result["status"], "built")
            self.assertFalse(result["model_run_allowed"])
            self.assertEqual(result["student_count"], 2)
            self.assertEqual(result["image_count"], 4)
            self.assertEqual(
                _tree_files(target),
                {
                    "anonymized_pages/S001/S001-p01.png",
                    "anonymized_pages/S001/S001-p03.png",
                    "anonymized_pages/S002/S002-p01.png",
                    "anonymized_pages/S002/S002-p03.png",
                    SNAPSHOT_MANIFEST_RELATIVE_PATH.as_posix(),
                },
            )
            manifest = json.loads(
                (target / SNAPSHOT_MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["scope"]["page_suffixes"], ["p01", "p03"])
            self.assertEqual(manifest["image_count"], 4)
            for image in manifest["images"]:
                copied = target / image["snapshot_image"]
                original = paths["artifact_root"] / image["source_image"]
                self.assertEqual(sha256_file(copied), sha256_file(original))
                self.assertEqual(image["sha256"], sha256_file(copied))

            again = _build(paths, target)
            self.assertEqual(again["status"], "already_built")

    def test_refuses_missing_final_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _make_approved_artifact(root, pending_status=True)

            with self.assertRaisesRegex(ScopedSnapshotError, "not approved"):
                _build(paths, root / "private" / "artifacts" / "scoped")

    def test_refuses_incomplete_selected_suffix_for_any_student(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _make_approved_artifact(root, missing_suffix_for="S002")

            with self.assertRaisesRegex(ScopedSnapshotError, "incomplete for S002"):
                _build(paths, root / "private" / "artifacts" / "scoped")

    def test_refuses_unexpected_source_file_even_when_report_claims_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _make_approved_artifact(root)
            (paths["artifact_root"] / "anonymized_pages" / "S001" / "notes.txt").write_text(
                "unexpected", encoding="utf-8"
            )

            with self.assertRaisesRegex(ScopedSnapshotError, "unexpected file type/page"):
                _build(paths, root / "private" / "artifacts" / "scoped")

    def test_refuses_existing_divergent_target_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _make_approved_artifact(root)
            target = root / "private" / "artifacts" / "scoped"
            _build(paths, target)
            selected = target / "anonymized_pages" / "S001" / "S001-p01.png"
            selected.write_bytes(b"tampered output")

            with self.assertRaisesRegex(ScopedSnapshotError, "changed scoped image"):
                _build(paths, target)
            self.assertEqual(selected.read_bytes(), b"tampered output")

    def test_records_ready_cohort_preflight_in_snapshot_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _make_approved_artifact(root)
            preflight = _write_ready_cohort_preflight(paths)
            target = root / "private" / "artifacts" / "scoped"

            _build(paths, target, cohort_preflight_path=preflight)
            manifest = json.loads(
                (target / SNAPSHOT_MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8")
            )
            preflight_sha256 = sha256_file(preflight)

        self.assertEqual(
            manifest["source_provenance"]["cohort_preflight_sha256"],
            preflight_sha256,
        )

    def test_refuses_nonready_cohort_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _make_approved_artifact(root)
            preflight = _write_ready_cohort_preflight(paths)
            payload = json.loads(preflight.read_text(encoding="utf-8"))
            payload["status"] = "not_ready"
            preflight.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ScopedSnapshotError, "preflight report is not ready"):
                _build(
                    paths,
                    root / "private" / "artifacts" / "scoped",
                    cohort_preflight_path=preflight,
                )


def _build(
    paths: dict[str, Path],
    target: Path,
    *,
    cohort_preflight_path: Path | None = None,
) -> dict[str, object]:
    return build_scoped_anonymous_image_snapshot(
        artifact_root=paths["artifact_root"],
        final_review_path=paths["review_path"],
        final_review_validation_path=paths["validation_path"],
        page_suffixes=("p03", "p01"),
        scope_id="mcq-q9-q10",
        output_root=target,
        cohort_preflight_path=cohort_preflight_path,
    )


def _make_approved_artifact(
    root: Path,
    *,
    pending_status: bool = False,
    missing_suffix_for: str | None = None,
) -> dict[str, Path]:
    artifact_root = root / "private" / "artifacts" / "v1"
    manifest_root = artifact_root / "manifest"
    rows: list[dict[str, str]] = []
    for anonymous_id in ("S001", "S002"):
        suffixes = ("p01", "p02") if anonymous_id == missing_suffix_for else ("p01", "p02", "p03")
        for local_index, suffix in enumerate(suffixes, start=1):
            image = artifact_root / "anonymized_pages" / anonymous_id / f"{anonymous_id}-{suffix}.png"
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(f"image:{anonymous_id}:{suffix}".encode("ascii"))
            rows.append(
                {
                    "anonymous_id": anonymous_id,
                    "source_page": str(local_index),
                    "output_image": image.relative_to(artifact_root).as_posix(),
                    "output_pdf": f"anonymized_pdfs/{anonymous_id}.pdf",
                }
            )
        pdf = artifact_root / "anonymized_pdfs" / f"{anonymous_id}.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(f"pdf:{anonymous_id}".encode("ascii"))

    render_spec_sha256 = "a" * 64
    artifact_paths = sorted(
        [row["output_image"] for row in rows]
        + sorted({row["output_pdf"] for row in rows})
    )
    artifact_manifest = {
        "schema_version": 1,
        "record_type": "anonymized_assessment_output_artifacts",
        "render_spec_sha256": render_spec_sha256,
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
    artifact_manifest_sha256 = sha256_file(artifact_manifest_path)

    review_path = manifest_root / "anonymization_review.csv"
    with review_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANONYMIZATION_REVIEW_COLUMNS)
        writer.writeheader()
        for index, row in enumerate(rows):
            status = "pending" if pending_status and index == 0 else "approved"
            writer.writerow(
                {
                    "render_spec_sha256": render_spec_sha256,
                    "artifact_manifest_sha256": artifact_manifest_sha256,
                    "anonymous_id": row["anonymous_id"],
                    "source_page": row["source_page"],
                    "output_image": row["output_image"],
                    "output_pdf": row["output_pdf"],
                    "identity_redaction_rectangles": "[]",
                    "grading_mark_mask_rectangles": "[]",
                    "privacy_review_status": status,
                    "privacy_reviewer": "reviewer" if status == "approved" else "",
                    "privacy_reviewed_at": "2026-08-03T00:00:00Z" if status == "approved" else "",
                    "privacy_notes": "approved",
                    "blindness_review_status": "approved",
                    "blindness_reviewer": "reviewer",
                    "blindness_reviewed_at": "2026-08-03T00:00:00Z",
                    "blindness_notes": "approved",
                    "answer_content_status": "approved",
                    "answer_content_reviewer": "reviewer",
                    "answer_content_reviewed_at": "2026-08-03T00:00:00Z",
                    "answer_content_notes": "approved",
                }
            )

    write_json(
        manifest_root / "prep-metadata.json",
        {
            "schema_version": 2,
            "record_type": "anonymized_assessment_preparation",
            "assessment_id": "synthetic_scope",
            "review_path": "manifest/anonymization_review.csv",
            "artifact_manifest_path": "manifest/output-artifacts.json",
            "artifact_manifest_sha256": artifact_manifest_sha256,
            "render_spec_sha256": render_spec_sha256,
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
                {"id": check_id, "status": "passed", "detail": "synthetic"}
                for check_id in sorted(
                    {
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
                    }
                )
            ],
        },
    )
    return {
        "artifact_root": artifact_root,
        "review_path": review_path,
        "validation_path": validation_path,
    }


def _write_ready_cohort_preflight(paths: dict[str, Path]) -> Path:
    metadata_path = paths["artifact_root"] / "manifest" / "prep-metadata.json"
    preflight = paths["artifact_root"].parent / "cohort-preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record_type": "private_anonymous_cohort_preflight",
                "status": "ready",
                "failed_checks": [],
                "assessment_id": "synthetic_scope",
                "model_run_allowed": False,
                "bindings": {
                    "preparation_metadata_sha256": sha256_file(metadata_path),
                    "final_review_validation_sha256": sha256_file(paths["validation_path"]),
                },
            }
        ),
        encoding="utf-8",
    )
    return preflight


def _tree_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


if __name__ == "__main__":
    unittest.main()
