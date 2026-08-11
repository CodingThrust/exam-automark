"""Validate the reproducible lineage of direct and transcription grading routes.

The M1 route grades frozen submission images directly.  The T1-to-G1 route
first transcribes the same images, then grades only the recorded transcripts.
This module checks the packet and transcript-run bindings without running a
model or reading student-answer text into its report.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .packets import audit_prompt_packet, directory_digest


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
_ANONYMOUS_STUDENT_ID = re.compile(r"\bS\d{3,}\b")
_ABSOLUTE_PATH = re.compile(r"(?:^[A-Za-z]:[\\/]|^[\\/]{2}|^/[A-Za-z]|[A-Za-z]:[\\/])")
_PRIVATE_PATH = re.compile(r"(?i)(?:^|[\\/])(?:data|\.private-data|local)(?:[\\/]|$)")
_CANONICAL_NEXT_GATE = (
    "This lineage check never authorizes a model run. Complete the human gold "
    "and explicit run-approval gates separately."
)
_LINEAGE_PRIVACY = {
    "aggregate_only": True,
    "student_ids_included": False,
    "per_student_scores_included": False,
    "raw_answers_included": False,
    "model_evidence_included": False,
    "private_paths_included": False,
}


def check_m1_t1_g1_lineage(
    *,
    m1_packet: Path,
    t1_packet: Path,
    g1_packet: Path | None = None,
    t1_run: Path | None = None,
) -> dict[str, Any]:
    """Return a privacy-safe readiness report for the M1 and T1-to-G1 routes.

    Supplying neither G1 packet nor T1 run checks the image-packet pair before
    any model execution.  Supplying one requires the other and additionally
    proves that the G1 packet copied the validated T1 output bytes.
    """

    if (g1_packet is None) != (t1_run is None):
        raise ValueError("g1_packet and t1_run must be supplied together")
    m1 = _load_packet(m1_packet, "M1")
    t1 = _load_packet(t1_packet, "T1")
    checks = _image_route_checks(m1, t1)
    stage = "image_packets"
    g1: dict[str, Any] | None = None
    if g1_packet is not None and t1_run is not None:
        g1 = _load_packet(g1_packet, "G1")
        checks.extend(_transcript_route_checks(m1, t1, g1, Path(t1_run)))
        stage = "full_routes"
    binding: dict[str, Any] | None = None
    if g1 is not None and t1_run is not None and not any(
        check["status"] == "failed" for check in checks
    ):
        try:
            binding = canonicalize_public_route_lineage_binding(
                _build_public_lineage_binding(
                    m1=m1,
                    t1=t1,
                    g1=g1,
                    t1_run=Path(t1_run),
                    ready=True,
                )
            )
            checks.append(
                _check(
                    "public_lineage_binding_valid",
                    True,
                    "the aggregate lineage binding is structurally safe and complete",
                )
            )
        except ValueError:
            checks.append(
                _check(
                    "public_lineage_binding_valid",
                    False,
                    "the aggregate lineage binding must be structurally safe and complete",
                )
            )
    failed_checks = [check["id"] for check in checks if check["status"] == "failed"]
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_type": "m1_t1_g1_route_lineage",
        "status": "ready" if not failed_checks else "not_ready",
        "stage": stage,
        "model_run_allowed": False,
        "student_count": len(m1["manifest"].get("student_ids", [])),
        "checks": checks,
        "failed_checks": failed_checks,
        "next_gate": _CANONICAL_NEXT_GATE,
    }
    if binding is not None:
        report["lineage_binding"] = binding
    return report


def write_route_lineage_report(report: Mapping[str, Any], output: Path) -> None:
    """Write the safe aggregate-only report without packet inputs or answers."""

    _write_json_atomic(output, canonicalize_route_lineage_report(report))


def canonicalize_route_lineage_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild a write-safe aggregate lineage audit with no free-form fields."""

    payload = dict(report)
    expected = {
        "schema_version",
        "report_type",
        "status",
        "stage",
        "model_run_allowed",
        "student_count",
        "checks",
        "failed_checks",
        "next_gate",
    }
    if "lineage_binding" in payload:
        expected.add("lineage_binding")
    _require_exact_keys(payload, expected, "route lineage report")
    if payload["schema_version"] != 1 or payload["report_type"] != "m1_t1_g1_route_lineage":
        raise ValueError("route lineage report schema is invalid")
    if payload["status"] not in {"ready", "not_ready"}:
        raise ValueError("route lineage report status is invalid")
    if payload["stage"] not in {"image_packets", "full_routes"}:
        raise ValueError("route lineage report stage is invalid")
    if payload["model_run_allowed"] is not False:
        raise ValueError("route lineage report must not authorize a model run")
    if not isinstance(payload["student_count"], int) or isinstance(payload["student_count"], bool) or payload["student_count"] <= 0:
        raise ValueError("route lineage report student_count is invalid")
    checks_value = payload["checks"]
    if not isinstance(checks_value, list) or not checks_value:
        raise ValueError("route lineage report checks are invalid")
    checks: list[dict[str, str]] = []
    for value in checks_value:
        check = _mapping(value, "route lineage check")
        # Fresh checker output includes a human-readable detail, while the
        # persisted aggregate audit deliberately omits it.  Both shapes are
        # valid inputs to this canonicalizer; detail is never propagated.
        # This keeps a report written by ``write_route_lineage_report`` usable
        # by the later public-binding projection without admitting arbitrary
        # extra fields into a public artifact.
        check_keys = set(check)
        if check_keys not in ({"id", "status"}, {"id", "status", "detail"}):
            _require_exact_keys(
                check, {"id", "status", "detail"}, "route lineage check"
            )
        check_id = _safe_identifier(check["id"], "route lineage check id")
        if check["status"] not in {"passed", "failed"}:
            raise ValueError("route lineage check status is invalid")
        checks.append({"id": check_id, "status": check["status"]})
    if len({check["id"] for check in checks}) != len(checks):
        raise ValueError("route lineage check IDs must be unique")
    failed = [check["id"] for check in checks if check["status"] == "failed"]
    if payload["failed_checks"] != failed:
        raise ValueError("route lineage report failed_checks are inconsistent")
    if (payload["status"] == "ready") != (not failed):
        raise ValueError("route lineage report status is inconsistent with checks")
    result: dict[str, Any] = {
        "schema_version": 1,
        "report_type": "m1_t1_g1_route_lineage",
        "status": payload["status"],
        "stage": payload["stage"],
        "model_run_allowed": False,
        "student_count": payload["student_count"],
        "checks": checks,
        "failed_checks": failed,
        "next_gate": _CANONICAL_NEXT_GATE,
    }
    if "lineage_binding" in payload:
        result["lineage_binding"] = canonicalize_public_route_lineage_binding(
            _mapping(payload["lineage_binding"], "lineage binding")
        )
    return result


def project_public_route_lineage_binding(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the safe opaque binding from a completed full-route report.

    The route-lineage checker may run beside private packets, but this
    projection contains only route metadata and SHA-256 commitments.  It is
    designed to be passed to the aggregate multi-route report without exposing
    packet manifests, transcript files, names, or roster entries.
    """

    canonical = canonicalize_route_lineage_report(report)
    if canonical["stage"] != "full_routes" or canonical["status"] != "ready":
        raise ValueError("a ready full-route lineage report is required")
    binding = canonical.get("lineage_binding")
    if not isinstance(binding, Mapping):
        raise ValueError("full-route lineage report has no public binding")
    return canonicalize_public_route_lineage_binding(binding)


def write_public_route_lineage_binding(
    report: Mapping[str, Any], output: Path
) -> dict[str, Any]:
    """Write a canonical aggregate-only lineage commitment."""

    binding = project_public_route_lineage_binding(report)
    _write_json_atomic(output, binding)
    return binding


def canonicalize_public_route_lineage_binding(
    binding: Mapping[str, Any],
) -> dict[str, Any]:
    """Strictly validate and rebuild the public lineage binding schema."""

    payload = dict(binding)
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "record_type",
            "status",
            "privacy",
            "course",
            "scope",
            "m1",
            "t1",
            "g1",
        },
        "lineage binding",
    )
    if payload["schema_version"] != 1:
        raise ValueError("lineage binding schema_version must be 1")
    if payload["record_type"] != "public_full_route_lineage_binding":
        raise ValueError("lineage binding record_type is invalid")
    if payload["status"] != "ready":
        raise ValueError("a ready lineage binding is required")
    if payload["privacy"] != _LINEAGE_PRIVACY:
        raise ValueError("lineage binding privacy declaration is invalid")
    course = _mapping(payload["course"], "lineage course")
    _require_exact_keys(course, {"course_id", "assessment_id"}, "lineage course")
    scope = _mapping(payload["scope"], "lineage scope")
    _require_exact_keys(
        scope, {"data_snapshot_hash", "roster_hash"}, "lineage scope"
    )
    m1 = _mapping(payload["m1"], "M1 lineage")
    _require_exact_keys(
        m1, {"packet_hash", "data_snapshot_hash", "rubric_hash"}, "M1 lineage"
    )
    t1 = _mapping(payload["t1"], "T1 lineage")
    _require_exact_keys(
        t1,
        {
            "packet_hash",
            "run_id",
            "data_snapshot_hash",
            "task",
            "input_mode",
            "condition",
            "validation_status",
        },
        "T1 lineage",
    )
    g1 = _mapping(payload["g1"], "G1 lineage")
    _require_exact_keys(
        g1,
        {
            "packet_hash",
            "data_snapshot_hash",
            "rubric_hash",
            "text_source_hash",
            "source_run_id",
            "source_transcription_packet_hash",
        },
        "G1 lineage",
    )
    result = {
        "schema_version": 1,
        "record_type": "public_full_route_lineage_binding",
        "status": "ready",
        "privacy": dict(_LINEAGE_PRIVACY),
        "course": {
            "course_id": _safe_identifier(course["course_id"], "course_id"),
            "assessment_id": _safe_identifier(
                course["assessment_id"], "assessment_id"
            ),
        },
        "scope": {
            "data_snapshot_hash": _sha256(
                scope["data_snapshot_hash"], "data_snapshot_hash"
            ),
            "roster_hash": _sha256(scope["roster_hash"], "roster_hash"),
        },
        "m1": {
            "packet_hash": _sha256(m1["packet_hash"], "M1 packet_hash"),
            "data_snapshot_hash": _sha256(
                m1["data_snapshot_hash"], "M1 data_snapshot_hash"
            ),
            "rubric_hash": _sha256(m1["rubric_hash"], "M1 rubric_hash"),
        },
        "t1": {
            "packet_hash": _sha256(t1["packet_hash"], "T1 packet_hash"),
            "run_id": _safe_identifier(t1["run_id"], "T1 run_id"),
            "data_snapshot_hash": _sha256(
                t1["data_snapshot_hash"], "T1 data_snapshot_hash"
            ),
            "task": _safe_identifier(t1["task"], "T1 task"),
            "input_mode": _safe_identifier(t1["input_mode"], "T1 input_mode"),
            "condition": _safe_identifier(t1["condition"], "T1 condition"),
            "validation_status": _safe_identifier(
                t1["validation_status"], "T1 validation_status"
            ),
        },
        "g1": {
            "packet_hash": _sha256(g1["packet_hash"], "G1 packet_hash"),
            "data_snapshot_hash": _sha256(
                g1["data_snapshot_hash"], "G1 data_snapshot_hash"
            ),
            "rubric_hash": _sha256(g1["rubric_hash"], "G1 rubric_hash"),
            "text_source_hash": _sha256(
                g1["text_source_hash"], "G1 text_source_hash"
            ),
            "source_run_id": _safe_identifier(
                g1["source_run_id"], "G1 source_run_id"
            ),
            "source_transcription_packet_hash": _sha256(
                g1["source_transcription_packet_hash"],
                "G1 source_transcription_packet_hash",
            ),
        },
    }
    snapshot = result["scope"]["data_snapshot_hash"]
    if not all(
        value == snapshot
        for value in (
            result["m1"]["data_snapshot_hash"],
            result["t1"]["data_snapshot_hash"],
            result["g1"]["data_snapshot_hash"],
        )
    ):
        raise ValueError("lineage binding data snapshot hashes do not match")
    if result["t1"]["task"] != "transcribe":
        raise ValueError("T1 lineage task must be transcribe")
    if result["t1"]["input_mode"] != "multimodal":
        raise ValueError("T1 lineage input_mode must be multimodal")
    if result["t1"]["condition"] != "T1":
        raise ValueError("T1 lineage condition must be T1")
    if result["t1"]["validation_status"] != "passed":
        raise ValueError("T1 lineage validation_status must be passed")
    if result["g1"]["source_run_id"] != result["t1"]["run_id"]:
        raise ValueError("G1 source_run_id does not bind the T1 run")
    if (
        result["g1"]["source_transcription_packet_hash"]
        != result["t1"]["packet_hash"]
    ):
        raise ValueError("G1 source_transcription_packet_hash does not bind T1")
    if result["m1"]["rubric_hash"] != result["g1"]["rubric_hash"]:
        raise ValueError("M1 and G1 lineage rubric hashes do not match")
    return result


def _build_public_lineage_binding(
    *,
    m1: Mapping[str, Any],
    t1: Mapping[str, Any],
    g1: Mapping[str, Any],
    t1_run: Path,
    ready: bool,
) -> dict[str, Any]:
    """Build an opaque, safe-to-publish commitment for one full route chain."""

    m1_manifest = _manifest(m1)
    t1_manifest = _manifest(t1)
    g1_manifest = _manifest(g1)
    t1_run_metadata = _read_optional_json(t1_run / "run-metadata.json")
    m1_snapshot = _snapshot_hash(m1_manifest)
    g1_snapshot = _snapshot_hash(g1_manifest)
    g1_metadata = _metadata(g1_manifest)
    t1_values: dict[str, Any] = {
        "packet_hash": t1["packet_hash"],
        "run_id": None,
        "data_snapshot_hash": None,
        "task": None,
        "input_mode": None,
        "condition": None,
        "validation_status": None,
    }
    if t1_run_metadata is not None:
        for field in (
            "run_id",
            "data_snapshot_hash",
            "task",
            "input_mode",
            "condition",
            "validation_status",
        ):
            t1_values[field] = t1_run_metadata.get(field)
    return {
        "schema_version": 1,
        "record_type": "public_full_route_lineage_binding",
        "status": "ready" if ready else "not_ready",
        "privacy": dict(_LINEAGE_PRIVACY),
        "course": {
            "course_id": m1_manifest.get("course_id"),
            "assessment_id": m1_manifest.get("assessment_id"),
        },
        "scope": {
            "data_snapshot_hash": m1_snapshot,
            "roster_hash": _roster_hash(m1_manifest.get("student_ids")),
        },
        "m1": {
            "packet_hash": m1["packet_hash"],
            "data_snapshot_hash": m1_snapshot,
            "rubric_hash": m1_manifest.get("rubric_hash"),
        },
        "t1": t1_values,
        "g1": {
            "packet_hash": g1["packet_hash"],
            "data_snapshot_hash": g1_snapshot,
            "rubric_hash": g1_manifest.get("rubric_hash"),
            "text_source_hash": g1_metadata.get("text_source_hash"),
            "source_run_id": g1_metadata.get("source_run_id"),
            "source_transcription_packet_hash": g1_metadata.get(
                "source_transcription_packet_hash"
            ),
        },
    }


def _load_packet(path: Path, label: str) -> dict[str, Any]:
    root = Path(path)
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"{label} packet must be a real directory")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError(f"{label} packet manifest is missing or unsafe")
    manifest = _read_json(manifest_path, f"{label} packet manifest")
    if not isinstance(manifest.get("student_ids"), list) or not manifest["student_ids"]:
        raise ValueError(f"{label} packet has no student_ids")
    if not isinstance(manifest.get("input_hashes"), dict):
        raise ValueError(f"{label} packet has no input_hashes")
    if set(manifest["student_ids"]) != set(manifest["input_hashes"]):
        raise ValueError(f"{label} packet input hashes do not match student IDs")
    return {
        "label": label,
        "path": root.resolve(),
        "manifest": manifest,
        "packet_hash": directory_digest(root),
        "audit_findings": audit_prompt_packet(root),
    }


def _image_route_checks(m1: Mapping[str, Any], t1: Mapping[str, Any]) -> list[dict[str, str]]:
    m1_manifest = _manifest(m1)
    t1_manifest = _manifest(t1)
    checks = [
        _check(
            "m1_packet_role",
            m1_manifest.get("condition") == "M1" and m1_manifest.get("task") == "grade",
            "M1 is a direct-image grade packet",
        ),
        _check(
            "t1_packet_role",
            t1_manifest.get("condition") == "T1" and t1_manifest.get("task") == "transcribe",
            "T1 is an image transcription packet",
        ),
        _check(
            "m1_t1_packets_audit_clean",
            not m1["audit_findings"] and not t1["audit_findings"],
            "both image packets pass the packet isolation audit",
        ),
        _check(
            "m1_t1_course_binding_matches",
            _same_fields(m1_manifest, t1_manifest, ("course_id", "assessment_id")),
            "M1 and T1 bind the same course assessment",
        ),
        _check(
            "m1_t1_student_order_matches",
            m1_manifest.get("student_ids") == t1_manifest.get("student_ids"),
            "M1 and T1 contain the same anonymous students in the same order",
        ),
        _check(
            "m1_t1_input_hashes_match",
            m1_manifest.get("input_hashes") == t1_manifest.get("input_hashes"),
            "M1 and T1 use byte-identical input directories per student",
        ),
        _check(
            "m1_t1_snapshot_binding_matches",
            _same_snapshot_binding(m1_manifest, t1_manifest),
            "M1 and T1 bind the same immutable anonymous submission snapshot",
        ),
        _check(
            "m1_grade_rubric_present",
            _is_sha256(m1_manifest.get("rubric_hash")),
            "M1 has a hashed grading rubric",
        ),
        _check(
            "t1_has_no_grading_rubric",
            t1_manifest.get("rubric_hash") is None,
            "T1 is transcription-only and carries no grading rubric",
        ),
    ]
    return checks


def _transcript_route_checks(
    m1: Mapping[str, Any], t1: Mapping[str, Any], g1: Mapping[str, Any], t1_run: Path
) -> list[dict[str, str]]:
    m1_manifest = _manifest(m1)
    t1_manifest = _manifest(t1)
    g1_manifest = _manifest(g1)
    checks = [
        _check(
            "g1_packet_role",
            g1_manifest.get("condition") == "G1" and g1_manifest.get("task") == "grade",
            "G1 is a transcript-only grade packet",
        ),
        _check(
            "g1_packet_audit_clean",
            not g1["audit_findings"],
            "G1 passes the packet isolation audit",
        ),
        _check(
            "g1_course_binding_matches_m1",
            _same_fields(m1_manifest, g1_manifest, ("course_id", "assessment_id")),
            "G1 binds the same course assessment as M1",
        ),
        _check(
            "g1_student_order_matches_m1",
            g1_manifest.get("student_ids") == m1_manifest.get("student_ids"),
            "G1 contains the same anonymous students in the same order as M1",
        ),
        _check(
            "g1_snapshot_binding_matches_m1",
            _snapshot_hash(g1_manifest) == _snapshot_hash(m1_manifest),
            "G1 records the same immutable anonymous submission snapshot as M1",
        ),
        _check(
            "g1_transcription_packet_hash_matches_t1",
            _metadata(g1_manifest).get("source_transcription_packet_hash")
            == t1["packet_hash"],
            "G1 records the exact T1 packet hash as its transcription source",
        ),
        _check(
            "g1_source_run_id_present",
            isinstance(_metadata(g1_manifest).get("source_run_id"), str)
            and bool(_metadata(g1_manifest)["source_run_id"].strip()),
            "G1 records a non-empty transcription run identifier",
        ),
    ]
    try:
        run_metadata = _read_json(t1_run / "run-metadata.json", "T1 run metadata")
        run_outputs = t1_run / "outputs"
        expected_hashes = _metadata(g1_manifest).get("text_source_input_hashes")
        if not isinstance(expected_hashes, dict):
            raise ValueError("G1 packet has no text_source_input_hashes")
        observed_hashes = {
            student_id: _sha256_file(run_outputs / f"{student_id}.json")
            for student_id in m1_manifest["student_ids"]
        }
        checks.extend(
            [
                _check(
                    "t1_run_metadata_matches_t1_packet",
                    run_metadata.get("packet_hash") == t1["packet_hash"]
                    and run_metadata.get("task") == "transcribe"
                    and run_metadata.get("condition") == "T1"
                    and run_metadata.get("input_mode") == "multimodal"
                    and run_metadata.get("validation_status") == "passed",
                    "T1 run metadata binds the audited T1 transcription packet",
                ),
                _check(
                    "t1_run_snapshot_matches_t1_packet",
                    run_metadata.get("data_snapshot_hash")
                    == _snapshot_hash(t1_manifest),
                    "T1 run metadata binds the immutable anonymous submission snapshot",
                ),
                _check(
                    "g1_source_run_id_matches_t1_run",
                    _metadata(g1_manifest).get("source_run_id")
                    == run_metadata.get("run_id")
                    and isinstance(run_metadata.get("run_id"), str)
                    and bool(run_metadata["run_id"].strip()),
                    "G1 records the exact completed T1 run identifier",
                ),
                _check(
                    "g1_transcript_bytes_match_t1_run",
                    expected_hashes == observed_hashes,
                    "G1 copied the exact per-student T1 transcript output bytes",
                ),
            ]
        )
    except (OSError, ValueError, json.JSONDecodeError):
        checks.extend(
            [
                _check(
                    "t1_run_metadata_matches_t1_packet",
                    False,
                    "T1 run metadata and successful outputs are required",
                ),
                _check(
                    "t1_run_snapshot_matches_t1_packet",
                    False,
                    "T1 run metadata must bind the immutable anonymous submission snapshot",
                ),
                _check(
                    "g1_source_run_id_matches_t1_run",
                    False,
                    "G1 must record the exact completed T1 run identifier",
                ),
                _check(
                    "g1_transcript_bytes_match_t1_run",
                    False,
                    "G1 transcript sources must be hash-bound to T1 outputs",
                ),
            ]
        )
    return checks


def _manifest(packet: Mapping[str, Any]) -> Mapping[str, Any]:
    manifest = packet["manifest"]
    assert isinstance(manifest, Mapping)
    return manifest


def _metadata(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = manifest.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}


def _same_fields(left: Mapping[str, Any], right: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(left.get(field) == right.get(field) for field in fields)


def _same_snapshot_binding(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    fields = (
        "input_mode",
        "snapshot_record_type",
        "snapshot_manifest_sha256",
        "input_snapshot_manifest_sha256",
        "snapshot_grading_unit",
    )
    left_metadata = _metadata(left)
    right_metadata = _metadata(right)
    return all(
        isinstance(left_metadata.get(field), str)
        and bool(left_metadata[field])
        and left_metadata.get(field) == right_metadata.get(field)
        for field in fields
    )


def _read_json(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    try:
        return _read_json(path, "route run metadata") if path.is_file() else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=path.parent,
        suffix=".tmp",
    ) as handle:
        handle.write(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")
        staged = Path(handle.name)
    try:
        os.replace(staged, path)
    finally:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            pass


def _snapshot_hash(manifest: Mapping[str, Any]) -> str | None:
    metadata = _metadata(manifest)
    for field in ("data_snapshot_hash", "input_snapshot_manifest_sha256"):
        value = metadata.get(field)
        if _is_sha256(value):
            return str(value)
    return None


def _roster_hash(student_ids: object) -> str | None:
    if not isinstance(student_ids, list) or not all(
        isinstance(student_id, str) for student_id in student_ids
    ):
        return None
    return hashlib.sha256("\n".join(student_ids).encode("utf-8")).hexdigest()


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], label: str
) -> None:
    observed = set(value)
    if observed != expected:
        unexpected = sorted(observed - expected)
        missing = sorted(expected - observed)
        fragments = []
        if unexpected:
            fragments.append("unexpected " + ", ".join(unexpected))
        if missing:
            fragments.append("missing " + ", ".join(missing))
        raise ValueError(f"{label} keys are invalid: " + "; ".join(fragments))


def _safe_identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a compact public identifier")
    if (
        _ANONYMOUS_STUDENT_ID.search(value)
        or _ABSOLUTE_PATH.search(value)
        or _PRIVATE_PATH.search(value)
    ):
        raise ValueError(f"{label} is not safe for a public lineage binding")
    return value


def _sha256(value: object, label: str) -> str:
    if not _is_sha256(value):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return str(value)


def _sha256_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError("expected T1 transcript output is missing or unsafe")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def _check(check_id: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "id": check_id,
        "status": "passed" if passed else "failed",
        "detail": detail,
    }
