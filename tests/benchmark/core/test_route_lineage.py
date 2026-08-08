import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.packets import (
    PromptPacketSpec,
    TextGradingPacketSpec,
    build_prompt_packet,
    build_text_grading_packet,
    directory_digest,
)
from benchmark.core.route_lineage import check_m1_t1_g1_lineage
from benchmark.core.schema import CourseSpec


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class RouteLineageTests(unittest.TestCase):
    def _course(self) -> CourseSpec:
        return CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")

    def test_image_pair_is_ready_when_m1_and_t1_bind_same_snapshot_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m1, t1 = self._build_image_pair(root)

            report = check_m1_t1_g1_lineage(
                m1_packet=m1.packet_path,
                t1_packet=t1.packet_path,
            )

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["stage"], "image_packets")
        self.assertFalse(report["model_run_allowed"])
        self.assertEqual(report["student_count"], 1)

    def test_image_pair_rejects_different_anonymous_input_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m1, _ = self._build_image_pair(root)
            changed_input = root / "changed-input"
            changed_student = changed_input / "S001"
            changed_student.mkdir(parents=True)
            (changed_student / "page-0001.png").write_bytes(b"different")
            t1 = build_prompt_packet(
                PromptPacketSpec(
                    course=self._course(),
                    packet_id="T1-dev-r2",
                    condition="T1",
                    task="transcribe",
                    prompt_text="Transcribe visible work only.",
                    student_ids=("S001",),
                    input_root=changed_input,
                    output_root=root / "packets",
                    metadata=_snapshot_metadata(),
                )
            )

            report = check_m1_t1_g1_lineage(
                m1_packet=m1.packet_path,
                t1_packet=t1.packet_path,
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("m1_t1_input_hashes_match", report["failed_checks"])

    def test_full_route_hash_binds_g1_transcripts_to_t1_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m1, t1 = self._build_image_pair(root)
            run = root / "runs" / "t1-dev-r1"
            outputs = run / "outputs"
            outputs.mkdir(parents=True)
            transcript = {
                "student_id": "S001",
                "answers": [
                    {"question_id": "Q1", "text": "x", "unclear": False},
                    {"question_id": "Q2a", "text": "y", "unclear": False},
                    {"question_id": "Q2b", "text": "z", "unclear": False},
                ],
            }
            (outputs / "S001.json").write_text(
                json.dumps(transcript, sort_keys=True), encoding="utf-8"
            )
            (run / "run-metadata.json").write_text(
                json.dumps(
                    {
                        "packet_hash": directory_digest(t1.packet_path),
                        "task": "transcribe",
                        "condition": "T1",
                        "validation_status": "passed",
                        "course_id": "dsaa3073",
                        "assessment_id": "hw1",
                        "data_snapshot_hash": "a" * 64,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            g1 = build_text_grading_packet(
                TextGradingPacketSpec(
                    course=self._course(),
                    packet_id="G1-dev-r1",
                    condition="G1",
                    prompt_text="Grade transcript evidence only.",
                    student_ids=("S001",),
                    transcript_source=outputs,
                    output_root=root / "packets",
                    rubric=json.loads(
                        (FIXTURES / "rubric_dsaa3073_hw1.json").read_text(
                            encoding="utf-8"
                        )
                    ),
                    text_source_kind="transcript",
                    source_run_id="t1-dev-r1",
                    metadata={},
                )
            )

            report = check_m1_t1_g1_lineage(
                m1_packet=m1.packet_path,
                t1_packet=t1.packet_path,
                g1_packet=g1.packet_path,
                t1_run=run,
            )

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["stage"], "full_routes")
        self.assertFalse(report["failed_checks"])

    def _build_image_pair(self, root: Path):
        input_root = root / "inputs"
        student = input_root / "S001"
        student.mkdir(parents=True)
        (student / "page-0001.png").write_bytes(b"synthetic image")
        course = self._course()
        m1 = build_prompt_packet(
            PromptPacketSpec(
                course=course,
                packet_id="M1-dev-r1",
                condition="M1",
                task="grade",
                prompt_text="Grade visible evidence only.",
                student_ids=("S001",),
                input_root=input_root,
                output_root=root / "packets",
                rubric=json.loads(
                    (FIXTURES / "rubric_dsaa3073_hw1.json").read_text(encoding="utf-8")
                ),
                metadata=_snapshot_metadata(),
            )
        )
        t1 = build_prompt_packet(
            PromptPacketSpec(
                course=course,
                packet_id="T1-dev-r1",
                condition="T1",
                task="transcribe",
                prompt_text="Transcribe visible work only.",
                student_ids=("S001",),
                input_root=input_root,
                output_root=root / "packets",
                metadata=_snapshot_metadata(),
            )
        )
        return m1, t1


def _snapshot_metadata() -> dict[str, str]:
    return {
        "input_mode": "anonymous_submission_snapshot",
        "snapshot_record_type": "anonymous_submission_cohort_snapshot",
        "snapshot_manifest_sha256": "a" * 64,
        "input_snapshot_manifest_sha256": "a" * 64,
        "snapshot_grading_unit": "anonymous_submission",
    }


if __name__ == "__main__":
    unittest.main()
