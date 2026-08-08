from __future__ import annotations

"""Local-only browser reviewer for anonymous question-level gold scores.

This tool is deliberately a *human* data-entry aid.  It only serves images
already selected into an approved scoped snapshot, writes the already-created
private gold CSV, and binds to ``127.0.0.1`` with a single-session token.  It
does not invoke a model, discover raw submissions, or create a grading packet.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import secrets
import sys
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymization import sha256_file  # noqa: E402
from benchmark.core.anonymous_cohort_snapshot import (  # noqa: E402
    COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    COHORT_SNAPSHOT_RECORD_TYPE,
)
from benchmark.core.readiness_scaffolding import GOLD_TEMPLATE_COLUMNS  # noqa: E402
from benchmark.core.schema import CourseSpec, QuestionSpec  # noqa: E402
from benchmark.core.scoped_anonymous_images import (  # noqa: E402
    SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SNAPSHOT_RECORD_TYPE,
    SNAPSHOT_SCHEMA_VERSION,
)
from benchmark.core.submission_scope_workflow import (  # noqa: E402
    SUBMISSION_SCOPE_SCHEMA_VERSION,
    SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SUBMISSION_SNAPSHOT_RECORD_TYPE,
)


_PAGE_SUFFIX_PATTERN = re.compile(r"^p[0-9]{2,}$")
_SNAPSHOT_IMAGE_PATTERN = re.compile(
    r"^anonymized_pages/(S[0-9]{3})/(S[0-9]{3})-(p[0-9]{2,})\.png$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_NOTE_LENGTH = 2_000
_MAX_REVIEWER_LENGTH = 120
_MAX_TIMESTAMP_LENGTH = 100
_SUPPORTED_SNAPSHOT_MANIFESTS = {
    SNAPSHOT_RECORD_TYPE: SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SUBMISSION_SNAPSHOT_RECORD_TYPE: SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    COHORT_SNAPSHOT_RECORD_TYPE: COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a localhost-only browser UI for human entry of anonymous "
            "question-level gold scores. No model is called."
        )
    )
    parser.add_argument(
        "--course",
        type=Path,
        required=True,
        help="tracked course specification JSON that declares the in-scope questions",
    )
    parser.add_argument(
        "--scoped-image-root",
        type=Path,
        required=True,
        help=(
            "private final-approved anonymous snapshot root (legacy scoped, "
            "submission-level, or cohort-level)"
        ),
    )
    parser.add_argument(
        "--binding",
        type=Path,
        required=True,
        help=(
            "tracked reviewer-binding JSON that pins this course specification "
            "to the exact private scoped-snapshot manifest"
        ),
    )
    parser.add_argument(
        "--gold",
        type=Path,
        required=True,
        help="existing private blank/question-level gold CSV to edit atomically",
    )
    parser.add_argument(
        "--students-file",
        type=Path,
        help=(
            "optional UTF-8 one-anonymous-ID-per-line frozen review subset; "
            "only these students are shown, while the complete snapshot and gold "
            "table are still validated and preserved"
        ),
    )
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    try:
        store = GoldReviewStore(
            course_path=args.course,
            scoped_image_root=args.scoped_image_root,
            binding_path=args.binding,
            gold_path=args.gold,
            students_file=args.students_file,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    access_token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), _handler_class(store, access_token=access_token)
    )
    print(
        "Open this local, single-session URL in a browser (do not share it): "
        f"http://127.0.0.1:{args.port}/?token={access_token}"
    )
    print("This tool is for human gold entry only; no model is called.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Local question-level gold reviewer stopped.")
    finally:
        server.server_close()
    return 0


class GoldReviewStore:
    """Stateful, lock-protected view of one anonymous snapshot and gold table."""

    def __init__(
        self,
        *,
        course_path: Path,
        scoped_image_root: Path,
        binding_path: Path,
        gold_path: Path,
        students_file: Path | None = None,
    ) -> None:
        self.course_path = _require_regular_file(course_path, "course specification")
        self.scoped_image_root = _require_regular_directory(
            scoped_image_root, "scoped image root"
        )
        self.binding_path = _require_regular_file(binding_path, "reviewer binding")
        self.gold_path = _require_regular_file(gold_path, "gold CSV")
        private_boundary = _private_boundary(self.scoped_image_root)
        if not _is_within(self.gold_path, private_boundary):
            raise ValueError(
                "gold CSV must stay under the scoped snapshot's private-data boundary: "
                f"{private_boundary}"
            )
        self._lock = threading.Lock()

        self._course_payload = _load_json_object(self.course_path, "course specification")
        self.course = CourseSpec.from_dict(self._course_payload)
        self._page_questions = (
            _load_page_question_mapping(self._course_payload, self.course)
            if "page_mapping" in self._course_payload
            else {}
        )
        self._binding = _load_reviewer_binding(
            self.binding_path,
            course_path=self.course_path,
            course=self.course,
            scoped_image_root=self.scoped_image_root,
        )
        self._images_by_student = _load_scoped_snapshot(
            self.scoped_image_root,
            self.course,
            page_questions=self._page_questions,
            binding=self._binding,
        )
        self._all_students = tuple(sorted(self._images_by_student))
        self._rows = self._load_and_validate_gold_rows()
        self._students = _load_review_student_ids(
            students_file,
            course=self.course,
            snapshot_students=self._all_students,
        )
        self._allowed_image_paths = frozenset(
            page["image_path"]
            for anonymous_id in self._students
            for page in self._images_by_student[anonymous_id]
        )
        self._gold_sha256 = _file_sha256(self.gold_path)

    def state(self) -> dict[str, Any]:
        """Return only anonymous/scope-limited state needed by the local UI."""

        with self._lock:
            students = []
            filled_score_rows = 0
            fully_scored = 0
            question_map = self.course.question_map
            for anonymous_id in self._students:
                questions = []
                for question_id in self.course.question_ids:
                    row = self._rows[(anonymous_id, question_id)]
                    if row["score"]:
                        filled_score_rows += 1
                    question = question_map[question_id]
                    questions.append(
                        {
                            "question_id": question_id,
                            "title": question.title or question_id,
                            "max_score": question.max_score,
                            "score_step": question.score_step,
                            "score": row["score"],
                            "notes": row["notes"],
                        }
                    )
                completed = all(question["score"] for question in questions)
                if completed:
                    fully_scored += 1
                students.append(
                    {
                        "anonymous_id": anonymous_id,
                        "pages": [dict(page) for page in self._images_by_student[anonymous_id]],
                        "questions": questions,
                        "completed": completed,
                    }
                )
            return {
                "assessment": {
                    "course_id": self.course.course_id,
                    "assessment_id": self.course.assessment_id,
                    "score_unit": self.course.score_unit,
                    "question_count": len(self.course.question_ids),
                },
                "students": students,
                "summary": {
                    "student_count": len(students),
                    "fully_scored_students": fully_scored,
                    "pending_students": len(students) - fully_scored,
                    "filled_score_rows": filled_score_rows,
                    "total_score_rows": len(students) * len(self.course.question_ids),
                    "snapshot_student_count": len(self._all_students),
                    "snapshot_total_score_rows": len(self._all_students)
                    * len(self.course.question_ids),
                },
            }

    def save_draft(self, payload: Mapping[str, Any]) -> None:
        self._save_student(payload, require_complete=False)

    def approve_student(self, payload: Mapping[str, Any]) -> None:
        self._save_student(payload, require_complete=True)

    def image_path(self, relative_path: str) -> Path:
        if relative_path not in self._allowed_image_paths:
            raise ValueError("requested resource is not an approved scoped anonymous PNG")
        candidate = _scoped_regular_image_file(self.scoped_image_root, relative_path)
        if not _is_within(candidate, self.scoped_image_root):
            raise ValueError("image path escapes the scoped image root")
        if candidate.suffix.lower() != ".png":
            raise FileNotFoundError(candidate)
        return candidate

    def _load_and_validate_gold_rows(self) -> dict[tuple[str, str], dict[str, str]]:
        try:
            with self.gold_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                columns = tuple(reader.fieldnames or ())
        except OSError as error:
            raise ValueError(f"cannot read gold CSV: {self.gold_path}") from error
        if columns != GOLD_TEMPLATE_COLUMNS:
            raise ValueError(
                "gold CSV must have exactly the canonical columns: "
                + ", ".join(GOLD_TEMPLATE_COLUMNS)
            )

        expected_pairs = {
            (anonymous_id, question_id)
            for anonymous_id in self._all_students
            for question_id in self.course.question_ids
        }
        by_pair: dict[tuple[str, str], dict[str, str]] = {}
        question_map = self.course.question_map
        for row_number, row in enumerate(rows, start=2):
            anonymous_id = _cell(row, "student_id")
            question_id = _cell(row, "question_id")
            try:
                self.course.validate_student_id(anonymous_id)
            except ValueError as error:
                raise ValueError(
                    f"gold CSV row {row_number} has an invalid anonymous student ID"
                ) from error
            if question_id not in question_map:
                raise ValueError(
                    f"gold CSV row {row_number} has an out-of-scope question_id: {question_id}"
                )
            pair = (anonymous_id, question_id)
            if pair in by_pair:
                raise ValueError(f"gold CSV has a duplicate student/question pair: {pair}")
            score = _parse_optional_score(
                _cell(row, "score"), question_map[question_id], row_number=row_number
            )
            reviewer = _cell(row, "reviewer")
            reviewed_at = _cell(row, "reviewed_at")
            notes = _validate_notes(_cell(row, "notes"))
            if score is None:
                if reviewer or reviewed_at:
                    raise ValueError(
                        f"gold CSV row {row_number} has review metadata but no score"
                    )
            else:
                _validate_reviewer(reviewer)
                _validate_reviewed_at(reviewed_at)
            by_pair[pair] = {
                "student_id": anonymous_id,
                "question_id": question_id,
                "score": score or "",
                "reviewer": reviewer,
                "reviewed_at": reviewed_at,
                "notes": notes,
            }
        actual_pairs = set(by_pair)
        if actual_pairs != expected_pairs:
            missing = sorted(expected_pairs - actual_pairs)
            unexpected = sorted(actual_pairs - expected_pairs)
            parts = []
            if missing:
                parts.append(f"missing={len(missing)}")
            if unexpected:
                parts.append(f"unexpected={len(unexpected)}")
            raise ValueError(
                "gold CSV must cover exactly the snapshot's anonymous students and "
                "the course's in-scope questions (" + "; ".join(parts) + ")"
            )
        return by_pair

    def _save_student(self, payload: Mapping[str, Any], *, require_complete: bool) -> None:
        anonymous_id = _required_text(payload, "anonymous_id")
        reviewer = _required_text(payload, "reviewer")
        reviewed_at = _required_text(payload, "reviewed_at")
        _validate_reviewer(reviewer)
        _validate_reviewed_at(reviewed_at)
        scores = _question_mapping(payload.get("scores"), "scores")
        notes = _question_mapping(payload.get("notes"), "notes")
        expected_question_ids = set(self.course.question_ids)
        if set(scores) != expected_question_ids or set(notes) != expected_question_ids:
            raise ValueError("scores and notes must each contain exactly the in-scope question IDs")

        question_map = self.course.question_map
        parsed_scores = {
            question_id: _parse_optional_score(scores[question_id], question_map[question_id])
            for question_id in self.course.question_ids
        }
        parsed_notes = {
            question_id: _validate_notes(notes[question_id])
            for question_id in self.course.question_ids
        }
        if require_complete and any(score is None for score in parsed_scores.values()):
            raise ValueError(
                "approve requires a valid score for every in-scope question of this student"
            )

        with self._lock:
            if anonymous_id not in self._students:
                raise ValueError("anonymous student ID is outside this review subset")
            for question_id in self.course.question_ids:
                score = parsed_scores[question_id]
                row = self._rows[(anonymous_id, question_id)]
                row["score"] = score or ""
                row["notes"] = parsed_notes[question_id]
                row["reviewer"] = reviewer if score is not None else ""
                row["reviewed_at"] = reviewed_at if score is not None else ""
            self._write_rows_atomically()

    def _write_rows_atomically(self) -> None:
        """Replace the complete private CSV only when it has not changed externally."""

        if _file_sha256(self.gold_path) != self._gold_sha256:
            raise ValueError(
                "gold CSV changed outside this local reviewer; reload it before saving "
                "so no external edit is overwritten"
            )
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream,
            fieldnames=GOLD_TEMPLATE_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        for anonymous_id in self._all_students:
            for question_id in self.course.question_ids:
                writer.writerow(self._rows[(anonymous_id, question_id)])
        encoded = stream.getvalue().encode("utf-8")

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                dir=self.gold_path.parent,
                prefix=f".{self.gold_path.name}.",
                suffix=".tmp",
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.gold_path)
        except Exception:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
            raise
        self._gold_sha256 = hashlib.sha256(encoded).hexdigest()


def _load_review_student_ids(
    students_file: Path | None,
    *,
    course: CourseSpec,
    snapshot_students: Sequence[str],
) -> tuple[str, ...]:
    """Return the optional frozen review subset without weakening full checks.

    The snapshot and gold CSV are always loaded and validated before this
    selection is applied.  A subset therefore only limits what this local UI
    may view or edit; it cannot hide incomplete snapshot coverage or permit a
    partial gold table to be saved.
    """

    if students_file is None:
        return tuple(snapshot_students)

    path = _require_regular_file(students_file, "students file")
    try:
        values = [
            line.strip()
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except OSError as error:
        raise ValueError(f"cannot read students file: {path}") from error
    if not values:
        raise ValueError("students file must contain at least one anonymous student ID")
    if len(values) != len(set(values)):
        duplicates = sorted(
            student_id for student_id in set(values) if values.count(student_id) > 1
        )
        raise ValueError(
            "students file must list each anonymous student ID only once; duplicates: "
            + ", ".join(duplicates)
        )

    for student_id in values:
        try:
            course.validate_student_id(student_id)
        except ValueError as error:
            raise ValueError(
                "students file has an invalid anonymous student ID: " + student_id
            ) from error
    snapshot_student_set = set(snapshot_students)
    outside_snapshot = sorted(set(values) - snapshot_student_set)
    if outside_snapshot:
        raise ValueError(
            "students file names anonymous students outside the scoped snapshot: "
            + ", ".join(outside_snapshot)
        )
    return tuple(sorted(values))


def _load_page_question_mapping(
    payload: Mapping[str, Any], course: CourseSpec
) -> dict[str, tuple[str, ...]]:
    raw_mapping = payload.get("page_mapping")
    if not isinstance(raw_mapping, Mapping) or not raw_mapping:
        raise ValueError("course specification must define a non-empty page_mapping")
    result: dict[str, tuple[str, ...]] = {}
    encountered: list[str] = []
    for page_suffix, value in raw_mapping.items():
        if page_suffix == "basis":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("course page_mapping.basis must be non-empty explanatory text")
            continue
        if not isinstance(page_suffix, str) or not _PAGE_SUFFIX_PATTERN.fullmatch(page_suffix):
            raise ValueError("course page_mapping keys must use the pNN page-suffix form")
        if not isinstance(value, Mapping):
            raise ValueError(f"course page_mapping[{page_suffix}] must be an object")
        raw_question_ids = value.get("question_ids")
        if not isinstance(raw_question_ids, list) or not raw_question_ids:
            raise ValueError(
                f"course page_mapping[{page_suffix}].question_ids must be a non-empty list"
            )
        question_ids = tuple(raw_question_ids)
        if not all(isinstance(question_id, str) for question_id in question_ids):
            raise ValueError(f"course page_mapping[{page_suffix}] question IDs must be text")
        result[page_suffix] = question_ids
        encountered.extend(question_ids)
    if len(encountered) != len(set(encountered)):
        raise ValueError("each in-scope question must map to exactly one snapshot page")
    if set(encountered) != set(course.question_ids):
        raise ValueError(
            "course page_mapping must cover exactly the course's in-scope question IDs"
        )
    return dict(sorted(result.items()))


def _load_scoped_snapshot(
    root: Path,
    course: CourseSpec,
    *,
    page_questions: Mapping[str, tuple[str, ...]],
    binding: "GoldReviewerBinding",
) -> dict[str, tuple[dict[str, Any], ...]]:
    manifest_path = _require_regular_file(
        root / binding.snapshot_manifest_relative_path, "approved snapshot manifest"
    )
    manifest = _load_json_object(manifest_path, "approved snapshot manifest")
    if manifest.get("record_type") != binding.snapshot_record_type:
        raise ValueError("approved snapshot record_type does not match the reviewer binding")
    if manifest.get("assessment_id") != binding.scoped_snapshot_assessment_id:
        raise ValueError(
            "approved snapshot assessment_id does not match the exact ID declared by "
            "the reviewer binding"
        )
    if manifest.get("model_run_allowed") is not False:
        raise ValueError("gold review requires a model-free anonymous image snapshot")
    if binding.snapshot_record_type in {
        SUBMISSION_SNAPSHOT_RECORD_TYPE,
        COHORT_SNAPSHOT_RECORD_TYPE,
    }:
        if manifest.get("schema_version") != SUBMISSION_SCOPE_SCHEMA_VERSION:
            raise ValueError("submission snapshot manifest has an unsupported schema version")
        return _load_submission_level_snapshot(root, course, manifest)
    if manifest.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("scoped snapshot manifest has an unsupported schema version")
    if binding.snapshot_record_type != SNAPSHOT_RECORD_TYPE:
        raise ValueError("reviewer binding declares an unsupported snapshot record type")
    if not page_questions:
        raise ValueError("legacy scoped snapshots require a course page_mapping")
    scope = manifest.get("scope")
    if not isinstance(scope, Mapping):
        raise ValueError("scoped snapshot manifest must contain a scope object")
    declared_suffixes = scope.get("page_suffixes")
    if not isinstance(declared_suffixes, list) or not all(
        isinstance(value, str) and _PAGE_SUFFIX_PATTERN.fullmatch(value)
        for value in declared_suffixes
    ):
        raise ValueError("scoped snapshot manifest has invalid/duplicate page suffixes")
    if len(declared_suffixes) != len(set(declared_suffixes)) or set(declared_suffixes) != set(page_questions):
        raise ValueError(
            "scoped snapshot pages do not exactly match the course page_mapping scope"
        )
    raw_images = manifest.get("images")
    if not isinstance(raw_images, list) or not raw_images:
        raise ValueError("scoped snapshot manifest must contain approved image entries")

    by_student: dict[str, dict[str, dict[str, Any]]] = {}
    for index, entry in enumerate(raw_images, start=1):
        if not isinstance(entry, Mapping):
            raise ValueError(f"scoped snapshot image entry {index} must be an object")
        anonymous_id = entry.get("anonymous_id")
        page_suffix = entry.get("page_suffix")
        relative_path = entry.get("snapshot_image")
        if not isinstance(anonymous_id, str):
            raise ValueError(f"scoped snapshot image entry {index} has no anonymous_id")
        try:
            course.validate_student_id(anonymous_id)
        except ValueError as error:
            raise ValueError(
                f"scoped snapshot image entry {index} has an invalid anonymous ID"
            ) from error
        if not isinstance(page_suffix, str) or page_suffix not in page_questions:
            raise ValueError(
                f"scoped snapshot image entry {index} has an out-of-scope page suffix"
            )
        if not isinstance(relative_path, str):
            raise ValueError(f"scoped snapshot image entry {index} has no snapshot_image")
        match = _SNAPSHOT_IMAGE_PATTERN.fullmatch(relative_path)
        if match is None or match.group(1) != anonymous_id or match.group(2) != anonymous_id or match.group(3) != page_suffix:
            raise ValueError(
                f"scoped snapshot image entry {index} does not use the expected anonymous PNG path"
            )
        try:
            image_path = _scoped_regular_image_file(root, relative_path)
        except ValueError as error:
            raise ValueError(f"scoped snapshot image entry {index} is missing or unsafe")
        if image_path.suffix.lower() != ".png":
            raise ValueError(f"scoped snapshot image entry {index} is not a PNG")
        expected_bytes = entry.get("bytes")
        expected_sha256 = entry.get("sha256")
        if (
            isinstance(expected_bytes, bool)
            or not isinstance(expected_bytes, int)
            or expected_bytes < 0
            or not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_sha256)
        ):
            raise ValueError(f"scoped snapshot image entry {index} has invalid integrity metadata")
        if image_path.stat().st_size != expected_bytes or sha256_file(image_path) != expected_sha256:
            raise ValueError(f"scoped snapshot image entry {index} fails its integrity check")
        student_pages = by_student.setdefault(anonymous_id, {})
        if page_suffix in student_pages:
            raise ValueError(
                f"scoped snapshot has duplicate anonymous/page entry: {anonymous_id}/{page_suffix}"
            )
        student_pages[page_suffix] = {
            "page_suffix": page_suffix,
            "image_path": relative_path,
            "question_ids": list(page_questions[page_suffix]),
        }

    expected_suffixes = set(page_questions)
    if not by_student:
        raise ValueError("scoped snapshot does not contain anonymous students")
    for anonymous_id, pages in by_student.items():
        if set(pages) != expected_suffixes:
            raise ValueError(
                f"scoped snapshot has incomplete page scope for anonymous student {anonymous_id}"
            )
    expected_image_count = len(by_student) * len(expected_suffixes)
    if manifest.get("student_count") != len(by_student) or manifest.get("image_count") != expected_image_count:
        raise ValueError("scoped snapshot student/image count does not match its entries")
    return {
        anonymous_id: tuple(pages[suffix] for suffix in sorted(pages))
        for anonymous_id, pages in by_student.items()
    }


def _load_submission_level_snapshot(
    root: Path, course: CourseSpec, manifest: Mapping[str, Any]
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Load ordered whole-submission images without imposing a page-to-question map."""

    if manifest.get("grading_unit") != "anonymous_submission":
        raise ValueError("submission snapshot must use anonymous_submission grading")
    raw_submissions = manifest.get("submissions")
    if not isinstance(raw_submissions, list) or not raw_submissions:
        raise ValueError("submission snapshot must contain anonymous submission entries")
    by_student: dict[str, tuple[dict[str, Any], ...]] = {}
    seen_images: set[str] = set()
    image_count = 0
    for index, submission in enumerate(raw_submissions, start=1):
        if not isinstance(submission, Mapping):
            raise ValueError(f"submission snapshot entry {index} must be an object")
        anonymous_id = submission.get("anonymous_id")
        if not isinstance(anonymous_id, str) or anonymous_id in by_student:
            raise ValueError("submission snapshot has a duplicate or missing anonymous ID")
        try:
            course.validate_student_id(anonymous_id)
        except ValueError as error:
            raise ValueError("submission snapshot has an invalid anonymous ID") from error
        if submission.get("grading_unit") != "anonymous_submission":
            raise ValueError("submission snapshot entry must use anonymous_submission grading")
        raw_images = submission.get("images")
        if not isinstance(raw_images, list) or not raw_images:
            raise ValueError("submission snapshot entry must contain ordered images")
        pages: list[dict[str, Any]] = []
        previous_source_page = 0
        for image_index, entry in enumerate(raw_images, start=1):
            if not isinstance(entry, Mapping):
                raise ValueError("submission snapshot image entry must be an object")
            source_page = entry.get("source_page")
            if (
                type(source_page) is not int
                or source_page < 1
                or source_page <= previous_source_page
            ):
                raise ValueError("submission snapshot source pages must be positive and ordered")
            previous_source_page = source_page
            relative_path = entry.get("snapshot_image")
            if not isinstance(relative_path, str):
                raise ValueError("submission snapshot image entry has no snapshot_image")
            expected_suffix = f"p{source_page:02d}"
            if relative_path in seen_images:
                raise ValueError("submission snapshot has a duplicate image path")
            seen_images.add(relative_path)
            try:
                image_path = _scoped_regular_image_file(root, relative_path)
            except ValueError as error:
                raise ValueError("submission snapshot image entry is missing or unsafe") from error
            expected_bytes = entry.get("bytes")
            expected_sha256 = entry.get("sha256")
            if (
                isinstance(expected_bytes, bool)
                or not isinstance(expected_bytes, int)
                or expected_bytes < 1
                or not isinstance(expected_sha256, str)
                or not _SHA256_PATTERN.fullmatch(expected_sha256)
                or image_path.stat().st_size != expected_bytes
                or sha256_file(image_path) != expected_sha256
            ):
                raise ValueError("submission snapshot image entry fails its integrity check")
            pages.append(
                {
                    "page_suffix": expected_suffix,
                    "image_path": relative_path,
                    "question_ids": [],
                    "page_label": (
                        f"Source page {source_page} — ordered whole-submission evidence; "
                        "no fixed question-to-page mapping"
                    ),
                }
            )
            image_count += 1
        by_student[anonymous_id] = tuple(pages)
    if (
        manifest.get("student_count") != len(by_student)
        or manifest.get("image_count") != image_count
    ):
        raise ValueError("submission snapshot student/image count does not match its entries")
    return dict(sorted(by_student.items()))


@dataclass(frozen=True)
class GoldReviewerBinding:
    scoped_snapshot_assessment_id: str
    scoped_snapshot_manifest_sha256: str
    snapshot_manifest_relative_path: Path
    snapshot_record_type: str


def _load_reviewer_binding(
    path: Path,
    *,
    course_path: Path,
    course: CourseSpec,
    scoped_image_root: Path,
) -> GoldReviewerBinding:
    """Verify the tracked exception that binds a partial course to one snapshot.

    This is intentionally narrower than accepting any snapshot with a matching
    course: the binding is tied to the immutable course file hash, its logical
    assessment ID, one source snapshot assessment ID, and the current snapshot
    manifest hash.
    """

    payload = _load_json_object(path, "reviewer binding")
    schema_version = payload.get("schema_version")
    if schema_version not in {1, 2}:
        raise ValueError("reviewer binding has an unsupported schema version")
    if payload.get("record_type") != "question_gold_reviewer_binding":
        raise ValueError("reviewer binding has an unexpected record type")
    if payload.get("course_id") != course.course_id:
        raise ValueError("reviewer binding course_id does not match the course specification")
    if payload.get("course_assessment_id") != course.assessment_id:
        raise ValueError(
            "reviewer binding course_assessment_id does not match the course specification"
        )
    if payload.get("course_spec_sha256") != sha256_file(course_path):
        raise ValueError("reviewer binding course_spec_sha256 does not match the course file")

    snapshot_assessment_id = payload.get("scoped_snapshot_assessment_id")
    if (
        not isinstance(snapshot_assessment_id, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", snapshot_assessment_id)
    ):
        raise ValueError("reviewer binding scoped_snapshot_assessment_id is invalid")
    declared_manifest_sha256 = payload.get("scoped_snapshot_manifest_sha256")
    if not isinstance(declared_manifest_sha256, str) or not _SHA256_PATTERN.fullmatch(
        declared_manifest_sha256
    ):
        raise ValueError("reviewer binding scoped_snapshot_manifest_sha256 is invalid")
    if schema_version == 1:
        snapshot_record_type = SNAPSHOT_RECORD_TYPE
        manifest_relative_path = SNAPSHOT_MANIFEST_RELATIVE_PATH
    else:
        snapshot_record_type = payload.get("snapshot_record_type")
        if snapshot_record_type not in _SUPPORTED_SNAPSHOT_MANIFESTS:
            raise ValueError("reviewer binding snapshot_record_type is unsupported")
        raw_relative_path = payload.get("snapshot_manifest_relative_path")
        expected_relative_path = _SUPPORTED_SNAPSHOT_MANIFESTS[snapshot_record_type]
        if raw_relative_path != expected_relative_path.as_posix():
            raise ValueError(
                "reviewer binding snapshot_manifest_relative_path is not canonical "
                "for its record type"
            )
        manifest_relative_path = expected_relative_path
    manifest_path = _require_regular_file(
        scoped_image_root / manifest_relative_path, "approved snapshot manifest"
    )
    if sha256_file(manifest_path) != declared_manifest_sha256:
        raise ValueError(
            "reviewer binding scoped_snapshot_manifest_sha256 does not match the "
            "current private scoped snapshot"
        )
    return GoldReviewerBinding(
        scoped_snapshot_assessment_id=snapshot_assessment_id,
        scoped_snapshot_manifest_sha256=declared_manifest_sha256,
        snapshot_manifest_relative_path=manifest_relative_path,
        snapshot_record_type=snapshot_record_type,
    )


def _parse_optional_score(
    value: object, question: QuestionSpec, *, row_number: int | None = None
) -> str | None:
    if not isinstance(value, str):
        raise ValueError(f"{question.id} score must be text")
    text = value.strip()
    if not text:
        return None
    try:
        score = Decimal(text)
        maximum = Decimal(str(question.max_score))
        step = Decimal(str(question.score_step))
    except InvalidOperation as error:
        raise ValueError(_score_error_prefix(question, row_number) + "must be a number") from error
    if not score.is_finite():
        raise ValueError(_score_error_prefix(question, row_number) + "must be finite")
    if score < 0 or score > maximum or score % step != 0:
        raise ValueError(
            _score_error_prefix(question, row_number)
            + f"is out of range or off step (0–{maximum}, step {step})"
        )
    return _canonical_decimal(score)


def _score_error_prefix(question: QuestionSpec, row_number: int | None) -> str:
    return f"gold CSV row {row_number} {question.id} score " if row_number else f"{question.id} score "


def _canonical_decimal(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _question_mapping(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object keyed by question ID")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{label} must map question IDs to text values")
        result[key] = item
    return result


def _validate_reviewer(value: str) -> None:
    if not value or len(value) > _MAX_REVIEWER_LENGTH or "\n" in value or "\r" in value:
        raise ValueError("reviewer must be one non-empty line of at most 120 characters")


def _validate_reviewed_at(value: str) -> None:
    if not value or len(value) > _MAX_TIMESTAMP_LENGTH:
        raise ValueError("reviewed_at must be a non-empty ISO-8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("reviewed_at must be an ISO-8601 timestamp") from error


def _validate_notes(value: str) -> str:
    if len(value) > _MAX_NOTE_LENGTH or "\x00" in value:
        raise ValueError("each note must be at most 2,000 characters and contain no NUL")
    return value


def _cell(row: Mapping[str, str | None], key: str) -> str:
    value = row.get(key)
    return value.strip() if isinstance(value, str) else ""


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    result = value.strip() if isinstance(value, str) else ""
    if not result:
        raise ValueError(f"{key} is required")
    return result


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not readable JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def _require_regular_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a readable regular file: {path}")
    return path.resolve()


def _require_regular_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{label} must be a readable regular directory: {path}")
    return path.resolve()


def _private_boundary(snapshot_root: Path) -> Path:
    for candidate in (snapshot_root, *snapshot_root.parents):
        if candidate.name.lower() == "data":
            return candidate
    return snapshot_root.parent


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scoped_regular_image_file(root: Path, relative_path: str) -> Path:
    """Resolve one manifest-listed PNG without permitting a symlink escape."""

    raw_path = root / Path(relative_path)
    current = raw_path
    while current != root:
        if current.is_symlink():
            raise ValueError("scoped image path contains a symlink")
        current = current.parent
    resolved = raw_path.resolve()
    if not _is_within(resolved, root) or not resolved.is_file():
        raise ValueError("scoped image path is outside the snapshot or missing")
    return resolved


def next_incomplete_student_index(students: Sequence[Mapping[str, Any]], after: int) -> int:
    """Return the next not-fully-scored UI index, wrapping around if needed."""

    if not students:
        raise ValueError("students must not be empty")
    if not 0 <= after < len(students):
        raise ValueError("after must name a current student index")
    for offset in range(1, len(students) + 1):
        index = (after + offset) % len(students)
        if not bool(students[index].get("completed")):
            return index
    return after


def _handler_class(
    store: GoldReviewStore, *, access_token: str
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not self._token_is_valid(request):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
                return
            if request.path == "/":
                self._send_bytes(HTTPStatus.OK, _HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif request.path == "/api/state":
                self._send_json(HTTPStatus.OK, store.state())
            elif request.path.startswith("/images/"):
                try:
                    image_path = store.image_path(unquote(request.path.removeprefix("/images/")))
                except (FileNotFoundError, ValueError):
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "image not found"})
                    return
                self._send_bytes(HTTPStatus.OK, image_path.read_bytes(), "image/png")
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if not self._token_is_valid(request):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid local access token"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("request body must be between 1 and 1,000,000 bytes")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError("JSON object required")
                if request.path == "/api/save-draft":
                    store.save_draft(payload)
                elif request.path == "/api/approve":
                    store.approve_student(payload)
                else:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self._send_json(HTTPStatus.OK, {"status": "saved"})

        def _token_is_valid(self, request: Any) -> bool:
            provided = parse_qs(request.query, keep_blank_values=True).get("token", [""])[0]
            return isinstance(provided, str) and secrets.compare_digest(provided, access_token)

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send_json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
            self._send_bytes(
                status,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


_HTML = r"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><title>匿名 Gold 录入 / Anonymous gold review</title>
<style>
body { font:14px system-ui,sans-serif; margin:16px; color:#18212f; background:#f7f9fc; }
#top { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
button,select,input,textarea { font:inherit; padding:6px 8px; } button { cursor:pointer; }
#main { display:grid; grid-template-columns:minmax(0,1fr) 370px; gap:16px; align-items:start; }
#images { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; }
.image-card,#panel { background:white; border:1px solid #d4dce8; padding:12px; border-radius:8px; }
.image-card img { width:100%; border:1px solid #9aa8bc; background:white; display:block; }
.hint { color:#526175; line-height:1.55; } .warning { color:#8a5600; font-weight:600; }
.ok { color:#20724d; font-weight:600; } .question { border-top:1px solid #e3e8f0; padding:10px 0; }
.question:first-child { border-top:0; } .question input { width:100px; } textarea { width:100%; min-height:42px; box-sizing:border-box; }
#message { white-space:pre-wrap; } .status-complete { color:#20724d; } .status-pending { color:#8a5600; }
@media (max-width:900px) { #main { grid-template-columns:1fr; } }
</style>
<body><h1>匿名 Gold 录入 / Anonymous question-level gold review</h1>
<p class="hint">仅在本机运行。请根据已终审的匿名图片人工录入本次 scope 内的逐题 gold 分数；页面不包含原始身份，也不会调用模型。保存会原子替换私有 gold CSV。<br>Local only. Enter human gold scores only for the frozen in-scope questions. No raw identity and no model call are involved.</p>
<p id="binding" class="ok">Scoped anonymous snapshot and private gold table loaded.</p>
<div id="top"><label>审核人 / Reviewer <input id="reviewer" placeholder="姓名或缩写 / name or initials"></label><span id="summary"></span><button id="prev">上一位 / Previous</button><select id="student"></select><button id="next">下一位 / Next</button></div>
<div id="main"><div><div id="images"></div><p class="hint">只显示课程 scope 声明的匿名页；例如 p01 对应 Q1–Q4，p03 对应 Q9–Q10。请不要根据未显示页面给分。<br>Only approved pages declared by the course scope are shown; do not score from unseen pages.</p></div>
<div id="panel"><h2 id="title"></h2><p class="hint">填写分数后可先保存草稿；“保存并核准”要求该匿名学生所有 scope 内题目均有合法分数，并自动跳到下一位未完成学生。<br>Save draft keeps partial work. Save & approve requires valid scores for every in-scope question and advances automatically.</p><div id="questions"></div><button id="draft">保存草稿 / Save draft</button> <button id="approve">保存并核准 / Save & approve</button><p id="message"></p></div></div>
<script>
let state,index=0;
const $=s=>document.querySelector(s), now=()=>new Date().toISOString();
const token=new URLSearchParams(location.search).get('token');
function protectedPath(path){const url=new URL(path,location.origin);url.searchParams.set('token',token||'');return url.pathname+url.search;}
async function api(path,method='GET',body){const r=await fetch(protectedPath(path),{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const j=await r.json();if(!r.ok)throw Error(j.error||'request failed');return j;}
function student(){return state.students[index]}
function nextIncomplete(after){for(let offset=1;offset<=state.students.length;offset++){const i=(after+offset)%state.students.length;if(!state.students[i].completed)return i}return after}
async function load(keep=true,advanceAfter=null){const old=keep&&state?state.students[index]?.anonymous_id:null;state=await api('/api/state');const s=state.summary;const subset=s.student_count===s.snapshot_student_count?'':` (review subset / 审核子集: ${s.student_count}/${s.snapshot_student_count})`;$('#summary').textContent=`${s.fully_scored_students}/${s.student_count} students complete; ${s.filled_score_rows}/${s.total_score_rows} score rows saved${subset}`;const select=$('#student');select.replaceChildren();state.students.forEach((entry,i)=>{const option=document.createElement('option');option.value=i;option.textContent=`${entry.anonymous_id} — ${entry.completed?'complete / 已完成':'pending / 待完成'}`;select.append(option)});if(advanceAfter!==null){index=nextIncomplete(advanceAfter)}else if(old){const found=state.students.findIndex(entry=>entry.anonymous_id===old);if(found>=0)index=found}render();}
function render(){const entry=student();$('#student').value=index;$('#title').textContent=`${entry.anonymous_id} — ${entry.completed?'complete / 已核准':'pending / 待完成'}`;const images=$('#images');images.replaceChildren();entry.pages.forEach(page=>{const card=document.createElement('section');card.className='image-card';const heading=document.createElement('h3');heading.textContent=`${page.page_suffix}: ${page.question_ids.join(', ')}`;const image=document.createElement('img');image.alt=`${entry.anonymous_id} ${page.page_suffix} anonymous assessment page`;image.src=protectedPath('/images/'+encodeURIComponent(page.image_path));card.append(heading,image);images.append(card)});const questions=$('#questions');questions.replaceChildren();entry.questions.forEach(question=>{const card=document.createElement('div');card.className='question';const heading=document.createElement('strong');heading.textContent=`${question.question_id} — ${question.title}`;const scoreLabel=document.createElement('label');scoreLabel.textContent=`Score / 分数 (0–${question.max_score}, step ${question.score_step}) `;const score=document.createElement('input');score.type='number';score.id=`score-${question.question_id}`;score.min='0';score.max=String(question.max_score);score.step=String(question.score_step);score.value=question.score;score.autocomplete='off';scoreLabel.append(score);const noteLabel=document.createElement('label');noteLabel.textContent='Notes / 备注';const notes=document.createElement('textarea');notes.id=`notes-${question.question_id}`;notes.maxLength=2000;notes.value=question.notes;noteLabel.append(notes);card.append(heading,document.createElement('br'),scoreLabel,document.createElement('br'),noteLabel);questions.append(card)});}
function payload(){const entry=student(),scores={},notes={};entry.questions.forEach(question=>{scores[question.question_id]=$(`#score-${question.question_id}`).value.trim();notes[question.question_id]=$(`#notes-${question.question_id}`).value;});return {anonymous_id:entry.anonymous_id,reviewer:$('#reviewer').value.trim(),reviewed_at:now(),scores,notes};}
async function save(kind){const reviewer=$('#reviewer').value.trim();if(!reviewer){alert('请先填写审核人姓名或缩写 / Enter reviewer name or initials first.');return}const before=index;try{await api(kind==='approve'?'/api/approve':'/api/save-draft','POST',payload());await load(false,kind==='approve'?before:null);$('#message').textContent=kind==='approve'?'已原子保存并核准；已跳到下一位未完成学生。\nSaved atomically and approved; moved to the next incomplete student.':'草稿已原子保存。\nDraft saved atomically.'}catch(error){$('#message').textContent=error.message}};
$('#student').onchange=e=>{index=+e.target.value;render()};$('#prev').onclick=()=>{index=Math.max(0,index-1);render()};$('#next').onclick=()=>{index=Math.min(state.students.length-1,index+1);render()};$('#draft').onclick=()=>save('draft');$('#approve').onclick=()=>save('approve');if(!token){$('#binding').textContent='此页面需要本次本地会话 token / This page requires its single-session local access token.';$('#binding').className='warning';}else{load(false).catch(error=>{$('#binding').textContent=error.message;$('#binding').className='warning';});}
</script></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
