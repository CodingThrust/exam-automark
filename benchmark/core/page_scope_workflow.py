from __future__ import annotations

"""Private, auditable review scaffolding for anomalous submission page counts.

The mixed-submission assembler deliberately keeps a converted group even when
its page count differs from the course expectation.  That is safer than
silently dropping a page, but it leaves a human scope decision before a group
can join a frozen grading cohort.

This module makes that decision reviewable without copying raw filenames,
answers, or source-page paths into the worksheet.  It is not an anonymization
approval and it never authorizes a model run.
"""

import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


PAGE_SCOPE_REVIEW_COLUMNS = (
    "anonymous_id",
    "rendered_page_count",
    "expected_pages_per_group",
    "scope_review_status",
    "reviewer",
    "reviewed_at",
    "notes",
)

PAGE_SCOPE_REVIEW_SCHEMA_VERSION = 1
PAGE_SCOPE_REVIEW_RECORD_TYPE = "private_page_scope_review"
PAGE_SCOPE_REVIEW_STATUSES = frozenset(
    {"pending", "approved_include_all", "requires_correction"}
)

_ANONYMOUS_ID_PATTERN = re.compile(r"^S[0-9]{3,}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PageScopeReviewError(ValueError):
    """Raised when page-scope review inputs are incomplete or inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PageScopeReviewError(f"cannot load {label}: {path}") from error
    if not isinstance(payload, dict):
        raise PageScopeReviewError(f"{label} must be a JSON object")
    return payload


def page_scope_review_rows(
    private_manifest: Mapping[str, Any], *, expected_pages_per_group: int
) -> list[dict[str, str]]:
    """Return one non-sensitive review row for each anomalous converted group."""

    anomalies = _validated_anomaly_groups(
        private_manifest, expected_pages_per_group=expected_pages_per_group
    )
    return [
        {
            "anonymous_id": anonymous_id,
            "rendered_page_count": str(rendered_page_count),
            "expected_pages_per_group": str(expected_pages_per_group),
            "scope_review_status": "pending",
            "reviewer": "",
            "reviewed_at": "",
            "notes": (
                "confirm whether every displayed page belongs to this same submission; "
                "use requires_correction for a missing page, duplicate, separator, "
                "unrelated page, or any nonstandard continuation that needs a revised layout"
            ),
        }
        for anonymous_id, rendered_page_count in anomalies
    ]


def build_page_scope_review_metadata(
    *,
    private_manifest: Mapping[str, Any],
    private_manifest_sha256: str,
    expected_pages_per_group: int,
) -> dict[str, Any]:
    """Build a raw-filename-free binding for a private review worksheet."""

    if not _SHA256_PATTERN.fullmatch(private_manifest_sha256):
        raise PageScopeReviewError("private manifest hash must be a SHA-256 digest")
    anomalies = _validated_anomaly_groups(
        private_manifest, expected_pages_per_group=expected_pages_per_group
    )
    assessment_id = private_manifest.get("assessment_id")
    if not isinstance(assessment_id, str) or not assessment_id:
        raise PageScopeReviewError("private manifest requires a non-empty assessment_id")
    return {
        "schema_version": PAGE_SCOPE_REVIEW_SCHEMA_VERSION,
        "record_type": PAGE_SCOPE_REVIEW_RECORD_TYPE,
        "assessment_id": assessment_id,
        "private_manifest_sha256": private_manifest_sha256,
        "expected_pages_per_group": expected_pages_per_group,
        "anomaly_group_count": len(anomalies),
        "anomaly_rows_sha256": _anomaly_rows_sha256(anomalies),
        "model_run_allowed": False,
        "model_run_blockers": [
            "Each anomalous page-count group requires a completed page-scope decision.",
            "This review does not replace identity, grading-mark, or final anonymization approval.",
        ],
    }


def initialize_page_scope_review(
    *,
    private_manifest_path: Path,
    expected_pages_per_group: int,
    review_csv_path: Path,
    metadata_path: Path,
) -> dict[str, Any]:
    """Write a fresh private worksheet and its immutable input binding.

    Existing outputs are accepted only when byte-for-byte identical to the
    canonical pending template.  A reviewed worksheet is therefore never
    silently overwritten by a later initialization run.
    """

    _require_distinct_paths(review_csv_path, metadata_path)
    manifest_path = _require_regular_file(private_manifest_path, "private manifest")
    manifest = load_json_object(manifest_path, "private manifest")
    rows = page_scope_review_rows(
        manifest, expected_pages_per_group=expected_pages_per_group
    )
    metadata = build_page_scope_review_metadata(
        private_manifest=manifest,
        private_manifest_sha256=sha256_file(manifest_path),
        expected_pages_per_group=expected_pages_per_group,
    )
    expected_outputs = {
        review_csv_path: _review_csv_bytes(rows),
        metadata_path: _canonical_json_bytes(metadata),
    }
    status = _write_output_group_only_if_empty_or_identical(expected_outputs)
    return {
        "status": "already_matches_template" if status == "already_matches" else "created",
        "review_csv_path": str(review_csv_path),
        "metadata_path": str(metadata_path),
        "anomaly_group_count": len(rows),
        "model_run_allowed": False,
    }


def validate_page_scope_review(
    *,
    private_manifest_path: Path,
    expected_pages_per_group: int,
    review_csv_path: Path,
    metadata_path: Path,
) -> dict[str, Any]:
    """Validate the worksheet against its source manifest without exposing it."""

    manifest_path = _require_regular_file(private_manifest_path, "private manifest")
    review_path = _require_regular_file(review_csv_path, "page-scope review CSV")
    metadata_file = _require_regular_file(metadata_path, "page-scope review metadata")
    manifest = load_json_object(manifest_path, "private manifest")
    metadata = load_json_object(metadata_file, "page-scope review metadata")
    expected_anomalies = _validated_anomaly_groups(
        manifest, expected_pages_per_group=expected_pages_per_group
    )
    expected_rows = {
        anonymous_id: rendered_page_count
        for anonymous_id, rendered_page_count in expected_anomalies
    }
    columns, rows = _load_csv_rows(review_path)

    checks: list[dict[str, str]] = []
    _check(
        checks,
        "metadata_schema_supported",
        metadata.get("schema_version") == PAGE_SCOPE_REVIEW_SCHEMA_VERSION
        and metadata.get("record_type") == PAGE_SCOPE_REVIEW_RECORD_TYPE,
        "page-scope review metadata schema is supported",
        "page-scope review metadata schema or record type is invalid",
    )
    _check(
        checks,
        "metadata_binds_private_manifest",
        metadata.get("private_manifest_sha256") == sha256_file(manifest_path),
        "review metadata binds to the supplied private manifest",
        "review metadata does not match the supplied private manifest",
    )
    _check(
        checks,
        "metadata_matches_expected_scope",
        metadata.get("assessment_id") == manifest.get("assessment_id")
        and metadata.get("expected_pages_per_group") == expected_pages_per_group
        and metadata.get("anomaly_group_count") == len(expected_rows)
        and metadata.get("anomaly_rows_sha256")
        == _anomaly_rows_sha256(expected_anomalies),
        "review metadata matches the current anomalous-group set",
        "review metadata does not match the current anomalous-group set",
    )
    _check(
        checks,
        "review_columns_exact",
        tuple(columns) == PAGE_SCOPE_REVIEW_COLUMNS,
        "review CSV has the canonical non-sensitive columns",
        "review CSV columns differ from the canonical non-sensitive schema",
    )

    row_by_id: dict[str, Mapping[str, str]] = {}
    malformed_rows = 0
    unexpected_or_duplicate_rows = 0
    pending_rows = 0
    correction_rows = 0
    audit_missing = 0
    correction_notes_missing = 0
    for row in rows:
        anonymous_id = _cell(row, "anonymous_id")
        page_count = _positive_int(_cell(row, "rendered_page_count"))
        expected_count = _positive_int(_cell(row, "expected_pages_per_group"))
        if (
            not _ANONYMOUS_ID_PATTERN.fullmatch(anonymous_id)
            or page_count is None
            or expected_count is None
            or anonymous_id not in expected_rows
            or anonymous_id in row_by_id
        ):
            unexpected_or_duplicate_rows += 1
            continue
        row_by_id[anonymous_id] = row
        if page_count != expected_rows[anonymous_id] or expected_count != expected_pages_per_group:
            malformed_rows += 1
        status = _cell(row, "scope_review_status")
        if status not in PAGE_SCOPE_REVIEW_STATUSES:
            malformed_rows += 1
            continue
        if status == "pending":
            pending_rows += 1
        else:
            if not _cell(row, "reviewer") or not _cell(row, "reviewed_at"):
                audit_missing += 1
            if status == "requires_correction":
                correction_rows += 1
                if not _cell(row, "notes"):
                    correction_notes_missing += 1
    missing_rows = set(expected_rows) - set(row_by_id)
    _check(
        checks,
        "review_rows_match_anomaly_groups",
        not malformed_rows and not unexpected_or_duplicate_rows and not missing_rows,
        "review CSV has one matching row per anomalous group",
        (
            f"malformed={malformed_rows}; unexpected_or_duplicate="
            f"{unexpected_or_duplicate_rows}; missing={len(missing_rows)}"
        ),
    )
    _check(
        checks,
        "all_page_scope_decisions_completed",
        pending_rows == 0,
        "every anomalous group has a scope decision",
        f"{pending_rows} anomalous groups remain pending",
    )
    _check(
        checks,
        "completed_decisions_have_audit_trail",
        audit_missing == 0,
        "completed decisions have reviewer and timestamp",
        f"{audit_missing} completed decisions lack reviewer or timestamp",
    )
    _check(
        checks,
        "corrections_are_explained",
        correction_notes_missing == 0,
        "scope corrections include a note",
        f"{correction_notes_missing} scope corrections lack a note",
    )
    _check(
        checks,
        "all_anomalies_approved_include_all",
        correction_rows == 0,
        (
            "all anomalous groups record that every displayed page belongs to the "
            "same submission; nonstandard page counts still need cohort-scope handling"
        ),
        (
            f"{correction_rows} group(s) require a new corrected assembly or "
            "page layout before cohort freeze"
        ),
    )
    failed = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "private_page_scope_review_readiness",
        "status": "ready" if not failed else "not_ready",
        "anomaly_group_count": len(expected_rows),
        "checks": checks,
        "failed_checks": failed,
        "model_run_allowed": False,
    }


def _validated_anomaly_groups(
    private_manifest: Mapping[str, Any], *, expected_pages_per_group: int
) -> tuple[tuple[str, int], ...]:
    if expected_pages_per_group < 1:
        raise PageScopeReviewError("expected_pages_per_group must be positive")
    if private_manifest.get("record_type") != "private_mixed_submission_assembly":
        raise PageScopeReviewError("private manifest has an unexpected record_type")
    groups = private_manifest.get("groups")
    if not isinstance(groups, list):
        raise PageScopeReviewError("private manifest groups must be a list")
    anomalies: list[tuple[str, int]] = []
    seen_ids: set[str] = set()
    for group in groups:
        if not isinstance(group, Mapping):
            raise PageScopeReviewError("private manifest contains a malformed group")
        if group.get("status") != "converted_pending_page_review":
            continue
        anonymous_id = group.get("anonymous_id")
        page_count = group.get("rendered_page_count")
        page_count_status = group.get("page_count_status")
        if (
            not isinstance(anonymous_id, str)
            or not _ANONYMOUS_ID_PATTERN.fullmatch(anonymous_id)
            or isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or page_count < 1
            or anonymous_id in seen_ids
        ):
            raise PageScopeReviewError("private manifest has an invalid converted group")
        seen_ids.add(anonymous_id)
        should_be_anomaly = page_count != expected_pages_per_group
        if page_count_status != (
            "requires_page_scope_review" if should_be_anomaly else "matches_expected"
        ):
            raise PageScopeReviewError(
                "private manifest page_count_status does not match the supplied expected page count"
            )
        if should_be_anomaly:
            anomalies.append((anonymous_id, page_count))
    return tuple(sorted(anomalies))


def _anomaly_rows_sha256(rows: Sequence[tuple[str, int]]) -> str:
    canonical = json.dumps(list(rows), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _review_csv_bytes(rows: Sequence[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=PAGE_SCOPE_REVIEW_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in PAGE_SCOPE_REVIEW_COLUMNS})
    return stream.getvalue().encode("utf-8")


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _write_output_group_only_if_empty_or_identical(expected_outputs: Mapping[Path, bytes]) -> str:
    existing_nonempty = {
        path: path.read_bytes()
        for path in expected_outputs
        if path.exists() and path.is_file() and path.read_bytes()
    }
    invalid_targets = [path for path in expected_outputs if path.exists() and not path.is_file()]
    if invalid_targets:
        raise PageScopeReviewError(
            "page-scope review outputs must be files: "
            + ", ".join(str(path) for path in invalid_targets)
        )
    if existing_nonempty:
        divergent = [
            path
            for path, expected in expected_outputs.items()
            if not path.is_file() or path.read_bytes() != expected
        ]
        if divergent:
            raise PageScopeReviewError(
                "refusing to overwrite existing divergent page-scope review outputs: "
                + ", ".join(str(path) for path in divergent)
            )
        return "already_matches"
    for path, expected in expected_outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
    return "created"


def _load_csv_rows(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def _require_regular_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise PageScopeReviewError(f"{label} must be a regular file: {path}")
    return resolved


def _require_distinct_paths(*paths: Path) -> None:
    normalized = [path.resolve() for path in paths]
    if len(normalized) != len(set(normalized)):
        raise PageScopeReviewError("page-scope review output paths must be distinct")


def _cell(row: Mapping[str, str], column: str) -> str:
    value = row.get(column, "")
    return value.strip() if isinstance(value, str) else ""


def _positive_int(value: str) -> int | None:
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _check(
    checks: list[dict[str, str]],
    check_id: str,
    passed: bool,
    success_detail: str,
    failure_detail: str,
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": "passed" if passed else "failed",
            "detail": success_detail if passed else failure_detail,
        }
    )
