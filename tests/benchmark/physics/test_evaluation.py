import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.physics.evaluation import evaluate_conditions, freeze_revised_workflow
from benchmark.physics.gold import SCORE_FIELDS
from benchmark.physics.schema import QUESTION_IDS


class EvaluationTests(unittest.TestCase):
    def _workspace(self, root: Path, *, omit_run: str | None = None) -> Path:
        benchmark_root = root / "benchmark"
        (benchmark_root / "manifest").mkdir(parents=True)
        (benchmark_root / "gold").mkdir()
        (benchmark_root / "rubric").mkdir()
        (benchmark_root / "runs").mkdir()

        dev_ids = [f"S{index:03d}" for index in range(1, 9)]
        transcript_ids = dev_ids[:4]
        (benchmark_root / "manifest" / "split.json").write_text(
            json.dumps(
                {
                    "development_student_ids": dev_ids,
                    "heldout_student_ids": ["S009"],
                    "transcript_gold": {
                        "development_student_ids": transcript_ids,
                        "heldout_student_ids": ["S009"],
                    },
                }
            ),
            encoding="utf-8",
        )
        self._write_scores(
            benchmark_root / "gold" / "primary_scores.csv", dev_ids, score="1"
        )
        self._write_scores(
            benchmark_root / "gold" / "reviewer_scores.csv", dev_ids, score=""
        )
        (benchmark_root / "rubric" / "rubric_v1.json").write_text(
            json.dumps({"rubric_version": "rubric_v1"}), encoding="utf-8"
        )

        runs = {
            "G0-all-r1": dev_ids,
            "G2-dev-r1": dev_ids,
            "D1-dev-r1": dev_ids,
            "G3-dev-r1": transcript_ids,
            "D2-dev-r1": transcript_ids,
        }
        for run_id, student_ids in runs.items():
            if run_id == omit_run:
                continue
            run_dir = benchmark_root / "runs" / run_id
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(
                json.dumps({"run_id": run_id, "end_time": "2026-07-02T00:00:00Z"}),
                encoding="utf-8",
            )
            self._write_scores(run_dir / "predictions.csv", student_ids, score="1")

        failed = benchmark_root / "runs" / "G1-dev-r1"
        failed.mkdir()
        (failed / "manifest.json").write_text(
            json.dumps({"run_id": "G1-dev-r1", "end_time": "2026-07-02T00:00:00Z"}),
            encoding="utf-8",
        )
        self._write_scores(failed / "predictions.csv", [], score="")
        return benchmark_root

    @staticmethod
    def _write_scores(path: Path, student_ids: list[str], *, score: str) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
            writer.writeheader()
            for student_id in student_ids:
                for question_id in QUESTION_IDS:
                    writer.writerow(
                        {
                            "student_id": student_id,
                            "question_id": question_id,
                            "score": score,
                            "confidence": "high" if score else "",
                            "evidence": "",
                            "ambiguity_code": "",
                        }
                    )

    @staticmethod
    def _append_scores(path: Path, student_ids: list[str], *, score: str) -> None:
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
            for student_id in student_ids:
                for question_id in QUESTION_IDS:
                    writer.writerow(
                        {
                            "student_id": student_id,
                            "question_id": question_id,
                            "score": score,
                            "confidence": "high",
                            "evidence": "",
                            "ambiguity_code": "",
                        }
                    )

    def test_excludes_failed_g1_and_keeps_subset_metrics_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._workspace(Path(tmp))

            result = evaluate_conditions(root, split="dev")

            self.assertNotIn("G1", result["conditions"])
            self.assertEqual(result["excluded_runs"], ["G1-dev-r1"])
            self.assertEqual(result["conditions"]["G2"]["n_students"], 8)
            self.assertEqual(result["conditions"]["G2"]["population"], "full_split")
            self.assertEqual(result["conditions"]["G3"]["n_students"], 4)
            self.assertEqual(
                result["conditions"]["G3"]["population"], "transcript_subset"
            )
            self.assertEqual(
                result["transcript_subset_comparisons"]["GPT"]["n_students"],
                4,
            )
            self.assertEqual(
                result["transcript_subset_comparisons"]["GPT"][
                    "human_minus_automatic"
                ]["mean_difference"],
                0.0,
            )
            self.assertEqual(result["reference_status"], "single_primary_rater")
            self.assertNotIn("human_agreement", result)
            self.assertTrue((root / "metrics-dev.json").exists())

    def test_freezes_revised_models_prompts_and_input_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._workspace(Path(tmp))

            freeze = freeze_revised_workflow(root, candidate="staged_v1")

            self.assertEqual(freeze["gpt_display_model"], "GPT-5.5")
            self.assertEqual(freeze["deepseek_model"], "deepseek-v4-pro")
            self.assertEqual(freeze["runs_per_condition"], 1)
            self.assertIn("T1", freeze["prompt_hashes"])
            self.assertEqual(
                freeze["input_policy"], "frozen anonymous transcript workflow"
            )
            self.assertEqual(
                json.loads((root / "freeze.json").read_text(encoding="utf-8")),
                freeze,
            )

    def test_rejects_incomplete_primary_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._workspace(Path(tmp))
            gold_path = root / "gold" / "primary_scores.csv"
            lines = gold_path.read_text(encoding="utf-8").splitlines()
            gold_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "primary gold is incomplete"):
                evaluate_conditions(root, split="dev")

    def test_all_split_combines_development_and_heldout_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._workspace(Path(tmp))
            self._append_scores(
                root / "gold" / "primary_scores.csv", ["S009"], score="1"
            )
            self._append_scores(
                root / "runs" / "G0-all-r1" / "predictions.csv",
                ["S009"],
                score="1",
            )
            for condition in ("G2", "D1", "G3", "D2"):
                run_id = f"{condition}-test-r1"
                run_dir = root / "runs" / run_id
                run_dir.mkdir()
                (run_dir / "manifest.json").write_text(
                    json.dumps(
                        {"run_id": run_id, "end_time": "2026-07-03T00:00:00Z"}
                    ),
                    encoding="utf-8",
                )
                self._write_scores(
                    run_dir / "predictions.csv", ["S009"], score="1"
                )

            result = evaluate_conditions(root, split="all")

            self.assertEqual(result["conditions"]["G2"]["n_students"], 9)
            self.assertEqual(result["conditions"]["G3"]["n_students"], 5)
            self.assertIn("G2-dev-r1", result["conditions"]["G2"]["run_id"])
            self.assertIn("G2-test-r1", result["conditions"]["G2"]["run_id"])
            self.assertTrue((root / "metrics-all.json").exists())

    def test_freeze_rejects_missing_required_development_run(self):
        for missing in ("G2-dev-r1", "D1-dev-r1"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                root = self._workspace(Path(tmp), omit_run=missing)

                with self.assertRaisesRegex(ValueError, missing):
                    freeze_revised_workflow(root, candidate="staged_v1")

                self.assertFalse((root / "freeze.json").exists())


if __name__ == "__main__":
    unittest.main()
