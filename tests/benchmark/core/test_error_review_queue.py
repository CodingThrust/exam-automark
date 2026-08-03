import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.core.error_review_queue import (
    build_root_cause_review_queue,
    empty_human_review_document,
    load_rubric_review_context,
    update_human_review_document,
    validate_human_review_document,
    validate_root_cause_review_queue,
    write_root_cause_review_queue,
)
from benchmark.core.scoped_anonymous_images import (
    SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SNAPSHOT_RECORD_TYPE,
    SNAPSHOT_SCHEMA_VERSION,
)


REPO_ROOT = Path(__file__).parents[3]
REVIEWER_SCRIPT = REPO_ROOT / "scripts" / "review_error_cases.py"


def _load_reviewer_module():
    spec = importlib.util.spec_from_file_location("review_error_cases_test", REVIEWER_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ErrorReviewQueueTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[dict[str, Path], Path, Path]:
        snapshot_root = root / "snapshot"
        image_paths = []
        for student_id in ("S001", "S002"):
            relative = f"anonymized_pages/{student_id}/{student_id}-p02.png"
            image_path = snapshot_root / relative
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(b"synthetic anonymous image " + student_id.encode())
            image_paths.append(
                {
                    "anonymous_id": student_id,
                    "page_suffix": "p02",
                    "snapshot_image": relative,
                    "sha256": _sha256_file(image_path),
                    "bytes": image_path.stat().st_size,
                }
            )
        manifest_path = snapshot_root / SNAPSHOT_MANIFEST_RELATIVE_PATH
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "record_type": SNAPSHOT_RECORD_TYPE,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "assessment_id": "legacy-week4-label",
            "images": image_paths,
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        snapshot_hash = _sha256_file(manifest_path)

        rubric_path = root / "rubric.json"
        rubric_path.write_text(
            json.dumps(
                {
                    "course_id": "DSAA3071",
                    "assessment_id": "week4",
                    "questions": [
                        {
                            "id": "Q7",
                            "expected": "Expected Q7 answer.",
                            "full_credit_rule": "Q7 full-credit rule.",
                            "material_errors": [],
                            "score_bands": {"full": {"minimum": 15, "maximum": 15}},
                            "scoring_elements": [],
                        },
                        {
                            "id": "Q8",
                            "expected": "Expected Q8 answer.",
                            "full_credit_rule": "Q8 full-credit rule.",
                            "material_errors": [],
                            "score_bands": {"full": {"minimum": 15, "maximum": 15}},
                            "scoring_elements": [],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        common = {
            "course_id": "DSAA3071",
            "assessment_id": "week4",
            "gold_sha256": "1" * 64,
            "data_snapshot_sha256": snapshot_hash,
            "prompt_sha256": "2" * 64,
            "rubric_sha256": _sha256_file(rubric_path),
        }
        books = {
            "codex_m1": [
                _case("M1-1", "S001", "Q7", 10, 0),
                _case("M1-2", "S002", "Q7", 10, 0),
                _case("M1-3", "S001", "Q8", 10, 0),
                _case("M1-4", "S002", "Q8", 10, 0),
            ],
            "codex_g1": [
                _case("G1-1", "S001", "Q7", 10, 0),
                _case("G1-2", "S002", "Q7", 10, 15),
                _case("G1-3", "S001", "Q8", 10, 0),
                _case("G1-4", "S002", "Q8", 10, 15),
            ],
            "deepseek_g1": [
                _case("D1-1", "S001", "Q7", 10, 0),
                _case("D1-3", "S001", "Q8", 10, 0),
            ],
        }
        paths: dict[str, Path] = {}
        for condition_id, cases in books.items():
            path = root / f"{condition_id}.private.json"
            path.write_text(
                json.dumps(
                    {
                        "record_type": "grading_error_book_private",
                        "schema_version": 1,
                        "scope": {
                            "split": "development",
                            "selection_rule": "all student-question pairs with predicted_score != gold_score",
                        },
                        "population": {
                            "students": 2,
                            "student_question_pairs": 4,
                            "error_pairs": len(cases),
                        },
                        "technical_failures": {
                            "count": 0,
                            "included_as_grading_cases": False,
                        },
                        "provenance": {
                            **common,
                            "run_id": f"{condition_id}-run",
                            "provider": (
                                "test-deepseek"
                                if condition_id == "deepseek_g1"
                                else "test-codex"
                            ),
                            "model": (
                                "test-deepseek-model"
                                if condition_id == "deepseek_g1"
                                else "test-codex-model"
                            ),
                            "input_mode": "image" if condition_id == "codex_m1" else "text",
                            "skill_version_id": "skill-v1",
                            "output_set_sha256": "4" * 64,
                            "text_source_sha256": "5" * 64,
                        },
                        "cases": cases,
                    }
                ),
                encoding="utf-8",
            )
            paths[condition_id] = path
        return paths, snapshot_root, rubric_path

    def test_builds_diverse_private_queue_and_binds_human_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, snapshot_root, rubric_path = self._fixture(root)
            queue = build_root_cause_review_queue(
                sources=sources,
                question_ids=["Q7", "Q8"],
                page_suffix_by_question={"Q7": "p02", "Q8": "p02"},
                rubric_context=load_rubric_review_context(
                    rubric_path, question_ids=["Q7", "Q8"]
                ),
                items_per_question=2,
            )
            validate_root_cause_review_queue(queue)
            self.assertEqual(len(queue["items"]), 4)
            self.assertEqual(
                [item["question_id"] for item in queue["items"]],
                ["Q7", "Q7", "Q8", "Q8"],
            )
            self.assertTrue(queue["items"][0]["selection"]["all_conditions_have_score_error"])
            self.assertEqual(
                queue["items"][1]["selection"]["m1_vs_codex_g1_score_delta"], 15.0
            )
            exact_view = next(
                view
                for item in queue["items"]
                if item["anonymous_student_id"] == "S002" and item["question_id"] == "Q7"
                for view in item["condition_views"]
                if view["condition_id"] == "deepseek_g1"
            )
            self.assertTrue(exact_view["matches_gold"])
            self.assertEqual(exact_view["predicted_score"], 10.0)

            queue_path = root / "root-cause-review-queue.json"
            write_root_cause_review_queue(
                output_path=queue_path, queue=queue, private_root=root
            )
            document = empty_human_review_document(queue_path=queue_path, queue=queue)
            updated = update_human_review_document(
                document=document,
                queue_path=queue_path,
                queue=queue,
                review={
                    "queue_item_id": queue["items"][0]["queue_item_id"],
                    "review_status": "reviewed",
                    "mechanism_code": "explicit_evidence_omission",
                    "primary_cause": "model_grading_error",
                    "reviewer": "YY",
                    "reviewed_at": "2026-08-03T12:00:00Z",
                    "review_rationale": "Visible evidence was missed in every condition.",
                    "typical_case": True,
                },
            )
            validate_human_review_document(
                document=updated, queue_path=queue_path, queue=queue
            )

            reviewer = _load_reviewer_module()
            store = reviewer.ErrorCaseReviewStore(
                queue_path=queue_path,
                scoped_image_root=snapshot_root,
                review_output=root / "human-root-cause-review.json",
                private_root=root,
            )
            self.assertEqual(store.state()["summary"]["unreviewed_count"], 4)
            self.assertIsNotNone(store.state()["binding"]["warning"])
            image_path = store.image_path(queue["items"][0]["image"]["relative_path"])
            self.assertTrue(image_path.is_file())
            with self.assertRaises(ValueError):
                store.image_path("anonymized_pages/S999/S999-p02.png")
            store.save_review(
                {
                    "queue_item_id": queue["items"][0]["queue_item_id"],
                    "review_status": "reviewed",
                    "mechanism_code": "explicit_evidence_omission",
                    "reviewer": "YY",
                    "reviewed_at": "2026-08-03T12:00:00Z",
                    "review_rationale": "Visible evidence was missed in every condition.",
                    "typical_case": True,
                }
            )
            self.assertEqual(store.state()["summary"]["reviewed_count"], 1)

    def test_rejects_incomparable_source_snapshot_and_invalid_partial_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, _, rubric_path = self._fixture(root)
            mutated = json.loads(sources["deepseek_g1"].read_text(encoding="utf-8"))
            mutated["provenance"]["data_snapshot_sha256"] = "9" * 64
            sources["deepseek_g1"].write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "data_snapshot_sha256"):
                build_root_cause_review_queue(
                    sources=sources,
                    question_ids=["Q7"],
                    page_suffix_by_question={"Q7": "p02"},
                    rubric_context=load_rubric_review_context(
                        rubric_path, question_ids=["Q7"]
                    ),
                )

    def test_needs_more_evidence_cannot_assert_a_mechanism(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, _, rubric_path = self._fixture(root)
            queue = build_root_cause_review_queue(
                sources=sources,
                question_ids=["Q7"],
                page_suffix_by_question={"Q7": "p02"},
                rubric_context=load_rubric_review_context(
                    rubric_path, question_ids=["Q7"]
                ),
            )
            queue_path = root / "queue.json"
            write_root_cause_review_queue(
                output_path=queue_path, queue=queue, private_root=root
            )
            document = empty_human_review_document(queue_path=queue_path, queue=queue)
            with self.assertRaisesRegex(ValueError, "must not assert a mechanism"):
                update_human_review_document(
                    document=document,
                    queue_path=queue_path,
                    queue=queue,
                    review={
                        "queue_item_id": queue["items"][0]["queue_item_id"],
                        "review_status": "needs_more_evidence",
                        "mechanism_code": "explicit_evidence_omission",
                        "primary_cause": "model_grading_error",
                        "reviewer": "YY",
                        "reviewed_at": "2026-08-03T12:00:00Z",
                        "review_rationale": "Need an adjudicator.",
                        "typical_case": False,
                    },
                )

            with self.assertRaisesRegex(ValueError, "cannot be marked as typical"):
                update_human_review_document(
                    document=document,
                    queue_path=queue_path,
                    queue=queue,
                    review={
                        "queue_item_id": queue["items"][0]["queue_item_id"],
                        "review_status": "needs_more_evidence",
                        "mechanism_code": None,
                        "primary_cause": None,
                        "reviewer": "YY",
                        "reviewed_at": "2026-08-03T12:00:00Z",
                        "review_rationale": "Need an adjudicator.",
                        "typical_case": True,
                    },
                )

    def test_provenance_contract_rejects_changed_text_source_and_incomplete_book(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, _, rubric_path = self._fixture(root)
            changed_text = json.loads(
                sources["deepseek_g1"].read_text(encoding="utf-8")
            )
            changed_text["provenance"]["text_source_sha256"] = "8" * 64
            sources["deepseek_g1"].write_text(
                json.dumps(changed_text), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "exact same text source"):
                build_root_cause_review_queue(
                    sources=sources,
                    question_ids=["Q7"],
                    page_suffix_by_question={"Q7": "p02"},
                    rubric_context=load_rubric_review_context(
                        rubric_path, question_ids=["Q7"]
                    ),
                )

            incomplete = json.loads(sources["deepseek_g1"].read_text(encoding="utf-8"))
            incomplete["provenance"]["text_source_sha256"] = "5" * 64
            incomplete["scope"].pop("selection_rule")
            sources["deepseek_g1"].write_text(json.dumps(incomplete), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "complete disagreement coverage"):
                build_root_cause_review_queue(
                    sources=sources,
                    question_ids=["Q7"],
                    page_suffix_by_question={"Q7": "p02"},
                    rubric_context=load_rubric_review_context(
                        rubric_path, question_ids=["Q7"]
                    ),
                )

    def test_no_shared_failure_never_uses_shared_failure_reason(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, _, rubric_path = self._fixture(root)
            selected_case_ids = {
                "codex_m1": "M1-1",
                "codex_g1": "G1-2",
                "deepseek_g1": "D1-1",
            }
            for condition_id, case_id in selected_case_ids.items():
                book = json.loads(sources[condition_id].read_text(encoding="utf-8"))
                book["cases"] = [
                    case for case in book["cases"] if case["case_id"] == case_id
                ]
                book["population"]["error_pairs"] = 1
                sources[condition_id].write_text(json.dumps(book), encoding="utf-8")
            queue = build_root_cause_review_queue(
                sources=sources,
                question_ids=["Q7"],
                page_suffix_by_question={"Q7": "p02"},
                rubric_context=load_rubric_review_context(
                    rubric_path, question_ids=["Q7"]
                ),
            )
            self.assertFalse(
                any(
                    item["selection"]["reason_code"]
                    == "shared_failure_highest_average_error"
                    for item in queue["items"]
                )
            )

    def test_rejects_output_outside_designated_private_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, _, rubric_path = self._fixture(root)
            queue = build_root_cause_review_queue(
                sources=sources,
                question_ids=["Q7"],
                page_suffix_by_question={"Q7": "p02"},
                rubric_context=load_rubric_review_context(
                    rubric_path, question_ids=["Q7"]
                ),
            )
            private_root = root / "private"
            private_root.mkdir()
            with self.assertRaisesRegex(ValueError, "designated private root"):
                write_root_cause_review_queue(
                    output_path=root / "outside.json",
                    queue=queue,
                    private_root=private_root,
                )

    def test_local_reviewer_refuses_an_image_changed_after_startup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, snapshot_root, rubric_path = self._fixture(root)
            queue = build_root_cause_review_queue(
                sources=sources,
                question_ids=["Q7"],
                page_suffix_by_question={"Q7": "p02"},
                rubric_context=load_rubric_review_context(
                    rubric_path, question_ids=["Q7"]
                ),
            )
            queue_path = root / "queue.json"
            write_root_cause_review_queue(
                output_path=queue_path, queue=queue, private_root=root
            )
            reviewer = _load_reviewer_module()
            store = reviewer.ErrorCaseReviewStore(
                queue_path=queue_path,
                scoped_image_root=snapshot_root,
                review_output=root / "review.json",
                private_root=root,
            )
            relative_path = queue["items"][0]["image"]["relative_path"]
            image_path = snapshot_root / relative_path
            image_path.write_bytes(b"changed after reviewer startup")
            with self.assertRaisesRegex(ValueError, "image changed"):
                store.image_path(relative_path)


def _case(
    case_id: str,
    student_id: str,
    question_id: str,
    gold_score: float,
    predicted_score: float,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "anonymous_student_id": student_id,
        "question_id": question_id,
        "gold_score": gold_score,
        "predicted_score": predicted_score,
        "absolute_error": abs(predicted_score - gold_score),
        "confidence": "high",
        "flags": ["private model flag"],
        "evidence": "private model rationale",
        "extracted_evidence": "private extracted answer",
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
