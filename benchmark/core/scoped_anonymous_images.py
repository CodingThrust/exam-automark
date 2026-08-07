from __future__ import annotations

"""Build a narrow, audited image-only snapshot from approved anonymous inputs.

The anonymization renderer deliberately produces every page that was needed for
human final review.  A grading experiment should not have to receive every one
of those pages: for example, a week may use only its first and third rendered
pages.  This module creates that smaller input set only after it rechecks the
post-render approval evidence and the rendered-artifact hashes.

The output is deliberately *not* a grading packet and never authorizes a model
run.  It is a local, image-only transport boundary for a separately approved
question scope.
"""

import csv
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from benchmark.core.anonymization import (
    ANONYMIZATION_REVIEW_COLUMNS,
    ANONYMOUS_ID_PATTERN,
    SHA256_PATTERN,
    sha256_file,
    write_json,
)


SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_RECORD_TYPE = "scoped_anonymous_image_snapshot"
SNAPSHOT_MANIFEST_RELATIVE_PATH = Path("manifest/scoped-anonymous-image-snapshot.json")

_PAGE_SUFFIX_PATTERN = re.compile(r"^p[0-9]{2,}$")
_SCOPE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_IMAGE_PATH_PATTERN = re.compile(
    r"^anonymized_pages/(S[0-9]{3})/(S[0-9]{3})-(p[0-9]{2,})\.png$"
)
_PDF_PATH_PATTERN = re.compile(r"^anonymized_pdfs/(S[0-9]{3})\.pdf$")

_APPROVAL_COLUMNS = (
    ("privacy_review_status", "privacy_reviewer", "privacy_reviewed_at"),
    ("blindness_review_status", "blindness_reviewer", "blindness_reviewed_at"),
    (
        "answer_content_status",
        "answer_content_reviewer",
        "answer_content_reviewed_at",
    ),
)

_REQUIRED_FINAL_VALIDATION_CHECKS = frozenset(
    {
        "required_columns_present",
        "review_pairs_match_layout",
        "review_output_paths_match_layout",
        "review_render_spec_matches_preparation",
        "review_artifact_manifest_matches_preparation",
        "review_status_values_valid",
        "privacy_review_approved",
        "blindness_review_approved",
        "answer_content_review_approved",
        "approved_reviews_have_audit_trail",
        "layout_hash_matches_preparation",
        "review_path_matches_preparation_metadata",
        "render_spec_matches_preparation",
        "artifact_manifest_hash_matches_preparation",
        "artifact_manifest_covers_expected_outputs",
        "prepared_output_tree_matches_expected_paths",
        "prepared_output_hashes_match",
    }
)


class ScopedSnapshotError(ValueError):
    """Raised when a source, scope, or target fails the local safety contract."""


def build_scoped_anonymous_image_snapshot(
    *,
    artifact_root: Path,
    final_review_path: Path,
    final_review_validation_path: Path,
    page_suffixes: Sequence[str],
    scope_id: str,
    output_root: Path,
    cohort_preflight_path: Path | None = None,
) -> dict[str, Any]:
    """Copy selected, final-approved PNGs into a new local snapshot root.

    ``page_suffixes`` are the local rendered page numbers (for example
    ``("p01", "p03")``), not source-PDF page numbers.  Every anonymous student
    in the final review must have every requested suffix.  The function is
    idempotent only when an existing target exactly matches the requested
    manifest and image hashes; any divergent target is refused without writing.
    """

    normalized_suffixes = _normalize_page_suffixes(page_suffixes)
    normalized_scope_id = _normalize_scope_id(scope_id)
    source_root = _require_directory(artifact_root, "artifact root")
    output_root = output_root.resolve()
    _reject_overlapping_roots(source_root, output_root)
    _require_private_output_root(source_root, output_root)

    manifest_root = (source_root / "manifest").resolve()
    expected_review_path = manifest_root / "anonymization_review.csv"
    expected_validation_path = manifest_root / "final-review-validation.json"
    review_path = _require_file(final_review_path, "final review CSV")
    validation_path = _require_file(
        final_review_validation_path, "final-review-validation report"
    )
    if review_path != expected_review_path:
        raise ScopedSnapshotError(
            "final review CSV must be artifact_root/manifest/anonymization_review.csv"
        )
    if validation_path != expected_validation_path:
        raise ScopedSnapshotError(
            "final-review-validation report must be the sibling "
            "artifact_root/manifest/final-review-validation.json"
        )

    metadata_path = _require_file(manifest_root / "prep-metadata.json", "prep metadata")
    metadata = _load_json_object(metadata_path, "prep metadata")
    _validate_preparation_metadata(
        metadata=metadata,
        source_root=source_root,
        review_path=review_path,
    )

    validation = _load_json_object(validation_path, "final-review-validation report")
    review_rows = _load_final_review_rows(
        review_path,
        expected_render_spec_sha256=_required_sha256(
            metadata.get("render_spec_sha256"), "prep metadata render_spec_sha256"
        ),
        expected_artifact_manifest_sha256=_required_sha256(
            metadata.get("artifact_manifest_sha256"),
            "prep metadata artifact_manifest_sha256",
        ),
    )
    _validate_final_review_validation(
        validation=validation,
        review_row_count=len(review_rows),
    )
    cohort_preflight = _load_and_validate_cohort_preflight(
        cohort_preflight_path=cohort_preflight_path,
        metadata=metadata,
        metadata_path=metadata_path,
        validation_path=validation_path,
    )

    artifact_manifest_path = _resolve_metadata_relative_path(
        source_root=source_root,
        value=metadata.get("artifact_manifest_path"),
        field_name="artifact_manifest_path",
    )
    artifact_manifest = _load_json_object(artifact_manifest_path, "output artifact manifest")
    declared_artifact_manifest_sha256 = _required_sha256(
        metadata.get("artifact_manifest_sha256"), "prep metadata artifact_manifest_sha256"
    )
    if sha256_file(artifact_manifest_path) != declared_artifact_manifest_sha256:
        raise ScopedSnapshotError(
            "output artifact manifest hash does not match schema-v2 preparation metadata"
        )

    source_artifacts = _validate_source_artifact_tree(
        source_root=source_root,
        review_rows=review_rows,
        artifact_manifest=artifact_manifest,
        expected_render_spec_sha256=_required_sha256(
            metadata.get("render_spec_sha256"), "prep metadata render_spec_sha256"
        ),
    )
    selected = _select_complete_scope(
        review_rows=review_rows,
        source_artifacts=source_artifacts,
        page_suffixes=normalized_suffixes,
    )
    snapshot_manifest = _build_snapshot_manifest(
        metadata=metadata,
        metadata_path=metadata_path,
        review_path=review_path,
        validation_path=validation_path,
        artifact_manifest_path=artifact_manifest_path,
        scope_id=normalized_scope_id,
        page_suffixes=normalized_suffixes,
        selected=selected,
        cohort_preflight=cohort_preflight,
    )

    if output_root.exists():
        _validate_existing_target(output_root, snapshot_manifest)
        return {
            "status": "already_built",
            "output_root": str(output_root),
            "manifest_path": str(output_root / SNAPSHOT_MANIFEST_RELATIVE_PATH),
            "student_count": snapshot_manifest["student_count"],
            "image_count": snapshot_manifest["image_count"],
            "model_run_allowed": False,
        }

    _write_new_snapshot(
        source_root=source_root,
        output_root=output_root,
        selected=selected,
        snapshot_manifest=snapshot_manifest,
    )
    return {
        "status": "built",
        "output_root": str(output_root),
        "manifest_path": str(output_root / SNAPSHOT_MANIFEST_RELATIVE_PATH),
        "student_count": snapshot_manifest["student_count"],
        "image_count": snapshot_manifest["image_count"],
        "model_run_allowed": False,
    }


def _normalize_page_suffixes(page_suffixes: Sequence[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for suffix in page_suffixes:
        if not isinstance(suffix, str) or not _PAGE_SUFFIX_PATTERN.fullmatch(suffix.strip()):
            raise ScopedSnapshotError(
                "each page suffix must use the rendered-page form pNN, for example p01"
            )
        normalized.add(suffix.strip())
    if not normalized:
        raise ScopedSnapshotError("at least one declared page suffix is required")
    return tuple(sorted(normalized))


def _normalize_scope_id(scope_id: str) -> str:
    normalized = scope_id.strip() if isinstance(scope_id, str) else ""
    if not _SCOPE_ID_PATTERN.fullmatch(normalized):
        raise ScopedSnapshotError(
            "scope_id must be 1-100 characters of letters, digits, dot, underscore, or hyphen"
        )
    return normalized


def _require_directory(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_dir():
        raise ScopedSnapshotError(f"{label} is not a directory: {path}")
    return resolved


def _require_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise ScopedSnapshotError(f"{label} is not a regular file: {path}")
    return resolved


def _reject_overlapping_roots(source_root: Path, output_root: Path) -> None:
    if _is_within(output_root, source_root) or _is_within(source_root, output_root):
        raise ScopedSnapshotError(
            "output root must not be the artifact root, its parent, or any descendant"
        )


def _require_private_output_root(source_root: Path, output_root: Path) -> None:
    """Keep copied student work below the source's local private-data boundary.

    Course artifacts conventionally live under an ignored ``Data`` directory.
    For synthetic/test artifacts outside that layout, the artifact-root parent is
    the local boundary.  Either way, this prevents a caller from accidentally
    writing the copied PNGs into a tracked repository directory.
    """

    private_root = _nearest_data_ancestor(source_root) or source_root.parent
    if not _is_within(output_root, private_root):
        raise ScopedSnapshotError(
            "output root must stay inside the source private-data boundary: "
            f"{private_root}"
        )


def _nearest_data_ancestor(path: Path) -> Path | None:
    candidates = (path, *path.parents)
    for candidate in candidates:
        if candidate.name.lower() == "data":
            return candidate
    return None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScopedSnapshotError(f"{label} is not readable JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ScopedSnapshotError(f"{label} must be a JSON object: {path}")
    return payload


def _validate_preparation_metadata(
    *, metadata: Mapping[str, Any], source_root: Path, review_path: Path
) -> None:
    if metadata.get("schema_version") != 2:
        raise ScopedSnapshotError("snapshot building requires schema-v2 preparation metadata")
    if metadata.get("record_type") != "anonymized_assessment_preparation":
        raise ScopedSnapshotError("prep metadata has an unexpected record_type")
    declared_review = _resolve_metadata_relative_path(
        source_root=source_root,
        value=metadata.get("review_path"),
        field_name="review_path",
    )
    if declared_review != review_path:
        raise ScopedSnapshotError(
            "supplied final review CSV differs from the schema-v2 preparation metadata"
        )
    _required_sha256(metadata.get("render_spec_sha256"), "prep metadata render_spec_sha256")
    _required_sha256(
        metadata.get("artifact_manifest_sha256"), "prep metadata artifact_manifest_sha256"
    )


def _resolve_metadata_relative_path(
    *, source_root: Path, value: object, field_name: str
) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ScopedSnapshotError(f"prep metadata {field_name} must be non-empty text")
    relative = Path(value)
    if relative.is_absolute():
        raise ScopedSnapshotError(f"prep metadata {field_name} must be relative to artifact root")
    candidate = (source_root / relative).resolve()
    if not _is_within(candidate, source_root):
        raise ScopedSnapshotError(
            f"prep metadata {field_name} must resolve inside the artifact root"
        )
    if not candidate.is_file() or candidate.is_symlink():
        raise ScopedSnapshotError(f"prep metadata {field_name} does not name a regular file")
    return candidate


def _required_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise ScopedSnapshotError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _load_final_review_rows(
    review_path: Path,
    *,
    expected_render_spec_sha256: str,
    expected_artifact_manifest_sha256: str,
) -> list[dict[str, Any]]:
    try:
        with review_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = tuple(reader.fieldnames or ())
    except OSError as error:
        raise ScopedSnapshotError(f"cannot read final review CSV: {review_path}") from error

    missing = [column for column in ANONYMIZATION_REVIEW_COLUMNS if column not in fieldnames]
    if missing:
        raise ScopedSnapshotError(
            "final review CSV is missing required columns: " + ", ".join(missing)
        )
    if not rows:
        raise ScopedSnapshotError("final review CSV must contain at least one approved page")

    records: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, int]] = set()
    seen_images: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        if _cell(row, "render_spec_sha256") != expected_render_spec_sha256:
            raise ScopedSnapshotError(
                f"final review row {row_number} is bound to a different render specification"
            )
        if _cell(row, "artifact_manifest_sha256") != expected_artifact_manifest_sha256:
            raise ScopedSnapshotError(
                f"final review row {row_number} is bound to a different artifact manifest"
            )
        anonymous_id = _cell(row, "anonymous_id")
        if not ANONYMOUS_ID_PATTERN.fullmatch(anonymous_id):
            raise ScopedSnapshotError(f"final review row {row_number} has an invalid anonymous ID")
        try:
            source_page = int(_cell(row, "source_page"))
        except ValueError as error:
            raise ScopedSnapshotError(
                f"final review row {row_number} has an invalid source page"
            ) from error
        if source_page <= 0:
            raise ScopedSnapshotError(f"final review row {row_number} has an invalid source page")
        pair = (anonymous_id, source_page)
        if pair in seen_pairs:
            raise ScopedSnapshotError(f"final review has duplicate anonymous/source-page row: {pair}")
        seen_pairs.add(pair)

        for status_column, reviewer_column, reviewed_at_column in _APPROVAL_COLUMNS:
            if _cell(row, status_column) != "approved":
                raise ScopedSnapshotError(
                    f"final review row {row_number} is not approved for {status_column}"
                )
            if not _cell(row, reviewer_column) or not _cell(row, reviewed_at_column):
                raise ScopedSnapshotError(
                    f"final review row {row_number} lacks audit trail for {status_column}"
                )

        image_path, suffix = _parse_review_image_path(
            _cell(row, "output_image"), anonymous_id=anonymous_id, row_number=row_number
        )
        if image_path in seen_images:
            raise ScopedSnapshotError(f"final review has duplicate output image: {image_path}")
        seen_images.add(image_path)
        pdf_path = _parse_review_pdf_path(
            _cell(row, "output_pdf"), anonymous_id=anonymous_id, row_number=row_number
        )
        records.append(
            {
                "anonymous_id": anonymous_id,
                "source_page": source_page,
                "page_suffix": suffix,
                "output_image": image_path,
                "output_pdf": pdf_path,
            }
        )
    return sorted(records, key=lambda record: (record["anonymous_id"], record["page_suffix"]))


def _cell(row: Mapping[str, object], column: str) -> str:
    value = row.get(column, "")
    return value.strip() if isinstance(value, str) else ""


def _parse_review_image_path(value: str, *, anonymous_id: str, row_number: int) -> tuple[str, str]:
    match = _IMAGE_PATH_PATTERN.fullmatch(value)
    if match is None or match.group(1) != anonymous_id or match.group(2) != anonymous_id:
        raise ScopedSnapshotError(
            f"final review row {row_number} has an unexpected anonymous PNG path"
        )
    return value, match.group(3)


def _parse_review_pdf_path(value: str, *, anonymous_id: str, row_number: int) -> str:
    match = _PDF_PATH_PATTERN.fullmatch(value)
    if match is None or match.group(1) != anonymous_id:
        raise ScopedSnapshotError(
            f"final review row {row_number} has an unexpected anonymous PDF path"
        )
    return value


def _validate_final_review_validation(
    *, validation: Mapping[str, Any], review_row_count: int
) -> None:
    if validation.get("schema_version") != 1:
        raise ScopedSnapshotError("final-review-validation report has an unsupported schema")
    if validation.get("report_type") != "anonymization_review_readiness":
        raise ScopedSnapshotError("final-review-validation report has an unexpected report_type")
    if validation.get("status") != "ready":
        raise ScopedSnapshotError("final-review-validation report is not ready")
    if validation.get("failed_checks") != []:
        raise ScopedSnapshotError("final-review-validation report must have no failed checks")
    if validation.get("expected_page_count") != review_row_count or validation.get(
        "review_row_count"
    ) != review_row_count:
        raise ScopedSnapshotError(
            "final-review-validation page counts do not match the supplied review CSV"
        )

    checks = validation.get("checks")
    if not isinstance(checks, list):
        raise ScopedSnapshotError("final-review-validation report must contain checks")
    check_statuses: dict[str, str] = {}
    for check in checks:
        if not isinstance(check, Mapping):
            raise ScopedSnapshotError("final-review-validation report contains an invalid check")
        check_id = check.get("id")
        status = check.get("status")
        if not isinstance(check_id, str) or not isinstance(status, str) or check_id in check_statuses:
            raise ScopedSnapshotError("final-review-validation report contains duplicate/invalid checks")
        check_statuses[check_id] = status
    missing = sorted(
        check_id
        for check_id in _REQUIRED_FINAL_VALIDATION_CHECKS
        if check_statuses.get(check_id) != "passed"
    )
    if missing:
        raise ScopedSnapshotError(
            "final-review-validation lacks passed required checks: " + ", ".join(missing)
        )


def _load_and_validate_cohort_preflight(
    *,
    cohort_preflight_path: Path | None,
    metadata: Mapping[str, Any],
    metadata_path: Path,
    validation_path: Path,
) -> dict[str, str] | None:
    """Optionally bind this snapshot to a ready cohort preflight.

    The optional argument preserves compatibility for existing generic
    snapshots.  When present, it proves that the preflight's final-approval
    and page-scope decision were created for these exact source artifacts.
    """

    if cohort_preflight_path is None:
        return None
    preflight_path = _require_file(cohort_preflight_path, "cohort preflight report")
    preflight = _load_json_object(preflight_path, "cohort preflight report")
    if preflight.get("schema_version") != 1:
        raise ScopedSnapshotError("cohort preflight report has an unsupported schema")
    if preflight.get("record_type") != "private_anonymous_cohort_preflight":
        raise ScopedSnapshotError("cohort preflight report has an unexpected record_type")
    if preflight.get("status") != "ready" or preflight.get("failed_checks") != []:
        raise ScopedSnapshotError("cohort preflight report is not ready")
    if preflight.get("model_run_allowed") is not False:
        raise ScopedSnapshotError("cohort preflight report must not authorize model execution")
    if preflight.get("assessment_id") != metadata.get("assessment_id"):
        raise ScopedSnapshotError("cohort preflight assessment does not match prep metadata")
    bindings = preflight.get("bindings")
    if not isinstance(bindings, Mapping):
        raise ScopedSnapshotError("cohort preflight report lacks provenance bindings")
    if bindings.get("preparation_metadata_sha256") != sha256_file(metadata_path):
        raise ScopedSnapshotError(
            "cohort preflight preparation metadata hash does not match this artifact"
        )
    if bindings.get("final_review_validation_sha256") != sha256_file(validation_path):
        raise ScopedSnapshotError(
            "cohort preflight final validation hash does not match this artifact"
        )
    return {"sha256": sha256_file(preflight_path)}


def _validate_source_artifact_tree(
    *,
    source_root: Path,
    review_rows: Sequence[Mapping[str, Any]],
    artifact_manifest: Mapping[str, Any],
    expected_render_spec_sha256: str,
) -> dict[str, dict[str, Any]]:
    if artifact_manifest.get("schema_version") != 1:
        raise ScopedSnapshotError("output artifact manifest has an unsupported schema")
    if artifact_manifest.get("record_type") != "anonymized_assessment_output_artifacts":
        raise ScopedSnapshotError("output artifact manifest has an unexpected record_type")
    if artifact_manifest.get("render_spec_sha256") != expected_render_spec_sha256:
        raise ScopedSnapshotError("output artifact manifest is bound to a different render specification")

    expected_paths = {
        str(record["output_image"]) for record in review_rows
    } | {str(record["output_pdf"]) for record in review_rows}
    _validate_source_media_tree(source_root, expected_paths)

    raw_entries = artifact_manifest.get("artifacts")
    if not isinstance(raw_entries, list):
        raise ScopedSnapshotError("output artifact manifest must contain an artifacts list")
    entries: dict[str, dict[str, Any]] = {}
    for entry in raw_entries:
        if not isinstance(entry, Mapping):
            raise ScopedSnapshotError("output artifact manifest contains an invalid artifact entry")
        path = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("bytes")
        if not isinstance(path, str) or path not in expected_paths or path in entries:
            raise ScopedSnapshotError("output artifact manifest contains unexpected/duplicate paths")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ScopedSnapshotError("output artifact manifest contains an invalid SHA-256 digest")
        if type(size) is not int or size < 0:
            raise ScopedSnapshotError("output artifact manifest contains an invalid byte count")
        entries[path] = {"sha256": digest, "bytes": size}
    if set(entries) != expected_paths:
        raise ScopedSnapshotError(
            "output artifact manifest does not cover exactly the approved review outputs"
        )

    for relative_path, entry in entries.items():
        source_path = _safe_source_file(source_root, relative_path)
        if source_path.stat().st_size != entry["bytes"] or sha256_file(source_path) != entry["sha256"]:
            raise ScopedSnapshotError(
                f"approved source artifact changed or is missing: {relative_path}"
            )
    return entries


def _validate_source_media_tree(source_root: Path, expected_paths: set[str]) -> None:
    for directory in ("anonymized_pages", "anonymized_pdfs"):
        root = source_root / directory
        if not root.is_dir() or root.is_symlink():
            raise ScopedSnapshotError(f"source artifact is missing regular {directory} directory")
        allowed_directories = {directory}
        for expected_path in expected_paths:
            if expected_path.startswith(directory + "/"):
                parent = Path(expected_path).parent
                while parent != Path("."):
                    allowed_directories.add(parent.as_posix())
                    parent = parent.parent
        actual_files: set[str] = set()
        for path in root.rglob("*"):
            relative = path.relative_to(source_root).as_posix()
            if path.is_symlink():
                raise ScopedSnapshotError(f"source artifact contains a symlink: {relative}")
            if path.is_dir():
                if relative not in allowed_directories:
                    raise ScopedSnapshotError(f"source artifact contains an unexpected directory: {relative}")
            elif path.is_file():
                if relative not in expected_paths:
                    raise ScopedSnapshotError(
                        f"source artifact contains an unexpected file type/page: {relative}"
                    )
                actual_files.add(relative)
            else:
                raise ScopedSnapshotError(f"source artifact contains an unsupported entry: {relative}")
        expected_for_directory = {
            path for path in expected_paths if path.startswith(directory + "/")
        }
        if actual_files != expected_for_directory:
            raise ScopedSnapshotError(
                f"source artifact {directory} tree does not match the final review outputs"
            )


def _safe_source_file(source_root: Path, relative_path: str) -> Path:
    candidate = (source_root / relative_path).resolve()
    if not _is_within(candidate, source_root) or not candidate.is_file() or candidate.is_symlink():
        raise ScopedSnapshotError(f"source artifact path is unsafe or missing: {relative_path}")
    return candidate


def _select_complete_scope(
    *,
    review_rows: Sequence[Mapping[str, Any]],
    source_artifacts: Mapping[str, Mapping[str, Any]],
    page_suffixes: Sequence[str],
) -> list[dict[str, Any]]:
    by_student: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in review_rows:
        anonymous_id = str(row["anonymous_id"])
        suffix = str(row["page_suffix"])
        student_rows = by_student.setdefault(anonymous_id, {})
        if suffix in student_rows:
            raise ScopedSnapshotError(
                f"final review maps {anonymous_id} more than once to rendered suffix {suffix}"
            )
        student_rows[suffix] = row

    selected: list[dict[str, Any]] = []
    for anonymous_id in sorted(by_student):
        rows_by_suffix = by_student[anonymous_id]
        missing = [suffix for suffix in page_suffixes if suffix not in rows_by_suffix]
        if missing:
            raise ScopedSnapshotError(
                f"declared scope is incomplete for {anonymous_id}: missing {', '.join(missing)}"
            )
        for suffix in page_suffixes:
            row = rows_by_suffix[suffix]
            image_path = str(row["output_image"])
            entry = source_artifacts[image_path]
            selected.append(
                {
                    "anonymous_id": anonymous_id,
                    "source_page": int(row["source_page"]),
                    "page_suffix": suffix,
                    "source_image": image_path,
                    "snapshot_image": image_path,
                    "sha256": str(entry["sha256"]),
                    "bytes": int(entry["bytes"]),
                }
            )
    return selected


def _build_snapshot_manifest(
    *,
    metadata: Mapping[str, Any],
    metadata_path: Path,
    review_path: Path,
    validation_path: Path,
    artifact_manifest_path: Path,
    scope_id: str,
    page_suffixes: Sequence[str],
    selected: Sequence[Mapping[str, Any]],
    cohort_preflight: Mapping[str, str] | None,
) -> dict[str, Any]:
    assessment_id = metadata.get("assessment_id")
    if not isinstance(assessment_id, str) or not assessment_id.strip():
        raise ScopedSnapshotError("prep metadata must contain a non-empty assessment_id")
    source_provenance = {
        "preparation_metadata_sha256": sha256_file(metadata_path),
        "final_review_sha256": sha256_file(review_path),
        "final_review_validation_sha256": sha256_file(validation_path),
        "output_artifact_manifest_sha256": sha256_file(artifact_manifest_path),
        "render_spec_sha256": metadata["render_spec_sha256"],
    }
    if cohort_preflight is not None:
        source_provenance["cohort_preflight_sha256"] = cohort_preflight["sha256"]
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "record_type": SNAPSHOT_RECORD_TYPE,
        "assessment_id": assessment_id,
        "scope": {
            "scope_id": scope_id,
            "page_suffixes": list(page_suffixes),
        },
        "source_provenance": source_provenance,
        "student_count": len({str(entry["anonymous_id"]) for entry in selected}),
        "image_count": len(selected),
        "images": [dict(entry) for entry in selected],
        "model_run_allowed": False,
        "model_run_blockers": [
            "This local scoped image snapshot is not a grading packet.",
            "A frozen split, reviewed transcripts, question-level gold, rubric, packet audit, and separate run-readiness approval remain required.",
        ],
    }


def _validate_existing_target(output_root: Path, expected_manifest: Mapping[str, Any]) -> None:
    manifest_path = output_root / SNAPSHOT_MANIFEST_RELATIVE_PATH
    if not output_root.is_dir() or output_root.is_symlink() or not manifest_path.is_file():
        raise ScopedSnapshotError(
            f"output root already exists and is not a matching scoped snapshot: {output_root}"
        )
    existing_manifest = _load_json_object(manifest_path, "existing snapshot manifest")
    if existing_manifest != expected_manifest:
        raise ScopedSnapshotError(
            f"output root already exists with divergent snapshot provenance or selection: {output_root}"
        )
    expected_files = {SNAPSHOT_MANIFEST_RELATIVE_PATH.as_posix()} | {
        str(entry["snapshot_image"]) for entry in expected_manifest["images"]
    }
    actual_files = _regular_tree_files(output_root)
    if actual_files != expected_files:
        raise ScopedSnapshotError(
            f"output root already exists with unexpected/missing files: {output_root}"
        )
    for entry in expected_manifest["images"]:
        relative = str(entry["snapshot_image"])
        path = _safe_output_file(output_root, relative)
        if path.stat().st_size != entry["bytes"] or sha256_file(path) != entry["sha256"]:
            raise ScopedSnapshotError(
                f"output root already exists with changed scoped image: {relative}"
            )


def _regular_tree_files(root: Path) -> set[str]:
    files: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ScopedSnapshotError(f"snapshot root contains a symlink: {relative}")
        if path.is_file():
            files.add(relative)
        elif not path.is_dir():
            raise ScopedSnapshotError(f"snapshot root contains an unsupported entry: {relative}")
    return files


def _safe_output_file(output_root: Path, relative_path: str) -> Path:
    candidate = (output_root / relative_path).resolve()
    if not _is_within(candidate, output_root) or not candidate.is_file() or candidate.is_symlink():
        raise ScopedSnapshotError(f"snapshot output path is unsafe or missing: {relative_path}")
    return candidate


def _write_new_snapshot(
    *,
    source_root: Path,
    output_root: Path,
    selected: Iterable[Mapping[str, Any]],
    snapshot_manifest: Mapping[str, Any],
) -> None:
    output_parent = output_root.parent
    if output_parent.exists() and not output_parent.is_dir():
        raise ScopedSnapshotError(f"snapshot output parent is not a directory: {output_parent}")
    output_parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.tmp-", dir=str(output_parent))
    )
    try:
        for entry in selected:
            relative = str(entry["source_image"])
            source_path = _safe_source_file(source_root, relative)
            target_path = temporary_root / str(entry["snapshot_image"])
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target_path)
            if target_path.stat().st_size != entry["bytes"] or sha256_file(target_path) != entry["sha256"]:
                raise ScopedSnapshotError(f"copied image hash mismatch: {relative}")
        write_json(temporary_root / SNAPSHOT_MANIFEST_RELATIVE_PATH, snapshot_manifest)
        temporary_root.replace(output_root)
    except Exception:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)
        raise
