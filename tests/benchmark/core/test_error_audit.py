import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.error_audit import (
    build_error_confidence_audit,
    render_error_confidence_markdown,
)
from benchmark.core.error_book import audit_public_error_summary
from benchmark.core.error_book_iteration import validate_error_book_registry
from benchmark.core.cli import main


REPO_ROOT = Path(__file__).parents[3]
RECORD_ROOT = (
    REPO_ROOT
    / "experiments"
    / "records"
    / "DSAA3071-week5-confidence-taxonomy"
)


class ErrorConfidenceAuditTests(unittest.TestCase):
    def _fixture(
        self, root: Path, *, model_flag: str = "needs_manual_review"
    ) -> tuple[Path, Path, Path, Path]:
        run = root / "run"
        outputs = run / "outputs"
        outputs.mkdir(parents=True)
        self._write_output(
            outputs / "S001.json",
            "S001",
            [
                self._score("Q1", "high", []),
                self._score("Q2", "high", []),
            ],
        )
        self._write_output(
            outputs / "S002.json",
            "S002",
            [
                self._score("Q1", "medium", [model_flag]),
                self._score("Q2", "low", ["unclear_region"]),
            ],
        )
        output_hash = self._directory_hash(outputs)
        provenance = {
            "course_id": "COURSE1",
            "assessment_id": "week1",
            "condition": "C3",
            "provider": "provider",
            "model": "model",
            "input_mode": "text-only",
            "skill_version_id": "skill_candidate",
            "run_id": "run-1",
            "run_commit": "abc1234",
            "packet_id": "packet-1",
            "packet_sha256": "1" * 64,
            "output_set_sha256": output_hash,
            "gold_sha256": "2" * 64,
            "prompt_sha256": "3" * 64,
            "rubric_sha256": "4" * 64,
            "data_snapshot_sha256": "5" * 64,
            "text_source_sha256": "6" * 64,
        }
        metadata = {
            "split": "development",
            "dry_run": False,
            "validation_status": "passed",
            "student_ids": ["S001", "S002"],
            "course_id": provenance["course_id"],
            "assessment_id": provenance["assessment_id"],
            "provider": provenance["provider"],
            "model": provenance["model"],
            "input_mode": provenance["input_mode"],
            "skill_version_id": provenance["skill_version_id"],
            "packet_hash": provenance["packet_sha256"],
        }
        (run / "run-metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        population = {
            "students": 2,
            "student_question_pairs": 4,
            "exact_pairs": 2,
            "error_pairs": 2,
            "severe_error_pairs": 1,
        }
        book = {
            "record_type": "grading_error_book_private",
            "scope": {"split": "development"},
            "provenance": provenance,
            "population": population,
            "technical_failures": {
                "count": 0,
                "included_as_grading_cases": False,
            },
            "cases": [
                {
                    "case_id": "DEV-ERR-001",
                    "anonymous_student_id": "S001",
                    "question_id": "Q2",
                    "confidence": "high",
                    "flags": [],
                    "absolute_error": 6.0,
                    "severe_error": True,
                    "direction": "under_score",
                },
                {
                    "case_id": "DEV-ERR-002",
                    "anonymous_student_id": "S002",
                    "question_id": "Q1",
                    "confidence": "medium",
                    "flags": [model_flag],
                    "absolute_error": 2.0,
                    "severe_error": False,
                    "direction": "over_score",
                },
            ],
        }
        private_book = root / "error-book.private.json"
        private_book.write_text(json.dumps(book), encoding="utf-8")
        diagnoses = {
            "annotations": [
                {
                    "case_id": "DEV-ERR-001",
                    "primary_cause": "model_grading_error",
                    "mechanism_code": "unsupported_evidence_credit",
                },
                {
                    "case_id": "DEV-ERR-002",
                    "primary_cause": "model_grading_error",
                    "mechanism_code": "explicit_evidence_omission",
                },
            ]
        }
        diagnoses_path = root / "diagnoses.private.json"
        diagnoses_path.write_text(json.dumps(diagnoses), encoding="utf-8")
        public_summary = {
            "record_type": "grading_error_book_public_summary",
            "scope": {"split": "development"},
            "provenance": provenance,
            "population": population,
        }
        public_summary_path = root / "public-summary.json"
        public_summary_path.write_text(
            json.dumps(public_summary), encoding="utf-8"
        )
        return run, private_book, diagnoses_path, public_summary_path

    def test_builds_confidence_flag_and_mechanism_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, book, diagnoses, summary = self._fixture(Path(tmp))

            result = build_error_confidence_audit(
                run_dir=run,
                private_book_path=book,
                diagnoses_path=diagnoses,
                public_error_summary_path=summary,
            )

        levels = {
            row["confidence"]: row
            for row in result["confidence_audit"]["levels"]
        }
        self.assertEqual(levels["high"]["error_pairs"], 1)
        self.assertEqual(levels["medium"]["error_rate"], 1.0)
        self.assertEqual(
            result["flag_audit"]["any_flag"]["review_pairs"],
            2,
        )
        self.assertEqual(
            {
                row["mechanism_code"]: row["cases"]
                for row in result["error_taxonomy"]["mechanisms"]
            },
            {
                "explicit_evidence_omission": 1,
                "unsupported_evidence_credit": 1,
            },
        )

    def test_public_audit_contains_no_student_ids_or_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, book, diagnoses, summary = self._fixture(Path(tmp))
            result = build_error_confidence_audit(
                run_dir=run,
                private_book_path=book,
                diagnoses_path=diagnoses,
                public_error_summary_path=summary,
            )

        serialized = json.dumps(result)
        self.assertNotIn("S001", serialized)
        self.assertNotIn("S002", serialized)
        self.assertEqual(audit_public_error_summary(result), [])

    def test_public_audit_excludes_freeform_model_flag_text(self):
        freeform_flag = "student wrote EXFILTRATION_SENTINEL"
        with tempfile.TemporaryDirectory() as tmp:
            run, book, diagnoses, summary = self._fixture(
                Path(tmp), model_flag=freeform_flag
            )
            result = build_error_confidence_audit(
                run_dir=run,
                private_book_path=book,
                diagnoses_path=diagnoses,
                public_error_summary_path=summary,
            )

        serialized = json.dumps(result)
        markdown = render_error_confidence_markdown(result)
        self.assertNotIn("EXFILTRATION_SENTINEL", serialized)
        self.assertNotIn("EXFILTRATION_SENTINEL", markdown)
        self.assertFalse(result["flag_audit"]["model_flag_text_published"])

    def test_rejects_output_drift_after_error_book_was_built(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, book, diagnoses, summary = self._fixture(Path(tmp))
            output = run / "outputs" / "S001.json"
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["scores"][0]["flags"] = ["tampered"]
            output.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "output hash"):
                build_error_confidence_audit(
                    run_dir=run,
                    private_book_path=book,
                    diagnoses_path=diagnoses,
                    public_error_summary_path=summary,
                )

    def test_rejects_case_without_fixed_mechanism(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, book, diagnoses, summary = self._fixture(Path(tmp))
            payload = json.loads(diagnoses.read_text(encoding="utf-8"))
            del payload["annotations"][0]["mechanism_code"]
            diagnoses.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "mechanism_code"):
                build_error_confidence_audit(
                    run_dir=run,
                    private_book_path=book,
                    diagnoses_path=diagnoses,
                    public_error_summary_path=summary,
                )

    def test_cli_generates_public_json_and_bilingual_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, book, diagnoses, summary = self._fixture(root)
            public_output = root / "audit.json"
            markdown_output = root / "ANALYSIS.md"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "audit-error-confidence",
                        "--run-dir",
                        str(run),
                        "--private-book",
                        str(book),
                        "--diagnoses",
                        str(diagnoses),
                        "--public-error-summary",
                        str(summary),
                        "--public-output",
                        str(public_output),
                        "--markdown-output",
                        str(markdown_output),
                    ]
                )

            report = markdown_output.read_text(encoding="utf-8")
            result = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(result["privacy_audit"], "passed")
            self.assertTrue(public_output.is_file())
            self.assertIn("## 中文版", report)
            self.assertIn("## English Version", report)
            self.assertIn("explicit_evidence_omission", report)
            self.assertIn("1 个评分对", report)
            self.assertIn("contains 1 pair", report)
            self.assertNotIn("TASK6", report)
            self.assertNotIn("33 个差异", report)
            self.assertNotIn("candidate-v3.3", report)

    @staticmethod
    def _score(
        question_id: str,
        confidence: str,
        flags: list[str],
    ) -> dict[str, object]:
        return {
            "question_id": question_id,
            "score": 1,
            "confidence": confidence,
            "flags": flags,
        }

    @staticmethod
    def _write_output(
        path: Path,
        student_id: str,
        scores: list[dict[str, object]],
    ) -> None:
        path.write_text(
            json.dumps({"student_id": student_id, "scores": scores}),
            encoding="utf-8",
        )

    @staticmethod
    def _directory_hash(path: Path) -> str:
        digest = hashlib.sha256()
        files = (item for item in path.rglob("*") if item.is_file())
        for file_path in sorted(
            files,
            key=lambda item: (
                item.relative_to(path).as_posix().casefold(),
                item.relative_to(path).as_posix(),
            ),
        ):
            digest.update(
                file_path.relative_to(path).as_posix().encode("utf-8")
            )
            digest.update(b"\0")
            digest.update(file_path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()


class CommittedConfidenceAuditTests(unittest.TestCase):
    def test_committed_record_has_expected_counts_and_bilingual_report(self):
        payload = json.loads(
            (RECORD_ROOT / "confidence-taxonomy-summary.json").read_text(
                encoding="utf-8"
            )
        )
        report = (RECORD_ROOT / "ANALYSIS.md").read_text(encoding="utf-8")

        self.assertEqual(payload["population"]["student_question_pairs"], 70)
        self.assertEqual(payload["population"]["error_pairs"], 33)
        self.assertEqual(payload["population"]["severe_error_pairs"], 16)
        self.assertEqual(
            {
                row["skill_update_disposition"]: row["cases"]
                for row in payload["error_taxonomy"][
                    "skill_update_dispositions"
                ]
            },
            {
                "calibration_anchor_only": 10,
                "direct_skill_candidate": 11,
                "paired_multimodal_required": 1,
                "requires_human_adjudication": 11,
            },
        )
        self.assertEqual(audit_public_error_summary(payload), [])
        self.assertIn("## 中文版", report)
        self.assertIn("## English Version", report)

    def test_error_book_registry_requires_confidence_taxonomy_audit(self):
        registry_path = (
            REPO_ROOT
            / "experiments"
            / "records"
            / "grading-skill-error-book-registry.json"
        )
        with tempfile.TemporaryDirectory() as tmp:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["entries"][-1][
                "public_confidence_taxonomy_audit"
            ] = "experiments/records/missing-confidence-audit.json"
            bad_path = Path(tmp) / "registry.json"
            bad_path.write_text(json.dumps(registry), encoding="utf-8")

            findings = validate_error_book_registry(
                repo_root=REPO_ROOT,
                registry_path=bad_path,
            )

        self.assertTrue(
            any(
                "missing public confidence taxonomy audit" in finding
                for finding in findings
            )
        )


if __name__ == "__main__":
    unittest.main()
