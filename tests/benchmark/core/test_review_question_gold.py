import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.readiness_scaffolding import initialize_blank_gold
from benchmark.core.schema import CourseSpec
from benchmark.core.scoped_anonymous_images import (
    SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SNAPSHOT_RECORD_TYPE,
    SNAPSHOT_SCHEMA_VERSION,
)
from scripts.review_question_gold import GoldReviewStore, next_incomplete_student_index


class QuestionGoldReviewTests(unittest.TestCase):
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


def _store(paths: dict[str, Path]) -> GoldReviewStore:
    return GoldReviewStore(
        course_path=paths["course_path"],
        scoped_image_root=paths["snapshot_root"],
        binding_path=paths["binding_path"],
        gold_path=paths["gold_path"],
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


if __name__ == "__main__":
    unittest.main()
