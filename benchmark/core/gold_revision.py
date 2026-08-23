"""Prepare a private, development-only revision of a human gold table.

The helper deliberately works from structured gold rows and a frozen split.
It never opens submissions, images, transcripts, or model outputs.  A new
revision is derived by clearing selected question cells for the already-frozen
development students while preserving the sealed held-out rows unchanged.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from .anonymization import sha256_file
from .readiness_scaffolding import GOLD_TEMPLATE_COLUMNS
from .schema import CourseSpec


REVISION_SCHEMA_VERSION = 1
REVISION_RECORD_TYPE = "private_gold_revision"


class GoldRevisionError(ValueError):
    """Raised when a private gold revision would be unsafe or ambiguous."""


def prepare_gold_revision(
    *,
    course_path: Path,
    candidate_plan_path: Path,
    rubric_path: Path,
    calibration_decisions_path: Path,
    source_gold_path: Path,
    source_binding_path: Path,
    frozen_split_path: Path,
    reset_question_ids: Sequence[str],
    output_root: Path,
    repository_root: Path | None = None,
) -> dict[str, object]:
    """Create an idempotent, hash-bound, development-only gold revision.

    ``source_gold_path``, ``source_binding_path``, ``frozen_split_path``, and
    ``output_root`` must all be below the same ``Data`` boundary.  Public
    candidate artifacts are hash-checked against the candidate plan before a
    private write is considered.
    """

    repo_root = (repository_root or Path(__file__).resolve().parents[2]).resolve()
    course_file = _require_public_file(course_path, "course specification", repo_root)
    candidate_plan_file = _require_public_file(
        candidate_plan_path, "candidate plan", repo_root
    )
    rubric_file = _require_public_file(rubric_path, "rubric", repo_root)
    calibration_file = _require_public_file(
        calibration_decisions_path, "calibration decisions", repo_root
    )
    source_gold_file = _require_regular_file(source_gold_path, "source gold CSV")
    source_binding_file = _require_regular_file(
        source_binding_path, "source reviewer binding"
    )
    frozen_split_file = _require_regular_file(frozen_split_path, "frozen split")
    target = Path(output_root).resolve()

    course = CourseSpec.from_json_path(course_file)
    _validate_candidate_plan(
        candidate_plan_file,
        course_file=course_file,
        rubric_file=rubric_file,
        calibration_file=calibration_file,
        course=course,
        repository_root=repo_root,
    )
    _validate_source_binding(source_binding_file, course_file=course_file, course=course)
    development_ids, heldout_ids = _load_frozen_split(frozen_split_file, course)
    private_root = _nearest_data_ancestor(source_gold_file)
    if private_root is None:
        raise GoldRevisionError("source gold CSV must be inside a Data boundary")
    for path, label in (
        (source_binding_file, "source reviewer binding"),
        (frozen_split_file, "frozen split"),
        (target, "revision output"),
    ):
        if not _is_within(path, private_root):
            raise GoldRevisionError(f"{label} must stay within the source Data boundary")

    reset_questions = _normalize_reset_questions(reset_question_ids, course)
    fieldnames, source_rows = _read_gold_rows(source_gold_file)
    _validate_source_rows(
        fieldnames,
        source_rows,
        course=course,
        development_ids=development_ids,
        heldout_ids=heldout_ids,
    )
    revision_rows = _clear_development_cells(
        source_rows,
        development_ids=set(development_ids),
        reset_questions=set(reset_questions),
    )
    revision_gold = _csv_bytes(revision_rows)
    revision_manifest = _revision_manifest(
        course=course,
        course_file=course_file,
        candidate_plan_file=candidate_plan_file,
        rubric_file=rubric_file,
        calibration_file=calibration_file,
        source_gold_file=source_gold_file,
        source_binding_file=source_binding_file,
        frozen_split_file=frozen_split_file,
        development_count=len(development_ids),
        heldout_count=len(heldout_ids),
        reset_questions=reset_questions,
        source_row_count=len(source_rows),
        repository_root=repo_root,
    )
    outputs = {
        target / "question-gold.csv": revision_gold,
        target / "reviewer-binding.json": source_binding_file.read_bytes(),
        target / "revision-manifest.json": _json_bytes(revision_manifest),
        target / "development-review-students.txt": _student_list_bytes(development_ids),
    }
    status = _write_group_only_if_absent_or_identical(target, outputs)
    return {
        "status": status,
        "record_type": REVISION_RECORD_TYPE,
        "development_student_count": len(development_ids),
        "heldout_student_count": len(heldout_ids),
        "reset_question_count": len(reset_questions),
        "reset_score_row_count": len(development_ids) * len(reset_questions),
        "inherited_score_row_count": len(development_ids)
        * (len(course.question_ids) - len(reset_questions)),
        "heldout_score_row_count": len(heldout_ids) * len(course.question_ids),
        "model_calls": 0,
        "heldout_accessed": False,
    }


def _validate_candidate_plan(
    candidate_plan_file: Path,
    *,
    course_file: Path,
    rubric_file: Path,
    calibration_file: Path,
    course: CourseSpec,
    repository_root: Path,
) -> None:
    payload = _load_json_object(candidate_plan_file, "candidate plan")
    if payload.get("candidate_status") != (
        "human_calibrated_development_candidate_not_frozen_not_run"
    ):
        raise GoldRevisionError("candidate plan is not an unrun human-calibrated candidate")
    scope = payload.get("scope")
    if not isinstance(scope, Mapping):
        raise GoldRevisionError("candidate plan scope must be an object")
    if (
        scope.get("course_id") != course.course_id
        or scope.get("assessment_id") != course.assessment_id
        or scope.get("split") != "development_only"
        or scope.get("heldout_accessed") is not False
        or scope.get("model_calls") != 0
    ):
        raise GoldRevisionError("candidate plan does not declare an unrun development-only scope")
    bindings = payload.get("candidate_bindings")
    if not isinstance(bindings, Mapping):
        raise GoldRevisionError("candidate plan bindings must be an object")
    _validate_public_binding(
        bindings.get("course_spec"), course_file, "course specification", repository_root
    )
    _validate_public_binding(bindings.get("rubric"), rubric_file, "rubric", repository_root)
    _validate_public_binding(
        bindings.get("course_owner_calibration"),
        calibration_file,
        "calibration decisions",
        repository_root,
    )


def _validate_public_binding(
    binding: object, path: Path, label: str, repository_root: Path
) -> None:
    if not isinstance(binding, Mapping):
        raise GoldRevisionError(f"candidate plan is missing its {label} binding")
    if binding.get("path") != _repo_relative_path(path, repository_root):
        raise GoldRevisionError(f"candidate plan {label} path does not match the input")
    if binding.get("sha256") != sha256_file(path):
        raise GoldRevisionError(f"candidate plan {label} hash does not match the input")


def _validate_source_binding(
    binding_path: Path, *, course_file: Path, course: CourseSpec
) -> None:
    payload = _load_json_object(binding_path, "source reviewer binding")
    if payload.get("schema_version") not in {1, 2}:
        raise GoldRevisionError("source reviewer binding has an unsupported schema version")
    if payload.get("record_type") != "question_gold_reviewer_binding":
        raise GoldRevisionError("source reviewer binding has an unexpected record type")
    if (
        payload.get("course_id") != course.course_id
        or payload.get("course_assessment_id") != course.assessment_id
        or payload.get("course_spec_sha256") != sha256_file(course_file)
    ):
        raise GoldRevisionError("source reviewer binding does not match the course")


def _load_frozen_split(path: Path, course: CourseSpec) -> tuple[tuple[str, ...], tuple[str, ...]]:
    payload = _load_json_object(path, "frozen split")
    if (
        payload.get("schema_version") != 1
        or payload.get("status") != "frozen"
        or payload.get("course_id") != course.course_id
        or payload.get("assessment_id") != course.assessment_id
    ):
        raise GoldRevisionError("frozen split does not match the course")
    development = _validated_split_ids(payload.get("development_student_ids"), course, "development")
    heldout = _validated_split_ids(payload.get("heldout_student_ids"), course, "held-out")
    if set(development) & set(heldout):
        raise GoldRevisionError("frozen split development and held-out IDs overlap")
    if payload.get("development_count") != len(development) or payload.get("heldout_count") != len(heldout):
        raise GoldRevisionError("frozen split counts do not match its ID lists")
    if payload.get("student_count") != len(development) + len(heldout):
        raise GoldRevisionError("frozen split student count does not match its ID lists")
    return development, heldout


def _validated_split_ids(value: object, course: CourseSpec, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise GoldRevisionError(f"frozen split {label} IDs must be a non-empty string list")
    normalized = tuple(sorted(value))
    if len(normalized) != len(set(normalized)):
        raise GoldRevisionError(f"frozen split {label} IDs must be unique")
    for student_id in normalized:
        try:
            course.validate_student_id(student_id)
        except ValueError as error:
            raise GoldRevisionError(f"frozen split has an invalid {label} anonymous ID") from error
    return normalized


def _normalize_reset_questions(
    question_ids: Sequence[str], course: CourseSpec
) -> tuple[str, ...]:
    if not question_ids:
        raise GoldRevisionError("provide at least one reset question ID")
    normalized = tuple(sorted(question_ids))
    if len(normalized) != len(set(normalized)):
        raise GoldRevisionError("reset question IDs must be unique")
    unknown = set(normalized) - set(course.question_ids)
    if unknown:
        raise GoldRevisionError("reset question IDs must belong to the course")
    return normalized


def _read_gold_rows(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def _validate_source_rows(
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    *,
    course: CourseSpec,
    development_ids: Sequence[str],
    heldout_ids: Sequence[str],
) -> None:
    if tuple(fieldnames) != GOLD_TEMPLATE_COLUMNS:
        raise GoldRevisionError("source gold CSV must use the canonical gold columns")
    expected_pairs = {
        (student_id, question_id)
        for student_id in (*development_ids, *heldout_ids)
        for question_id in course.question_ids
    }
    actual_pairs = [
        (_cell(row, "student_id"), _cell(row, "question_id")) for row in rows
    ]
    pair_counts = Counter(actual_pairs)
    if set(actual_pairs) != expected_pairs or any(count != 1 for count in pair_counts.values()):
        raise GoldRevisionError("source gold CSV must cover the frozen full cohort exactly once")
    development_set = set(development_ids)
    heldout_set = set(heldout_ids)
    missing_development_scores = 0
    nonblank_heldout_cells = 0
    for row in rows:
        student_id = _cell(row, "student_id")
        if student_id in development_set and not _cell(row, "score"):
            missing_development_scores += 1
        if student_id in heldout_set and any(
            _cell(row, column) for column in GOLD_TEMPLATE_COLUMNS[2:]
        ):
            nonblank_heldout_cells += 1
    if missing_development_scores:
        raise GoldRevisionError("source gold CSV has incomplete development scores")
    if nonblank_heldout_cells:
        raise GoldRevisionError("source gold CSV must keep all held-out score cells blank")


def _clear_development_cells(
    rows: Sequence[Mapping[str, str]],
    *,
    development_ids: set[str],
    reset_questions: set[str],
) -> list[dict[str, str]]:
    revised: list[dict[str, str]] = []
    for source in rows:
        row = {column: source.get(column) or "" for column in GOLD_TEMPLATE_COLUMNS}
        if (
            row["student_id"] in development_ids
            and row["question_id"] in reset_questions
        ):
            for column in GOLD_TEMPLATE_COLUMNS[2:]:
                row[column] = ""
        revised.append(row)
    return revised


def _revision_manifest(
    *,
    course: CourseSpec,
    course_file: Path,
    candidate_plan_file: Path,
    rubric_file: Path,
    calibration_file: Path,
    source_gold_file: Path,
    source_binding_file: Path,
    frozen_split_file: Path,
    development_count: int,
    heldout_count: int,
    reset_questions: Sequence[str],
    source_row_count: int,
    repository_root: Path,
) -> dict[str, object]:
    reset_set = set(reset_questions)
    return {
        "schema_version": REVISION_SCHEMA_VERSION,
        "record_type": REVISION_RECORD_TYPE,
        "course_id": course.course_id,
        "assessment_id": course.assessment_id,
        "candidate": {
            "plan": _public_file_binding(candidate_plan_file, repository_root),
            "course_spec": _public_file_binding(course_file, repository_root),
            "rubric": _public_file_binding(rubric_file, repository_root),
            "calibration_decisions": _public_file_binding(calibration_file, repository_root),
        },
        "private_lineage": {
            "source_gold_sha256": sha256_file(source_gold_file),
            "source_reviewer_binding_sha256": sha256_file(source_binding_file),
            "frozen_split_sha256": sha256_file(frozen_split_file),
        },
        "scope": {
            "split": "development_only",
            "development_student_count": development_count,
            "heldout_student_count": heldout_count,
            "source_score_row_count": source_row_count,
            "reset_question_ids": list(reset_questions),
            "inherited_question_ids": [
                question_id
                for question_id in course.question_ids
                if question_id not in reset_set
            ],
            "reset_score_row_count": development_count * len(reset_questions),
            "heldout_score_row_count": heldout_count * len(course.question_ids),
        },
        "operations": {
            "source_submission_content_read": False,
            "model_calls": 0,
            "heldout_scores_copied_or_scored": False,
            "heldout_rows_preserved_blank": True,
            "reset_cells_clear_score_and_review_metadata": True,
        },
    }


def _public_file_binding(path: Path, repository_root: Path) -> dict[str, str]:
    return {"path": _repo_relative_path(path, repository_root), "sha256": sha256_file(path)}


def _repo_relative_path(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as error:
        raise GoldRevisionError("public candidate artifacts must stay inside the repository") from error


def _csv_bytes(rows: Sequence[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=GOLD_TEMPLATE_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({column: _cell(row, column) for column in GOLD_TEMPLATE_COLUMNS})
    return stream.getvalue().encode("utf-8")


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _student_list_bytes(student_ids: Sequence[str]) -> bytes:
    return ("\n".join(student_ids) + "\n").encode("utf-8")


def _write_group_only_if_absent_or_identical(
    target: Path, outputs: Mapping[Path, bytes]
) -> str:
    if target.exists() and not target.is_dir():
        raise GoldRevisionError("revision output root must be a directory")
    existing = [path for path in outputs if path.exists()]
    if existing:
        scope_file = target / "development-review-students.txt"
        primary_outputs = {
            path: expected
            for path, expected in outputs.items()
            if path != scope_file
        }
        if (
            set(existing) == set(primary_outputs)
            and all(
                path.is_file() and path.read_bytes() == expected
                for path, expected in primary_outputs.items()
            )
            and set(target.iterdir()) == set(primary_outputs)
        ):
            scope_file.write_bytes(outputs[scope_file])
            return "prepared_review_scope"
        if len(existing) != len(outputs):
            raise GoldRevisionError("refusing to complete a partial private gold revision")
        if any(not path.is_file() or path.read_bytes() != expected for path, expected in outputs.items()):
            raise GoldRevisionError("refusing to overwrite a divergent private gold revision")
        return "already_prepared"
    if target.exists() and any(target.iterdir()):
        raise GoldRevisionError("revision output root must be new or empty")
    target.mkdir(parents=True, exist_ok=True)
    for path, content in outputs.items():
        path.write_bytes(content)
    return "prepared"


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GoldRevisionError(f"{label} must be readable JSON") from error
    if not isinstance(payload, dict):
        raise GoldRevisionError(f"{label} must be a JSON object")
    return payload


def _require_regular_file(path: Path, label: str) -> Path:
    candidate = Path(path).resolve()
    if not candidate.is_file() or candidate.is_symlink():
        raise GoldRevisionError(f"{label} must be a regular file")
    return candidate


def _require_public_file(path: Path, label: str, repository_root: Path) -> Path:
    candidate = _require_regular_file(path, label)
    _repo_relative_path(candidate, repository_root)
    if _nearest_data_ancestor(candidate) is not None:
        raise GoldRevisionError(f"{label} must not be inside Data")
    return candidate


def _nearest_data_ancestor(path: Path) -> Path | None:
    for candidate in (Path(path).resolve(), *Path(path).resolve().parents):
        if candidate.name.lower() == "data":
            return candidate
    return None


def _is_within(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _cell(row: Mapping[str, str], key: str) -> str:
    return (row.get(key) or "").strip()
