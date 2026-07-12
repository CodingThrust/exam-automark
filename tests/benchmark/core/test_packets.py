import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.packets import (
    FORBIDDEN_TEXT_TERMS,
    PromptPacketSpec,
    audit_prompt_packet,
    build_prompt_packet,
    directory_digest,
    grading_output_schema,
    transcript_output_schema,
)
from benchmark.core.schema import CourseSpec


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class CorePacketTests(unittest.TestCase):
    def _course(self) -> CourseSpec:
        return CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")

    @staticmethod
    def _inputs(root: Path, student_ids: tuple[str, ...] = ("S001",)) -> Path:
        input_root = root / "inputs"
        for student_id in student_ids:
            student_dir = input_root / student_id
            student_dir.mkdir(parents=True)
            (student_dir / "page-001.txt").write_text(
                f"anonymous visible work for {student_id}\n",
                encoding="utf-8",
            )
        return input_root

    def test_builds_transcript_packet_with_reproducible_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            input_root = self._inputs(root)

            result = build_prompt_packet(
                PromptPacketSpec(
                    course=course,
                    packet_id="T1-dev-r1",
                    condition="T1",
                    task="transcribe",
                    prompt_text="Transcribe visible answers.\r\nDo not infer missing work.",
                    student_ids=("S001",),
                    input_root=input_root,
                    output_root=root / "packets",
                )
            )

            manifest = json.loads(
                (result.packet_path / "manifest.json").read_text(encoding="utf-8")
            )
            schema = json.loads(
                (result.packet_path / "output.schema.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result.packet_path.name, "T1-dev-r1")
            self.assertEqual(manifest["course_id"], "dsaa3073")
            self.assertEqual(manifest["task"], "transcribe")
            self.assertEqual(manifest["student_ids"], ["S001"])
            self.assertEqual(schema["properties"]["answers"]["minItems"], 3)
            self.assertTrue((result.packet_path / "outputs").is_dir())
            self.assertEqual(audit_prompt_packet(result.packet_path), [])
            self.assertEqual(result.packet_hash, directory_digest(result.packet_path))
            self.assertNotIn(b"\r\n", (result.packet_path / "prompt.txt").read_bytes())
            self.assertNotIn(
                b"\r\n", (result.packet_path / "manifest.json").read_bytes()
            )

    def test_packet_hash_is_stable_for_identical_inputs(self):
        hashes = []
        manifests = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            input_root = self._inputs(root, ("S001", "S002"))
            for output_name in ("packets-a", "packets-b"):
                result = build_prompt_packet(
                    PromptPacketSpec(
                        course=course,
                        packet_id="G2-dev-r1",
                        condition="G2",
                        task="grade",
                        prompt_text="Grade with evidence first.",
                        student_ids=("S001", "S002"),
                        input_root=input_root,
                        output_root=root / output_name,
                        rubric={"rubric_version": "synthetic_v1", "questions": []},
                    )
                )
                hashes.append(result.packet_hash)
                manifests.append(result.manifest)

        self.assertEqual(hashes[0], hashes[1])
        self.assertEqual(manifests[0]["input_hashes"], manifests[1]["input_hashes"])
        self.assertEqual(manifests[0]["prompt_hash"], manifests[1]["prompt_hash"])

    def test_grade_packet_requires_rubric(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "require a rubric"):
                PromptPacketSpec(
                    course=self._course(),
                    packet_id="G2-dev-r1",
                    condition="G2",
                    task="grade",
                    prompt_text="Grade with evidence first.",
                    student_ids=("S001",),
                    input_root=self._inputs(root),
                    output_root=root / "packets",
                )

    def test_audit_rejects_leaked_reference_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet"
            packet.mkdir()
            (packet / "notes.txt").write_text(
                "Look at student_map before scoring.", encoding="utf-8"
            )

            findings = audit_prompt_packet(packet)

        self.assertTrue(any("student_map" in finding for finding in findings))

    def test_schemas_track_course_questions_and_score_bounds(self):
        course = self._course()
        transcript_schema = transcript_output_schema(course)
        grading_schema = grading_output_schema(course)

        self.assertEqual(
            transcript_schema["properties"]["answers"]["items"]["properties"][
                "question_id"
            ]["enum"],
            ["Q1", "Q2a", "Q2b"],
        )
        self.assertEqual(grading_schema["properties"]["total"]["maximum"], 15.0)
        self.assertEqual(grading_schema["properties"]["scores"]["minItems"], 3)

    def test_standard_prompt_templates_avoid_forbidden_reference_terms(self):
        template_paths = sorted(Path("experiments/prompt_templates").glob("*.txt"))

        for path in template_paths:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=path):
                for term in FORBIDDEN_TEXT_TERMS:
                    self.assertNotIn(term.lower(), text)


if __name__ == "__main__":
    unittest.main()
