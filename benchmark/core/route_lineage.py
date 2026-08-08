"""Validate the reproducible lineage of direct and transcription grading routes.

The M1 route grades frozen submission images directly.  The T1-to-G1 route
first transcribes the same images, then grades only the recorded transcripts.
This module checks the packet and transcript-run bindings without running a
model or reading student-answer text into its report.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .packets import audit_prompt_packet, directory_digest


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
    if g1_packet is not None and t1_run is not None:
        g1 = _load_packet(g1_packet, "G1")
        checks.extend(_transcript_route_checks(m1, t1, g1, Path(t1_run)))
        stage = "full_routes"
    failed_checks = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "m1_t1_g1_route_lineage",
        "status": "ready" if not failed_checks else "not_ready",
        "stage": stage,
        "model_run_allowed": False,
        "student_count": len(m1["manifest"].get("student_ids", [])),
        "checks": checks,
        "failed_checks": failed_checks,
        "next_gate": (
            "This lineage check never authorizes a model run. Complete the human "
            "gold and explicit run-approval gates separately."
        ),
    }


def write_route_lineage_report(report: Mapping[str, Any], output: Path) -> None:
    """Write the safe aggregate-only report without packet inputs or answers."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


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
            _metadata(g1_manifest).get("input_snapshot_manifest_sha256")
            == _metadata(m1_manifest).get("input_snapshot_manifest_sha256"),
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
                    and run_metadata.get("validation_status") == "passed",
                    "T1 run metadata binds the audited T1 transcription packet",
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
