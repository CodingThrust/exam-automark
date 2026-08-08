from __future__ import annotations

"""Assemble final-approved anonymous submission snapshots into one cohort.

Courses may receive an isolated late or supplementary submission in a
different file format.  Once each source has independently completed the
anonymization and submission-scope gates, this module combines their *already
anonymous* image snapshots.  It deliberately cannot grade, create a packet,
or authorize a model run.
"""

import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from benchmark.core.anonymization import ANONYMOUS_ID_PATTERN, SHA256_PATTERN, sha256_file, write_json
from benchmark.core.scoped_anonymous_images import _is_within, _nearest_data_ancestor
from benchmark.core.submission_scope_workflow import (
    SUBMISSION_SCOPE_SCHEMA_VERSION,
    SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SUBMISSION_SNAPSHOT_RECORD_TYPE,
    SubmissionScopeError,
)


COHORT_SNAPSHOT_RECORD_TYPE = "anonymous_submission_cohort_snapshot"
COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH = Path(
    "manifest/anonymous-submission-cohort-snapshot.json"
)
_COHORT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_QUESTION_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")


def merge_anonymous_submission_image_snapshots(
    *,
    snapshot_roots: Sequence[Path],
    cohort_id: str,
    output_root: Path,
) -> dict[str, Any]:
    """Copy independently frozen submission snapshots into one private cohort.

    The output is idempotent: a pre-existing target is accepted only when its
    complete manifest and every copied image exactly match the requested
    cohort.  Source manifests are recorded by hash, while local absolute paths
    are deliberately excluded from the output manifest.
    """

    if not snapshot_roots:
        raise SubmissionScopeError("at least one submission snapshot is required")
    normalized_cohort_id = _normalize_cohort_id(cohort_id)
    target = output_root.resolve()
    sources = [_load_snapshot_root(root) for root in snapshot_roots]
    _validate_output_root(target=target, sources=sources)

    assessment_ids = {str(source["manifest"]["assessment_id"]) for source in sources}
    if len(assessment_ids) != 1:
        raise SubmissionScopeError("all submission snapshots must have the same assessment_id")

    submissions: list[dict[str, Any]] = []
    source_records: list[dict[str, Any]] = []
    anonymous_ids: set[str] = set()
    snapshot_paths: set[str] = set()
    scope_ids: set[str] = set()
    for source in sources:
        manifest = source["manifest"]
        scope_id = str(manifest["scope_id"])
        if scope_id in scope_ids:
            raise SubmissionScopeError("submission snapshots contain a duplicate scope_id")
        scope_ids.add(scope_id)
        source_records.append(
            {
                "scope_id": scope_id,
                "manifest_sha256": source["manifest_sha256"],
                "student_count": manifest["student_count"],
                "image_count": manifest["image_count"],
            }
        )
        for submission in manifest["submissions"]:
            anonymous_id = submission["anonymous_id"]
            if anonymous_id in anonymous_ids:
                raise SubmissionScopeError(
                    "submission snapshots contain a duplicate anonymous_id"
                )
            anonymous_ids.add(anonymous_id)
            images: list[dict[str, Any]] = []
            for image in submission["images"]:
                snapshot_image = image["snapshot_image"]
                if snapshot_image in snapshot_paths:
                    raise SubmissionScopeError(
                        "submission snapshots contain a duplicate snapshot image path"
                    )
                snapshot_paths.add(snapshot_image)
                images.append(
                    {
                        "source_page": image["source_page"],
                        "snapshot_image": snapshot_image,
                        "sha256": image["sha256"],
                        "bytes": image["bytes"],
                        "source_snapshot_scope_id": manifest["scope_id"],
                    }
                )
            submissions.append(
                {
                    "anonymous_id": anonymous_id,
                    "grading_unit": "anonymous_submission",
                    "missing_question_ids": list(submission["missing_question_ids"]),
                    "images": images,
                }
            )

    submissions.sort(key=lambda item: str(item["anonymous_id"]))
    manifest = {
        "schema_version": SUBMISSION_SCOPE_SCHEMA_VERSION,
        "record_type": COHORT_SNAPSHOT_RECORD_TYPE,
        "assessment_id": assessment_ids.pop(),
        "cohort_id": normalized_cohort_id,
        "grading_unit": "anonymous_submission",
        "source_snapshots": source_records,
        "student_count": len(submissions),
        "image_count": sum(len(item["images"]) for item in submissions),
        "submissions": submissions,
        "model_run_allowed": False,
        "model_run_blockers": [
            "This cohort snapshot is not a grading packet and cannot authorize a model run.",
            "Grade each anonymous submission as one ordered set of pages; never score or sum pages independently.",
            "A frozen split, rubric, gold, packet audit, and explicit model-run approval remain required.",
        ],
    }
    if target.exists():
        _validate_existing_cohort_snapshot(target, manifest)
        status = "already_built"
    else:
        _write_cohort_snapshot(output_root=target, sources=sources, manifest=manifest)
        status = "built"
    return {
        "status": status,
        "output_root": str(target),
        "manifest_path": str(target / COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH),
        "student_count": manifest["student_count"],
        "image_count": manifest["image_count"],
        "source_snapshot_count": len(sources),
        "model_run_allowed": False,
    }


def _load_snapshot_root(root: Path) -> dict[str, Any]:
    unresolved = Path(root)
    if unresolved.is_symlink() or not unresolved.is_dir():
        raise SubmissionScopeError("submission snapshot root must be a real directory")
    source_root = unresolved.resolve()
    manifest_path = source_root / SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise SubmissionScopeError("submission snapshot manifest is missing or unsafe")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SubmissionScopeError("submission snapshot manifest is not readable JSON") from error
    if not isinstance(payload, dict):
        raise SubmissionScopeError("submission snapshot manifest must be a JSON object")
    _validate_snapshot_manifest(payload, source_root=source_root)
    return {
        "root": source_root,
        "manifest": payload,
        "manifest_sha256": sha256_file(manifest_path),
    }


def _validate_snapshot_manifest(payload: Mapping[str, Any], *, source_root: Path) -> None:
    if payload.get("schema_version") != SUBMISSION_SCOPE_SCHEMA_VERSION:
        raise SubmissionScopeError("submission snapshot has an unsupported schema_version")
    if payload.get("record_type") != SUBMISSION_SNAPSHOT_RECORD_TYPE:
        raise SubmissionScopeError("submission snapshot has an unexpected record_type")
    assessment_id = payload.get("assessment_id")
    if not isinstance(assessment_id, str) or not assessment_id.strip():
        raise SubmissionScopeError("submission snapshot assessment_id must be non-empty text")
    _normalize_cohort_id(payload.get("scope_id"), field_name="scope_id")
    if payload.get("grading_unit") != "anonymous_submission":
        raise SubmissionScopeError("submission snapshot must use anonymous_submission grading")
    if payload.get("model_run_allowed") is not False:
        raise SubmissionScopeError("submission snapshot must not authorize a model run")
    submissions = payload.get("submissions")
    if not isinstance(submissions, list) or not submissions:
        raise SubmissionScopeError("submission snapshot must contain at least one submission")

    anonymous_ids: set[str] = set()
    snapshot_paths: set[str] = set()
    image_count = 0
    for submission in submissions:
        if not isinstance(submission, Mapping):
            raise SubmissionScopeError("submission snapshot has an invalid submission record")
        anonymous_id = submission.get("anonymous_id")
        if (
            not isinstance(anonymous_id, str)
            or not ANONYMOUS_ID_PATTERN.fullmatch(anonymous_id)
            or anonymous_id in anonymous_ids
        ):
            raise SubmissionScopeError("submission snapshot has a duplicate or invalid anonymous_id")
        anonymous_ids.add(anonymous_id)
        if submission.get("grading_unit") != "anonymous_submission":
            raise SubmissionScopeError("submission record must use anonymous_submission grading")
        _validate_question_ids(submission.get("missing_question_ids"))
        images = submission.get("images")
        if not isinstance(images, list) or not images:
            raise SubmissionScopeError("submission record must contain at least one image")
        previous_page = 0
        for image in images:
            _validate_image_record(
                image,
                source_root=source_root,
                used_paths=snapshot_paths,
                previous_page=previous_page,
            )
            previous_page = image["source_page"]
            image_count += 1

    if payload.get("student_count") != len(submissions):
        raise SubmissionScopeError("submission snapshot student_count does not match submissions")
    if payload.get("image_count") != image_count:
        raise SubmissionScopeError("submission snapshot image_count does not match images")
    expected = {SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH.as_posix(), *snapshot_paths}
    actual = {
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise SubmissionScopeError("submission snapshot has unexpected or missing files")


def _validate_question_ids(value: object) -> None:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not _QUESTION_ID_PATTERN.fullmatch(item)
        for item in value
    ) or len(set(value)) != len(value):
        raise SubmissionScopeError("missing_question_ids must be a unique list of question IDs")


def _validate_image_record(
    image: object,
    *,
    source_root: Path,
    used_paths: set[str],
    previous_page: int,
) -> None:
    if not isinstance(image, Mapping):
        raise SubmissionScopeError("submission snapshot has an invalid image record")
    source_page = image.get("source_page")
    if type(source_page) is not int or source_page < 1 or source_page <= previous_page:
        raise SubmissionScopeError("submission image source_page values must be positive and ordered")
    relative = _safe_relative_png(image.get("snapshot_image"))
    if relative in used_paths:
        raise SubmissionScopeError("submission snapshot has a duplicate snapshot image path")
    digest = image.get("sha256")
    byte_count = image.get("bytes")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise SubmissionScopeError("submission image sha256 is invalid")
    if type(byte_count) is not int or byte_count < 1:
        raise SubmissionScopeError("submission image bytes must be a positive integer")
    candidate = (source_root / relative).resolve()
    if (
        not _is_within(candidate, source_root)
        or not candidate.is_file()
        or candidate.is_symlink()
        or sha256_file(candidate) != digest
        or candidate.stat().st_size != byte_count
    ):
        raise SubmissionScopeError("submission snapshot image does not match its manifest")
    used_paths.add(relative)


def _safe_relative_png(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise SubmissionScopeError("snapshot_image must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".png":
        raise SubmissionScopeError("snapshot_image must be a safe relative PNG path")
    normalized = path.as_posix()
    if normalized != value or normalized == ".":
        raise SubmissionScopeError("snapshot_image must be normalized")
    return normalized


def _normalize_cohort_id(value: object, *, field_name: str = "cohort_id") -> str:
    if not isinstance(value, str) or not _COHORT_ID_PATTERN.fullmatch(value):
        raise SubmissionScopeError(f"{field_name} must be a stable ASCII identifier")
    return value


def _validate_output_root(*, target: Path, sources: Sequence[Mapping[str, Any]]) -> None:
    roots = [Path(source["root"]) for source in sources]
    if len(set(roots)) != len(roots):
        raise SubmissionScopeError("the same submission snapshot cannot be merged twice")
    for source_root in roots:
        if _is_within(target, source_root) or _is_within(source_root, target):
            raise SubmissionScopeError(
                "cohort output root must not overlap a source submission snapshot"
            )
        private_root = _nearest_data_ancestor(source_root) or source_root.parent
        if not _is_within(target, private_root):
            raise SubmissionScopeError(
                "cohort output root must stay inside each source private-data boundary"
            )


def _validate_existing_cohort_snapshot(output_root: Path, manifest: Mapping[str, Any]) -> None:
    manifest_path = output_root / COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH
    if not output_root.is_dir() or not manifest_path.is_file():
        raise SubmissionScopeError("existing cohort snapshot target is incomplete")
    try:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SubmissionScopeError("existing cohort snapshot manifest is unreadable") from error
    if existing != manifest:
        raise SubmissionScopeError("existing cohort snapshot target has a divergent manifest")
    expected = {COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH.as_posix()}
    for submission in manifest["submissions"]:
        for image in submission["images"]:
            relative = str(image["snapshot_image"])
            expected.add(relative)
            copied = output_root / relative
            if (
                not copied.is_file()
                or copied.is_symlink()
                or sha256_file(copied) != image["sha256"]
                or copied.stat().st_size != image["bytes"]
            ):
                raise SubmissionScopeError("existing cohort snapshot image has changed")
    actual = {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise SubmissionScopeError("existing cohort snapshot target has unexpected or missing files")


def _write_cohort_snapshot(
    *, output_root: Path, sources: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]
) -> None:
    source_by_scope = {
        str(source["manifest"]["scope_id"]): Path(source["root"])
        for source in sources
    }
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.tmp-", dir=output_root.parent))
    try:
        for submission in manifest["submissions"]:
            for image in submission["images"]:
                source_root = source_by_scope[str(image["source_snapshot_scope_id"])]
                source = (source_root / str(image["snapshot_image"])).resolve()
                target = temporary / str(image["snapshot_image"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                if sha256_file(target) != image["sha256"] or target.stat().st_size != image["bytes"]:
                    raise SubmissionScopeError("copied cohort image hash mismatch")
        write_json(temporary / COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH, dict(manifest))
        temporary.replace(output_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
