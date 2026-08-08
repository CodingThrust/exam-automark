from __future__ import annotations

"""Freeze variable-page anonymous submissions without ever grading a page alone.

An anonymization layout normally has a common number of rendered pages per
student.  Real submissions may not: a duplicate page can be excluded, an
answer can continue across several pages, and a page can be missing.  This
module records those decisions locally, binds them to final anonymization
approvals, and makes one ordered image list for each anonymous *submission*.

The result is intentionally only a private input snapshot.  It does not
create a grading packet, assign any score, or authorize a model.
"""

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from benchmark.core.anonymization import ANONYMOUS_ID_PATTERN, SHA256_PATTERN, sha256_file, write_json
from benchmark.core.scoped_anonymous_images import (
    ScopedSnapshotError,
    _load_final_review_rows,
    _load_json_object,
    _reject_overlapping_roots,
    _require_directory,
    _require_file,
    _require_private_output_root,
    _required_sha256,
    _resolve_metadata_relative_path,
    _safe_source_file,
    _validate_final_review_validation,
    _validate_preparation_metadata,
    _validate_source_artifact_tree,
)


SUBMISSION_SCOPE_SCHEMA_VERSION = 1
SUBMISSION_SCOPE_RECORD_TYPE = "private_anonymous_submission_scope_resolution"
SUBMISSION_SCOPE_DECISIONS_RECORD_TYPE = "private_anonymous_submission_scope_decisions"
SUBMISSION_SNAPSHOT_RECORD_TYPE = "anonymous_submission_image_snapshot"
SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH = Path(
    "manifest/anonymous-submission-image-snapshot.json"
)

_SCOPE_STATUS_AUTOMATIC = "automatic_include_all"
_SCOPE_STATUS_PENDING = "pending_human_resolution"
_SCOPE_STATUS_HUMAN = "human_resolved"
_SCOPE_STATUSES = frozenset(
    {_SCOPE_STATUS_AUTOMATIC, _SCOPE_STATUS_PENDING, _SCOPE_STATUS_HUMAN}
)
_SCOPE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_QUESTION_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")


class SubmissionScopeError(ValueError):
    """Raised when a private submission-scope artifact is not safely bound."""


def initialize_submission_scope_resolution(
    *,
    artifact_root: Path,
    final_review_path: Path,
    final_review_validation_path: Path,
    private_assembly_manifest_path: Path,
    expected_pages_per_submission: int,
    resolution_path: Path,
) -> dict[str, Any]:
    """Create an immutable draft with automatic decisions only for normal groups.

    A group with the expected page count can safely begin as
    ``automatic_include_all`` because every page was already final-approved.
    Every nonstandard group is deliberately left pending for a human scope
    decision; no page is implicitly discarded.
    """

    context = _load_context(
        artifact_root=artifact_root,
        final_review_path=final_review_path,
        final_review_validation_path=final_review_validation_path,
        private_assembly_manifest_path=private_assembly_manifest_path,
        expected_pages_per_submission=expected_pages_per_submission,
    )
    submissions = []
    for anonymous_id, pages in context["pages_by_student"].items():
        expected_source_pages = [int(page["source_page"]) for page in pages]
        is_normal = len(expected_source_pages) == expected_pages_per_submission
        submissions.append(
            {
                "anonymous_id": anonymous_id,
                "scope_status": _SCOPE_STATUS_AUTOMATIC if is_normal else _SCOPE_STATUS_PENDING,
                "included_source_pages": expected_source_pages if is_normal else [],
                "excluded_source_pages": [] if is_normal else expected_source_pages,
                "missing_question_ids": [],
                "reviewer": "",
                "reviewed_at": "",
                "notes": "" if is_normal else "human scope decision required for nonstandard page count",
            }
        )
    payload = _resolution_payload(context=context, submissions=submissions)
    _write_only_if_empty_or_identical(resolution_path, payload)
    return {
        "status": "created" if resolution_path.stat().st_size else "created",
        "submission_count": len(submissions),
        "pending_human_resolution_count": sum(
            submission["scope_status"] == _SCOPE_STATUS_PENDING for submission in submissions
        ),
        "model_run_allowed": False,
    }


def apply_submission_scope_decisions(
    *,
    artifact_root: Path,
    final_review_path: Path,
    final_review_validation_path: Path,
    private_assembly_manifest_path: Path,
    expected_pages_per_submission: int,
    template_resolution_path: Path,
    decisions_path: Path,
    resolved_resolution_path: Path,
) -> dict[str, Any]:
    """Apply one exact human decision per pending submission into a new file."""

    context = _load_context(
        artifact_root=artifact_root,
        final_review_path=final_review_path,
        final_review_validation_path=final_review_validation_path,
        private_assembly_manifest_path=private_assembly_manifest_path,
        expected_pages_per_submission=expected_pages_per_submission,
    )
    template = _load_resolution(template_resolution_path, context=context)
    decisions = _load_json_object(_require_file(decisions_path, "scope decisions"), "scope decisions")
    if decisions.get("schema_version") != SUBMISSION_SCOPE_SCHEMA_VERSION or decisions.get(
        "record_type"
    ) != SUBMISSION_SCOPE_DECISIONS_RECORD_TYPE:
        raise SubmissionScopeError("scope decisions have an unsupported schema or record type")
    if decisions.get("template_resolution_sha256") != sha256_file(template_resolution_path):
        raise SubmissionScopeError("scope decisions do not bind to the supplied resolution template")
    raw_decisions = decisions.get("decisions")
    if not isinstance(raw_decisions, list):
        raise SubmissionScopeError("scope decisions must contain a decisions list")
    pending_ids = {
        str(submission["anonymous_id"])
        for submission in template["submissions"]
        if submission["scope_status"] == _SCOPE_STATUS_PENDING
    }
    decision_by_id: dict[str, Mapping[str, Any]] = {}
    for decision in raw_decisions:
        if not isinstance(decision, Mapping):
            raise SubmissionScopeError("scope decisions contain an invalid entry")
        anonymous_id = decision.get("anonymous_id")
        if not isinstance(anonymous_id, str) or anonymous_id not in pending_ids or anonymous_id in decision_by_id:
            raise SubmissionScopeError("scope decisions must contain each pending anonymous ID exactly once")
        decision_by_id[anonymous_id] = decision
    if set(decision_by_id) != pending_ids:
        raise SubmissionScopeError("scope decisions do not cover every pending anonymous submission")

    resolved_submissions: list[dict[str, Any]] = []
    for submission in template["submissions"]:
        anonymous_id = str(submission["anonymous_id"])
        if submission["scope_status"] != _SCOPE_STATUS_PENDING:
            resolved_submissions.append(dict(submission))
            continue
        decision = decision_by_id[anonymous_id]
        expected_pages = [
            int(page["source_page"]) for page in context["pages_by_student"][anonymous_id]
        ]
        included = _ordered_source_pages(
            decision.get("included_source_pages"), expected_pages, "included_source_pages"
        )
        if not included:
            raise SubmissionScopeError(f"{anonymous_id} must retain at least one page")
        excluded = [page for page in expected_pages if page not in included]
        resolved_submissions.append(
            {
                "anonymous_id": anonymous_id,
                "scope_status": _SCOPE_STATUS_HUMAN,
                "included_source_pages": included,
                "excluded_source_pages": excluded,
                "missing_question_ids": _question_ids(
                    decision.get("missing_question_ids"), anonymous_id=anonymous_id
                ),
                "reviewer": _required_text(decision.get("reviewer"), f"{anonymous_id} reviewer"),
                "reviewed_at": _required_text(decision.get("reviewed_at"), f"{anonymous_id} reviewed_at"),
                "notes": _required_text(decision.get("notes"), f"{anonymous_id} notes"),
            }
        )
    payload = _resolution_payload(context=context, submissions=resolved_submissions)
    report = _validate_resolution_payload(payload, context=context)
    if report["status"] != "ready_scope_only":
        raise SubmissionScopeError(
            "resolved scope decisions are incomplete: " + ", ".join(report["failed_checks"])
        )
    _write_only_if_empty_or_identical(resolved_resolution_path, payload)
    return {
        "status": "resolved",
        "submission_count": len(resolved_submissions),
        "human_resolved_submission_count": len(pending_ids),
        "model_run_allowed": False,
    }


def validate_submission_scope_resolution(
    *,
    artifact_root: Path,
    final_review_path: Path,
    final_review_validation_path: Path,
    private_assembly_manifest_path: Path,
    expected_pages_per_submission: int,
    resolution_path: Path,
) -> dict[str, Any]:
    """Validate a complete private page-selection decision without model access."""

    context = _load_context(
        artifact_root=artifact_root,
        final_review_path=final_review_path,
        final_review_validation_path=final_review_validation_path,
        private_assembly_manifest_path=private_assembly_manifest_path,
        expected_pages_per_submission=expected_pages_per_submission,
    )
    payload = _load_resolution(resolution_path, context=context)
    return _validate_resolution_payload(payload, context=context)


def build_anonymous_submission_image_snapshot(
    *,
    artifact_root: Path,
    final_review_path: Path,
    final_review_validation_path: Path,
    private_assembly_manifest_path: Path,
    expected_pages_per_submission: int,
    resolution_path: Path,
    scope_id: str,
    output_root: Path,
) -> dict[str, Any]:
    """Copy every selected page, grouped by student, into a private snapshot.

    The manifest's unit is explicitly ``anonymous_submission``.  Downstream
    packet builders must pass all listed pages for one student together before
    scoring questions; they must never score or sum pages independently.
    """

    context = _load_context(
        artifact_root=artifact_root,
        final_review_path=final_review_path,
        final_review_validation_path=final_review_validation_path,
        private_assembly_manifest_path=private_assembly_manifest_path,
        expected_pages_per_submission=expected_pages_per_submission,
    )
    resolution = _load_resolution(resolution_path, context=context)
    report = _validate_resolution_payload(resolution, context=context)
    if report["status"] != "ready_scope_only":
        raise SubmissionScopeError(
            "submission scope is not ready: " + ", ".join(report["failed_checks"])
        )
    normalized_scope_id = _normalize_scope_id(scope_id)
    source_root = context["artifact_root"]
    target = output_root.resolve()
    _reject_overlapping_roots(source_root, target)
    _require_private_output_root(source_root, target)

    selected_submissions: list[dict[str, Any]] = []
    for submission in resolution["submissions"]:
        anonymous_id = str(submission["anonymous_id"])
        selected_pages = set(submission["included_source_pages"])
        pages = []
        for source in context["pages_by_student"][anonymous_id]:
            if source["source_page"] not in selected_pages:
                continue
            image_path = str(source["output_image"])
            artifact = context["source_artifacts"][image_path]
            pages.append(
                {
                    "source_page": int(source["source_page"]),
                    "source_image": image_path,
                    "snapshot_image": image_path,
                    "sha256": str(artifact["sha256"]),
                    "bytes": int(artifact["bytes"]),
                }
            )
        selected_submissions.append(
            {
                "anonymous_id": anonymous_id,
                "grading_unit": "anonymous_submission",
                "missing_question_ids": list(submission["missing_question_ids"]),
                "images": pages,
            }
        )
    manifest = {
        "schema_version": SUBMISSION_SCOPE_SCHEMA_VERSION,
        "record_type": SUBMISSION_SNAPSHOT_RECORD_TYPE,
        "assessment_id": context["assessment_id"],
        "scope_id": normalized_scope_id,
        "grading_unit": "anonymous_submission",
        "source_provenance": {
            **context["source_provenance"],
            "submission_scope_resolution_sha256": sha256_file(resolution_path),
        },
        "student_count": len(selected_submissions),
        "image_count": sum(len(item["images"]) for item in selected_submissions),
        "submissions": selected_submissions,
        "model_run_allowed": False,
        "model_run_blockers": [
            "This snapshot is not a grading packet and cannot authorize a model run.",
            "Grade each anonymous submission as one ordered set of pages; never score or sum pages independently.",
            "A frozen split, rubric, gold, packet audit, and explicit model-run approval remain required.",
        ],
    }
    if target.exists():
        _validate_existing_snapshot(target, manifest)
        status = "already_built"
    else:
        _write_snapshot(source_root=source_root, output_root=target, manifest=manifest)
        status = "built"
    return {
        "status": status,
        "output_root": str(target),
        "manifest_path": str(target / SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH),
        "student_count": manifest["student_count"],
        "image_count": manifest["image_count"],
        "model_run_allowed": False,
    }


def _load_context(
    *,
    artifact_root: Path,
    final_review_path: Path,
    final_review_validation_path: Path,
    private_assembly_manifest_path: Path,
    expected_pages_per_submission: int,
) -> dict[str, Any]:
    if expected_pages_per_submission < 1:
        raise SubmissionScopeError("expected_pages_per_submission must be positive")
    source_root = _require_directory(artifact_root, "artifact root")
    review_path = _require_file(final_review_path, "final review CSV")
    validation_path = _require_file(final_review_validation_path, "final-review validation")
    manifest_root = source_root / "manifest"
    if review_path != (manifest_root / "anonymization_review.csv").resolve():
        raise SubmissionScopeError("final review must be artifact_root/manifest/anonymization_review.csv")
    if validation_path != (manifest_root / "final-review-validation.json").resolve():
        raise SubmissionScopeError("final review validation must be artifact_root/manifest/final-review-validation.json")
    metadata_path = _require_file(manifest_root / "prep-metadata.json", "prep metadata")
    metadata = _load_json_object(metadata_path, "prep metadata")
    _validate_preparation_metadata(metadata=metadata, source_root=source_root, review_path=review_path)
    review_rows = _load_final_review_rows(
        review_path,
        expected_render_spec_sha256=_required_sha256(metadata.get("render_spec_sha256"), "prep metadata render_spec_sha256"),
        expected_artifact_manifest_sha256=_required_sha256(metadata.get("artifact_manifest_sha256"), "prep metadata artifact_manifest_sha256"),
    )
    _validate_final_review_validation(
        validation=_load_json_object(validation_path, "final-review validation"),
        review_row_count=len(review_rows),
    )
    artifact_manifest_path = _resolve_metadata_relative_path(
        source_root=source_root,
        value=metadata.get("artifact_manifest_path"),
        field_name="artifact_manifest_path",
    )
    if sha256_file(artifact_manifest_path) != _required_sha256(
        metadata.get("artifact_manifest_sha256"), "prep metadata artifact_manifest_sha256"
    ):
        raise SubmissionScopeError("output artifact manifest hash does not match prep metadata")
    source_artifacts = _validate_source_artifact_tree(
        source_root=source_root,
        review_rows=review_rows,
        artifact_manifest=_load_json_object(artifact_manifest_path, "output artifact manifest"),
        expected_render_spec_sha256=_required_sha256(metadata.get("render_spec_sha256"), "prep metadata render_spec_sha256"),
    )
    pages_by_student: dict[str, list[dict[str, Any]]] = {}
    for row in review_rows:
        pages_by_student.setdefault(str(row["anonymous_id"]), []).append(dict(row))
    assembly_path = _require_file(private_assembly_manifest_path, "private assembly manifest")
    _validate_assembly_manifest(
        _load_json_object(assembly_path, "private assembly manifest"), pages_by_student=pages_by_student
    )
    assessment_id = metadata.get("assessment_id")
    if not isinstance(assessment_id, str) or not assessment_id.strip():
        raise SubmissionScopeError("prep metadata must include an assessment_id")
    return {
        "artifact_root": source_root,
        "assessment_id": assessment_id,
        "expected_pages_per_submission": expected_pages_per_submission,
        "pages_by_student": {key: pages_by_student[key] for key in sorted(pages_by_student)},
        "source_artifacts": source_artifacts,
        "source_provenance": {
            "preparation_metadata_sha256": sha256_file(metadata_path),
            "final_review_sha256": sha256_file(review_path),
            "final_review_validation_sha256": sha256_file(validation_path),
            "output_artifact_manifest_sha256": sha256_file(artifact_manifest_path),
            "private_assembly_manifest_sha256": sha256_file(assembly_path),
        },
    }


def _validate_assembly_manifest(
    payload: Mapping[str, Any], *, pages_by_student: Mapping[str, Sequence[Mapping[str, Any]]]
) -> None:
    if payload.get("record_type") != "private_mixed_submission_assembly":
        raise SubmissionScopeError("private assembly manifest has an unexpected record type")
    raw_groups = payload.get("groups")
    if not isinstance(raw_groups, list):
        raise SubmissionScopeError("private assembly manifest must contain groups")
    counts: dict[str, int] = {}
    for group in raw_groups:
        if not isinstance(group, Mapping) or group.get("status") != "converted_pending_page_review":
            continue
        anonymous_id = group.get("anonymous_id")
        count = group.get("rendered_page_count")
        if (
            not isinstance(anonymous_id, str)
            or not ANONYMOUS_ID_PATTERN.fullmatch(anonymous_id)
            or type(count) is not int
            or count < 1
            or anonymous_id in counts
        ):
            raise SubmissionScopeError("private assembly manifest has an invalid converted group")
        counts[anonymous_id] = count
    if set(counts) != set(pages_by_student):
        raise SubmissionScopeError("private assembly groups do not match final-approved submissions")
    for anonymous_id, pages in pages_by_student.items():
        if counts[anonymous_id] != len(pages):
            raise SubmissionScopeError("private assembly page count does not match final-approved pages")


def _resolution_payload(*, context: Mapping[str, Any], submissions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SUBMISSION_SCOPE_SCHEMA_VERSION,
        "record_type": SUBMISSION_SCOPE_RECORD_TYPE,
        "assessment_id": context["assessment_id"],
        "expected_pages_per_submission": context["expected_pages_per_submission"],
        "grading_unit": "anonymous_submission",
        "source_provenance": dict(context["source_provenance"]),
        "submissions": [dict(submission) for submission in submissions],
        "model_run_allowed": False,
        "model_run_blockers": [
            "Page selection and page ownership are not scoring decisions.",
            "Rubric, gold, split, packet audit, and explicit model-run approval remain required.",
        ],
    }


def _load_resolution(path: Path, *, context: Mapping[str, Any]) -> dict[str, Any]:
    payload = _load_json_object(_require_file(path, "submission-scope resolution"), "submission-scope resolution")
    if payload.get("schema_version") != SUBMISSION_SCOPE_SCHEMA_VERSION or payload.get(
        "record_type"
    ) != SUBMISSION_SCOPE_RECORD_TYPE:
        raise SubmissionScopeError("submission-scope resolution has an unsupported schema or record type")
    if payload.get("assessment_id") != context["assessment_id"]:
        raise SubmissionScopeError("submission-scope resolution assessment does not match source artifacts")
    if payload.get("expected_pages_per_submission") != context["expected_pages_per_submission"]:
        raise SubmissionScopeError("submission-scope resolution expected page count does not match")
    if payload.get("grading_unit") != "anonymous_submission":
        raise SubmissionScopeError("submission-scope resolution must use anonymous_submission grading unit")
    if payload.get("source_provenance") != context["source_provenance"]:
        raise SubmissionScopeError("submission-scope resolution provenance does not match source artifacts")
    return payload


def _validate_resolution_payload(payload: Mapping[str, Any], *, context: Mapping[str, Any]) -> dict[str, Any]:
    raw_submissions = payload.get("submissions")
    checks: list[dict[str, str]] = []
    malformed = 0
    pending = 0
    audit_missing = 0
    unsafe_auto = 0
    selected_empty = 0
    seen: set[str] = set()
    if not isinstance(raw_submissions, list):
        raw_submissions = []
        malformed += 1
    for submission in raw_submissions:
        if not isinstance(submission, Mapping):
            malformed += 1
            continue
        anonymous_id = submission.get("anonymous_id")
        if not isinstance(anonymous_id, str) or anonymous_id not in context["pages_by_student"] or anonymous_id in seen:
            malformed += 1
            continue
        seen.add(anonymous_id)
        expected_pages = [int(page["source_page"]) for page in context["pages_by_student"][anonymous_id]]
        status = submission.get("scope_status")
        try:
            included = _ordered_source_pages(submission.get("included_source_pages"), expected_pages, "included_source_pages")
            excluded = _ordered_source_pages(submission.get("excluded_source_pages"), expected_pages, "excluded_source_pages")
            _question_ids(submission.get("missing_question_ids"), anonymous_id=anonymous_id)
        except SubmissionScopeError:
            malformed += 1
            continue
        if status not in _SCOPE_STATUSES or set(included) & set(excluded) or set(included) | set(excluded) != set(expected_pages):
            malformed += 1
            continue
        if excluded != [page for page in expected_pages if page not in included]:
            malformed += 1
        if not included:
            selected_empty += 1
        if status == _SCOPE_STATUS_PENDING:
            pending += 1
        elif status == _SCOPE_STATUS_HUMAN:
            if not _text(submission.get("reviewer")) or not _text(submission.get("reviewed_at")) or not _text(submission.get("notes")):
                audit_missing += 1
        elif (
            len(expected_pages) != context["expected_pages_per_submission"]
            or included != expected_pages
            or excluded
            or submission.get("missing_question_ids")
            or _text(submission.get("reviewer"))
            or _text(submission.get("reviewed_at"))
            or _text(submission.get("notes"))
        ):
            unsafe_auto += 1
    _check(checks, "submission_rows_match_final_approvals", not malformed and seen == set(context["pages_by_student"]), "one valid scope row exists for each final-approved anonymous submission", f"malformed={malformed}; missing={len(set(context['pages_by_student']) - seen)}")
    _check(checks, "all_human_scope_decisions_completed", pending == 0, "every nonstandard submission has a completed human scope decision", f"{pending} submission(s) remain pending")
    _check(checks, "human_scope_decisions_have_audit_trail", audit_missing == 0, "every human scope decision has reviewer, time, and notes", f"{audit_missing} human decision(s) lack audit fields")
    _check(checks, "automatic_scope_is_limited_to_normal_complete_groups", unsafe_auto == 0, "automatic inclusion is used only for normal complete groups", f"{unsafe_auto} automatic decision(s) require human resolution")
    _check(checks, "each_submission_retains_evidence", selected_empty == 0, "each anonymous submission retains at least one page", f"{selected_empty} submission(s) retain no pages")
    failed = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": SUBMISSION_SCOPE_SCHEMA_VERSION,
        "report_type": "private_anonymous_submission_scope_readiness",
        "status": "ready_scope_only" if not failed else "not_ready",
        "submission_count": len(context["pages_by_student"]),
        "checks": checks,
        "failed_checks": failed,
        "model_run_allowed": False,
    }


def _ordered_source_pages(value: object, expected: Sequence[int], field: str) -> list[int]:
    if not isinstance(value, list) or any(type(item) is not int for item in value):
        raise SubmissionScopeError(f"{field} must be an integer list")
    if len(set(value)) != len(value) or any(item not in expected for item in value):
        raise SubmissionScopeError(f"{field} contains duplicate or unknown source pages")
    expected_order = [page for page in expected if page in value]
    if value != expected_order:
        raise SubmissionScopeError(f"{field} must preserve approved rendered-page order")
    return list(value)


def _question_ids(value: object, *, anonymous_id: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SubmissionScopeError(f"{anonymous_id} missing_question_ids must be a string list")
    result = [item.strip() for item in value]
    if len(set(result)) != len(result) or any(not _QUESTION_ID_PATTERN.fullmatch(item) for item in result):
        raise SubmissionScopeError(f"{anonymous_id} missing_question_ids are invalid or duplicated")
    return result


def _required_text(value: object, label: str) -> str:
    result = _text(value)
    if not result:
        raise SubmissionScopeError(f"{label} is required")
    return result


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_scope_id(value: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not _SCOPE_ID_PATTERN.fullmatch(normalized):
        raise SubmissionScopeError("scope_id must be 1-100 letters, digits, dots, underscores, or hyphens")
    return normalized


def _check(checks: list[dict[str, str]], check_id: str, passed: bool, success: str, failure: str) -> None:
    checks.append({"id": check_id, "status": "passed" if passed else "failed", "detail": success if passed else failure})


def _write_only_if_empty_or_identical(path: Path, payload: Mapping[str, Any]) -> None:
    canonical = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if not path.is_file() or path.read_bytes() != canonical:
            raise SubmissionScopeError(f"refusing to overwrite divergent private scope output: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical)


def _validate_existing_snapshot(output_root: Path, manifest: Mapping[str, Any]) -> None:
    path = output_root / SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH
    if not output_root.is_dir() or not path.is_file():
        raise SubmissionScopeError("existing snapshot target is incomplete")
    if _load_json_object(path, "existing snapshot manifest") != manifest:
        raise SubmissionScopeError("existing snapshot target has divergent manifest")
    expected = {SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH.as_posix()}
    for submission in manifest["submissions"]:
        for image in submission["images"]:
            relative = str(image["snapshot_image"])
            expected.add(relative)
            copied = output_root / relative
            if not copied.is_file() or sha256_file(copied) != image["sha256"]:
                raise SubmissionScopeError("existing snapshot target has changed image")
    actual = {path.relative_to(output_root).as_posix() for path in output_root.rglob("*") if path.is_file()}
    if actual != expected:
        raise SubmissionScopeError("existing snapshot target has unexpected or missing files")


def _write_snapshot(*, source_root: Path, output_root: Path, manifest: Mapping[str, Any]) -> None:
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.tmp-", dir=output_root.parent))
    try:
        for submission in manifest["submissions"]:
            for image in submission["images"]:
                source = _safe_source_file(source_root, str(image["source_image"]))
                target = temporary / str(image["snapshot_image"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                if sha256_file(target) != image["sha256"] or target.stat().st_size != image["bytes"]:
                    raise SubmissionScopeError("copied image hash mismatch")
        write_json(temporary / SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH, manifest)
        temporary.replace(output_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
