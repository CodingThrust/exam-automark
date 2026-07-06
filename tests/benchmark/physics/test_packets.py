import json
import tempfile
import unittest
from pathlib import Path

from benchmark.physics.packets import audit_blind_packet, build_blind_packet


class PacketTests(unittest.TestCase):
    def _workspace(self, root: Path) -> Path:
        benchmark_root = root / "benchmark"
        (benchmark_root / "manifest").mkdir(parents=True)
        (benchmark_root / "rubric").mkdir()
        image_dir = benchmark_root / "anonymized" / "S008"
        image_dir.mkdir(parents=True)
        (image_dir / "S008-p01.jpg").write_bytes(b"anonymous-jpeg")
        (benchmark_root / "manifest" / "privacy_review.csv").write_text(
            "page,approved,reviewer,reviewed_at\n"
            "S008-p01.jpg,true,teacher,2026-07-02\n",
            encoding="utf-8",
        )
        (benchmark_root / "manifest" / "split.json").write_text(
            json.dumps(
                {
                    "development_student_ids": ["S008"],
                    "heldout_student_ids": ["S009"],
                    "transcript_gold": {
                        "development_student_ids": ["S008"],
                        "heldout_student_ids": ["S009"],
                    },
                }
            ),
            encoding="utf-8",
        )
        (benchmark_root / "rubric" / "rubric_v1.json").write_text(
            json.dumps({"rubric_version": "rubric_v1", "questions": []}),
            encoding="utf-8",
        )
        return benchmark_root

    def test_builds_isolated_t1_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark_root = self._workspace(root)

            packet = build_blind_packet(
                benchmark_root=benchmark_root,
                condition="T1",
                split="dev",
                repetition=1,
                output_root=root / "packets",
            )
            manifest = json.loads(
                (packet / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(packet.name, "T1-dev-r1")
            self.assertEqual(manifest["display_model"], "GPT-5.5")
            self.assertEqual(manifest["student_ids"], ["S008"])
            self.assertTrue(
                (packet / "inputs" / "S008" / "S008-p01.jpg").exists()
            )
            self.assertTrue((packet / "outputs").is_dir())
            self.assertTrue((packet / "prompt.txt").exists())
            self.assertTrue((packet / "output.schema.json").exists())
            self.assertEqual(audit_blind_packet(packet), [])

    def test_input_hashes_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark_root = self._workspace(root)

            first = build_blind_packet(
                benchmark_root, "T1", "dev", 1, root / "packets-a"
            )
            second = build_blind_packet(
                benchmark_root, "T1", "dev", 1, root / "packets-b"
            )
            first_manifest = json.loads(
                (first / "manifest.json").read_text(encoding="utf-8")
            )
            second_manifest = json.loads(
                (second / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(
                first_manifest["input_hashes"], second_manifest["input_hashes"]
            )
            self.assertEqual(
                first_manifest["prompt_hash"], second_manifest["prompt_hash"]
            )

    def test_audit_reports_forbidden_packet_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet"
            packet.mkdir()
            (packet / "outputs").mkdir()
            (packet / "private-notes.txt").write_text(
                "read primary_scores before grading", encoding="utf-8"
            )

            findings = audit_blind_packet(packet)

            self.assertTrue(any("primary_scores" in finding for finding in findings))

    def test_audit_allows_reports_as_a_rubric_verb(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet"
            packet.mkdir()
            (packet / "rubric.json").write_text(
                json.dumps({"common_errors": ["Reports omega without B_m."]}),
                encoding="utf-8",
            )

            self.assertEqual(audit_blind_packet(packet), [])

    def test_audit_still_rejects_reports_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet"
            reports = packet / "reports"
            reports.mkdir(parents=True)
            (reports / "summary.json").write_text("{}", encoding="utf-8")

            findings = audit_blind_packet(packet)

            self.assertTrue(any("forbidden path term reports" in row for row in findings))

    def test_test_split_is_sealed_before_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark_root = self._workspace(root)

            with self.assertRaisesRegex(ValueError, "held-out split is sealed"):
                build_blind_packet(
                    benchmark_root, "T1", "test", 1, root / "packets"
                )


if __name__ == "__main__":
    unittest.main()
