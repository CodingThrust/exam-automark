from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ANONYMOUS_ID_PATTERN = re.compile(r"^S[0-9]{3}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})

ANONYMIZATION_REVIEW_COLUMNS = (
    "render_spec_sha256",
    "artifact_manifest_sha256",
    "anonymous_id",
    "source_page",
    "output_image",
    "output_pdf",
    "identity_redaction_rectangles",
    "grading_mark_mask_rectangles",
    "privacy_review_status",
    "privacy_reviewer",
    "privacy_reviewed_at",
    "privacy_notes",
    "blindness_review_status",
    "blindness_reviewer",
    "blindness_reviewed_at",
    "blindness_notes",
    "answer_content_status",
    "answer_content_reviewer",
    "answer_content_reviewed_at",
    "answer_content_notes",
)

_REVIEW_STATUS_COLUMNS = (
    ("privacy_review_status", "privacy_reviewer", "privacy_reviewed_at"),
    ("blindness_review_status", "blindness_reviewer", "blindness_reviewed_at"),
    (
        "answer_content_status",
        "answer_content_reviewer",
        "answer_content_reviewed_at",
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_page_layout(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"page layout must be a JSON object: {path}")
    return payload


def validate_page_layout(
    layout: Mapping[str, Any],
    *,
    source_page_count: int,
    source_sha256: str,
) -> dict[str, Any]:
    """Validate a private anonymous page-group layout before rendering inputs.

    The layout deliberately contains only anonymous IDs and source page numbers.
    Any identity-based matching used to construct it must remain private.
    """

    checks: list[dict[str, str]] = []
    schema_valid = layout.get("schema_version") == 1
    _check(
        checks,
        "schema_version_supported",
        schema_valid,
        "schema_version=1" if schema_valid else "schema_version must be 1",
    )

    assessment_id = layout.get("assessment_id")
    _check(
        checks,
        "assessment_id_present",
        _is_nonempty_text(assessment_id),
        "assessment_id is present"
        if _is_nonempty_text(assessment_id)
        else "assessment_id must be non-empty text",
    )

    declared_hash = layout.get("source_sha256")
    hash_format_valid = isinstance(declared_hash, str) and bool(
        SHA256_PATTERN.fullmatch(declared_hash)
    )
    _check(
        checks,
        "source_sha256_format_valid",
        hash_format_valid,
        "layout source_sha256 is a 64-character lowercase SHA-256 digest"
        if hash_format_valid
        else "layout source_sha256 must be a 64-character lowercase SHA-256 digest",
    )
    _check(
        checks,
        "source_sha256_matches",
        hash_format_valid and declared_hash == source_sha256,
        "layout source hash matches the rendered PDF"
        if hash_format_valid and declared_hash == source_sha256
        else "layout source hash does not match the rendered PDF",
    )

    declared_count = layout.get("expected_page_count")
    _check(
        checks,
        "source_page_count_matches",
        _is_positive_int(declared_count) and declared_count == source_page_count,
        f"layout and PDF both have {source_page_count} pages"
        if _is_positive_int(declared_count) and declared_count == source_page_count
        else (
            f"layout expected_page_count={declared_count!r}; "
            f"PDF page count={source_page_count}"
        ),
    )

    groups = layout.get("page_groups")
    groups_valid = isinstance(groups, list) and bool(groups)
    _check(
        checks,
        "page_groups_present",
        groups_valid,
        "at least one anonymous page group is present"
        if groups_valid
        else "page_groups must be a non-empty list",
    )
    groups = groups if isinstance(groups, list) else []

    anonymous_ids: list[str] = []
    page_counts: Counter[int] = Counter()
    invalid_group_entries = 0
    invalid_masks = 0
    for group in groups:
        if not isinstance(group, Mapping):
            invalid_group_entries += 1
            continue
        anonymous_id = group.get("anonymous_id")
        if not isinstance(anonymous_id, str) or not ANONYMOUS_ID_PATTERN.fullmatch(
            anonymous_id
        ):
            invalid_group_entries += 1
        else:
            anonymous_ids.append(anonymous_id)

        source_pages = group.get("source_pages")
        if not isinstance(source_pages, list) or not source_pages:
            invalid_group_entries += 1
            source_pages = []
        valid_group_pages: set[int] = set()
        for page in source_pages:
            if not _is_positive_int(page) or page > source_page_count:
                invalid_group_entries += 1
                continue
            page_counts[page] += 1
            valid_group_pages.add(page)

        page_masks = group.get("page_masks", [])
        if not isinstance(page_masks, list):
            invalid_masks += 1
            continue
        for mask in page_masks:
            if not isinstance(mask, Mapping):
                invalid_masks += 1
                continue
            source_page = mask.get("source_page")
            if source_page not in valid_group_pages:
                invalid_masks += 1
            if not _is_nonempty_text(mask.get("reason")):
                invalid_masks += 1
            rectangles = mask.get("rectangles")
            if not isinstance(rectangles, list) or not rectangles:
                invalid_masks += 1
                continue
            if any(not _valid_rectangle(rectangle) for rectangle in rectangles):
                invalid_masks += 1

    _check(
        checks,
        "anonymous_ids_valid_and_unique",
        invalid_group_entries == 0
        and len(anonymous_ids) == len(groups)
        and len(anonymous_ids) == len(set(anonymous_ids)),
        "all page groups use distinct S### anonymous IDs"
        if invalid_group_entries == 0
        and len(anonymous_ids) == len(groups)
        and len(anonymous_ids) == len(set(anonymous_ids))
        else "page groups contain invalid/duplicate anonymous IDs or invalid source pages",
    )
    _check(
        checks,
        "page_masks_valid",
        invalid_masks == 0,
        "all optional page-specific masks are normalized and tied to their group pages"
        if invalid_masks == 0
        else f"{invalid_masks} page-mask fields are invalid",
    )

    excluded_pages = layout.get("excluded_pages", [])
    excluded_counts: Counter[int] = Counter()
    invalid_exclusions = 0
    if not isinstance(excluded_pages, list):
        invalid_exclusions += 1
        excluded_pages = []
    for exclusion in excluded_pages:
        if not isinstance(exclusion, Mapping):
            invalid_exclusions += 1
            continue
        page = exclusion.get("source_page")
        if not _is_positive_int(page) or page > source_page_count:
            invalid_exclusions += 1
            continue
        if not _is_nonempty_text(exclusion.get("reason")):
            invalid_exclusions += 1
        excluded_counts[page] += 1

    _check(
        checks,
        "excluded_pages_valid",
        invalid_exclusions == 0,
        "excluded pages have valid page numbers and documented reasons"
        if invalid_exclusions == 0
        else f"{invalid_exclusions} excluded-page entries are invalid",
    )

    expected_pages = set(range(1, source_page_count + 1))
    assigned_pages = set(page_counts)
    excluded = set(excluded_counts)
    duplicate_pages = sorted(
        page
        for page in expected_pages
        if page_counts[page] + excluded_counts[page] > 1
    )
    missing_pages = sorted(expected_pages - assigned_pages - excluded)
    unexpected_pages = sorted((assigned_pages | excluded) - expected_pages)
    _check(
        checks,
        "all_pages_covered_once",
        not missing_pages and not duplicate_pages and not unexpected_pages,
        "every source page is assigned to one anonymous group or one documented exclusion"
        if not missing_pages and not duplicate_pages and not unexpected_pages
        else (
            f"missing={missing_pages}; duplicate={duplicate_pages}; "
            f"unexpected={unexpected_pages}"
        ),
    )

    failed_checks = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "anonymous_page_layout_validation",
        "status": "ready" if not failed_checks else "not_ready",
        "assessment_id": assessment_id if isinstance(assessment_id, str) else None,
        "source_page_count": source_page_count,
        "anonymous_group_count": len(groups),
        "covered_page_count": len(assigned_pages),
        "excluded_page_count": len(excluded),
        "missing_page_numbers": missing_pages,
        "duplicate_page_numbers": duplicate_pages,
        "unexpected_page_numbers": unexpected_pages,
        "checks": checks,
        "failed_checks": failed_checks,
    }


def expected_review_pairs(layout: Mapping[str, Any]) -> set[tuple[str, int]]:
    pairs: set[tuple[str, int]] = set()
    groups = layout.get("page_groups")
    if not isinstance(groups, list):
        raise ValueError("page_groups must be a list")
    for group in groups:
        if not isinstance(group, Mapping):
            raise ValueError("each page group must be an object")
        anonymous_id = group.get("anonymous_id")
        source_pages = group.get("source_pages")
        if not isinstance(anonymous_id, str) or not isinstance(source_pages, list):
            raise ValueError("page group requires anonymous_id and source_pages")
        for source_page in source_pages:
            if not _is_positive_int(source_page):
                raise ValueError("source_pages must contain positive integers")
            pairs.add((anonymous_id, source_page))
    return pairs


def expected_review_outputs(
    layout: Mapping[str, Any],
) -> dict[tuple[str, int], tuple[str, str]]:
    """Return the deterministic rendered image/PDF path for every layout page.

    Final human approvals are meaningful only when each row is tied to the
    actual anonymous page the reviewer inspected.  Source-page numbers cannot
    be used as image page numbers because a student's assigned source pages
    need not be consecutive.
    """

    outputs: dict[tuple[str, int], tuple[str, str]] = {}
    groups = layout.get("page_groups")
    if not isinstance(groups, list):
        raise ValueError("page_groups must be a list")
    for group in groups:
        if not isinstance(group, Mapping):
            raise ValueError("each page group must be an object")
        anonymous_id = group.get("anonymous_id")
        source_pages = group.get("source_pages")
        if not isinstance(anonymous_id, str) or not isinstance(source_pages, list):
            raise ValueError("page group requires anonymous_id and source_pages")
        output_pdf = f"anonymized_pdfs/{anonymous_id}.pdf"
        for local_page, source_page in enumerate(source_pages, start=1):
            if not _is_positive_int(source_page):
                raise ValueError("source_pages must contain positive integers")
            pair = (anonymous_id, source_page)
            if pair in outputs:
                raise ValueError("page groups must not duplicate anonymous source pages")
            outputs[pair] = (
                f"anonymized_pages/{anonymous_id}/{anonymous_id}-p{local_page:02d}.png",
                output_pdf,
            )
    return outputs


def review_rows_for_layout(
    layout: Mapping[str, Any],
    *,
    identity_rectangles: Sequence[Mapping[str, float]],
    render_spec_sha256: str,
    artifact_manifest_sha256: str,
) -> list[dict[str, str]]:
    if not SHA256_PATTERN.fullmatch(render_spec_sha256):
        raise ValueError(
            "render_spec_sha256 must be a 64-character lowercase SHA-256 digest"
        )
    if not SHA256_PATTERN.fullmatch(artifact_manifest_sha256):
        raise ValueError(
            "artifact_manifest_sha256 must be a 64-character lowercase SHA-256 digest"
        )
    rows: list[dict[str, str]] = []
    expected_outputs = expected_review_outputs(layout)
    for group in layout.get("page_groups", []):
        if not isinstance(group, Mapping):
            continue
        anonymous_id = str(group["anonymous_id"])
        source_pages = list(group["source_pages"])
        masks_by_page = _masks_by_page(group)
        output_pdf = f"anonymized_pdfs/{anonymous_id}.pdf"
        for local_page, source_page in enumerate(source_pages, start=1):
            output_image, output_pdf = expected_outputs[(anonymous_id, source_page)]
            rows.append(
                {
                    "render_spec_sha256": render_spec_sha256,
                    "artifact_manifest_sha256": artifact_manifest_sha256,
                    "anonymous_id": anonymous_id,
                    "source_page": str(source_page),
                    "output_image": output_image,
                    "output_pdf": output_pdf,
                    "identity_redaction_rectangles": _rectangles_to_json(
                        identity_rectangles
                    ),
                    "grading_mark_mask_rectangles": _rectangles_to_json(
                        masks_by_page.get(source_page, ())
                    ),
                    "privacy_review_status": "pending",
                    "privacy_reviewer": "",
                    "privacy_reviewed_at": "",
                    "privacy_notes": "verify that no direct identifier remains visible",
                    "blindness_review_status": "pending",
                    "blindness_reviewer": "",
                    "blindness_reviewed_at": "",
                    "blindness_notes": (
                        "verify that scores, ticks/crosses, totals, and grader comments "
                        "cannot leak gold to a direct-multimodal grader"
                    ),
                    "answer_content_status": "pending",
                    "answer_content_reviewer": "",
                    "answer_content_reviewed_at": "",
                    "answer_content_notes": (
                        "verify that masking did not hide question text or student work "
                        "needed for the declared scope"
                    ),
                }
            )
    return rows


def masks_for_group_page(
    group: Mapping[str, Any], source_page: int
) -> list[Mapping[str, float]]:
    return list(_masks_by_page(group).get(source_page, ()))


def validate_anonymization_review(
    review_path: Path,
    *,
    expected_pairs: Iterable[tuple[str, int]],
    expected_outputs: Mapping[tuple[str, int], tuple[str, str]],
    expected_render_spec_sha256: str | None,
    expected_artifact_manifest_sha256: str | None,
) -> dict[str, Any]:
    with review_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = tuple(reader.fieldnames or ())

    missing_columns = [
        column for column in ANONYMIZATION_REVIEW_COLUMNS if column not in fieldnames
    ]
    expected = set(expected_pairs)
    output_pairs = set(expected_outputs)
    actual_pairs: list[tuple[str, int]] = []
    malformed_pairs = 0
    invalid_statuses = 0
    privacy_unapproved = 0
    blindness_unapproved = 0
    answer_content_unapproved = 0
    missing_audit_trails = 0
    render_spec_binding_mismatches = 0
    artifact_manifest_binding_mismatches = 0
    output_path_mismatches = 0
    expected_render_spec_valid = isinstance(
        expected_render_spec_sha256, str
    ) and bool(SHA256_PATTERN.fullmatch(expected_render_spec_sha256))
    expected_artifact_manifest_valid = isinstance(
        expected_artifact_manifest_sha256, str
    ) and bool(SHA256_PATTERN.fullmatch(expected_artifact_manifest_sha256))

    for row in rows:
        if _cell(row, "render_spec_sha256") != expected_render_spec_sha256:
            render_spec_binding_mismatches += 1
        if (
            _cell(row, "artifact_manifest_sha256")
            != expected_artifact_manifest_sha256
        ):
            artifact_manifest_binding_mismatches += 1

        anonymous_id = _cell(row, "anonymous_id")
        source_page_text = _cell(row, "source_page")
        try:
            source_page = int(source_page_text)
        except ValueError:
            malformed_pairs += 1
        else:
            if not ANONYMOUS_ID_PATTERN.fullmatch(anonymous_id) or source_page <= 0:
                malformed_pairs += 1
            else:
                pair = (anonymous_id, source_page)
                actual_pairs.append(pair)
                expected_output = expected_outputs.get(pair)
                if expected_output is None or (
                    _cell(row, "output_image") != expected_output[0]
                    or _cell(row, "output_pdf") != expected_output[1]
                ):
                    output_path_mismatches += 1

        for status_column, reviewer_column, reviewed_at_column in _REVIEW_STATUS_COLUMNS:
            status = _cell(row, status_column)
            if status not in REVIEW_STATUSES:
                invalid_statuses += 1
                continue
            if status != "approved":
                if status_column == "privacy_review_status":
                    privacy_unapproved += 1
                elif status_column == "blindness_review_status":
                    blindness_unapproved += 1
                else:
                    answer_content_unapproved += 1
            elif not _cell(row, reviewer_column) or not _cell(row, reviewed_at_column):
                missing_audit_trails += 1

    counts = Counter(actual_pairs)
    duplicate_pairs = [pair for pair, count in counts.items() if count > 1]
    actual = set(actual_pairs)
    missing_pairs = expected - actual
    unexpected_pairs = actual - expected

    checks = [
        _check_item(
            "required_columns_present",
            not missing_columns,
            "all required review columns are present"
            if not missing_columns
            else f"missing columns: {', '.join(missing_columns)}",
        ),
        _check_item(
            "review_pairs_match_layout",
            not malformed_pairs
            and not duplicate_pairs
            and not missing_pairs
            and not unexpected_pairs,
            "every private-layout page has exactly one review row"
            if not malformed_pairs
            and not duplicate_pairs
            and not missing_pairs
            and not unexpected_pairs
            else (
                f"malformed={malformed_pairs}; duplicates={len(duplicate_pairs)}; "
                f"missing={len(missing_pairs)}; unexpected={len(unexpected_pairs)}"
            ),
        ),
        _check_item(
            "review_output_paths_match_layout",
            output_pairs == expected and output_path_mismatches == 0,
            "every review row is tied to its deterministic anonymous image and PDF"
            if output_pairs == expected and output_path_mismatches == 0
            else (
                f"expected-output mapping differs for {len(expected ^ output_pairs)} pairs; "
                f"{output_path_mismatches} review rows name a different image or PDF"
            ),
        ),
        _check_item(
            "review_render_spec_matches_preparation",
            expected_render_spec_valid
            and render_spec_binding_mismatches == 0
            and bool(rows),
            "every review row is bound to the preparation render specification"
            if expected_render_spec_valid
            and render_spec_binding_mismatches == 0
            and rows
            else (
                "preparation render-spec hash is invalid"
                if not expected_render_spec_valid
                else (
                    "review has no rows"
                    if not rows
                    else (
                        f"{render_spec_binding_mismatches} review rows belong to a "
                        "different render specification"
                    )
                )
            ),
        ),
        _check_item(
            "review_artifact_manifest_matches_preparation",
            expected_artifact_manifest_valid
            and artifact_manifest_binding_mismatches == 0
            and bool(rows),
            "every review row is bound to the rendered output artifact manifest"
            if expected_artifact_manifest_valid
            and artifact_manifest_binding_mismatches == 0
            and rows
            else (
                "preparation artifact-manifest hash is invalid"
                if not expected_artifact_manifest_valid
                else (
                    "review has no rows"
                    if not rows
                    else (
                        f"{artifact_manifest_binding_mismatches} review rows belong "
                        "to a different rendered artifact manifest"
                    )
                )
            ),
        ),
        _check_item(
            "review_status_values_valid",
            invalid_statuses == 0,
            "all review status values are pending, approved, or rejected"
            if invalid_statuses == 0
            else f"{invalid_statuses} invalid review status values",
        ),
        _check_item(
            "privacy_review_approved",
            privacy_unapproved == 0 and rows,
            "every reviewed page has privacy approval"
            if privacy_unapproved == 0 and rows
            else f"{privacy_unapproved} page rows lack privacy approval",
        ),
        _check_item(
            "blindness_review_approved",
            blindness_unapproved == 0 and rows,
            "every reviewed page is blind to existing grading evidence"
            if blindness_unapproved == 0 and rows
            else f"{blindness_unapproved} page rows lack blindness approval",
        ),
        _check_item(
            "answer_content_review_approved",
            answer_content_unapproved == 0 and rows,
            "every reviewed page preserves in-scope question and answer content"
            if answer_content_unapproved == 0 and rows
            else f"{answer_content_unapproved} page rows lack content-preservation approval",
        ),
        _check_item(
            "approved_reviews_have_audit_trail",
            missing_audit_trails == 0,
            "each approval has a reviewer and timestamp"
            if missing_audit_trails == 0
            else f"{missing_audit_trails} approvals lack reviewer or timestamp",
        ),
    ]
    failed_checks = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "anonymization_review_readiness",
        "status": "ready" if not failed_checks else "not_ready",
        "review_path": review_path.as_posix(),
        "expected_page_count": len(expected),
        "review_row_count": len(rows),
        "checks": checks,
        "failed_checks": failed_checks,
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_review_csv(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANONYMIZATION_REVIEW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in ANONYMIZATION_REVIEW_COLUMNS})


def _masks_by_page(group: Mapping[str, Any]) -> dict[int, list[Mapping[str, float]]]:
    result: dict[int, list[Mapping[str, float]]] = {}
    for mask in group.get("page_masks", []):
        if not isinstance(mask, Mapping):
            continue
        source_page = mask.get("source_page")
        if not _is_positive_int(source_page):
            continue
        rectangles = mask.get("rectangles", [])
        if not isinstance(rectangles, list):
            continue
        result.setdefault(source_page, []).extend(
            rectangle
            for rectangle in rectangles
            if isinstance(rectangle, Mapping) and _valid_rectangle(rectangle)
        )
    return result


def _rectangles_to_json(rectangles: Iterable[Mapping[str, float]]) -> str:
    return json.dumps(
        [
            {
                "left": float(rectangle["left"]),
                "top": float(rectangle["top"]),
                "right": float(rectangle["right"]),
                "bottom": float(rectangle["bottom"]),
            }
            for rectangle in rectangles
        ],
        sort_keys=True,
        separators=(",", ":"),
    )


def _valid_rectangle(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        left = float(value["left"])
        top = float(value["top"])
        right = float(value["right"])
        bottom = float(value["bottom"])
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= left < right <= 1 and 0 <= top < bottom <= 1


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check(
    checks: list[dict[str, str]], check_id: str, passed: bool, detail: str
) -> None:
    checks.append(_check_item(check_id, passed, detail))


def _check_item(check_id: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "id": check_id,
        "status": "passed" if passed else "failed",
        "detail": detail,
    }


def _cell(row: Mapping[str, str], key: str) -> str:
    return (row.get(key) or "").strip()
