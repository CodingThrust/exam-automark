import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from benchmark.physics.cli import main
from benchmark.physics.schema import ProviderResult, QUESTION_IDS, QUESTION_MAX
from benchmark.physics.skillopt_preflight import run_target_preflight


class FakeProvider:
    model = "deepseek-v4-pro"

    def __init__(self, raw_texts: list[str]):
        self.raw_texts = list(raw_texts)
        self.prompts: list[str] = []

    def complete_text(self, prompt: str) -> ProviderResult:
        self.prompts.append(prompt)
        raw_text = self.raw_texts.pop(0)
        return ProviderResult(
            raw_text=raw_text,
            model=self.model,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


class SkillOptTargetPreflightTests(unittest.TestCase):
    def _write_split(self, root: Path, student_id: str = "S001") -> Path:
        split_dir = root / "split"
        val_dir = split_dir / "val"
        val_dir.mkdir(parents=True)
        item = {
            "id": f"G1-dev-r1-{student_id}",
            "student_id": student_id,
            "course_id": "physics",
            "assessment_id": "week9",
            "question": "Grade this anonymous physics week 9 transcript.",
            "course": {
                "questions": [
                    {
                        "id": question_id,
                        "max_score": QUESTION_MAX[question_id],
                        "score_step": 0.25,
                    }
                    for question_id in QUESTION_IDS
                ],
                "score_unit": "points",
            },
            "rubric": {
                "rubric_version": "rubric-test",
                "questions": [],
            },
            "transcript": {
                "student_id": student_id,
                "answers": [
                    {
                        "question_id": question_id,
                        "text": f"answer for {question_id}",
                        "unclear": False,
                    }
                    for question_id in QUESTION_IDS
                ],
            },
            "gold_scores": [
                {"question_id": question_id, "score": 1.0}
                for question_id in QUESTION_IDS
            ],
            "gold_total": float(len(QUESTION_IDS)),
            "prompt_text": "Return valid JSON.",
        }
        (val_dir / "items.json").write_text(
            json.dumps([item], indent=2),
            encoding="utf-8",
        )
        return split_dir

    def _valid_payload(self, student_id: str = "S001") -> str:
        return json.dumps(
            {
                "student_id": student_id,
                "scores": [
                    {"question_id": question_id, "score": 1.0}
                    for question_id in QUESTION_IDS
                ],
                "total": float(len(QUESTION_IDS)),
            }
        )

    def test_preflight_scores_valid_target_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = self._write_split(root)
            output_dir = root / "preflight"
            provider = FakeProvider([self._valid_payload()])

            summary = run_target_preflight(
                split_dir=split_dir,
                output_dir=output_dir,
                split="val",
                provider=provider,
            )

            self.assertEqual(summary["record_type"], "physics_skillopt_target_preflight")
            self.assertEqual(summary["status"], "ready")
            self.assertEqual(summary["items_expected"], 1)
            self.assertEqual(summary["items_passed"], 1)
            self.assertEqual(summary["hard_rate"], 1.0)
            self.assertEqual(summary["soft_avg"], 1.0)
            self.assertEqual(summary["total_abs_error"], 0.0)
            self.assertEqual(len(provider.prompts), 1)
            self.assertIn("Return one JSON object only", provider.prompts[0])
            self.assertIn("S001", provider.prompts[0])
            self.assertNotIn("data:image", provider.prompts[0])
            self.assertTrue((output_dir / "summary.json").exists())
            self.assertTrue((output_dir / "outputs" / "S001" / "result.json").exists())
            self.assertTrue((output_dir / "outputs" / "S001" / "raw_response.txt").exists())

    def test_preflight_records_unparseable_target_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = self._write_split(root)
            output_dir = root / "preflight"
            provider = FakeProvider(["I cannot grade this."])

            summary = run_target_preflight(
                split_dir=split_dir,
                output_dir=output_dir,
                split="val",
                provider=provider,
            )

            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["items_expected"], 1)
            self.assertEqual(summary["items_passed"], 0)
            self.assertEqual(summary["reason_counts"], {"json_parse_error": 1})
            result = json.loads(
                (output_dir / "outputs" / "S001" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["reason"], "json_parse_error")

    def test_cli_requires_deepseek_key_for_target_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = self._write_split(root)
            output_dir = root / "preflight"

            stdout = StringIO()
            stderr = StringIO()
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main(
                        [
                            "skillopt-target-preflight",
                            "--split-dir",
                            str(split_dir),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("DEEPSEEK_API_KEY is required", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
