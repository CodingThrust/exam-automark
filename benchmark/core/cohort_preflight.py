from __future__ import annotations

"""Model-free, private cohort preflight for approved anonymous artifacts.

This bridge closes a common gap between a page-level anonymization approval
and a cohort-level grading input: a group with an anomalous page count must
also have an explicit scope decision.  The report contains hashes, counts, and
anonymous-safe identifiers only.  It neither creates a packet nor authorizes a
model run.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from benchmark.core.anonymization import load_page_layout, sha256_file
from benchmark.core.page_scope_workflow import validate_page_scope_review


COHORT_PREFLIGHT_SCHEMA_VERSION = 1
COHORT_PREFLIGHT_RECORD_TYPE = "private_anonymous_cohort_preflight"


class CohortPreflightError(ValueError):
    """Raised when a preflight input is missing or is not safely bound."""


def build_anonymous_cohort_preflight(
    *,
    artifact_root: Path,
    layout_path: Path,
    final_review_validation_path: Path,
    private_manifest_path: Path,
    expected_pages_per_group: int,
    page_scope_review_csv_path: Path,
    page_scope_review_metadata_path: Path,
) -> dict[str, Any]:
    """Return a non-sensitive readiness report for one anonymous cohort.

    ``status=ready`` means final page approvals and every anomalous page-count
    decision are complete.  It deliberately remains ``model_run_allowed=false``:
    gold, split, packets, provider pinning, and run authorization are separate
    gates.
    """

    source_root = _require_directory(artifact_root, "artifact root")
    layout_file = _require_file(layout_path, "page layout")
    expected_final_validation = source_root / "manifest" / "final-review-validation.json"
    final_validation_file = _require_file(
        final_review_validation_path, "final anonymization validation"
    )
    if final_validation_file != expected_final_validation.resolve():
        raise CohortPreflightError(
            "final anonymization validation must be artifact_root/manifest/final-review-validation.json"
        )
    metadata_file = _require_file(
        source_root / "manifest" / "prep-metadata.json", "preparation metadata"
    )
    layout = load_page_layout(layout_file)
    metadata = _load_json_object(metadata_file, "preparation metadata")
    final_validation = _load_json_object(
        final_validation_file, "final anonymization validation"
    )
    page_scope = validate_page_scope_review(
        private_manifest_path=private_manifest_path,
        expected_pages_per_group=expected_pages_per_group,
        review_csv_path=page_scope_review_csv_path,
        metadata_path=page_scope_review_metadata_path,
    )

    expected_pages = _layout_page_count(layout)
    layout_sha256 = sha256_file(layout_file)
    checks: list[dict[str, str]] = []
    _check(
        checks,
        "preparation_metadata_schema_and_layout_binding",
        metadata.get("schema_version") == 2
        and metadata.get("record_type") == "anonymized_assessment_preparation"
        and metadata.get("layout_sha256") == layout_sha256
        and metadata.get("assessment_id") == layout.get("assessment_id"),
        "preparation metadata is schema-v2 and bound to the supplied layout",
        "preparation metadata is not schema-v2 or does not bind to the supplied layout",
    )
    _check(
        checks,
        "final_anonymization_validation_ready",
        final_validation.get("status") == "ready"
        and final_validation.get("failed_checks") == [],
        "final anonymization validation is ready with no failed checks",
        "final anonymization validation is not ready or contains failed checks",
    )
    _check(
        checks,
        "final_anonymization_validation_covers_layout",
        final_validation.get("expected_page_count") == expected_pages
        and final_validation.get("review_row_count") == expected_pages,
        "final validation row counts cover exactly the supplied layout",
        "final validation row counts do not cover the supplied layout",
    )
    _check(
        checks,
        "anomalous_page_scope_review_ready",
        page_scope.get("status") == "ready",
        "all anomalous page-count groups have approved include-all decisions",
        "anomalous page-count review is incomplete or requires a corrected assembly/layout",
    )
    _check(
        checks,
        "cohort_layout_has_no_unreassembled_page_count_anomalies",
        page_scope.get("anomaly_group_count") == 0,
        "the cohort layout has no remaining nonstandard page-count groups",
        (
            "page ownership decisions are not a substitute for a corrected layout: "
            "a nonstandard page-count group still requires reassembly or an explicitly "
            "supported variable-page scope before cohort freeze"
        ),
    )
    failed = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": COHORT_PREFLIGHT_SCHEMA_VERSION,
        "record_type": COHORT_PREFLIGHT_RECORD_TYPE,
        "status": "ready" if not failed else "not_ready",
        "assessment_id": layout.get("assessment_id"),
        "anonymous_page_count": expected_pages,
        "page_scope_anomaly_group_count": page_scope.get("anomaly_group_count"),
        "bindings": {
            "layout_sha256": layout_sha256,
            "preparation_metadata_sha256": sha256_file(metadata_file),
            "final_review_validation_sha256": sha256_file(final_validation_file),
            "private_manifest_sha256": sha256_file(
                _require_file(private_manifest_path, "private manifest")
            ),
            "page_scope_review_csv_sha256": sha256_file(
                _require_file(page_scope_review_csv_path, "page-scope review CSV")
            ),
            "page_scope_review_metadata_sha256": sha256_file(
                _require_file(page_scope_review_metadata_path, "page-scope review metadata")
            ),
        },
        "checks": checks,
        "failed_checks": failed,
        "model_run_allowed": False,
        "model_run_blockers": [
            "This preflight does not freeze a development/held-out split or question-level gold.",
            "This preflight does not build packets, pin a provider/model, or grant model-run authorization.",
        ],
    }


def canonical_report_bytes(report: Mapping[str, Any]) -> bytes:
    return (json.dumps(report, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _require_directory(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_dir():
        raise CohortPreflightError(f"{label} must be a directory: {path}")
    return resolved


def _require_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise CohortPreflightError(f"{label} must be a regular file: {path}")
    return resolved


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CohortPreflightError(f"cannot load {label}: {path}") from error
    if not isinstance(payload, dict):
        raise CohortPreflightError(f"{label} must be a JSON object")
    return payload


def _layout_page_count(layout: Mapping[str, Any]) -> int:
    groups = layout.get("page_groups")
    if not isinstance(groups, list) or not groups:
        raise CohortPreflightError("page layout must contain page_groups")
    count = 0
    for group in groups:
        if not isinstance(group, Mapping) or not isinstance(group.get("source_pages"), list):
            raise CohortPreflightError("page layout has an invalid page group")
        count += len(group["source_pages"])
    if count < 1:
        raise CohortPreflightError("page layout must contain at least one page")
    return count


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
