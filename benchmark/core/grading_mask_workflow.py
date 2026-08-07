from __future__ import annotations

"""Private grading-mark mask workflow primitives.

This module deliberately separates *candidate detection* from final masks.
Candidates are never rendered into a model-facing artifact until a human has
resolved every candidate and completed a page-level sweep for every page.
"""

import copy
import csv
import hashlib
import json
import re
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter


CANDIDATE_ID_PATTERN = re.compile(r"^C[0-9]{4,}$")
REVIEW_STATUSES = frozenset({"pending", "accepted", "rejected", "adjusted"})
SWEEP_STATUSES = frozenset({"pending", "completed", "rejected"})

MASK_CANDIDATE_DECISION_COLUMNS = (
    "candidate_id",
    "anonymous_id",
    "source_page",
    "decision_status",
    "final_rectangles",
    "reviewer",
    "reviewed_at",
    "notes",
)

PAGE_SWEEP_COLUMNS = (
    "anonymous_id",
    "source_page",
    "sweep_status",
    "reviewer",
    "reviewed_at",
    "added_rectangles",
    "notes",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def rectangles_to_json(rectangles: Iterable[Mapping[str, float]]) -> str:
    return json.dumps(_canonical_rectangles(rectangles), sort_keys=True, separators=(",", ":"))


def parse_rectangles(value: str) -> list[dict[str, float]]:
    if not value.strip():
        return []
    payload = json.loads(value)
    if not isinstance(payload, list):
        raise ValueError("rectangle value must be a JSON list")
    return _canonical_rectangles(payload)


def propose_red_ink_candidates(
    image: Image.Image,
    *,
    excluded_rectangles: Sequence[Mapping[str, float]],
    min_red: int = 90,
    dominance: int = 30,
    dilation_pixels: int = 9,
    min_component_area: int = 16,
    padding_pixels: int = 5,
) -> list[dict[str, float]]:
    """Return conservative red-ink component rectangles in normalized units.

    It is intentionally a high-recall proposal detector, not a proof that a
    page is blind. Grayscale marks are not detectable reliably from pixels
    alone and require the mandatory human page sweep.
    """

    if dilation_pixels < 1 or dilation_pixels % 2 == 0:
        raise ValueError("dilation_pixels must be a positive odd number")
    image = image.convert("RGB")
    mutable = image.copy()
    _apply_rectangles(mutable, excluded_rectangles)
    red, green, blue = mutable.split()
    red_green = ImageChops.subtract(red, green).point(
        lambda value: 255 if value >= dominance else 0
    )
    red_blue = ImageChops.subtract(red, blue).point(
        lambda value: 255 if value >= dominance else 0
    )
    bright_red = red.point(lambda value: 255 if value >= min_red else 0)
    binary = ImageChops.multiply(ImageChops.multiply(red_green, red_blue), bright_red)
    expanded = binary.filter(ImageFilter.MaxFilter(dilation_pixels))

    components = _component_boxes(expanded, min_component_area=min_component_area)
    rectangles: list[dict[str, float]] = []
    for left, top, right, bottom in components:
        rectangles.append(
            {
                "left": max(0.0, (left - padding_pixels) / image.width),
                "top": max(0.0, (top - padding_pixels) / image.height),
                "right": min(1.0, (right + padding_pixels) / image.width),
                "bottom": min(1.0, (bottom + padding_pixels) / image.height),
            }
        )
    return _canonical_rectangles(rectangles)


def build_candidate_manifest(
    *,
    layout: Mapping[str, Any],
    layout_sha256: str,
    candidates: Sequence[Mapping[str, Any]],
    detector: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "record_type": "grading_mark_mask_candidate_manifest",
        "assessment_id": layout.get("assessment_id"),
        "layout_sha256": layout_sha256,
        "detector": dict(detector),
        "manual_page_sweep_required": True,
        "candidates": [dict(candidate) for candidate in candidates],
    }


def candidate_decision_rows(manifest: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in _candidate_entries(manifest):
        rows.append(
            {
                "candidate_id": str(candidate["candidate_id"]),
                "anonymous_id": str(candidate["anonymous_id"]),
                "source_page": str(candidate["source_page"]),
                "decision_status": "pending",
                "final_rectangles": "",
                "reviewer": "",
                "reviewed_at": "",
                "notes": "review candidate; accept, reject, or adjust before compiling masks",
            }
        )
    return rows


def page_sweep_rows(layout: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for anonymous_id, source_page in sorted(expected_review_pairs(layout)):
        rows.append(
            {
                "anonymous_id": anonymous_id,
                "source_page": str(source_page),
                "sweep_status": "pending",
                "reviewer": "",
                "reviewed_at": "",
                "added_rectangles": "",
                "notes": (
                    "inspect the whole page for scores, ticks/crosses, totals, and "
                    "grader comments, including grayscale marks that detection can miss"
                ),
            }
        )
    return rows


def write_csv(path: Path, *, columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def load_csv_rows(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def validate_candidate_manifest(
    manifest: Mapping[str, Any],
    *,
    expected_pairs: Iterable[tuple[str, int]],
    assessment_id: str,
    layout_sha256: str,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    _check(
        checks,
        "candidate_manifest_schema_supported",
        manifest.get("schema_version") == 1,
        "candidate manifest uses schema_version=1",
        "candidate manifest must use schema_version=1",
    )
    _check(
        checks,
        "candidate_manifest_assessment_matches",
        manifest.get("assessment_id") == assessment_id,
        "candidate manifest assessment matches layout",
        "candidate manifest assessment does not match layout",
    )
    _check(
        checks,
        "candidate_manifest_layout_hash_matches",
        manifest.get("layout_sha256") == layout_sha256,
        "candidate manifest is tied to the source layout",
        "candidate manifest layout hash does not match source layout",
    )
    _check(
        checks,
        "manual_page_sweep_required",
        manifest.get("manual_page_sweep_required") is True,
        "mandatory page sweep is declared",
        "candidate manifest must require a manual page sweep",
    )

    expected = set(expected_pairs)
    candidates = manifest.get("candidates")
    entries = candidates if isinstance(candidates, list) else []
    invalid = 0
    ids: list[str] = []
    for candidate in entries:
        if not isinstance(candidate, Mapping):
            invalid += 1
            continue
        candidate_id = candidate.get("candidate_id")
        anonymous_id = candidate.get("anonymous_id")
        source_page = candidate.get("source_page")
        rectangles = candidate.get("rectangles")
        confidence = candidate.get("confidence")
        if not isinstance(candidate_id, str) or not CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
            invalid += 1
        else:
            ids.append(candidate_id)
        if not isinstance(anonymous_id, str) or not isinstance(source_page, int):
            invalid += 1
        elif (anonymous_id, source_page) not in expected:
            invalid += 1
        if not isinstance(rectangles, list) or not rectangles or not _rectangles_valid(rectangles):
            invalid += 1
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            invalid += 1
        if not _nonempty(candidate.get("detector")) or not _nonempty(candidate.get("rationale")):
            invalid += 1
    _check(
        checks,
        "candidate_entries_valid_and_unique",
        isinstance(candidates, list) and invalid == 0 and len(ids) == len(set(ids)),
        "all candidates are valid and use unique IDs",
        f"invalid candidates={invalid}; duplicate_ids={len(ids) - len(set(ids))}",
    )
    failed = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "grading_mark_mask_candidate_manifest_validation",
        "status": "ready" if not failed else "not_ready",
        "candidate_count": len(entries),
        "checks": checks,
        "failed_checks": failed,
    }


def validate_mask_review_workflow(
    *,
    layout: Mapping[str, Any],
    layout_sha256: str,
    candidate_manifest: Mapping[str, Any],
    decision_rows: Sequence[Mapping[str, str]],
    decision_columns: Sequence[str],
    sweep_rows: Sequence[Mapping[str, str]],
    sweep_columns: Sequence[str],
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    expected = expected_review_pairs(layout)
    candidate_report = validate_candidate_manifest(
        candidate_manifest,
        expected_pairs=expected,
        assessment_id=str(layout.get("assessment_id", "")),
        layout_sha256=layout_sha256,
    )
    _check(
        checks,
        "candidate_manifest_valid",
        candidate_report["status"] == "ready",
        "candidate manifest is valid",
        "candidate manifest is invalid",
    )
    _check(
        checks,
        "candidate_decision_columns_present",
        not _missing_columns(decision_columns, MASK_CANDIDATE_DECISION_COLUMNS),
        "all candidate decision columns are present",
        "candidate decision CSV is missing required columns",
    )
    _check(
        checks,
        "page_sweep_columns_present",
        not _missing_columns(sweep_columns, PAGE_SWEEP_COLUMNS),
        "all page sweep columns are present",
        "page sweep CSV is missing required columns",
    )

    candidates = {str(entry["candidate_id"]): entry for entry in _candidate_entries(candidate_manifest)}
    decision_by_id: dict[str, Mapping[str, str]] = {}
    malformed_decisions = 0
    pending_decisions = 0
    rejected_without_note = 0
    decision_audit_missing = 0
    adjusted_without_rectangles = 0
    unexpected_decisions = 0
    for row in decision_rows:
        candidate_id = _cell(row, "candidate_id")
        status = _cell(row, "decision_status")
        candidate = candidates.get(candidate_id)
        if candidate is None or candidate_id in decision_by_id:
            unexpected_decisions += 1
            continue
        decision_by_id[candidate_id] = row
        if _cell(row, "anonymous_id") != str(candidate["anonymous_id"]) or _cell(
            row, "source_page"
        ) != str(candidate["source_page"]):
            malformed_decisions += 1
        if status not in REVIEW_STATUSES:
            malformed_decisions += 1
            continue
        if status == "pending":
            pending_decisions += 1
        else:
            if not _cell(row, "reviewer") or not _cell(row, "reviewed_at"):
                decision_audit_missing += 1
            if status == "rejected" and not _cell(row, "notes"):
                rejected_without_note += 1
            if status == "adjusted":
                try:
                    rectangles = parse_rectangles(_cell(row, "final_rectangles"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    rectangles = []
                if not rectangles:
                    adjusted_without_rectangles += 1
    missing_decisions = set(candidates) - set(decision_by_id)
    _check(
        checks,
        "candidate_decisions_match_manifest",
        not malformed_decisions and not unexpected_decisions and not missing_decisions,
        "each candidate has exactly one matching decision row",
        (
            f"malformed={malformed_decisions}; unexpected_or_duplicate={unexpected_decisions}; "
            f"missing={len(missing_decisions)}"
        ),
    )
    _check(
        checks,
        "all_candidates_resolved",
        pending_decisions == 0,
        "all candidates are accepted, rejected, or adjusted",
        f"{pending_decisions} candidates remain pending",
    )
    _check(
        checks,
        "candidate_decisions_have_audit_trail",
        decision_audit_missing == 0,
        "resolved candidate decisions have reviewer and timestamp",
        f"{decision_audit_missing} resolved candidate decisions lack reviewer or timestamp",
    )
    _check(
        checks,
        "rejections_and_adjustments_are_explained",
        rejected_without_note == 0 and adjusted_without_rectangles == 0,
        "rejections have notes and adjustments have final rectangles",
        (
            f"rejections_without_note={rejected_without_note}; "
            f"adjustments_without_rectangles={adjusted_without_rectangles}"
        ),
    )

    sweep_by_pair: dict[tuple[str, int], Mapping[str, str]] = {}
    malformed_sweeps = 0
    pending_sweeps = 0
    rejected_sweeps = 0
    sweep_audit_missing = 0
    invalid_added_rectangles = 0
    for row in sweep_rows:
        pair = _review_pair(row)
        if pair is None or pair not in expected or pair in sweep_by_pair:
            malformed_sweeps += 1
            continue
        sweep_by_pair[pair] = row
        status = _cell(row, "sweep_status")
        if status not in SWEEP_STATUSES:
            malformed_sweeps += 1
            continue
        if status == "pending":
            pending_sweeps += 1
        elif status == "rejected":
            rejected_sweeps += 1
        if status != "pending" and (not _cell(row, "reviewer") or not _cell(row, "reviewed_at")):
            sweep_audit_missing += 1
        try:
            parse_rectangles(_cell(row, "added_rectangles"))
        except (TypeError, ValueError, json.JSONDecodeError):
            invalid_added_rectangles += 1
    missing_sweeps = expected - set(sweep_by_pair)
    _check(
        checks,
        "page_sweeps_match_layout",
        not malformed_sweeps and not missing_sweeps,
        "every layout page has exactly one sweep row",
        f"malformed_or_duplicate={malformed_sweeps}; missing={len(missing_sweeps)}",
    )
    _check(
        checks,
        "all_page_sweeps_completed",
        pending_sweeps == 0 and rejected_sweeps == 0,
        "every page received a completed manual sweep",
        f"pending={pending_sweeps}; rejected={rejected_sweeps}",
    )
    _check(
        checks,
        "page_sweeps_have_audit_trail",
        sweep_audit_missing == 0,
        "completed page sweeps have reviewer and timestamp",
        f"{sweep_audit_missing} completed/rejected sweeps lack reviewer or timestamp",
    )
    _check(
        checks,
        "page_sweep_rectangles_valid",
        invalid_added_rectangles == 0,
        "manual additions use normalized rectangles",
        f"{invalid_added_rectangles} page sweeps contain invalid added rectangles",
    )
    failed = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "grading_mark_mask_review_validation",
        "status": "ready" if not failed else "not_ready",
        "candidate_count": len(candidates),
        "page_count": len(expected),
        "checks": checks,
        "failed_checks": failed,
    }


def compile_approved_page_masks(
    *,
    base_layout: Mapping[str, Any],
    base_layout_sha256: str,
    candidate_manifest: Mapping[str, Any],
    decision_rows: Sequence[Mapping[str, str]],
    decision_columns: Sequence[str],
    sweep_rows: Sequence[Mapping[str, str]],
    sweep_columns: Sequence[str],
    candidate_manifest_sha256: str,
    decision_sha256: str,
    sweep_sha256: str,
) -> dict[str, Any]:
    workflow = validate_mask_review_workflow(
        layout=base_layout,
        layout_sha256=base_layout_sha256,
        candidate_manifest=candidate_manifest,
        decision_rows=decision_rows,
        decision_columns=decision_columns,
        sweep_rows=sweep_rows,
        sweep_columns=sweep_columns,
    )
    if workflow["status"] != "ready":
        raise ValueError("mask review workflow is not ready: " + ", ".join(workflow["failed_checks"]))

    candidates = {str(entry["candidate_id"]): entry for entry in _candidate_entries(candidate_manifest)}
    decisions = {str(row["candidate_id"]): row for row in decision_rows}
    additions: dict[tuple[str, int], list[dict[str, float]]] = {}
    reasons: dict[tuple[str, int], list[str]] = {}
    for candidate_id, candidate in candidates.items():
        decision = decisions[candidate_id]
        status = _cell(decision, "decision_status")
        if status == "rejected":
            continue
        if status == "accepted":
            rectangles = _canonical_rectangles(candidate["rectangles"])
        else:
            rectangles = parse_rectangles(_cell(decision, "final_rectangles"))
        pair = (str(candidate["anonymous_id"]), int(candidate["source_page"]))
        additions.setdefault(pair, []).extend(rectangles)
        reasons.setdefault(pair, []).append(f"candidate:{candidate_id}:{status}")
    for row in sweep_rows:
        pair = _review_pair(row)
        if pair is None:
            raise ValueError("page sweep row has invalid pair")
        rectangles = parse_rectangles(_cell(row, "added_rectangles"))
        if rectangles:
            additions.setdefault(pair, []).extend(rectangles)
            reasons.setdefault(pair, []).append("manual_page_sweep")

    result = copy.deepcopy(dict(base_layout))
    for group in result.get("page_groups", []):
        anonymous_id = str(group["anonymous_id"])
        existing = list(group.get("page_masks", []))
        for source_page in group["source_pages"]:
            pair = (anonymous_id, int(source_page))
            rectangles = _dedupe_rectangles(additions.get(pair, []))
            if not rectangles:
                continue
            existing.append(
                {
                    "source_page": source_page,
                    "reason": ";".join(reasons.get(pair, ["approved_grading_mark_mask"])),
                    "rectangles": rectangles,
                }
            )
        group["page_masks"] = existing
    result["grading_mask_review"] = {
        "schema_version": 1,
        "base_layout_sha256": base_layout_sha256,
        "candidate_manifest_sha256": candidate_manifest_sha256,
        "candidate_decisions_sha256": decision_sha256,
        "page_sweeps_sha256": sweep_sha256,
        "candidate_count": len(candidates),
        "page_sweep_count": len(expected_review_pairs(base_layout)),
    }
    return result


def validate_compiled_mask_provenance(
    *,
    layout: Mapping[str, Any],
    base_layout_path: Path,
    candidate_manifest_path: Path,
    decision_path: Path,
    sweep_path: Path,
) -> dict[str, Any]:
    """Verify that a compiled layout is exactly reproducible from its review.

    The caller must provide the actual base layout, rather than relying on the
    hash recorded inside the compiled layout.  This prevents a modified base
    layout, extra masks, or unrelated page-group changes from being accepted
    merely because the review CSVs still have matching hashes.
    """

    checks: list[dict[str, str]] = []
    provenance = layout.get("grading_mask_review")
    _check(
        checks,
        "grading_mask_review_metadata_present",
        isinstance(provenance, Mapping) and provenance.get("schema_version") == 1,
        "compiled layout contains grading mask review provenance",
        "compiled layout lacks grading mask review provenance",
    )
    if not isinstance(provenance, Mapping):
        failed = [check["id"] for check in checks if check["status"] == "failed"]
        return {"status": "not_ready", "checks": checks, "failed_checks": failed}

    base_layout: dict[str, Any] | None = None
    base_layout_hash: str | None = None
    base_present = base_layout_path.is_file()
    _check(
        checks,
        "base_layout_file_present",
        base_present,
        "an actual base layout was supplied",
        "compiled layouts require an existing --base-layout file",
    )
    if base_present:
        try:
            base_layout = _load_json_object(base_layout_path)
            base_layout_hash = sha256_file(base_layout_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            base_layout = None
    _check(
        checks,
        "base_layout_is_valid_json_object",
        base_layout is not None,
        "base layout is a JSON object",
        "base layout is not a readable JSON object",
    )
    _check(
        checks,
        "base_layout_sha256_matches",
        (
            base_layout_hash is not None
            and provenance.get("base_layout_sha256") == base_layout_hash
        ),
        "compiled layout is tied to the supplied base layout",
        "compiled layout was not derived from the supplied base layout",
    )

    files = {
        "candidate_manifest_sha256": candidate_manifest_path,
        "candidate_decisions_sha256": decision_path,
        "page_sweeps_sha256": sweep_path,
    }
    for field, path in files.items():
        present = path.is_file()
        try:
            actual_hash = sha256_file(path) if present else None
        except OSError:
            actual_hash = None
        matches = actual_hash is not None and provenance.get(field) == actual_hash
        _check(
            checks,
            f"{field}_matches",
            matches,
            f"{field} matches the reviewed private artifact",
            f"{field} does not match the reviewed private artifact",
        )

    review_inputs_present = all(path.is_file() for path in files.values())
    review_inputs_loaded = False
    manifest: dict[str, Any] | None = None
    decision_columns: tuple[str, ...] = ()
    decision_rows: list[dict[str, str]] = []
    sweep_columns: tuple[str, ...] = ()
    sweep_rows: list[dict[str, str]] = []
    if review_inputs_present:
        try:
            manifest = _load_json_object(candidate_manifest_path)
            decision_columns, decision_rows = load_csv_rows(decision_path)
            sweep_columns, sweep_rows = load_csv_rows(sweep_path)
            review_inputs_loaded = True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            review_inputs_loaded = False
    _check(
        checks,
        "grading_mask_review_inputs_parseable",
        review_inputs_loaded,
        "candidate manifest and review CSVs can be read",
        "candidate manifest or review CSVs cannot be read",
    )

    exact_recompile = False
    if base_layout is not None and base_layout_hash is not None and review_inputs_loaded:
        workflow = validate_mask_review_workflow(
            layout=base_layout,
            layout_sha256=base_layout_hash,
            candidate_manifest=manifest or {},
            decision_rows=decision_rows,
            decision_columns=decision_columns,
            sweep_rows=sweep_rows,
            sweep_columns=sweep_columns,
        )
        _check(
            checks,
            "grading_mask_review_workflow_ready",
            workflow["status"] == "ready",
            "candidate decisions and page sweeps are complete",
            "candidate decisions or page sweeps are incomplete/invalid",
        )
        if workflow["status"] == "ready":
            try:
                recompiled = compile_approved_page_masks(
                    base_layout=base_layout,
                    base_layout_sha256=base_layout_hash,
                    candidate_manifest=manifest or {},
                    decision_rows=decision_rows,
                    decision_columns=decision_columns,
                    sweep_rows=sweep_rows,
                    sweep_columns=sweep_columns,
                    candidate_manifest_sha256=sha256_file(candidate_manifest_path),
                    decision_sha256=sha256_file(decision_path),
                    sweep_sha256=sha256_file(sweep_path),
                )
                # Compare the entire JSON object, not only rectangle membership:
                # this rejects extra masks as well as source-page/group tampering.
                exact_recompile = dict(layout) == recompiled
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                exact_recompile = False
    else:
        _check(
            checks,
            "grading_mask_review_workflow_ready",
            False,
            "candidate decisions and page sweeps are complete",
            "cannot validate review workflow without a readable base layout and review files",
        )
    _check(
        checks,
        "compiled_layout_exactly_matches_reviewed_base",
        exact_recompile,
        "compiled layout exactly matches the supplied base layout plus approved review masks",
        "compiled layout differs from the exact approved base-layout recomputation",
    )
    failed = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "compiled_grading_mask_provenance_validation",
        "status": "ready" if not failed else "not_ready",
        "checks": checks,
        "failed_checks": failed,
    }


def build_render_spec(
    *,
    layout: Mapping[str, Any],
    layout_sha256: str,
    identity_rectangles: Sequence[Mapping[str, float]],
    render_scale: float,
    max_render_pixels: int | None = None,
) -> dict[str, Any]:
    spec = {
        "schema_version": 1,
        "renderer": "prepare_anonymized_assessment",
        "renderer_version": 2,
        "assessment_id": layout.get("assessment_id"),
        "source_sha256": layout.get("source_sha256"),
        "layout_sha256": layout_sha256,
        "identity_redaction_rectangles": _canonical_rectangles(identity_rectangles),
        "render_scale": float(render_scale),
    }
    if max_render_pixels is not None:
        if not isinstance(max_render_pixels, int) or max_render_pixels <= 0:
            raise ValueError("max_render_pixels must be a positive integer")
        spec["max_render_pixels"] = max_render_pixels
    return spec


def build_artifact_manifest(
    *,
    output_root: Path,
    layout: Mapping[str, Any],
    render_spec_sha256: str,
) -> dict[str, Any]:
    expected = expected_output_paths(layout)
    entries: list[dict[str, Any]] = []
    for relative_path in sorted(expected):
        path = output_root / relative_path
        if not path.is_file():
            raise FileNotFoundError(path)
        entries.append(
            {
                "path": relative_path,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return {
        "schema_version": 1,
        "record_type": "anonymized_assessment_output_artifacts",
        "render_spec_sha256": render_spec_sha256,
        "artifacts": entries,
    }


def validate_artifact_manifest(
    *,
    output_root: Path,
    layout: Mapping[str, Any],
    manifest: Mapping[str, Any],
    render_spec_sha256: str,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    _check(
        checks,
        "artifact_manifest_schema_supported",
        manifest.get("schema_version") == 1,
        "artifact manifest uses schema_version=1",
        "artifact manifest must use schema_version=1",
    )
    _check(
        checks,
        "artifact_manifest_render_spec_matches",
        manifest.get("render_spec_sha256") == render_spec_sha256,
        "artifact manifest matches render specification",
        "artifact manifest does not match render specification",
    )
    entries = manifest.get("artifacts")
    entries = entries if isinstance(entries, list) else []
    expected = expected_output_paths(layout)
    actual_output_files = _output_tree_files(output_root)
    actual: set[str] = set()
    malformed = 0
    changed = 0
    for entry in entries:
        if not isinstance(entry, Mapping):
            malformed += 1
            continue
        relative = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("bytes")
        if not isinstance(relative, str) or relative not in expected or relative in actual:
            malformed += 1
            continue
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            malformed += 1
            continue
        if not isinstance(size, int) or size < 0:
            malformed += 1
            continue
        actual.add(relative)
        path = output_root / relative
        if not path.is_file() or path.stat().st_size != size or sha256_file(path) != digest:
            changed += 1
    _check(
        checks,
        "artifact_manifest_covers_expected_outputs",
        not malformed and actual == expected,
        "artifact manifest covers exactly every expected image and PDF",
        f"malformed={malformed}; missing={len(expected - actual)}; unexpected={len(actual - expected)}",
    )
    _check(
        checks,
        "prepared_output_tree_matches_expected_paths",
        actual_output_files == expected,
        "prepared image/PDF directories contain exactly the expected anonymous outputs",
        (
            f"missing={len(expected - actual_output_files)}; "
            f"unexpected={len(actual_output_files - expected)}"
        ),
    )
    _check(
        checks,
        "prepared_output_hashes_match",
        changed == 0,
        "all prepared image/PDF hashes match the artifact manifest",
        f"{changed} prepared outputs are missing or changed",
    )
    failed = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "anonymized_assessment_artifact_validation",
        "status": "ready" if not failed else "not_ready",
        "expected_output_count": len(expected),
        "checks": checks,
        "failed_checks": failed,
    }


def expected_review_pairs(layout: Mapping[str, Any]) -> set[tuple[str, int]]:
    pairs: set[tuple[str, int]] = set()
    for group in layout.get("page_groups", []):
        if not isinstance(group, Mapping):
            raise ValueError("each page group must be an object")
        anonymous_id = group.get("anonymous_id")
        source_pages = group.get("source_pages")
        if not isinstance(anonymous_id, str) or not isinstance(source_pages, list):
            raise ValueError("page group requires anonymous_id and source_pages")
        for source_page in source_pages:
            if not isinstance(source_page, int) or source_page <= 0:
                raise ValueError("source_pages must contain positive integers")
            pairs.add((anonymous_id, source_page))
    return pairs


def expected_output_paths(layout: Mapping[str, Any]) -> set[str]:
    expected: set[str] = set()
    for group in layout.get("page_groups", []):
        anonymous_id = str(group["anonymous_id"])
        pages = list(group["source_pages"])
        expected.add(f"anonymized_pdfs/{anonymous_id}.pdf")
        for local_page, _source_page in enumerate(pages, start=1):
            expected.add(f"anonymized_pages/{anonymous_id}/{anonymous_id}-p{local_page:02d}.png")
    return expected


def _output_tree_files(output_root: Path) -> set[str]:
    """List only model-facing output files, excluding private manifests/reviews."""

    files: set[str] = set()
    for directory in ("anonymized_pages", "anonymized_pdfs"):
        root = output_root / directory
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                files.add(path.relative_to(output_root).as_posix())
    return files


def _component_boxes(mask: Image.Image, *, min_component_area: int) -> list[tuple[int, int, int, int]]:
    width, height = mask.size
    pixels = bytearray(mask.convert("L").tobytes())
    boxes: list[tuple[int, int, int, int]] = []
    for start, value in enumerate(pixels):
        if not value:
            continue
        pixels[start] = 0
        queue: deque[int] = deque([start])
        count = 0
        left = right = start % width
        top = bottom = start // width
        while queue:
            index = queue.popleft()
            x = index % width
            y = index // width
            count += 1
            left = min(left, x)
            right = max(right, x)
            top = min(top, y)
            bottom = max(bottom, y)
            for neighbor_y in range(max(0, y - 1), min(height, y + 2)):
                base = neighbor_y * width
                for neighbor_x in range(max(0, x - 1), min(width, x + 2)):
                    neighbor = base + neighbor_x
                    if pixels[neighbor]:
                        pixels[neighbor] = 0
                        queue.append(neighbor)
        if count >= min_component_area:
            boxes.append((left, top, right + 1, bottom + 1))
    return boxes


def _apply_rectangles(image: Image.Image, rectangles: Sequence[Mapping[str, float]]) -> None:
    draw = ImageDraw.Draw(image)
    for rectangle in rectangles:
        if not _valid_rectangle(rectangle):
            raise ValueError("invalid excluded rectangle")
        draw.rectangle(
            (
                int(image.width * float(rectangle["left"])),
                int(image.height * float(rectangle["top"])),
                int(image.width * float(rectangle["right"])),
                int(image.height * float(rectangle["bottom"])),
            ),
            fill="white",
        )


def _candidate_entries(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates = manifest.get("candidates")
    return [entry for entry in candidates if isinstance(entry, Mapping)] if isinstance(candidates, list) else []


def _canonical_rectangles(rectangles: Iterable[Mapping[str, Any]]) -> list[dict[str, float]]:
    result: list[dict[str, float]] = []
    for rectangle in rectangles:
        if not _valid_rectangle(rectangle):
            raise ValueError("invalid normalized rectangle")
        result.append(
            {
                "left": float(rectangle["left"]),
                "top": float(rectangle["top"]),
                "right": float(rectangle["right"]),
                "bottom": float(rectangle["bottom"]),
            }
        )
    return _dedupe_rectangles(result)


def _dedupe_rectangles(rectangles: Iterable[Mapping[str, Any]]) -> list[dict[str, float]]:
    result: list[dict[str, float]] = []
    seen: set[tuple[float, float, float, float]] = set()
    for rectangle in rectangles:
        normalized = (
            float(rectangle["left"]),
            float(rectangle["top"]),
            float(rectangle["right"]),
            float(rectangle["bottom"]),
        )
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(
            {
                "left": normalized[0],
                "top": normalized[1],
                "right": normalized[2],
                "bottom": normalized[3],
            }
        )
    return result


def _rectangles_valid(rectangles: Iterable[object]) -> bool:
    return all(_valid_rectangle(rectangle) for rectangle in rectangles)


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


def _review_pair(row: Mapping[str, str]) -> tuple[str, int] | None:
    try:
        page = int(_cell(row, "source_page"))
    except ValueError:
        return None
    anonymous_id = _cell(row, "anonymous_id")
    return (anonymous_id, page) if anonymous_id and page > 0 else None


def _missing_columns(actual: Sequence[str], required: Sequence[str]) -> list[str]:
    return [column for column in required if column not in actual]


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _cell(row: Mapping[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check(
    checks: list[dict[str, str]],
    check_id: str,
    passed: bool,
    passed_detail: str,
    failed_detail: str,
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": "passed" if passed else "failed",
            "detail": passed_detail if passed else failed_detail,
        }
    )
