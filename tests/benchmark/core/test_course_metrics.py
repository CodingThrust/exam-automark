import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.core.cli import main
from benchmark.core.course_metrics import CourseMetricsError, compare_course_runs, evaluate_course_scores
from benchmark.core.schema import CourseSpec, QuestionSpec


FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


class CourseMetricsTests(unittest.TestCase):
    def test_total_metric_applies_course_final_cap_after_bonus_leaf_scores(self):
        course = CourseSpec(
            course_id="synthetic",
            assessment_id="quiz",
            questions=(
                QuestionSpec("Q1", 100, score_step=1),
                QuestionSpec("Q1bonus", 10, score_step=1, is_bonus=True),
            ),
            base_total_points=100,
            final_score_cap=100,
        )
        gold = {("S001", "Q1"): 95.0, ("S001", "Q1bonus"): 10.0}
        predicted = {("S001", "Q1"): 100.0, ("S001", "Q1bonus"): 10.0}

        report = evaluate_course_scores(gold, predicted, course=course)

        self.assertEqual(report["subquestion_mae"], 2.5)
        self.assertEqual(report["total_score_mae"], 0.0)

    def test_compares_complete_runs_and_returns_aggregate_only_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            gold = self._write_gold(root)
            baseline = self._write_run(
                root,
                "baseline",
                {
                    "S001": {"Q1": 8, "Q2a": 2.75, "Q2b": 2},
                    "S002": {"Q1": 6, "Q2a": 2, "Q2b": 0.75},
                },
                snapshot="a" * 64,
            )
            candidate = self._write_run(
                root,
                "candidate",
                {
                    "S001": {"Q1": 8, "Q2a": 3, "Q2b": 2},
                    "S002": {"Q1": 6, "Q2a": 2, "Q2b": 1},
                },
                snapshot="a" * 64,
            )

            report = compare_course_runs(
                course,
                gold,
                ("S001", "S002"),
                baseline,
                candidate,
                bootstrap_samples=100,
                require_same_data_snapshot=True,
            )

        encoded = json.dumps(report, sort_keys=True)
        self.assertEqual(report["population"], {"student_count": 2, "score_row_count": 6})
        self.assertAlmostEqual(report["baseline"]["exact_agreement"], 4 / 6)
        self.assertEqual(report["candidate"]["exact_agreement"], 1.0)
        self.assertAlmostEqual(
            report["candidate_minus_baseline"]["exact_agreement"], 2 / 6
        )
        self.assertEqual(report["comparison_provenance"]["data_snapshot"], "matched")
        self.assertEqual(report["baseline"]["confidence_accuracy"]["status"], "available")
        self.assertNotIn("S001", encoded)
        self.assertNotIn("private answer", encoded)
        self.assertNotIn("baseline/outputs", encoded)

    def test_refuses_dry_run_or_failed_run_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            gold = self._write_gold(root)
            baseline = self._write_run(root, "baseline", self._perfect_scores())
            candidate = self._write_run(
                root,
                "candidate",
                self._perfect_scores(),
                dry_run=True,
            )

            with self.assertRaisesRegex(CourseMetricsError, "dry-run"):
                compare_course_runs(course, gold, ("S001", "S002"), baseline, candidate)

            metadata = json.loads(
                (candidate / "run-metadata.json").read_text(encoding="utf-8")
            )
            metadata["dry_run"] = False
            (candidate / "run-metadata.json").write_text(
                json.dumps(metadata), encoding="utf-8"
            )
            (candidate / "validation.json").write_text(
                json.dumps({"status": "failed"}), encoding="utf-8"
            )
            with self.assertRaisesRegex(CourseMetricsError, "validation status"):
                compare_course_runs(course, gold, ("S001", "S002"), baseline, candidate)

    def test_same_snapshot_gate_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            gold = self._write_gold(root)
            baseline = self._write_run(
                root, "baseline", self._perfect_scores(), snapshot="a" * 64
            )
            candidate = self._write_run(
                root, "candidate", self._perfect_scores(), snapshot="b" * 64
            )

            report = compare_course_runs(
                course, gold, ("S001", "S002"), baseline, candidate
            )
            self.assertEqual(report["comparison_provenance"]["data_snapshot"], "different")
            with self.assertRaisesRegex(CourseMetricsError, "same data snapshot"):
                compare_course_runs(
                    course,
                    gold,
                    ("S001", "S002"),
                    baseline,
                    candidate,
                    require_same_data_snapshot=True,
                )

    def test_cli_writes_safe_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course_path = FIXTURES / "course_dsaa3073_hw1.json"
            self._write_gold(root)
            baseline = self._write_run(root, "baseline", self._perfect_scores())
            candidate = self._write_run(root, "candidate", self._perfect_scores())
            students = root / "students.txt"
            students.write_text("S001\nS002\n", encoding="utf-8")
            output_json = root / "public" / "comparison.json"
            output_md = root / "public" / "comparison.md"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "compare-course-runs",
                        "--course",
                        str(course_path),
                        "--gold",
                        str(root / "gold.csv"),
                        "--students-file",
                        str(students),
                        "--baseline-run",
                        str(baseline / "outputs"),
                        "--candidate-run",
                        str(candidate),
                        "--output-json",
                        str(output_json),
                        "--output-md",
                        str(output_md),
                        "--bootstrap-samples",
                        "100",
                    ]
                )

            stdout_payload = json.loads(stdout.getvalue())
            public_text = output_json.read_text(encoding="utf-8") + output_md.read_text(
                encoding="utf-8"
            )

        self.assertEqual(code, 0)
        self.assertEqual(stdout_payload["privacy"], "aggregate_only")
        self.assertNotIn("S001", public_text)
        self.assertNotIn("private answer", public_text)
        self.assertNotIn(str(root), public_text)
        self.assertIn("course_generic_run_metrics_comparison", public_text)

    def test_incomplete_gold_blocks_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            gold = root / "gold.csv"
            gold.write_text(
                "student_id,question_id,score\nS001,Q1,8\n",
                encoding="utf-8",
            )
            baseline = self._write_run(root, "baseline", self._perfect_scores())
            candidate = self._write_run(root, "candidate", self._perfect_scores())

            with self.assertRaisesRegex(CourseMetricsError, "gold table is not ready"):
                compare_course_runs(course, gold, ("S001", "S002"), baseline, candidate)

    def test_accepts_complete_predictions_csv_run_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            gold = self._write_gold(root)
            baseline = self._write_prediction_csv_run(root, "baseline")
            candidate = self._write_prediction_csv_run(root, "candidate")

            report = compare_course_runs(
                course, gold, ("S001", "S002"), baseline, candidate
            )

        self.assertEqual(report["baseline_run"]["source_kind"], "run_directory_prediction_csv")
        self.assertEqual(report["baseline"]["confidence_accuracy"]["status"], "not_available")
        self.assertEqual(report["candidate"]["exact_agreement"], 1.0)

    def test_full_gold_csv_is_filtered_to_the_requested_split_before_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            gold = self._write_gold(root)
            # The held-out student's unfinished row must not invalidate a
            # fully reviewed development-only comparison.
            gold.write_text(
                gold.read_text(encoding="utf-8").replace("S002,Q1,6", "S002,Q1,"),
                encoding="utf-8",
            )
            scores = {"S001": {"Q1": 8, "Q2a": 3, "Q2b": 2}}
            baseline = self._write_run(root, "baseline", scores)
            candidate = self._write_run(root, "candidate", scores)

            report = compare_course_runs(
                course, gold, ("S001",), baseline, candidate
            )
            with self.assertRaisesRegex(CourseMetricsError, "gold table is not ready"):
                compare_course_runs(course, gold, ("S002",), baseline, candidate)

        self.assertEqual(report["population"], {"student_count": 1, "score_row_count": 3})
        self.assertNotIn("S001", json.dumps(report, sort_keys=True))

    def test_selected_gold_tempfile_stays_below_private_gold_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            private_gold_dir = root / "private-gold"
            private_gold_dir.mkdir()
            gold = self._write_gold(private_gold_dir)
            baseline = self._write_run(root, "baseline", self._perfect_scores())
            candidate = self._write_run(root, "candidate", self._perfect_scores())
            selected_temp = private_gold_dir / "selected-temp"
            selected_temp.mkdir()

            with patch(
                "benchmark.core.course_metrics.tempfile.TemporaryDirectory"
            ) as temporary_directory:
                temporary_directory.return_value.__enter__.return_value = str(selected_temp)
                report = compare_course_runs(
                    course, gold, ("S001", "S002"), baseline, candidate
                )

            self.assertEqual(
                temporary_directory.call_args.kwargs["dir"], gold.resolve().parent
            )
            self.assertTrue((selected_temp / "selected-gold.csv").is_file())

        self.assertEqual(report["population"]["student_count"], 2)

    def test_report_metadata_requires_compact_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = self._course()
            gold = self._write_gold(root)
            baseline = self._write_run(
                root,
                "baseline",
                self._perfect_scores(),
                model="kimi-code/k3",
                condition="candidate-v3.3",
                experiment_condition="route:multimodal@r1+audit",
            )
            candidate = self._write_run(
                root,
                "candidate",
                self._perfect_scores(),
                model="Claude-4.5",
            )

            report = compare_course_runs(
                course, gold, ("S001", "S002"), baseline, candidate
            )
            self.assertEqual(report["baseline_run"]["model"], "kimi-code/k3")
            self.assertEqual(
                report["baseline_run"]["experiment_condition"],
                "route:multimodal@r1+audit",
            )
            self.assertEqual(report["baseline_run"]["run_id"], "baseline-run")

            metadata_path = candidate / "run-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["model"] = "model/Data/week4"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(CourseMetricsError, "unsafe public identifier"):
                compare_course_runs(
                    course, gold, ("S001", "S002"), baseline, candidate
                )
            metadata["model"] = "private explanatory prose"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(CourseMetricsError, "unsafe public identifier"):
                compare_course_runs(
                    course, gold, ("S001", "S002"), baseline, candidate
                )

    def test_report_rejects_noncompact_course_score_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._course().to_dict()
            payload["score_unit"] = "private points prose"
            course = CourseSpec.from_dict(payload)
            gold = self._write_gold(root)
            baseline = self._write_run(root, "baseline", self._perfect_scores())
            candidate = self._write_run(root, "candidate", self._perfect_scores())

            with self.assertRaisesRegex(CourseMetricsError, "unsafe public identifier"):
                compare_course_runs(
                    course, gold, ("S001", "S002"), baseline, candidate
                )

    @staticmethod
    def _course() -> CourseSpec:
        return CourseSpec.from_json_path(FIXTURES / "course_dsaa3073_hw1.json")

    @staticmethod
    def _perfect_scores() -> dict[str, dict[str, float]]:
        return {
            "S001": {"Q1": 8, "Q2a": 3, "Q2b": 2},
            "S002": {"Q1": 6, "Q2a": 2, "Q2b": 1},
        }

    @staticmethod
    def _write_gold(root: Path) -> Path:
        path = root / "gold.csv"
        path.write_text(
            "student_id,question_id,score,reviewer,reviewed_at,notes\n"
            "S001,Q1,8,YY,2026-08-03,\n"
            "S001,Q2a,3,YY,2026-08-03,\n"
            "S001,Q2b,2,YY,2026-08-03,\n"
            "S002,Q1,6,YY,2026-08-03,\n"
            "S002,Q2a,2,YY,2026-08-03,\n"
            "S002,Q2b,1,YY,2026-08-03,\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _write_run(
        root: Path,
        name: str,
        scores_by_student: dict[str, dict[str, float]],
        *,
        snapshot: str = "a" * 64,
        dry_run: bool = False,
        model: str = "synthetic-model",
        condition: str = "candidate",
        experiment_condition: str | None = None,
    ) -> Path:
        run = root / name
        outputs = run / "outputs"
        outputs.mkdir(parents=True)
        for student_id, scores in scores_by_student.items():
            payload = {
                "student_id": student_id,
                "scores": [
                    {
                        "question_id": question_id,
                        "score": score,
                        "confidence": "high",
                        "extracted_evidence": "private answer must stay local",
                        "evidence": "private answer must stay local",
                        "flags": [],
                    }
                    for question_id, score in scores.items()
                ],
                "total": sum(scores.values()),
            }
            (outputs / f"{student_id}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
        student_ids = sorted(scores_by_student)
        (run / "validation.json").write_text(
            json.dumps(
                {
                    "status": "passed",
                    "students_expected": len(student_ids),
                    "students_passed": len(student_ids),
                    "students_failed": 0,
                }
            ),
            encoding="utf-8",
        )
        (run / "run-metadata.json").write_text(
            json.dumps(
                {
                    "record_type": "model_packet_run",
                    "provider": "synthetic",
                    "engine": "synthetic",
                    "model": model,
                    "input_mode": "text-only",
                    "condition": condition,
                    "experiment_condition": experiment_condition,
                    "task": "grade",
                    "run_id": f"{name}-run",
                    "dry_run": dry_run,
                    "course_id": "dsaa3073",
                    "assessment_id": "hw1",
                    "student_ids": student_ids,
                    "data_snapshot_hash": snapshot,
                    "packet_hash": "c" * 64,
                    "prompt_hash": "d" * 64,
                    "rubric_hash": "e" * 64,
                    "text_source_hash": "f" * 64,
                    "source_run_id": "t1-run",
                    "source_transcription_packet_hash": "a" * 64,
                }
            ),
            encoding="utf-8",
        )
        return run

    @staticmethod
    def _write_prediction_csv_run(root: Path, name: str) -> Path:
        run = root / name
        run.mkdir()
        (run / "predictions.csv").write_text(
            "student_id,question_id,score\n"
            "S001,Q1,8\nS001,Q2a,3\nS001,Q2b,2\n"
            "S002,Q1,6\nS002,Q2a,2\nS002,Q2b,1\n",
            encoding="utf-8",
        )
        return run


if __name__ == "__main__":
    unittest.main()
