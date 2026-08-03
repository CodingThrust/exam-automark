"""Safe, model-free helpers for initializing gold labels and frozen splits.

These functions intentionally operate only on a course specification and
anonymous student identifiers.  They do not discover, open, or copy student
submissions.  Their overwrite checks make the commands idempotent while
refusing to replace an existing, divergent gold table or split declaration.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .schema import CourseSpec


GOLD_TEMPLATE_COLUMNS = (
    "student_id",
    "question_id",
    "score",
    "reviewer",
    "reviewed_at",
    "notes",
)


class ReadinessScaffoldError(ValueError):
    """Raised when an initialization command would be ambiguous or unsafe."""


def collect_anonymous_student_ids(
    course: CourseSpec,
    *,
    student_ids: Sequence[str] | None = None,
    students_file: Path | None = None,
    students_dir: Path | None = None,
) -> tuple[str, ...]:
    """Collect, validate, deduplicate, and sort anonymous student IDs.

    ``students_dir`` is deliberately non-recursive: only direct child names
    that exactly match the course's anonymous-ID pattern are used.  This makes
    it safe to point at a normal artifact root containing unrelated manifests.
    """

    collected = list(student_ids or ())
    if students_file is not None:
        if not students_file.is_file():
            raise ReadinessScaffoldError(
                f"students file must be a readable file: {students_file}"
            )
        for line in students_file.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                collected.append(value)

    if students_dir is not None:
        if not students_dir.is_dir():
            raise ReadinessScaffoldError(
                f"students directory must be a directory: {students_dir}"
            )
        for child in students_dir.iterdir():
            try:
                course.validate_student_id(child.name)
            except ValueError:
                continue
            collected.append(child.name)

    if not collected:
        raise ReadinessScaffoldError(
            "provide at least one --student-id, --students-file, or --students-dir entry"
        )
    if len(collected) != len(set(collected)):
        duplicates = sorted(_duplicates(collected))
        raise ReadinessScaffoldError(
            "anonymous student ids must be unique; duplicates: "
            + ", ".join(duplicates)
        )

    for student_id in collected:
        try:
            course.validate_student_id(student_id)
        except ValueError as error:
            raise ReadinessScaffoldError(str(error)) from error
    return tuple(sorted(collected))


def blank_gold_template_bytes(
    course: CourseSpec, student_ids: Sequence[str]
) -> bytes:
    """Return the canonical, blank question-level gold CSV for a cohort."""

    normalized_ids = _validated_student_ids(course, student_ids)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=GOLD_TEMPLATE_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    for student_id in normalized_ids:
        for question_id in course.question_ids:
            writer.writerow(
                {
                    "student_id": student_id,
                    "question_id": question_id,
                    "score": "",
                    "reviewer": "",
                    "reviewed_at": "",
                    "notes": "",
                }
            )
    return stream.getvalue().encode("utf-8")


def initialize_blank_gold(
    course: CourseSpec,
    student_ids: Sequence[str],
    output_path: Path,
) -> dict[str, object]:
    """Create a blank gold CSV, or confirm an identical template already exists.

    A non-empty target is never replaced unless its bytes exactly match the
    canonical template requested by this invocation.
    """

    normalized_ids = _validated_student_ids(course, student_ids)
    expected = blank_gold_template_bytes(course, normalized_ids)
    status = _write_only_if_empty_or_identical(output_path, expected, "gold template")
    return {
        "status": status,
        "gold_path": str(output_path),
        "course_id": course.course_id,
        "assessment_id": course.assessment_id,
        "student_count": len(normalized_ids),
        "question_count": len(course.question_ids),
        "row_count": len(normalized_ids) * len(course.question_ids),
        "columns": list(GOLD_TEMPLATE_COLUMNS),
    }


def build_frozen_split(
    course: CourseSpec,
    student_ids: Sequence[str],
    *,
    seed: str,
    heldout_count: int,
) -> dict[str, object]:
    """Build a deterministic split selected by SHA-256(seed + '|' + ID).

    The lowest hash values become held-out members.  Lists in the returned
    document are lexicographically sorted for easy review; selection itself is
    independent of the original input order.
    """

    normalized_ids = _validated_student_ids(course, student_ids)
    if not isinstance(seed, str) or not seed:
        raise ReadinessScaffoldError("seed must be a non-empty string")
    if isinstance(heldout_count, bool) or not isinstance(heldout_count, int):
        raise ReadinessScaffoldError("heldout_count must be an integer")
    if len(normalized_ids) < 2:
        raise ReadinessScaffoldError("at least two anonymous students are required")
    if heldout_count < 1 or heldout_count >= len(normalized_ids):
        raise ReadinessScaffoldError(
            "heldout_count must leave at least one development and one held-out student"
        )

    ranked = sorted(
        (
            hashlib.sha256(f"{seed}|{student_id}".encode("utf-8")).hexdigest(),
            student_id,
        )
        for student_id in normalized_ids
    )
    heldout_ids = tuple(sorted(student_id for _, student_id in ranked[:heldout_count]))
    development_ids = tuple(
        sorted(student_id for _, student_id in ranked[heldout_count:])
    )
    cohort_fingerprint = hashlib.sha256(
        ("\n".join(normalized_ids) + "\n").encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "status": "frozen",
        "course_id": course.course_id,
        "assessment_id": course.assessment_id,
        "seed": seed,
        "selection_algorithm": (
            "sha256_utf8(seed + '|' + student_id), ascending digest then student_id; "
            "lowest heldout_count IDs are held out"
        ),
        "cohort_student_ids_sha256": cohort_fingerprint,
        "student_count": len(normalized_ids),
        "development_count": len(development_ids),
        "heldout_count": len(heldout_ids),
        "development_student_ids": list(development_ids),
        "heldout_student_ids": list(heldout_ids),
    }


def freeze_split(
    course: CourseSpec,
    student_ids: Sequence[str],
    *,
    seed: str,
    heldout_count: int,
    output_json: Path,
    development_students_file: Path,
    heldout_students_file: Path,
) -> dict[str, object]:
    """Persist a split transactionally after checking all three outputs.

    If any output already contains data, all three output files must be
    byte-for-byte identical to the new deterministic result.  This prevents a
    rerun with a changed seed, cohort, or held-out count from silently changing
    a frozen experiment split.
    """

    _require_distinct_paths(
        output_json, development_students_file, heldout_students_file
    )
    payload = build_frozen_split(
        course,
        student_ids,
        seed=seed,
        heldout_count=heldout_count,
    )
    expected_outputs = {
        output_json: _canonical_json_bytes(payload),
        development_students_file: _student_list_bytes(
            payload["development_student_ids"]
        ),
        heldout_students_file: _student_list_bytes(payload["heldout_student_ids"]),
    }
    status = _write_output_group_only_if_empty_or_identical(expected_outputs)
    result = dict(payload)
    result.update(
        {
            "status": "already_frozen" if status == "already_matches" else "frozen",
            "split_path": str(output_json),
            "development_students_file": str(development_students_file),
            "heldout_students_file": str(heldout_students_file),
        }
    )
    return result


def _validated_student_ids(
    course: CourseSpec, student_ids: Sequence[str]
) -> tuple[str, ...]:
    if not student_ids:
        raise ReadinessScaffoldError("student ids must not be empty")
    normalized = tuple(sorted(student_ids))
    if len(normalized) != len(set(normalized)):
        duplicates = sorted(_duplicates(normalized))
        raise ReadinessScaffoldError(
            "anonymous student ids must be unique; duplicates: "
            + ", ".join(duplicates)
        )
    for student_id in normalized:
        try:
            course.validate_student_id(student_id)
        except ValueError as error:
            raise ReadinessScaffoldError(str(error)) from error
    return normalized


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _write_only_if_empty_or_identical(
    path: Path, expected: bytes, label: str
) -> str:
    if path.exists():
        if not path.is_file():
            raise ReadinessScaffoldError(f"{label} output must be a file: {path}")
        current = path.read_bytes()
        if current:
            if current == expected:
                return "already_matches_template"
            raise ReadinessScaffoldError(
                f"refusing to overwrite non-empty {label} output with divergent content: {path}"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)
    return "created"


def _write_output_group_only_if_empty_or_identical(
    expected_outputs: Mapping[Path, bytes],
) -> str:
    existing_nonempty = {
        path: path.read_bytes()
        for path in expected_outputs
        if path.exists() and path.is_file() and path.read_bytes()
    }
    invalid_targets = [path for path in expected_outputs if path.exists() and not path.is_file()]
    if invalid_targets:
        raise ReadinessScaffoldError(
            "split outputs must be files: "
            + ", ".join(str(path) for path in invalid_targets)
        )
    if existing_nonempty:
        divergent = [
            path
            for path, expected in expected_outputs.items()
            if not path.is_file() or path.read_bytes() != expected
        ]
        if divergent:
            raise ReadinessScaffoldError(
                "refusing to overwrite divergent frozen split outputs: "
                + ", ".join(str(path) for path in divergent)
            )
        return "already_matches"

    for path, expected in expected_outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
    return "created"


def _require_distinct_paths(*paths: Path) -> None:
    normalized = [path.resolve() for path in paths]
    if len(normalized) != len(set(normalized)):
        raise ReadinessScaffoldError("split output paths must be distinct")


def _canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _student_list_bytes(student_ids: object) -> bytes:
    if not isinstance(student_ids, list) or not all(
        isinstance(student_id, str) for student_id in student_ids
    ):
        raise AssertionError("split payload must contain a string student-id list")
    return ("\n".join(student_ids) + "\n").encode("utf-8")
