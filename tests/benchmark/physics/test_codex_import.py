import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.physics.codex_import import (
    create_human_review_csv,
    import_codex_packet,
    parse_grading_output,
    parse_transcript_output,
    validate_human_review_csv,
)
from benchmark.physics.schema import QUESTION_IDS


class CodexImportTests(unittest.TestCase):
    def _payload(self, student_id: str = "S008") -> dict:
        return {
            "student_id": student_id,
            "answers": [
                {
                    "question_id": question_id,
                    "text": f"visible answer for {question_id}",
                    "unclear": False,
                }
                for question_id in QUESTION_IDS
            ],
        }

    def _packet(self, root: Path, payload: dict | None = None) -> Path:
        packet = root / "packet"
        (packet / "outputs").mkdir(parents=True)
        (packet / "manifest.json").write_text(
            json.dumps(
                {
                    "run_id": "T1-dev-r1",
                    "condition": "T1",
                    "split": "dev",
                    "repetition": 1,
                    "provider": "codex-plus-interactive",
                    "display_model": "GPT-5.5",
                    "student_ids": ["S008"],
                    "prompt_hash": "prompt-hash",
                    "rubric_hash": None,
                    "input_hashes": {"S008": "input-hash"},
                }
            ),
            encoding="utf-8",
        )
        if payload is not None:
            (packet / "outputs" / "S008.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
        return packet

    def _automatic_transcripts(
        self, benchmark_root: Path, student_ids: list[str], split: str = "dev"
    ) -> None:
        source = (
            benchmark_root
            / "transcripts"
            / "automatic"
            / f"T1-{split}-r1"
        )
        source.mkdir(parents=True)
        for student_id in student_ids:
            (source / f"{student_id}.json").write_text(
                json.dumps(self._payload(student_id)), encoding="utf-8"
            )

    def _grading_payload(self, student_id: str = "S008") -> dict:
        return {
            "student_id": student_id,
            "scores": [
                {
                    "question_id": question_id,
                    "extracted_evidence": "visible work",
                    "score": 0.0,
                    "evidence": "no credit in fixture",
                    "confidence": "high",
                    "flags": [],
                }
                for question_id in QUESTION_IDS
            ],
            "total": 0.0,
        }

    def _grading_packet(self, root: Path, payload: dict) -> Path:
        packet = root / "grading-packet"
        (packet / "outputs").mkdir(parents=True)
        (packet / "manifest.json").write_text(
            json.dumps(
                {
                    "run_id": "G2-dev-r1",
                    "condition": "G2",
                    "split": "dev",
                    "repetition": 1,
                    "provider": "codex-plus-interactive",
                    "display_model": "GPT-5.5",
                    "student_ids": ["S008"],
                    "prompt_hash": "prompt-hash",
                    "rubric_hash": "rubric-hash",
                    "input_hashes": {"S008": "input-hash"},
                }
            ),
            encoding="utf-8",
        )
        (packet / "outputs" / "S008.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        return packet

    def test_imports_complete_t1_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark_root = root / "benchmark"
            packet = self._packet(root, self._payload())

            run_dir = import_codex_packet(packet, benchmark_root)

            self.assertEqual(run_dir.name, "T1-dev-r1")
            frozen = (
                benchmark_root
                / "transcripts"
                / "automatic"
                / "T1-dev-r1"
                / "S008.json"
            )
            self.assertTrue(frozen.exists())
            rows = (run_dir / "transcripts.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(rows), 12)
            normalized = [json.loads(row) for row in rows]
            self.assertEqual(
                {row["question_id"] for row in normalized}, set(QUESTION_IDS)
            )
            manifest = json.loads(
                (run_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["provider"], "codex-plus-interactive")
            self.assertIsNotNone(manifest["end_time"])

    def test_rejects_incomplete_or_duplicate_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "S008.json"
            payload = self._payload()
            payload["answers"].pop()
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly 12"):
                parse_transcript_output(path, "S008")

            payload = self._payload()
            payload["answers"][-1]["question_id"] = "Q1a"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly once"):
                parse_transcript_output(path, "S008")

    def test_rejects_wrong_student_and_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "S008.json"
            path.write_text(json.dumps(self._payload("S009")), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "student_id does not match"):
                parse_transcript_output(path, "S008")

            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid transcript JSON"):
                parse_transcript_output(path, "S008")

    def test_unclear_answer_requires_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "S008.json"
            payload = self._payload()
            payload["answers"][0]["unclear"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, r"\[UNCLEAR\]"):
                parse_transcript_output(path, "S008")

    def test_import_requires_exact_packet_students_before_creating_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark_root = root / "benchmark"
            packet = self._packet(root, self._payload())
            (packet / "outputs" / "S009.json").write_text(
                json.dumps(self._payload("S009")), encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "do not match packet"):
                import_codex_packet(packet, benchmark_root)

            self.assertFalse((benchmark_root / "runs" / "T1-dev-r1").exists())

    def test_creates_human_review_for_frozen_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark_root = Path(tmp) / "benchmark"
            (benchmark_root / "manifest").mkdir(parents=True)
            student_ids = ["S008", "S010", "S018", "S022"]
            (benchmark_root / "manifest" / "split.json").write_text(
                json.dumps(
                    {
                        "transcript_gold": {
                            "development_student_ids": student_ids,
                            "heldout_student_ids": [],
                        }
                    }
                ),
                encoding="utf-8",
            )
            self._automatic_transcripts(benchmark_root, student_ids)

            review_path = create_human_review_csv(
                benchmark_root=benchmark_root,
                split="dev",
                output=benchmark_root / "transcripts" / "human" / "H1-dev.csv",
            )

            self.assertTrue(review_path.read_bytes().startswith(b"\xef\xbb\xbf"))
            with review_path.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 4 * 12)
            self.assertEqual(
                tuple(rows[0]),
                (
                    "student_id",
                    "question_id",
                    "automatic_text",
                    "human_text",
                    "reviewed",
                ),
            )
            self.assertEqual(rows[0]["human_text"], "")
            self.assertEqual(rows[0]["reviewed"], "")

    def test_human_review_requires_text_and_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark_root = Path(tmp) / "benchmark"
            (benchmark_root / "manifest").mkdir(parents=True)
            student_ids = ["S008"]
            (benchmark_root / "manifest" / "split.json").write_text(
                json.dumps(
                    {
                        "transcript_gold": {
                            "development_student_ids": student_ids,
                            "heldout_student_ids": [],
                        }
                    }
                ),
                encoding="utf-8",
            )
            self._automatic_transcripts(benchmark_root, student_ids)
            path = create_human_review_csv(
                benchmark_root, "dev", benchmark_root / "H1-dev.csv"
            )
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            with self.assertRaisesRegex(ValueError, "text is incomplete"):
                validate_human_review_csv(path, student_ids)

            for row in rows:
                row["human_text"] = row["automatic_text"]
                row["reviewed"] = "true"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            validate_human_review_csv(path, student_ids)

            rows[0]["reviewed"] = "false"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "review is incomplete"):
                validate_human_review_csv(path, student_ids)

    def test_imports_g2_grading_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark_root = root / "benchmark"
            packet = self._grading_packet(root, self._grading_payload())

            run_dir = import_codex_packet(packet, benchmark_root)

            with (run_dir / "predictions.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 12)
            self.assertEqual({row["student_id"] for row in rows}, {"S008"})
            self.assertEqual(
                {row["question_id"] for row in rows}, set(QUESTION_IDS)
            )
            manifest = json.loads(
                (run_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["provider"], "codex-plus-interactive")
            self.assertEqual(manifest["model"], "GPT-5.5")
            self.assertTrue((run_dir / "raw_responses.jsonl").stat().st_size)

    def test_grading_output_rejects_invalid_scores_and_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "S008.json"

            payload = self._grading_payload()
            payload["scores"][0]["score"] = 0.1
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "quarter-point"):
                parse_grading_output(path, "S008")

            payload = self._grading_payload()
            payload["scores"][0]["score"] = 3.0
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "out of range"):
                parse_grading_output(path, "S008")

            payload = self._grading_payload()
            payload["scores"][-1]["question_id"] = "Q1a"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly once"):
                parse_grading_output(path, "S008")

            payload = self._grading_payload()
            payload["total"] = 1.0
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "total does not match"):
                parse_grading_output(path, "S008")

    def test_grading_output_rejects_wrong_student(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "S008.json"
            path.write_text(
                json.dumps(self._grading_payload("S009")), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "student_id does not match"):
                parse_grading_output(path, "S008")


if __name__ == "__main__":
    unittest.main()
