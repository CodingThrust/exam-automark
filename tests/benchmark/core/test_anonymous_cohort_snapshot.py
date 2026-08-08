import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.anonymization import sha256_file, write_json
from benchmark.core.anonymous_cohort_snapshot import (
    COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    create_assessment_identity_alignment,
    merge_anonymous_submission_image_snapshots,
)
from benchmark.core.submission_scope_workflow import (
    SUBMISSION_SCOPE_SCHEMA_VERSION,
    SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SUBMISSION_SNAPSHOT_RECORD_TYPE,
    SubmissionScopeError,
)


class AnonymousCohortSnapshotTests(unittest.TestCase):
    def test_merges_distinct_final_submission_snapshots_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            first = _make_submission_snapshot(
                private_root / "first",
                scope_id="base-v1",
                submissions={"S001": [1, 2, 3, 4], "S002": [1, 2, 3]},
            )
            second = _make_submission_snapshot(
                private_root / "second",
                scope_id="docx-v1",
                submissions={"S003": [1, 2, 3, 4]},
            )
            output = private_root / "cohort"

            result = merge_anonymous_submission_image_snapshots(
                snapshot_roots=[first, second], cohort_id="all-submissions-v1", output_root=output
            )
            self.assertEqual(result["status"], "built")
            self.assertEqual(result["student_count"], 3)
            self.assertEqual(result["image_count"], 11)
            self.assertEqual(result["source_snapshot_count"], 2)
            self.assertFalse(result["model_run_allowed"])

            manifest = json.loads(
                (output / COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["grading_unit"], "anonymous_submission")
            self.assertEqual([item["anonymous_id"] for item in manifest["submissions"]], ["S001", "S002", "S003"])
            s002 = next(item for item in manifest["submissions"] if item["anonymous_id"] == "S002")
            self.assertEqual([image["source_page"] for image in s002["images"]], [1, 2, 3])
            self.assertEqual({image["source_snapshot_scope_id"] for image in s002["images"]}, {"base-v1"})
            self.assertTrue(
                (output / "anonymized_pages" / "S003" / "S003-p04.png").is_file()
            )

            again = merge_anonymous_submission_image_snapshots(
                snapshot_roots=[first, second], cohort_id="all-submissions-v1", output_root=output
            )
            self.assertEqual(again["status"], "already_built")

    def test_rejects_duplicate_anonymous_submission_across_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            first = _make_submission_snapshot(
                private_root / "first", scope_id="base-v1", submissions={"S001": [1, 2, 3, 4]}
            )
            second = _make_submission_snapshot(
                private_root / "second", scope_id="supplement-v1", submissions={"S001": [1, 2, 3, 4]}
            )
            with self.assertRaisesRegex(SubmissionScopeError, "duplicate anonymous_id"):
                merge_anonymous_submission_image_snapshots(
                    snapshot_roots=[first, second],
                    cohort_id="all-submissions-v1",
                    output_root=private_root / "cohort",
                )

    def test_rejects_duplicate_source_scope_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            first = _make_submission_snapshot(
                private_root / "first", scope_id="base-v1", submissions={"S001": [1, 2, 3, 4]}
            )
            second = _make_submission_snapshot(
                private_root / "second", scope_id="base-v1", submissions={"S002": [1, 2, 3, 4]}
            )
            with self.assertRaisesRegex(SubmissionScopeError, "duplicate scope_id"):
                merge_anonymous_submission_image_snapshots(
                    snapshot_roots=[first, second],
                    cohort_id="all-submissions-v1",
                    output_root=private_root / "cohort",
                )

    def test_rejects_sources_from_different_assessments(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            first = _make_submission_snapshot(
                private_root / "first",
                scope_id="base-v1",
                submissions={"S001": [1, 2, 3, 4]},
            )
            second = _make_submission_snapshot(
                private_root / "second",
                scope_id="supplement-v1",
                submissions={"S002": [1, 2, 3, 4]},
                assessment_id="different_quiz",
            )
            with self.assertRaisesRegex(SubmissionScopeError, "same assessment_id"):
                merge_anonymous_submission_image_snapshots(
                    snapshot_roots=[first, second],
                    cohort_id="all-submissions-v1",
                    output_root=private_root / "cohort",
                )

    def test_hash_bound_alignment_allows_confirmed_assessment_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            first = _make_submission_snapshot(
                private_root / "first",
                scope_id="base-v1",
                submissions={"S001": [1, 2, 3, 4]},
            )
            second = _make_submission_snapshot(
                private_root / "second",
                scope_id="supplement-v1",
                submissions={"S002": [1, 2, 3, 4]},
                assessment_id="supplement_label",
            )
            alignment = private_root / "alignment" / "decision.json"
            created = create_assessment_identity_alignment(
                snapshot_roots=[first, second],
                canonical_snapshot_root=first,
                reviewer="course_owner",
                reviewed_at="2026-08-08T12:00:00Z",
                reason="Course owner confirmed that both sources are Quiz 1.",
                output_path=alignment,
            )
            self.assertEqual(created["status"], "created")
            result = merge_anonymous_submission_image_snapshots(
                snapshot_roots=[first, second],
                cohort_id="all-submissions-v1",
                output_root=private_root / "cohort",
                assessment_alignment_path=alignment,
            )
            self.assertEqual(result["status"], "built")
            manifest = json.loads(
                (private_root / "cohort" / COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["assessment_id"], "synthetic_quiz")
            self.assertIn("assessment_identity_alignment", manifest)

    def test_alignment_rejects_a_source_manifest_changed_after_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            first = _make_submission_snapshot(
                private_root / "first",
                scope_id="base-v1",
                submissions={"S001": [1, 2, 3, 4]},
            )
            second = _make_submission_snapshot(
                private_root / "second",
                scope_id="supplement-v1",
                submissions={"S002": [1, 2, 3, 4]},
                assessment_id="supplement_label",
            )
            alignment = private_root / "alignment" / "decision.json"
            create_assessment_identity_alignment(
                snapshot_roots=[first, second],
                canonical_snapshot_root=first,
                reviewer="course_owner",
                reviewed_at="2026-08-08T12:00:00Z",
                reason="Course owner confirmed that both sources are Quiz 1.",
                output_path=alignment,
            )
            manifest_path = second / SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH
            changed = json.loads(manifest_path.read_text(encoding="utf-8"))
            changed["source_provenance"] = {"fixture": "changed-after-confirmation"}
            write_json(manifest_path, changed)
            with self.assertRaisesRegex(SubmissionScopeError, "does not bind exactly"):
                merge_anonymous_submission_image_snapshots(
                    snapshot_roots=[first, second],
                    cohort_id="all-submissions-v1",
                    output_root=private_root / "cohort",
                    assessment_alignment_path=alignment,
                )

    def test_rejects_tampered_source_image_before_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            source = _make_submission_snapshot(
                private_root / "source", scope_id="base-v1", submissions={"S001": [1, 2, 3, 4]}
            )
            image = source / "anonymized_pages" / "S001" / "S001-p02.png"
            image.write_bytes(b"tampered")
            with self.assertRaisesRegex(SubmissionScopeError, "does not match its manifest"):
                merge_anonymous_submission_image_snapshots(
                    snapshot_roots=[source],
                    cohort_id="all-submissions-v1",
                    output_root=private_root / "cohort",
                )


def _make_submission_snapshot(
    root: Path,
    *,
    scope_id: str,
    submissions: dict[str, list[int]],
    assessment_id: str = "synthetic_quiz",
) -> Path:
    records = []
    for anonymous_id, source_pages in submissions.items():
        images = []
        for source_page in source_pages:
            relative = f"anonymized_pages/{anonymous_id}/{anonymous_id}-p{source_page:02d}.png"
            image = root / relative
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(f"synthetic:{scope_id}:{anonymous_id}:{source_page}".encode("ascii"))
            images.append(
                {
                    "source_page": source_page,
                    "source_image": relative,
                    "snapshot_image": relative,
                    "sha256": sha256_file(image),
                    "bytes": image.stat().st_size,
                }
            )
        records.append(
            {
                "anonymous_id": anonymous_id,
                "grading_unit": "anonymous_submission",
                "missing_question_ids": [],
                "images": images,
            }
        )
    manifest = {
        "schema_version": SUBMISSION_SCOPE_SCHEMA_VERSION,
        "record_type": SUBMISSION_SNAPSHOT_RECORD_TYPE,
        "assessment_id": assessment_id,
        "scope_id": scope_id,
        "grading_unit": "anonymous_submission",
        "source_provenance": {"fixture": scope_id},
        "student_count": len(records),
        "image_count": sum(len(record["images"]) for record in records),
        "submissions": records,
        "model_run_allowed": False,
        "model_run_blockers": ["fixture only"],
    }
    write_json(root / SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH, manifest)
    return root


if __name__ == "__main__":
    unittest.main()
