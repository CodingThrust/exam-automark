import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.gold_revision import GoldRevisionError, prepare_gold_revision


class GoldRevisionTests(unittest.TestCase):
    def test_prepares_development_only_revision_and_preserves_blank_heldout(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            result = _prepare(paths)
            output = paths["output_root"]
            rows = _read_rows(output / "question-gold.csv")
            values = {(row["student_id"], row["question_id"]): row for row in rows}
            manifest = json.loads((output / "revision-manifest.json").read_text(encoding="utf-8"))

            second = _prepare(paths)
            binding_was_copied = (
                (output / "reviewer-binding.json").read_bytes()
                == paths["binding_path"].read_bytes()
            )
            review_scope = (output / "development-review-students.txt").read_text(
                encoding="utf-8"
            )

        self.assertEqual(result["status"], "prepared")
        self.assertEqual(second["status"], "already_prepared")
        self.assertEqual(result["reset_score_row_count"], 4)
        self.assertEqual(result["inherited_score_row_count"], 2)
        self.assertEqual(result["heldout_score_row_count"], 3)
        for student_id in ("S001", "S002"):
            self.assertEqual(values[(student_id, "Q1")]["score"], "")
            self.assertEqual(values[(student_id, "Q1")]["reviewer"], "")
            self.assertEqual(values[(student_id, "Q1")]["reviewed_at"], "")
            self.assertEqual(values[(student_id, "Q1")]["notes"], "")
            self.assertEqual(values[(student_id, "Q2")]["score"], "2")
        for question_id in ("Q1", "Q2", "Q3"):
            self.assertEqual(values[("S003", question_id)]["score"], "")
            self.assertEqual(values[("S003", question_id)]["reviewer"], "")
            self.assertEqual(values[("S003", question_id)]["reviewed_at"], "")
            self.assertEqual(values[("S003", question_id)]["notes"], "")
        self.assertEqual(manifest["scope"]["reset_question_ids"], ["Q1", "Q3"])
        self.assertEqual(manifest["scope"]["inherited_question_ids"], ["Q2"])
        self.assertFalse(manifest["operations"]["source_submission_content_read"])
        self.assertFalse(manifest["operations"]["heldout_scores_copied_or_scored"])
        self.assertTrue(binding_was_copied)
        self.assertEqual(review_scope, "S001\nS002\n")

    def test_rejects_incomplete_heldout_or_divergent_output_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            rows = _read_rows(paths["source_gold_path"])
            rows[-1]["notes"] = "must stay sealed"
            _write_rows(paths["source_gold_path"], rows)

            with self.assertRaisesRegex(GoldRevisionError, "held-out score cells blank"):
                _prepare(paths)
            self.assertFalse(paths["output_root"].exists())

            rows[-1]["notes"] = ""
            _write_rows(paths["source_gold_path"], rows)
            _prepare(paths)
            (paths["output_root"] / "question-gold.csv").write_text("divergent\n", encoding="utf-8")
            with self.assertRaisesRegex(GoldRevisionError, "divergent private gold revision"):
                _prepare(paths)

    def test_rejects_reset_outside_course_or_output_outside_data_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            with self.assertRaisesRegex(GoldRevisionError, "belong to the course"):
                _prepare(paths, reset_questions=("not-a-question",))
            paths["output_root"] = paths["root"] / "not-private"
            with self.assertRaisesRegex(GoldRevisionError, "source Data boundary"):
                _prepare(paths)

    def test_adds_a_missing_review_scope_only_when_existing_revision_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            _prepare(paths)
            scope_file = paths["output_root"] / "development-review-students.txt"
            scope_file.unlink()

            upgraded = _prepare(paths)

        self.assertEqual(upgraded["status"], "prepared_review_scope")


def _prepare(paths: dict[str, Path], *, reset_questions: tuple[str, ...] = ("Q1", "Q3")) -> dict[str, object]:
    return prepare_gold_revision(
        course_path=paths["course_path"],
        candidate_plan_path=paths["candidate_plan_path"],
        rubric_path=paths["rubric_path"],
        calibration_decisions_path=paths["calibration_path"],
        source_gold_path=paths["source_gold_path"],
        source_binding_path=paths["binding_path"],
        frozen_split_path=paths["split_path"],
        reset_question_ids=reset_questions,
        output_root=paths["output_root"],
        repository_root=paths["root"],
    )


def _make_inputs(root: Path) -> dict[str, Path]:
    course_payload = {
        "course_id": "SYN101",
        "assessment_id": "synthetic_quiz",
        "anonymous_id_pattern": "^S[0-9]{3}$",
        "input_modes": ["image"],
        "score_unit": "points",
        "questions": [
            {"id": "Q1", "max_score": 2, "score_step": 1, "title": "One"},
            {"id": "Q2", "max_score": 2, "score_step": 1, "title": "Two"},
            {"id": "Q3", "max_score": 2, "score_step": 1, "title": "Three"},
        ],
    }
    course_path = root / "course.json"
    course_path.write_text(json.dumps(course_payload), encoding="utf-8")
    public_root = root / "public"
    rubric_path = public_root / "rubric.json"
    calibration_path = public_root / "calibration.json"
    rubric_path.parent.mkdir(parents=True)
    rubric_path.write_text("{}\n", encoding="utf-8")
    calibration_path.write_text("{}\n", encoding="utf-8")
    candidate_plan_path = public_root / "plan.json"
    candidate_plan_path.write_text(
        json.dumps(
            {
                "candidate_status": "human_calibrated_development_candidate_not_frozen_not_run",
                "scope": {
                    "course_id": "SYN101",
                    "assessment_id": "synthetic_quiz",
                    "split": "development_only",
                    "heldout_accessed": False,
                    "model_calls": 0,
                },
                "candidate_bindings": {
                    "course_spec": _binding(course_path, root),
                    "rubric": _binding(rubric_path, root),
                    "course_owner_calibration": _binding(calibration_path, root),
                },
            }
        ),
        encoding="utf-8",
    )
    private_root = root / "Data" / "synthetic"
    source_gold_path = private_root / "source" / "question-gold.csv"
    source_gold_path.parent.mkdir(parents=True)
    rows = []
    for student_id in ("S001", "S002"):
        for question_id in ("Q1", "Q2", "Q3"):
            rows.append(
                {
                    "student_id": student_id,
                    "question_id": question_id,
                    "score": "2",
                    "reviewer": "reviewer",
                    "reviewed_at": "2026-08-20T00:00:00Z",
                    "notes": "synthetic",
                }
            )
    for question_id in ("Q1", "Q2", "Q3"):
        rows.append(
            {
                "student_id": "S003",
                "question_id": question_id,
                "score": "",
                "reviewer": "",
                "reviewed_at": "",
                "notes": "",
            }
        )
    _write_rows(source_gold_path, rows)
    binding_path = private_root / "source" / "reviewer-binding.json"
    binding_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "question_gold_reviewer_binding",
                "course_id": "SYN101",
                "course_assessment_id": "synthetic_quiz",
                "course_spec_sha256": _sha(course_path),
                "scoped_snapshot_assessment_id": "synthetic_quiz",
                "scoped_snapshot_manifest_sha256": "0" * 64,
                "snapshot_record_type": "anonymous_cohort_snapshot",
                "snapshot_manifest_relative_path": "manifests/anonymous-cohort-snapshot.json",
            }
        ),
        encoding="utf-8",
    )
    split_path = private_root / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "frozen",
                "course_id": "SYN101",
                "assessment_id": "synthetic_quiz",
                "student_count": 3,
                "development_count": 2,
                "heldout_count": 1,
                "development_student_ids": ["S001", "S002"],
                "heldout_student_ids": ["S003"],
            }
        ),
        encoding="utf-8",
    )
    return {
        "root": root,
        "course_path": course_path,
        "candidate_plan_path": candidate_plan_path,
        "rubric_path": rubric_path,
        "calibration_path": calibration_path,
        "source_gold_path": source_gold_path,
        "binding_path": binding_path,
        "split_path": split_path,
        "output_root": private_root / "r3-revision",
    }


def _binding(path: Path, root: Path) -> dict[str, str]:
    return {"path": path.relative_to(root).as_posix(), "sha256": _sha(path)}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("student_id", "question_id", "score", "reviewer", "reviewed_at", "notes"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
