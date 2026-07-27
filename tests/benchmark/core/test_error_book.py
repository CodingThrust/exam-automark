import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.cli import main
from benchmark.core.error_book import (
    audit_public_error_summary,
    build_error_book,
    build_public_diagnosis_summary,
    write_error_book,
)
from benchmark.core.packets import directory_digest


RECORD_ROOT = (
    Path(__file__).parents[3]
    / "experiments"
    / "records"
    / "DSAA3071-week5-candidate-v32-error-book"
)


class ErrorBookTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path]:
        packet = root / "packet"
        packet.mkdir()
        course = {
            "course_id": "COURSE1",
            "assessment_id": "week1",
            "questions": [
                {"id": "Q1", "max_score": 10, "score_step": 1},
                {"id": "Q2", "max_score": 10, "score_step": 1},
            ],
            "input_modes": ["text"],
            "anonymous_id_pattern": "^S[0-9]{3}$",
            "score_unit": "points",
        }
        manifest = {
            "course_id": "COURSE1",
            "assessment_id": "week1",
            "condition": "C3",
            "packet_id": "C32-dev-r1",
            "prompt_hash": "1" * 64,
            "rubric_hash": "2" * 64,
            "student_ids": ["S001", "S002"],
            "task": "grade",
            "metadata": {"split": "development"},
        }
        (packet / "course.json").write_text(
            json.dumps(course), encoding="utf-8"
        )
        (packet / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (packet / "prompt.txt").write_text("grade", encoding="utf-8")

        run = root / "run-C32"
        outputs = run / "outputs"
        outputs.mkdir(parents=True)
        self._write_output(
            outputs / "S001.json",
            "S001",
            [
                self._score("Q1", 10, "high", [], "secret exact"),
                self._score(
                    "Q2",
                    4,
                    "high",
                    ["material_error"],
                    "secret severe error",
                ),
            ],
        )
        self._write_output(
            outputs / "S002.json",
            "S002",
            [
                self._score(
                    "Q1",
                    5,
                    "medium",
                    ["needs_manual_review"],
                    "secret mild error",
                ),
                self._score("Q2", 10, "low", [], "secret exact"),
            ],
        )
        (run / "failures.jsonl").write_text("", encoding="utf-8")
        metadata = {
            "course_id": "COURSE1",
            "assessment_id": "week1",
            "condition": "C3",
            "packet_id": "C32-dev-r1",
            "packet_hash": directory_digest(packet),
            "prompt_hash": "1" * 64,
            "rubric_hash": "2" * 64,
            "student_ids": ["S001", "S002"],
            "split": "development",
            "dry_run": False,
            "validation_status": "passed",
            "provider": "provider",
            "model": "latest-model",
            "input_mode": "text-only",
            "skill_version_id": "skill_candidate_v3_2",
            "run_commit": "abc1234",
            "data_snapshot_hash": "3" * 64,
            "text_source_hash": "4" * 64,
        }
        (run / "run-metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )

        gold = root / "primary_scores.csv"
        gold.write_text(
            "\n".join(
                [
                    "student_id,question_id,score,notes",
                    "S001,Q1,10,private",
                    "S001,Q2,10,private",
                    "S002,Q1,3,private",
                    "S002,Q2,10,private",
                    "S999,Q1,0,heldout must be ignored",
                    "S999,Q2,0,heldout must be ignored",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return run, gold, packet

    @staticmethod
    def _score(
        question_id: str,
        score: float,
        confidence: str,
        flags: list[str],
        evidence: str,
    ) -> dict[str, object]:
        return {
            "question_id": question_id,
            "score": score,
            "confidence": confidence,
            "flags": flags,
            "evidence": evidence,
            "extracted_evidence": f"raw {evidence}",
        }

    @staticmethod
    def _write_output(
        path: Path,
        student_id: str,
        scores: list[dict[str, object]],
    ) -> None:
        payload = {
            "student_id": student_id,
            "scores": scores,
            "total": sum(float(row["score"]) for row in scores),
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def _write_diagnoses(path: Path, case_ids: list[str]) -> None:
        annotations = []
        for index, case_id in enumerate(case_ids):
            annotations.append(
                {
                    "case_id": case_id,
                    "primary_cause": (
                        "model_grading_error"
                        if index % 2 == 0
                        else "score_band_calibration"
                    ),
                    "review_confidence": "high",
                    "diagnosis_zh": "中文诊断",
                    "diagnosis_en": "English diagnosis",
                    "recommended_action": "review",
                }
            )
        path.write_text(
            json.dumps(
                {
                    "review_date": "2026-07-27",
                    "review_scope": {
                        "reviewer": "current model",
                        "reviewer_model_id": "not exposed",
                        "taxonomy_status": "provisional",
                    },
                    "annotations": annotations,
                }
            ),
            encoding="utf-8",
        )

    def test_builds_all_disagreements_and_aggregate_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, gold, packet = self._fixture(Path(tmp))
            result = build_error_book(
                run_dir=run,
                gold_path=gold,
                packet_dir=packet,
            )

        private = result.private_book
        public = result.public_summary
        self.assertEqual(len(private["cases"]), 2)
        self.assertEqual(private["population"]["error_pairs"], 2)
        self.assertEqual(private["population"]["severe_error_pairs"], 1)
        self.assertEqual(public["population"]["exact_pairs"], 2)
        self.assertEqual(public["population"]["error_pairs"], 2)
        self.assertEqual(public["metrics"]["question_exact_agreement"], 0.5)
        self.assertEqual(public["metrics"]["question_score_mae"], 2.0)
        self.assertEqual(public["metrics"]["student_total_score_mae"], 4.0)

    def test_public_summary_contains_no_student_ids_or_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, gold, packet = self._fixture(Path(tmp))
            result = build_error_book(
                run_dir=run,
                gold_path=gold,
                packet_dir=packet,
            )

        serialized = json.dumps(result.public_summary)
        self.assertEqual(audit_public_error_summary(result.public_summary), [])
        self.assertNotIn("S001", serialized)
        self.assertNotIn("S999", serialized)
        self.assertNotIn("secret", serialized)

    def test_rejects_non_development_run_before_building_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, gold, packet = self._fixture(Path(tmp))
            metadata_path = run / "run-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["split"] = "test"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "development"):
                build_error_book(
                    run_dir=run,
                    gold_path=gold,
                    packet_dir=packet,
                )

    def test_rejects_incomplete_gold_for_development_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, gold, packet = self._fixture(Path(tmp))
            rows = gold.read_text(encoding="utf-8").splitlines()
            gold.write_text(
                "\n".join(row for row in rows if not row.startswith("S002,Q2"))
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "incomplete"):
                build_error_book(
                    run_dir=run,
                    gold_path=gold,
                    packet_dir=packet,
                )

    def test_technical_failures_are_counted_but_not_grading_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, gold, packet = self._fixture(Path(tmp))
            (run / "failures.jsonl").write_text(
                '{"kind":"retryable_transport_error"}\n',
                encoding="utf-8",
            )
            result = build_error_book(
                run_dir=run,
                gold_path=gold,
                packet_dir=packet,
            )

        self.assertEqual(result.private_book["technical_failures"]["count"], 1)
        self.assertFalse(
            result.private_book["technical_failures"][
                "included_as_grading_cases"
            ]
        )
        self.assertEqual(len(result.private_book["cases"]), 2)

    def test_write_is_deterministic_and_keeps_private_and_public_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, gold, packet = self._fixture(root)
            private = root / "private" / "error-book.json"
            public = root / "public" / "summary.json"
            first = write_error_book(
                run_dir=run,
                gold_path=gold,
                packet_dir=packet,
                private_output=private,
                public_output=public,
            )
            first_private = private.read_bytes()
            first_public = public.read_bytes()
            second = write_error_book(
                run_dir=run,
                gold_path=gold,
                packet_dir=packet,
                private_output=private,
                public_output=public,
            )

            self.assertEqual(first, second)
            self.assertEqual(first_private, private.read_bytes())
            self.assertEqual(first_public, public.read_bytes())
            self.assertIn("S001", private.read_text(encoding="utf-8"))
            self.assertNotIn("S001", public.read_text(encoding="utf-8"))

    def test_write_rejects_same_private_and_public_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, gold, packet = self._fixture(root)
            output = root / "same.json"

            with self.assertRaisesRegex(ValueError, "different paths"):
                write_error_book(
                    run_dir=run,
                    gold_path=gold,
                    packet_dir=packet,
                    private_output=output,
                    public_output=output,
                )

    def test_cli_writes_both_outputs_and_reports_privacy_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, gold, packet = self._fixture(root)
            private = root / "private.json"
            public = root / "public.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "build-error-book",
                        "--run-dir",
                        str(run),
                        "--gold",
                        str(gold),
                        "--packet",
                        str(packet),
                        "--private-output",
                        str(private),
                        "--public-output",
                        str(public),
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(private.exists())
            self.assertTrue(public.exists())
            self.assertEqual(payload["error_pairs"], 2)
            self.assertEqual(payload["privacy_audit"], "passed")

    def test_builds_public_diagnosis_summary_only_after_complete_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, gold, packet = self._fixture(root)
            private = root / "private.json"
            public = root / "public.json"
            result = write_error_book(
                run_dir=run,
                gold_path=gold,
                packet_dir=packet,
                private_output=private,
                public_output=public,
            )
            diagnoses = root / "diagnoses.json"
            self._write_diagnoses(
                diagnoses,
                [case["case_id"] for case in result.private_book["cases"]],
            )

            summary = build_public_diagnosis_summary(
                private_book_path=private,
                diagnoses_path=diagnoses,
            )

        self.assertTrue(summary["review"]["all_error_cases_reviewed"])
        self.assertEqual(summary["review"]["case_count"], 2)
        self.assertEqual(
            {row["primary_cause"] for row in summary["primary_cause_counts"]},
            {"model_grading_error", "score_band_calibration"},
        )
        serialized = json.dumps(summary)
        self.assertNotIn("S001", serialized)
        self.assertNotIn("secret", serialized)
        self.assertEqual(audit_public_error_summary(summary), [])

    def test_rejects_incomplete_case_diagnoses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, gold, packet = self._fixture(root)
            private = root / "private.json"
            public = root / "public.json"
            result = write_error_book(
                run_dir=run,
                gold_path=gold,
                packet_dir=packet,
                private_output=private,
                public_output=public,
            )
            diagnoses = root / "diagnoses.json"
            self._write_diagnoses(
                diagnoses,
                [result.private_book["cases"][0]["case_id"]],
            )

            with self.assertRaisesRegex(ValueError, "cover every"):
                build_public_diagnosis_summary(
                    private_book_path=private,
                    diagnoses_path=diagnoses,
                )

    def test_diagnosis_summary_cli_writes_public_aggregate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, gold, packet = self._fixture(root)
            private = root / "private.json"
            raw_public = root / "raw-public.json"
            result = write_error_book(
                run_dir=run,
                gold_path=gold,
                packet_dir=packet,
                private_output=private,
                public_output=raw_public,
            )
            diagnoses = root / "diagnoses.json"
            self._write_diagnoses(
                diagnoses,
                [case["case_id"] for case in result.private_book["cases"]],
            )
            summary_path = root / "diagnosis-summary.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "summarize-error-book-diagnoses",
                        "--private-book",
                        str(private),
                        "--diagnoses",
                        str(diagnoses),
                        "--public-output",
                        str(summary_path),
                    ]
                )
            payload = json.loads(stdout.getvalue())

            self.assertEqual(code, 0)
            self.assertTrue(summary_path.exists())
            self.assertEqual(payload["case_count"], 2)
            self.assertEqual(payload["privacy_audit"], "passed")


class PublicSummaryAuditTests(unittest.TestCase):
    def test_rejects_forbidden_keys_ids_and_absolute_paths(self):
        findings = audit_public_error_summary(
            {
                "student_id": "S001",
                "nested": {
                    "safe_name": "C:\\private\\case.json",
                    "evidence": "not public",
                },
            }
        )

        self.assertTrue(any("forbidden key" in finding for finding in findings))
        self.assertTrue(any("student id" in finding for finding in findings))
        self.assertTrue(any("absolute path" in finding for finding in findings))


class CandidateV32ErrorBookRecordTests(unittest.TestCase):
    def test_committed_public_json_is_privacy_safe(self):
        for name in ("public-summary.json", "diagnosis-summary.json"):
            payload = json.loads((RECORD_ROOT / name).read_text(encoding="utf-8"))
            self.assertEqual(
                audit_public_error_summary(payload),
                [],
                msg=name,
            )

    def test_committed_counts_cover_the_complete_development_error_set(self):
        score_summary = json.loads(
            (RECORD_ROOT / "public-summary.json").read_text(encoding="utf-8")
        )
        diagnosis_summary = json.loads(
            (RECORD_ROOT / "diagnosis-summary.json").read_text(encoding="utf-8")
        )

        self.assertEqual(score_summary["population"]["student_question_pairs"], 70)
        self.assertEqual(score_summary["population"]["error_pairs"], 33)
        self.assertEqual(score_summary["population"]["severe_error_pairs"], 16)
        self.assertEqual(diagnosis_summary["review"]["case_count"], 33)
        self.assertTrue(
            diagnosis_summary["review"]["all_error_cases_reviewed"]
        )
        self.assertEqual(
            sum(
                row["error_pairs"]
                for row in diagnosis_summary["primary_cause_counts"]
            ),
            33,
        )

    def test_committed_analysis_and_suggestions_are_fully_bilingual(self):
        for name in ("ERROR-ANALYSIS.md", "MODIFICATION-SUGGESTIONS.md"):
            text = (RECORD_ROOT / name).read_text(encoding="utf-8")
            self.assertIn("## 中文版", text, msg=name)
            self.assertIn("## English Version", text, msg=name)
        settlement = (
            Path(__file__).parents[3]
            / "experiments"
            / "records"
            / "weekly-todo-integration-2026-07"
            / "TASK8-ZULIP-SETTLEMENT.md"
        ).read_text(encoding="utf-8")
        self.assertIn("## 中文", settlement)
        self.assertIn("## English", settlement)


if __name__ == "__main__":
    unittest.main()
