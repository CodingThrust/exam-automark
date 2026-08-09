import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.readiness_scaffolding import initialize_blank_gold
from benchmark.core.schema import CourseSpec
from benchmark.core.anonymous_cohort_snapshot import (
    COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    COHORT_SNAPSHOT_RECORD_TYPE,
)
from benchmark.core.scoped_anonymous_images import (
    SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SNAPSHOT_RECORD_TYPE,
    SNAPSHOT_SCHEMA_VERSION,
)
from scripts.review_question_gold import _HTML, GoldReviewStore, next_incomplete_student_index
from scripts.initialize_question_gold_review import initialize_question_gold_review


class QuestionGoldReviewTests(unittest.TestCase):
    def test_initializer_creates_hash_bound_gold_review_files_for_cohort_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_cohort_submission_inputs(Path(tmp))
            output_root = Path(tmp) / "Data" / "synthetic" / "gold-review"
            result = initialize_question_gold_review(
                course_path=paths["course_path"],
                snapshot_root=paths["snapshot_root"],
                output_root=output_root,
            )
            store = GoldReviewStore(
                course_path=paths["course_path"],
                scoped_image_root=paths["snapshot_root"],
                binding_path=Path(result["binding_path"]),
                gold_path=Path(result["gold_path"]),
            )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["student_count"], 1)
        self.assertEqual(store.state()["summary"]["total_score_rows"], 2)

    def test_cohort_submission_snapshot_uses_ordered_whole_submission_without_page_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_cohort_submission_inputs(Path(tmp))
            store = GoldReviewStore(
                course_path=paths["course_path"],
                scoped_image_root=paths["snapshot_root"],
                binding_path=paths["binding_path"],
                gold_path=paths["gold_path"],
            )
            state = store.state()

        self.assertEqual(state["summary"]["student_count"], 1)
        self.assertEqual([page["page_suffix"] for page in state["students"][0]["pages"]], ["p01", "p02"])
        self.assertEqual([page["question_ids"] for page in state["students"][0]["pages"]], [[], []])
        self.assertTrue(state["students"][0]["pages"][0]["page_label"].startswith("Source page 1"))

    def test_state_uses_only_declared_scope_questions_and_approved_snapshot_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            store = _store(paths)
            state = store.state()

            first = state["students"][0]
            self.assertEqual(state["summary"]["student_count"], 2)
            self.assertEqual(state["summary"]["total_score_rows"], 4)
            self.assertEqual(
                [page["page_suffix"] for page in first["pages"]], ["p01", "p03"]
            )
            self.assertEqual(
                [question["question_id"] for question in first["questions"]],
                ["Q1", "Q2"],
            )
            self.assertEqual(first["pages"][0]["question_ids"], ["Q1"])
            self.assertEqual(first["pages"][1]["question_ids"], ["Q2"])
            self.assertTrue(store.image_path(first["pages"][0]["image_path"]).is_file())
            with self.assertRaisesRegex(ValueError, "approved scoped anonymous PNG"):
                store.image_path("anonymized_pages/S001/S001-p02.png")

    def test_score_validation_rejects_off_step_without_changing_gold_then_approves_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            store = _store(paths)
            before = paths["gold_path"].read_bytes()
            invalid_payload = _payload("S001", {"Q1": "2", "Q2": "0.3"})

            with self.assertRaisesRegex(ValueError, "Q2 score is out of range or off step"):
                store.approve_student(invalid_payload)

            self.assertEqual(paths["gold_path"].read_bytes(), before)
            self.assertEqual(list(paths["gold_path"].parent.glob("*.tmp")), [])

            store.approve_student(_payload("S001", {"Q1": "2.0", "Q2": "2.5"}))
            with paths["gold_path"].open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            saved = {(row["student_id"], row["question_id"]): row for row in rows}
            state = store.state()

        self.assertEqual(saved[("S001", "Q1")]["score"], "2")
        self.assertEqual(saved[("S001", "Q2")]["score"], "2.5")
        self.assertEqual(saved[("S001", "Q2")]["reviewer"], "YY")
        self.assertEqual(saved[("S001", "Q2")]["notes"], "synthetic note")
        self.assertEqual(state["summary"]["fully_scored_students"], 1)
        self.assertEqual(state["summary"]["filled_score_rows"], 2)

    def test_draft_state_and_auto_advance_select_next_incomplete_anonymous_student(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            store = _store(paths)

            store.save_draft(_payload("S001", {"Q1": "1", "Q2": ""}))
            after_draft = store.state()
            store.approve_student(_payload("S001", {"Q1": "1", "Q2": "0.5"}))
            after_approval = store.state()

        self.assertEqual(after_draft["summary"]["fully_scored_students"], 0)
        self.assertEqual(after_draft["summary"]["filled_score_rows"], 1)
        self.assertEqual(after_approval["summary"]["fully_scored_students"], 1)
        self.assertEqual(next_incomplete_student_index(after_approval["students"], 0), 1)
        self.assertEqual(next_incomplete_student_index(after_approval["students"], 1), 1)

    def test_students_file_limits_local_ui_but_preserves_complete_gold_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            students_file = Path(tmp) / "development-students.txt"
            students_file.write_text("# frozen development subset\nS002\n", encoding="utf-8")
            store = _store(paths, students_file=students_file)

            state = store.state()
            self.assertEqual([entry["anonymous_id"] for entry in state["students"]], ["S002"])
            self.assertEqual(state["summary"]["student_count"], 1)
            self.assertEqual(state["summary"]["total_score_rows"], 2)
            self.assertEqual(state["summary"]["snapshot_student_count"], 2)
            self.assertEqual(state["summary"]["snapshot_total_score_rows"], 4)
            self.assertTrue(state["summary"]["review_subset"])
            with self.assertRaisesRegex(ValueError, "approved scoped anonymous PNG"):
                store.image_path("anonymized_pages/S001/S001-p01.png")
            with self.assertRaisesRegex(ValueError, "outside this review subset"):
                store.save_draft(_payload("S001", {"Q1": "1", "Q2": ""}))

            store.approve_student(_payload("S002", {"Q1": "2", "Q2": "2.5"}))
            with paths["gold_path"].open(newline="", encoding="utf-8") as handle:
                saved = {
                    (row["student_id"], row["question_id"]): row
                    for row in csv.DictReader(handle)
                }

        self.assertEqual(len(saved), 4)
        self.assertEqual(saved[("S001", "Q1")]["score"], "")
        self.assertEqual(saved[("S001", "Q2")]["score"], "")
        self.assertEqual(saved[("S002", "Q1")]["score"], "2")
        self.assertEqual(saved[("S002", "Q2")]["score"], "2.5")

    def test_local_ui_explains_review_subset_and_has_non_destructive_rotation_controls(self):
        self.assertIn('id="review-scope"', _HTML)
        self.assertIn("review_subset", _HTML)
        self.assertIn("rotationStorageKey", _HTML)
        self.assertIn("drawPage", _HTML)
        self.assertIn("Left", _HTML)
        self.assertIn("Right", _HTML)
        self.assertIn("Reset", _HTML)
        self.assertIn("grid-template-columns:minmax(0,1fr)", _HTML)
        self.assertIn("openNativeImageViewer", _HTML)
        self.assertIn("Full resolution", _HTML)

    def test_students_file_rejects_empty_duplicate_invalid_or_outside_snapshot_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            students_file = Path(tmp) / "review-students.txt"
            for contents, message in (
                ("# comments only\n\n", "at least one anonymous student ID"),
                ("S001\nS001\n", "only once"),
                ("not-an-anonymous-id\n", "invalid anonymous student ID"),
                ("S999\n", "outside the scoped snapshot"),
            ):
                students_file.write_text(contents, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    _store(paths, students_file=students_file)

    def test_students_file_does_not_bypass_full_snapshot_or_gold_coverage_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            students_file = Path(tmp) / "review-students.txt"
            students_file.write_text("S002\n", encoding="utf-8")
            full_gold = paths["gold_path"].read_bytes()

            with paths["gold_path"].open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            with paths["gold_path"].open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
                writer.writeheader()
                writer.writerows(row for row in rows if row["student_id"] != "S001")
            with self.assertRaisesRegex(ValueError, "cover exactly the snapshot's anonymous students"):
                _store(paths, students_file=students_file)

            paths["gold_path"].write_bytes(full_gold)
            manifest_path = paths["snapshot_root"] / SNAPSHOT_MANIFEST_RELATIVE_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["images"] = [
                entry
                for entry in manifest["images"]
                if not (
                    entry["anonymous_id"] == "S001"
                    and entry["page_suffix"] == "p03"
                )
            ]
            manifest["image_count"] = len(manifest["images"])
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            _write_binding(paths)
            with self.assertRaisesRegex(ValueError, "incomplete page scope for anonymous student S001"):
                _store(paths, students_file=students_file)

    def test_rejects_gold_table_outside_private_snapshot_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _make_inputs(root)
            outside_gold = root / "tracked-looking-gold.csv"
            outside_gold.write_bytes(paths["gold_path"].read_bytes())

            with self.assertRaisesRegex(ValueError, "private-data boundary"):
                GoldReviewStore(
                    course_path=paths["course_path"],
                    scoped_image_root=paths["snapshot_root"],
                    binding_path=paths["binding_path"],
                    gold_path=outside_gold,
                )

    def test_rejects_unknown_non_page_mapping_entry_but_accepts_basis_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            self.assertEqual(_store(paths).state()["summary"]["student_count"], 2)
            payload = json.loads(paths["course_path"].read_text(encoding="utf-8"))
            payload["page_mapping"]["unexpected"] = "not permitted"
            paths["course_path"].write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "keys must use the pNN"):
                _store(paths)

    def test_binding_accepts_only_the_explicit_source_snapshot_assessment_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            manifest_path = paths["snapshot_root"] / SNAPSHOT_MANIFEST_RELATIVE_PATH
            snapshot_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            snapshot_payload["assessment_id"] = "synthetic_full_source"
            manifest_path.write_text(json.dumps(snapshot_payload), encoding="utf-8")
            _write_binding(paths, snapshot_assessment_id="synthetic_full_source")

            self.assertEqual(_store(paths).state()["assessment"]["assessment_id"], "synthetic_question_gold")

            snapshot_payload["assessment_id"] = "undeclared_other_snapshot"
            manifest_path.write_text(json.dumps(snapshot_payload), encoding="utf-8")
            _write_binding(paths, snapshot_assessment_id="synthetic_full_source")
            with self.assertRaisesRegex(ValueError, "exact ID declared"):
                _store(paths)

    def test_binding_rejects_changed_course_or_snapshot_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_inputs(Path(tmp))
            course_payload = json.loads(paths["course_path"].read_text(encoding="utf-8"))
            course_payload["questions"][0]["title"] = "changed after binding"
            paths["course_path"].write_text(json.dumps(course_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "course_spec_sha256"):
                _store(paths)

            _write_binding(paths)
            manifest_path = paths["snapshot_root"] / SNAPSHOT_MANIFEST_RELATIVE_PATH
            snapshot_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            snapshot_payload["scope"]["scope_id"] = "changed after binding"
            manifest_path.write_text(json.dumps(snapshot_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "scoped_snapshot_manifest_sha256"):
                _store(paths)


def _store(
    paths: dict[str, Path], *, students_file: Path | None = None
) -> GoldReviewStore:
    return GoldReviewStore(
        course_path=paths["course_path"],
        scoped_image_root=paths["snapshot_root"],
        binding_path=paths["binding_path"],
        gold_path=paths["gold_path"],
        students_file=students_file,
    )


def _payload(anonymous_id: str, scores: dict[str, str]) -> dict[str, object]:
    return {
        "anonymous_id": anonymous_id,
        "reviewer": "YY",
        "reviewed_at": "2026-08-03T00:00:00Z",
        "scores": scores,
        "notes": {"Q1": "synthetic note", "Q2": "synthetic note"},
    }


def _make_inputs(root: Path) -> dict[str, Path]:
    course_payload = {
        "course_id": "SYN101",
        "assessment_id": "synthetic_question_gold",
        "anonymous_id_pattern": "^S[0-9]{3}$",
        "input_modes": ["image"],
        "score_unit": "points",
        "questions": [
            {"id": "Q1", "max_score": 2, "score_step": 1, "title": "First"},
            {"id": "Q2", "max_score": 3, "score_step": 0.5, "title": "Second"},
        ],
        "page_mapping": {
            "basis": "synthetic course-owner declaration",
            "p01": {"question_ids": ["Q1"]},
            "p03": {"question_ids": ["Q2"]},
        },
    }
    course_path = root / "course.json"
    course_path.write_text(json.dumps(course_payload), encoding="utf-8")
    snapshot_root = root / "Data" / "synthetic" / "week1" / "scoped"
    entries: list[dict[str, object]] = []
    for anonymous_id in ("S001", "S002"):
        for source_page, suffix in ((1, "p01"), (3, "p03")):
            relative = f"anonymized_pages/{anonymous_id}/{anonymous_id}-{suffix}.png"
            image_path = snapshot_root / relative
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(f"synthetic-{anonymous_id}-{suffix}".encode("ascii"))
            entries.append(
                {
                    "anonymous_id": anonymous_id,
                    "source_page": source_page,
                    "page_suffix": suffix,
                    "snapshot_image": relative,
                    "source_image": relative,
                    "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                    "bytes": image_path.stat().st_size,
                }
            )
    manifest_path = snapshot_root / SNAPSHOT_MANIFEST_RELATIVE_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "record_type": SNAPSHOT_RECORD_TYPE,
                "assessment_id": "synthetic_question_gold",
                "scope": {"scope_id": "synthetic", "page_suffixes": ["p01", "p03"]},
                "student_count": 2,
                "image_count": 4,
                "images": entries,
                "model_run_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    gold_path = root / "Data" / "synthetic" / "week1" / "gold" / "primary.csv"
    initialize_blank_gold(CourseSpec.from_dict(course_payload), ("S001", "S002"), gold_path)
    paths = {
        "course_path": course_path,
        "snapshot_root": snapshot_root,
        "gold_path": gold_path,
    }
    _write_binding(paths)
    return {**paths, "binding_path": root / "reviewer-binding.json"}


def _write_binding(
    paths: dict[str, Path], *, snapshot_assessment_id: str | None = None
) -> None:
    manifest_path = paths["snapshot_root"] / SNAPSHOT_MANIFEST_RELATIVE_PATH
    snapshot_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    binding_path = paths.get("binding_path", paths["course_path"].parent / "reviewer-binding.json")
    binding_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record_type": "question_gold_reviewer_binding",
                "course_id": "SYN101",
                "course_assessment_id": "synthetic_question_gold",
                "course_spec_sha256": hashlib.sha256(paths["course_path"].read_bytes()).hexdigest(),
                "scoped_snapshot_assessment_id": snapshot_assessment_id
                or snapshot_payload["assessment_id"],
                "scoped_snapshot_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


def _make_cohort_submission_inputs(root: Path) -> dict[str, Path]:
    course_payload = {
        "course_id": "SYN101",
        "assessment_id": "synthetic_question_gold",
        "anonymous_id_pattern": "^S[0-9]{3}$",
        "input_modes": ["image"],
        "score_unit": "points",
        "questions": [
            {"id": "Q1", "max_score": 2, "score_step": 1, "title": "First"},
            {"id": "Q2", "max_score": 3, "score_step": 0.5, "title": "Second"},
        ],
    }
    course_path = root / "course.json"
    course_path.write_text(json.dumps(course_payload), encoding="utf-8")
    snapshot_root = root / "Data" / "synthetic" / "cohort"
    images = []
    for source_page in (1, 2):
        relative = f"anonymized_pages/S001/rendered-source-{source_page}.png"
        image = snapshot_root / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(f"synthetic-submission-{source_page}".encode("ascii"))
        images.append(
            {
                "source_page": source_page,
                "snapshot_image": relative,
                "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "bytes": image.stat().st_size,
                "source_snapshot_scope_id": "fixture-v1",
            }
        )
    manifest_path = snapshot_root / COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record_type": COHORT_SNAPSHOT_RECORD_TYPE,
                "assessment_id": "synthetic_question_gold",
                "cohort_id": "fixture-cohort-v1",
                "grading_unit": "anonymous_submission",
                "source_snapshots": [],
                "student_count": 1,
                "image_count": 2,
                "submissions": [
                    {
                        "anonymous_id": "S001",
                        "grading_unit": "anonymous_submission",
                        "missing_question_ids": [],
                        "images": images,
                    }
                ],
                "model_run_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    gold_path = root / "Data" / "synthetic" / "gold" / "primary.csv"
    initialize_blank_gold(CourseSpec.from_dict(course_payload), ("S001",), gold_path)
    binding_path = root / "reviewer-binding.json"
    binding_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "record_type": "question_gold_reviewer_binding",
                "course_id": "SYN101",
                "course_assessment_id": "synthetic_question_gold",
                "course_spec_sha256": hashlib.sha256(course_path.read_bytes()).hexdigest(),
                "scoped_snapshot_assessment_id": "synthetic_question_gold",
                "scoped_snapshot_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "snapshot_record_type": COHORT_SNAPSHOT_RECORD_TYPE,
                "snapshot_manifest_relative_path": COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH.as_posix(),
            }
        ),
        encoding="utf-8",
    )
    return {
        "course_path": course_path,
        "snapshot_root": snapshot_root,
        "gold_path": gold_path,
        "binding_path": binding_path,
    }


if __name__ == "__main__":
    unittest.main()
