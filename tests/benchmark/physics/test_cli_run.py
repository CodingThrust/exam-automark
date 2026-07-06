import io
import csv
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from benchmark.physics.cli import main, run_condition
from benchmark.physics.schema import ProviderResult, QUESTION_IDS


class FakeImageProvider:
    def __init__(self, student_id="S008"):
        self.calls = []
        self.student_id = student_id

    def complete_images(self, prompt, images):
        self.calls.append({"prompt": prompt, "images": images})
        scores = [
            {
                "question_id": question_id,
                "extracted_evidence": "visible work",
                "score": 0.0,
                "evidence": "no credit in fixture",
                "confidence": "high",
                "flags": [],
            }
            for question_id in QUESTION_IDS
        ]
        return ProviderResult(
            raw_text=json.dumps(
                {"student_id": self.student_id, "scores": scores, "total": 0.0}
            ),
            model="gpt-5.4",
            usage={"input_tokens": 123, "output_tokens": 45},
        )


class CliRunTests(unittest.TestCase):
    def test_g1_raises_when_every_student_fails(self):
        class FailingProvider:
            def complete_images(self, prompt, images):
                raise RuntimeError("provider unavailable")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manifest").mkdir(parents=True)
            (root / "rubric").mkdir()
            image_dir = root / "anonymized" / "S008"
            image_dir.mkdir(parents=True)
            (root / "manifest" / "privacy_review.csv").write_text(
                "page,approved,reviewer,reviewed_at\n"
                "S008-p01.jpg,true,teacher,2026-07-02\n",
                encoding="utf-8",
            )
            (root / "manifest" / "split.json").write_text(
                json.dumps(
                    {
                        "development_student_ids": ["S008"],
                        "heldout_student_ids": ["S002"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "rubric" / "rubric_v1.json").write_text(
                json.dumps({"rubric_version": "rubric_v1", "questions": []}),
                encoding="utf-8",
            )
            (image_dir / "S008-p01.jpg").write_bytes(b"anonymous-jpeg")

            with self.assertRaisesRegex(RuntimeError, "produced no predictions"):
                run_condition(
                    root,
                    "G1",
                    "dev",
                    1,
                    provider=FailingProvider(),
                )

            run_dir = root / "runs" / "G1-dev-r1"
            self.assertTrue(run_dir.exists())
            self.assertTrue((run_dir / "failures.jsonl").read_text(encoding="utf-8"))

    def test_g1_blocks_an_image_missing_from_privacy_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manifest").mkdir(parents=True)
            (root / "rubric").mkdir()
            image_dir = root / "anonymized" / "S008"
            image_dir.mkdir(parents=True)
            (root / "manifest" / "privacy_review.csv").write_text(
                "page,approved,reviewer,reviewed_at\n"
                "S008-p01.jpg,true,teacher,2026-07-02\n",
                encoding="utf-8",
            )
            (root / "manifest" / "split.json").write_text(
                json.dumps(
                    {
                        "development_student_ids": ["S008"],
                        "heldout_student_ids": ["S002"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "rubric" / "rubric_v1.json").write_text(
                json.dumps({"rubric_version": "rubric_v1", "questions": []}),
                encoding="utf-8",
            )
            (image_dir / "S008-p01.jpg").write_bytes(b"approved")
            (image_dir / "S008-p02.jpg").write_bytes(b"not-reviewed")
            provider = FakeImageProvider()

            with self.assertRaisesRegex(
                ValueError, "privacy approval missing for: S008-p02.jpg"
            ):
                run_condition(root, "G1", "dev", 1, provider=provider)

            self.assertEqual(provider.calls, [])
            self.assertFalse((root / "runs" / "G1-dev-r1").exists())

    def test_g1_dev_executes_images_and_records_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manifest").mkdir(parents=True)
            (root / "rubric").mkdir()
            image_dir = root / "anonymized" / "S008"
            image_dir.mkdir(parents=True)
            (root / "manifest" / "privacy_review.csv").write_text(
                "page,approved,reviewer,reviewed_at\n"
                "S008-p01.jpg,true,teacher,2026-07-02\n",
                encoding="utf-8",
            )
            (root / "manifest" / "split.json").write_text(
                json.dumps(
                    {
                        "development_student_ids": ["S008"],
                        "heldout_student_ids": ["S002"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "rubric" / "rubric_v1.json").write_text(
                json.dumps({"rubric_version": "rubric_v1", "questions": []}),
                encoding="utf-8",
            )
            (image_dir / "S008-p01.jpg").write_bytes(b"anonymous-jpeg")
            provider = FakeImageProvider()

            run_dir = run_condition(
                root,
                "G1",
                "dev",
                1,
                provider=provider,
            )

            self.assertEqual(run_dir.name, "G1-dev-r1")
            self.assertEqual(len(provider.calls), 1)
            self.assertEqual(provider.calls[0]["images"], [b"anonymous-jpeg"])
            self.assertIn("Output student_id must be S008.", provider.calls[0]["prompt"])
            self.assertIn('"rubric_version": "rubric_v1"', provider.calls[0]["prompt"])
            with (run_dir / "predictions.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                predictions = list(csv.DictReader(handle))
            self.assertEqual(len(predictions), 12)
            self.assertEqual({row["student_id"] for row in predictions}, {"S008"})
            self.assertEqual(
                {row["question_id"] for row in predictions}, set(QUESTION_IDS)
            )
            manifest = json.loads(
                (run_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["condition"], "G1")
            self.assertEqual(manifest["student_ids"], ["S008"])
            self.assertIsNotNone(manifest["end_time"])
            self.assertEqual(manifest["usage"]["input_tokens"], 123)

    def test_run_blocks_unapproved_privacy_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_dir = root / "manifest"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "privacy_review.csv").write_text(
                "page,approved,reviewer,reviewed_at\nS001-p01.jpg,false,,\n",
                encoding="utf-8",
            )

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main(
                    [
                        "run",
                        "--root",
                        str(root),
                        "--condition",
                        "G1",
                        "--split",
                        "dev",
                        "--repetition",
                        "1",
                    ]
                )

            self.assertNotEqual(code, 0)
            self.assertIn("privacy approval missing", stderr.getvalue())

    def test_run_blocks_test_split_before_freeze_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_dir = root / "manifest"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "privacy_review.csv").write_text(
                "page,approved,reviewer,reviewed_at\nS001-p01.jpg,true,teacher,2026-07-02\n",
                encoding="utf-8",
            )

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main(
                    [
                        "run",
                        "--root",
                        str(root),
                        "--condition",
                        "G1",
                        "--split",
                        "test",
                        "--repetition",
                        "1",
                    ]
                )

            self.assertNotEqual(code, 0)
            self.assertIn("held-out split is sealed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
