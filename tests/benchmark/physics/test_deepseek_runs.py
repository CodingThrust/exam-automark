import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.physics.deepseek_runs import run_deepseek_condition
from benchmark.physics.schema import ProviderResult, QUESTION_IDS


class FakeDeepSeekProvider:
    model = "deepseek-v4-pro"

    def __init__(self, student_id: str = "S008"):
        self.student_id = student_id
        self.prompts = []

    def complete_text(self, prompt: str) -> ProviderResult:
        self.prompts.append(prompt)
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
            model=self.model,
            usage={"prompt_tokens": 50, "completion_tokens": 20},
        )


class DeepSeekRunTests(unittest.TestCase):
    def _transcript_payload(self, prefix: str) -> dict:
        return {
            "student_id": "S008",
            "answers": [
                {
                    "question_id": question_id,
                    "text": f"{prefix} {question_id}",
                    "unclear": False,
                }
                for question_id in QUESTION_IDS
            ],
        }

    def _workspace(self, root: Path) -> Path:
        benchmark_root = root / "benchmark"
        (benchmark_root / "manifest").mkdir(parents=True)
        (benchmark_root / "rubric").mkdir()
        automatic = (
            benchmark_root / "transcripts" / "automatic" / "T1-dev-r1"
        )
        automatic.mkdir(parents=True)
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
        (automatic / "S008.json").write_text(
            json.dumps(self._transcript_payload("automatic answer")),
            encoding="utf-8",
        )
        return benchmark_root

    def _human_review(self, benchmark_root: Path) -> None:
        path = benchmark_root / "transcripts" / "human" / "H1-dev.csv"
        path.parent.mkdir(parents=True)
        fieldnames = (
            "student_id",
            "question_id",
            "automatic_text",
            "human_text",
            "reviewed",
        )
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for question_id in QUESTION_IDS:
                writer.writerow(
                    {
                        "student_id": "S008",
                        "question_id": question_id,
                        "automatic_text": f"automatic answer {question_id}",
                        "human_text": f"human corrected {question_id}",
                        "reviewed": "true",
                    }
                )

    def test_d1_grades_frozen_automatic_text_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark_root = self._workspace(Path(tmp))
            provider = FakeDeepSeekProvider()

            run_dir = run_deepseek_condition(
                benchmark_root=benchmark_root,
                condition="D1",
                split="dev",
                repetition=1,
                provider=provider,
            )

            self.assertEqual(run_dir.name, "D1-dev-r1")
            self.assertEqual(len(provider.prompts), 1)
            self.assertIn("automatic answer Q1a", provider.prompts[0])
            self.assertNotIn("input_image", provider.prompts[0])
            self.assertNotIn("data:image", provider.prompts[0])
            with (run_dir / "predictions.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                predictions = list(csv.DictReader(handle))
            self.assertEqual(len(predictions), 12)
            manifest = json.loads(
                (run_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["model"], "deepseek-v4-pro")
            self.assertEqual(manifest["usage"]["prompt_tokens"], 50)

    def test_d2_grades_human_corrected_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark_root = self._workspace(Path(tmp))
            self._human_review(benchmark_root)
            provider = FakeDeepSeekProvider()

            run_deepseek_condition(
                benchmark_root, "D2", "dev", 1, provider
            )

            self.assertEqual(len(provider.prompts), 1)
            self.assertIn("human corrected Q1a", provider.prompts[0])
            self.assertNotIn("automatic answer Q1a", provider.prompts[0])

    def test_revised_policy_rejects_second_repetition(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "one run per condition"):
                run_deepseek_condition(
                    Path(tmp), "D1", "dev", 2, FakeDeepSeekProvider()
                )


if __name__ == "__main__":
    unittest.main()
