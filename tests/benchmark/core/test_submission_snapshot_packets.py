import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.anonymization import sha256_file, write_json
from benchmark.core.anonymous_cohort_snapshot import (
    COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    COHORT_SNAPSHOT_RECORD_TYPE,
)
from benchmark.core.packets import audit_prompt_packet
from benchmark.core.cli import main
from benchmark.core.schema import CourseSpec
from benchmark.core.submission_snapshot_packets import (
    SubmissionSnapshotPacketSpec,
    build_submission_snapshot_packet,
)
from benchmark.core.submission_snapshot_routes import (
    MatchedImageRouteSpec,
    build_matched_image_route_packets,
)


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class SubmissionSnapshotPacketTests(unittest.TestCase):
    def _course(self) -> CourseSpec:
        return CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")

    def test_builds_matched_whole_submission_packets_from_cohort_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            snapshot = _write_cohort_snapshot(
                private_root / "cohort",
                {
                    "S001": [1, 3],
                    "S002": [2],
                },
            )
            course = self._course()
            output_root = private_root / "packets"

            transcription = build_submission_snapshot_packet(
                SubmissionSnapshotPacketSpec(
                    course=course,
                    packet_id="T1-dev-r1",
                    condition="T1",
                    task="transcribe",
                    prompt_text="Transcribe only visible work.",
                    student_ids=("S001", "S002"),
                    snapshot_root=snapshot,
                    output_root=output_root,
                    metadata={"split": "development"},
                )
            )
            direct = build_submission_snapshot_packet(
                SubmissionSnapshotPacketSpec(
                    course=course,
                    packet_id="M1-dev-r1",
                    condition="M1",
                    task="grade",
                    prompt_text="Grade visible evidence only.",
                    student_ids=("S001", "S002"),
                    snapshot_root=snapshot,
                    output_root=output_root,
                    rubric={"rubric_version": "synthetic_v1", "questions": []},
                    metadata={"split": "development"},
                )
            )

            transcript_manifest = json.loads(
                (transcription.packet_path / "manifest.json").read_text(encoding="utf-8")
            )
            direct_manifest = json.loads(
                (direct.packet_path / "manifest.json").read_text(encoding="utf-8")
            )
            submission = json.loads(
                (transcription.packet_path / "inputs" / "S001" / "submission.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                [page["source_page"] for page in submission["pages"]], [1, 3]
            )
            self.assertEqual(
                [page["file"] for page in submission["pages"]],
                ["pages/p0001.png", "pages/p0003.png"],
            )
            self.assertEqual(submission["grading_unit"], "anonymous_submission")
            self.assertEqual(
                transcript_manifest["input_hashes"], direct_manifest["input_hashes"]
            )
            self.assertEqual(
                transcript_manifest["metadata"]["input_mode"],
                "anonymous_submission_snapshot",
            )
            self.assertEqual(
                transcript_manifest["metadata"]["snapshot_record_type"],
                COHORT_SNAPSHOT_RECORD_TYPE,
            )
            self.assertEqual(audit_prompt_packet(transcription.packet_path), [])
            self.assertEqual(audit_prompt_packet(direct.packet_path), [])

    def test_rejects_tampered_snapshot_before_writing_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            snapshot = _write_cohort_snapshot(private_root / "cohort", {"S001": [1]})
            image = snapshot / "anonymized_pages" / "S001" / "S001-p01.png"
            image.write_bytes(b"changed")

            with self.assertRaisesRegex(ValueError, "does not match its manifest"):
                build_submission_snapshot_packet(
                    SubmissionSnapshotPacketSpec(
                        course=self._course(),
                        packet_id="T1-dev-r1",
                        condition="T1",
                        task="transcribe",
                        prompt_text="Transcribe only visible work.",
                        student_ids=("S001",),
                        snapshot_root=snapshot,
                        output_root=private_root / "packets",
                    )
                )
            self.assertFalse((private_root / "packets" / "T1-dev-r1").exists())

    def test_rejects_unfrozen_or_overlapping_snapshot_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            snapshot = _write_cohort_snapshot(private_root / "cohort", {"S001": [1]})
            manifest_path = snapshot / COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["model_run_allowed"] = True
            write_json(manifest_path, manifest)

            with self.assertRaisesRegex(ValueError, "model-blocked"):
                build_submission_snapshot_packet(
                    SubmissionSnapshotPacketSpec(
                        course=self._course(),
                        packet_id="T1-dev-r1",
                        condition="T1",
                        task="transcribe",
                        prompt_text="Transcribe only visible work.",
                        student_ids=("S001",),
                        snapshot_root=snapshot,
                        output_root=private_root / "packets",
                    )
                )
            manifest["model_run_allowed"] = False
            write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "must not overlap"):
                build_submission_snapshot_packet(
                    SubmissionSnapshotPacketSpec(
                        course=self._course(),
                        packet_id="T1-dev-r1",
                        condition="T1",
                        task="transcribe",
                        prompt_text="Transcribe only visible work.",
                        student_ids=("S001",),
                        snapshot_root=snapshot,
                        output_root=snapshot / "packets",
                    )
                )

    def test_builds_and_checks_matched_m1_t1_route_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            snapshot = _write_cohort_snapshot(
                private_root / "cohort", {"S001": [1, 2]}
            )
            result = build_matched_image_route_packets(
                MatchedImageRouteSpec(
                    course=self._course(),
                    snapshot_root=snapshot,
                    output_root=private_root / "packets",
                    split="development",
                    student_ids=("S001",),
                    m1_packet_id="M1-dev-r1",
                    t1_packet_id="T1-dev-r1",
                    grade_prompt_text="Grade visible evidence only.",
                    transcribe_prompt_text="Transcribe visible work only.",
                    rubric={"rubric_version": "synthetic_v1", "questions": []},
                    metadata={"skill_version_id": "synthetic_candidate"},
                )
            )

            m1_packet = private_root / "packets" / "M1-dev-r1"
            t1_packet = private_root / "packets" / "T1-dev-r1"
            self.assertTrue(m1_packet.is_dir())
            self.assertTrue(t1_packet.is_dir())

        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["model_run_allowed"])
        self.assertEqual(result["lineage"]["status"], "ready")

    def test_snapshot_derived_t1_dry_run_binds_its_manifest_hash_in_run_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_root = Path(tmp) / "Data" / "synthetic"
            snapshot = _write_cohort_snapshot(
                private_root / "cohort", {"S001": [1]}
            )
            build_matched_image_route_packets(
                MatchedImageRouteSpec(
                    course=self._course(),
                    snapshot_root=snapshot,
                    output_root=private_root / "packets",
                    split="development",
                    student_ids=("S001",),
                    m1_packet_id="M1-dev-r1",
                    t1_packet_id="T1-dev-r1",
                    grade_prompt_text="Grade visible evidence only.",
                    transcribe_prompt_text="Transcribe visible work only.",
                    rubric={"rubric_version": "synthetic_v1", "questions": []},
                )
            )
            t1_packet = private_root / "packets" / "T1-dev-r1"
            expected_snapshot_hash = json.loads(
                (t1_packet / "manifest.json").read_text(encoding="utf-8")
            )["metadata"]["input_snapshot_manifest_sha256"]
            output = private_root / "runs" / "T1-dev-r1"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "run-model-packet",
                        "--provider",
                        "kimi",
                        "--model",
                        "kimi-test",
                        "--input-mode",
                        "multimodal",
                        "--packet",
                        str(t1_packet),
                        "--output",
                        str(output),
                        "--dry-run",
                    ]
                )
            run_metadata = json.loads(
                (output / "run-metadata.json").read_text(encoding="utf-8")
            )
            transcript = json.loads(
                (output / "outputs" / "S001.json").read_text(encoding="utf-8")
            )

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["validation_status"], "passed")
        self.assertEqual(run_metadata["task"], "transcribe")
        self.assertEqual(run_metadata["data_snapshot_hash"], expected_snapshot_hash)
        self.assertIn("answers", transcript)


def _write_cohort_snapshot(root: Path, submissions: dict[str, list[int]]) -> Path:
    records = []
    for anonymous_id, source_pages in submissions.items():
        images = []
        for source_page in source_pages:
            relative = f"anonymized_pages/{anonymous_id}/{anonymous_id}-p{source_page:02d}.png"
            image = root / relative
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(
                f"synthetic anonymous page {anonymous_id} {source_page}".encode("ascii")
            )
            images.append(
                {
                    "source_page": source_page,
                    "snapshot_image": relative,
                    "sha256": sha256_file(image),
                    "bytes": image.stat().st_size,
                    "source_snapshot_scope_id": "scope-v1",
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
        "schema_version": 1,
        "record_type": COHORT_SNAPSHOT_RECORD_TYPE,
        "assessment_id": "hw1",
        "cohort_id": "all-v1",
        "grading_unit": "anonymous_submission",
        "source_snapshots": [
            {
                "scope_id": "scope-v1",
                "manifest_sha256": "a" * 64,
                "student_count": len(records),
                "image_count": sum(len(record["images"]) for record in records),
            }
        ],
        "student_count": len(records),
        "image_count": sum(len(record["images"]) for record in records),
        "submissions": records,
        "model_run_allowed": False,
    }
    write_json(root / COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH, manifest)
    return root


if __name__ == "__main__":
    unittest.main()
