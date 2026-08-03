"""Validate the immutable lineage between image and transcript grading routes.

The direct-multimodal route and the transcript-first route can only be compared
when they begin with exactly the same approved anonymous images.  A packet
manifest records hashes of its local inputs, but the existing packet builders do
not compare the G1 and T1 routes after they have been built.  This module adds
that narrow, model-free gate without changing the runner or the general CLI.

The gate deliberately reads only packet and run receipts supplied by the
caller.  It never invokes a model and never reads student work outside those
explicit paths.  Its report contains counts and hashes, not answer text or an
anonymous-ID list.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .packets import directory_digest


LINEAGE_SCHEMA_VERSION = 1
LINEAGE_RECORD_TYPE = "direct_multimodal_transcript_lineage"

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
_IMAGE_SUFFIXES = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
_TEXT_SUFFIXES = {".json", ".txt"}


class ModalityLineageError(ValueError):
    """Raised when packet-route lineage is incomplete, unsafe, or mismatched."""


def validate_modality_lineage(
    *,
    direct_multimodal_packet: Path,
    transcription_packet: Path,
    transcript_first_packet: Path,
    transcription_run_output: Path,
    transcription_run_id: str,
) -> dict[str, Any]:
    """Validate a direct-multimodal and transcript-first comparison route.

    ``direct_multimodal_packet`` is the grading packet that receives images.
    ``transcription_packet`` is the T1 image packet used to create transcripts.
    ``transcript_first_packet`` is the text-only grading packet built from that
    T1 run.  ``transcription_run_output`` is the headless runner directory that
    contains ``run-metadata.json``, ``validation.json``, and ``outputs/``.

    The function verifies four links:

    1. G1 and T1 have identical, recomputed anonymous image hashes.
    2. The transcript-first packet references the exact immutable T1 packet.
    3. The T1 run receipt says it transcribed that packet with the declared
       engine/model and completed every anonymous student.
    4. The transcript-first packet's per-student source hashes match the T1
       run outputs that were actually used as transcript sources.

    It raises :class:`ModalityLineageError` for any missing, duplicate, stale,
    or mismatched field.  A successful result is deterministic and safe to save
    as a readiness record.
    """

    expected_run_id = _require_run_id(transcription_run_id)
    direct_root = _require_packet_directory(
        direct_multimodal_packet, "direct multimodal packet"
    )
    transcription_root = _require_packet_directory(
        transcription_packet, "transcription packet"
    )
    text_root = _require_packet_directory(
        transcript_first_packet, "transcript-first packet"
    )
    run_root = _require_directory(transcription_run_output, "transcription run output")

    direct_manifest = _read_manifest(direct_root, "direct multimodal packet")
    transcription_manifest = _read_manifest(transcription_root, "transcription packet")
    text_manifest = _read_manifest(text_root, "transcript-first packet")

    direct = _validate_packet_manifest(
        direct_manifest,
        packet_root=direct_root,
        label="direct multimodal packet",
        expected_task="grade",
        require_rubric=True,
        expected_input_kind="image",
    )
    transcription = _validate_packet_manifest(
        transcription_manifest,
        packet_root=transcription_root,
        label="transcription packet",
        expected_task="transcribe",
        require_rubric=False,
        expected_input_kind="image",
    )
    text = _validate_packet_manifest(
        text_manifest,
        packet_root=text_root,
        label="transcript-first packet",
        expected_task="grade",
        require_rubric=True,
        expected_input_kind="text",
    )

    _require_matching_route_contract(
        direct, transcription, "direct multimodal", "transcription"
    )
    _require_matching_route_contract(
        direct, text, "direct multimodal", "transcript-first"
    )
    if direct["rubric_hash"] != text["rubric_hash"]:
        raise ModalityLineageError(
            "direct multimodal and transcript-first packet rubric hashes differ"
        )
    if direct["input_hashes"] != transcription["input_hashes"]:
        raise ModalityLineageError(
            "direct multimodal and transcription packet image input hashes differ"
    )

    transcription_packet_hash = directory_digest(transcription_root)
    text_metadata = text["metadata"]
    _require_text_source_hashes(text_metadata, text["student_ids"])
    if text_metadata["source_run_id"] != expected_run_id:
        raise ModalityLineageError(
            "transcript-first packet source_run_id does not match the declared "
            "transcription run ID"
        )
    if text_metadata["source_transcription_packet_hash"] != transcription_packet_hash:
        raise ModalityLineageError(
            "transcript-first packet source_transcription_packet_hash does not "
            "match the transcription packet"
        )
    if text_metadata["text_source_hash"] != directory_digest(text_root / "inputs"):
        raise ModalityLineageError(
            "transcript-first packet text_source_hash does not match its text inputs"
        )

    run_metadata = _read_json_object(
        run_root / "run-metadata.json", "transcription run metadata"
    )
    validation = _read_json_object(
        run_root / "validation.json", "transcription run validation"
    )
    _validate_transcription_run(
        metadata=run_metadata,
        validation=validation,
        transcription=transcription,
        transcript_first_metadata=text_metadata,
        transcription_packet_hash=transcription_packet_hash,
    )
    _verify_transcript_source_hashes(
        text_source_hashes=text_metadata["text_source_input_hashes"],
        student_ids=text["student_ids"],
        transcript_outputs=run_root / "outputs",
    )

    return {
        "schema_version": LINEAGE_SCHEMA_VERSION,
        "record_type": LINEAGE_RECORD_TYPE,
        "status": "ready",
        "course_id": direct["course_id"],
        "assessment_id": direct["assessment_id"],
        "scope_id": direct["scope_id"],
        "input_snapshot_manifest_sha256": direct["input_snapshot_manifest_sha256"],
        "split": direct["split"],
        "student_count": len(direct["student_ids"]),
        "direct_condition": direct["condition"],
        "transcript_first_condition": text["condition"],
        "direct_packet_id": direct["packet_id"],
        "direct_packet_hash": directory_digest(direct_root),
        "transcription_packet_id": transcription["packet_id"],
        "transcription_packet_hash": transcription_packet_hash,
        "transcription_run_id": expected_run_id,
        "transcription_engine": run_metadata["engine"],
        "transcription_model": run_metadata["model"],
        "transcript_first_packet_id": text["packet_id"],
        "transcript_first_packet_hash": directory_digest(text_root),
        "checks": [
            {"id": "route_contract_matched", "status": "passed"},
            {"id": "image_inputs_matched", "status": "passed"},
            {"id": "transcription_packet_bound", "status": "passed"},
            {"id": "transcription_run_bound", "status": "passed"},
            {"id": "transcript_output_hashes_bound", "status": "passed"},
        ],
    }


def write_lineage_report(path: Path, report: Mapping[str, Any]) -> str:
    """Write a deterministic report, refusing to overwrite a divergent record."""

    target = Path(path)
    encoded = json.dumps(dict(report), indent=2, sort_keys=True) + "\n"
    if target.exists():
        if not target.is_file():
            raise ModalityLineageError(f"lineage report path is not a file: {target}")
        if target.read_text(encoding="utf-8") != encoded:
            raise ModalityLineageError(
                f"refusing to overwrite divergent lineage report: {target}"
            )
        return "reused"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(encoded, encoding="utf-8", newline="\n")
    return "written"


def _require_packet_directory(path: Path, label: str) -> Path:
    root = _require_directory(path, label)
    if not (root / "manifest.json").is_file():
        raise ModalityLineageError(f"{label} is missing manifest.json: {root}")
    if not (root / "inputs").is_dir():
        raise ModalityLineageError(f"{label} is missing inputs/: {root}")
    return root


def _require_directory(path: Path, label: str) -> Path:
    root = Path(path).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ModalityLineageError(f"{label} is not a regular directory: {path}")
    return root


def _read_manifest(packet_root: Path, label: str) -> dict[str, Any]:
    return _read_json_object(packet_root / "manifest.json", f"{label} manifest")


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except FileNotFoundError as error:
        raise ModalityLineageError(f"missing {label}: {path}") from error
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise ModalityLineageError(f"{label} is not readable unique-key JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ModalityLineageError(f"{label} must be a JSON object: {path}")
    return payload


def _unique_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _validate_packet_manifest(
    manifest: Mapping[str, Any],
    *,
    packet_root: Path,
    label: str,
    expected_task: str,
    require_rubric: bool,
    expected_input_kind: str,
) -> dict[str, Any]:
    if manifest.get("schema_version") != 1:
        raise ModalityLineageError(f"{label} manifest has unsupported schema_version")
    if manifest.get("task") != expected_task:
        raise ModalityLineageError(f"{label} task must be {expected_task}")

    metadata = _required_mapping(manifest.get("metadata"), f"{label} metadata")
    declared_input_mode = metadata.get("input_mode")
    expected_input_mode = "multimodal" if expected_input_kind == "image" else "text-only"
    if declared_input_mode is not None and declared_input_mode != "":
        if _required_text(
            declared_input_mode, f"{label} metadata.input_mode"
        ) != expected_input_mode:
            raise ModalityLineageError(
                f"{label} metadata.input_mode must be {expected_input_mode}"
            )

    student_ids = _student_ids(manifest.get("student_ids"), label)
    input_hashes = _verified_packet_input_hashes(
        packet_root=packet_root,
        student_ids=student_ids,
        declared=manifest.get("input_hashes"),
        label=label,
        expected_input_kind=expected_input_kind,
    )
    course_hash = _required_sha256(
        manifest.get("course_hash"), f"{label} course_hash"
    )
    prompt_hash = _required_sha256(
        manifest.get("prompt_hash"), f"{label} prompt_hash"
    )
    _verify_declared_file_hash(
        packet_root / "course.json", course_hash, f"{label} course.json"
    )
    _verify_declared_file_hash(
        packet_root / "prompt.txt", prompt_hash, f"{label} prompt.txt"
    )
    rubric_hash = (
        _required_sha256(manifest.get("rubric_hash"), f"{label} rubric_hash")
        if require_rubric
        else manifest.get("rubric_hash")
    )
    if require_rubric:
        assert isinstance(rubric_hash, str)
        _verify_declared_file_hash(
            packet_root / "rubric.json", rubric_hash, f"{label} rubric.json"
        )
    elif rubric_hash not in {None, ""}:
        _required_sha256(rubric_hash, f"{label} rubric_hash")

    result = {
        "packet_id": _required_text(manifest.get("packet_id"), f"{label} packet_id"),
        "course_id": _required_text(manifest.get("course_id"), f"{label} course_id"),
        "assessment_id": _required_text(
            manifest.get("assessment_id"), f"{label} assessment_id"
        ),
        "condition": _required_text(manifest.get("condition"), f"{label} condition"),
        "course_hash": course_hash,
        "prompt_hash": prompt_hash,
        "rubric_hash": rubric_hash,
        "student_ids": student_ids,
        "input_hashes": input_hashes,
        "metadata": metadata,
        "scope_id": _required_text(
            metadata.get("scope_id"), f"{label} metadata.scope_id"
        ),
        "input_snapshot_manifest_sha256": _input_snapshot_manifest_sha256(
            metadata, label
        ),
        "split": _normalize_split(
            _required_text(metadata.get("split"), f"{label} metadata.split")
        ),
    }
    return result


def _required_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ModalityLineageError(f"{label} must be a JSON object")
    return dict(value)


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModalityLineageError(f"{label} must be non-empty text")
    return value.strip()


def _required_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ModalityLineageError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _verify_declared_file_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ModalityLineageError(f"{label} must be a regular file")
    if _sha256_file(path) != expected:
        raise ModalityLineageError(f"{label} does not match its manifest hash")


def _input_snapshot_manifest_sha256(metadata: Mapping[str, Any], label: str) -> str:
    """Return the source snapshot digest while accepting the legacy alias.

    The W4 packet builder records the hash as
    ``input_snapshot_manifest_sha256``.  ``data_snapshot_hash`` is an older
    packet metadata convention surfaced by the headless runner, so accepting it
    preserves compatibility for previous local packet templates.  If both are
    present they must name the same immutable snapshot.
    """

    current = metadata.get("input_snapshot_manifest_sha256")
    legacy = metadata.get("data_snapshot_hash")
    current_missing = current is None or current == ""
    legacy_missing = legacy is None or legacy == ""
    if current_missing and legacy_missing:
        raise ModalityLineageError(
            f"{label} metadata requires input_snapshot_manifest_sha256"
        )
    if not current_missing:
        current = _required_sha256(
            current, f"{label} metadata.input_snapshot_manifest_sha256"
        )
    if not legacy_missing:
        legacy = _required_sha256(legacy, f"{label} metadata.data_snapshot_hash")
    if not current_missing and not legacy_missing and current != legacy:
        raise ModalityLineageError(
            f"{label} metadata snapshot-hash aliases disagree"
        )
    return str(current if not current_missing else legacy)


def _student_ids(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ModalityLineageError(f"{label} student_ids must be a non-empty list")
    normalized: list[str] = []
    for index, student_id in enumerate(value):
        if not isinstance(student_id, str) or not student_id.strip():
            raise ModalityLineageError(
                f"{label} student_ids[{index}] must be non-empty text"
            )
        normalized.append(student_id.strip())
    if len(normalized) != len(set(normalized)):
        raise ModalityLineageError(f"{label} student_ids contains duplicates")
    return tuple(normalized)


def _verified_packet_input_hashes(
    *,
    packet_root: Path,
    student_ids: Sequence[str],
    declared: Any,
    label: str,
    expected_input_kind: str,
) -> dict[str, str]:
    if not isinstance(declared, dict):
        raise ModalityLineageError(f"{label} input_hashes must be a JSON object")
    expected_ids = set(student_ids)
    if set(declared) != expected_ids:
        raise ModalityLineageError(
            f"{label} input_hashes keys must exactly match student_ids"
        )

    inputs_root = packet_root / "inputs"
    child_names = {path.name for path in inputs_root.iterdir()}
    if child_names != expected_ids:
        raise ModalityLineageError(
            f"{label} inputs/ directory names must exactly match student_ids"
        )

    verified: dict[str, str] = {}
    suffixes = _IMAGE_SUFFIXES if expected_input_kind == "image" else _TEXT_SUFFIXES
    for student_id in student_ids:
        value = _required_sha256(
            declared.get(student_id), f"{label} input_hashes[{student_id}]"
        )
        input_dir = inputs_root / student_id
        if not input_dir.is_dir() or input_dir.is_symlink():
            raise ModalityLineageError(
                f"{label} input directory is missing for {student_id}"
            )
        files = sorted(path for path in input_dir.rglob("*") if path.is_file())
        if not files:
            raise ModalityLineageError(f"{label} has no input files for {student_id}")
        invalid = [path.name for path in files if path.suffix.lower() not in suffixes]
        if invalid:
            raise ModalityLineageError(
                f"{label} has unexpected {expected_input_kind} input file type for "
                f"{student_id}: {invalid[0]}"
            )
        actual = directory_digest(input_dir)
        if value != actual:
            raise ModalityLineageError(
                f"{label} input_hashes does not match the actual inputs for "
                f"{student_id}"
            )
        verified[student_id] = value
    return verified


def _require_matching_route_contract(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    left_label: str,
    right_label: str,
) -> None:
    for field in (
        "student_ids",
        "course_id",
        "assessment_id",
        "course_hash",
        "scope_id",
        "input_snapshot_manifest_sha256",
        "split",
    ):
        if left[field] != right[field]:
            raise ModalityLineageError(
                f"{left_label} and {right_label} packet {field} values differ"
            )


def _normalize_split(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"heldout", "held_out", "test"}:
        return "heldout"
    if normalized == "development":
        return normalized
    raise ModalityLineageError(
        "packet metadata.split must be development, heldout, held_out, or test"
    )


def _require_run_id(value: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not _RUN_ID_PATTERN.fullmatch(normalized):
        raise ModalityLineageError(
            "transcription_run_id must be a non-empty safe run identifier"
        )
    return normalized


def _require_text_source_hashes(
    metadata: Mapping[str, Any], student_ids: Sequence[str]
) -> None:
    _required_text(
        metadata.get("source_run_id"),
        "transcript-first packet metadata.source_run_id",
    )
    _required_sha256(
        metadata.get("source_transcription_packet_hash"),
        "transcript-first packet metadata.source_transcription_packet_hash",
    )
    _required_sha256(
        metadata.get("text_source_hash"),
        "transcript-first packet metadata.text_source_hash",
    )
    _required_text(
        metadata.get("text_source_kind"),
        "transcript-first packet metadata.text_source_kind",
    )
    _required_text(
        metadata.get("text_source_path"),
        "transcript-first packet metadata.text_source_path",
    )
    source_hashes = metadata.get("text_source_input_hashes")
    if not isinstance(source_hashes, dict):
        raise ModalityLineageError(
            "transcript-first packet metadata.text_source_input_hashes must be a JSON object"
        )
    if set(source_hashes) != set(student_ids):
        raise ModalityLineageError(
            "transcript-first packet text_source_input_hashes keys must exactly match "
            "student_ids"
        )
    for student_id in student_ids:
        _required_sha256(
            source_hashes.get(student_id),
            f"transcript-first packet text_source_input_hashes[{student_id}]",
        )


def _validate_transcription_run(
    *,
    metadata: Mapping[str, Any],
    validation: Mapping[str, Any],
    transcription: Mapping[str, Any],
    transcript_first_metadata: Mapping[str, Any],
    transcription_packet_hash: str,
) -> None:
    if (
        metadata.get("schema_version") != 1
        or metadata.get("record_type") != "model_packet_run"
    ):
        raise ModalityLineageError("transcription run metadata has an unexpected schema")
    if metadata.get("task") != "transcribe":
        raise ModalityLineageError("transcription run metadata task must be transcribe")
    if metadata.get("input_mode") != "multimodal":
        raise ModalityLineageError(
            "transcription run metadata input_mode must be multimodal"
        )
    for field in ("course_id", "assessment_id"):
        if metadata.get(field) != transcription[field]:
            raise ModalityLineageError(
                f"transcription run metadata {field} does not match its T1 packet"
            )
    metadata_split = _normalize_split(
        _required_text(metadata.get("split"), "transcription run metadata split")
    )
    if metadata_split != transcription["split"]:
        raise ModalityLineageError(
            "transcription run metadata split does not match its T1 packet"
        )
    if tuple(metadata.get("student_ids", ())) != tuple(transcription["student_ids"]):
        raise ModalityLineageError(
            "transcription run metadata student_ids do not match its T1 packet"
        )
    if metadata.get("packet_hash") != transcription_packet_hash:
        raise ModalityLineageError(
            "transcription run metadata packet_hash does not match the T1 packet"
        )
    if metadata.get("validation_status") != "passed":
        raise ModalityLineageError(
            "transcription run metadata validation_status must be passed"
        )
    if validation.get("status") != "passed":
        raise ModalityLineageError("transcription run validation status must be passed")
    expected_count = len(transcription["student_ids"])
    if validation.get("students_expected") != expected_count or validation.get(
        "students_passed"
    ) != expected_count:
        raise ModalityLineageError(
            "transcription run validation does not cover every expected anonymous student"
        )
    engine = _required_text(metadata.get("engine"), "transcription run metadata engine")
    model = _required_text(metadata.get("model"), "transcription run metadata model")
    if _required_text(
        transcript_first_metadata.get("transcription_engine"),
        "transcript-first packet metadata.transcription_engine",
    ) != engine:
        raise ModalityLineageError(
            "transcript-first packet transcription_engine does not match the T1 run"
        )
    if _required_text(
        transcript_first_metadata.get("transcription_model"),
        "transcript-first packet metadata.transcription_model",
    ) != model:
        raise ModalityLineageError(
            "transcript-first packet transcription_model does not match the T1 run"
        )


def _verify_transcript_source_hashes(
    *,
    text_source_hashes: Mapping[str, Any],
    student_ids: Sequence[str],
    transcript_outputs: Path,
) -> None:
    if not transcript_outputs.is_dir() or transcript_outputs.is_symlink():
        raise ModalityLineageError(
            f"transcription run outputs directory is missing: {transcript_outputs}"
        )
    expected_files = {f"{student_id}.json" for student_id in student_ids}
    children = list(transcript_outputs.iterdir())
    if any(not path.is_file() or path.is_symlink() for path in children):
        raise ModalityLineageError(
            "transcription run outputs must contain regular transcript files only"
        )
    actual_files = {path.name for path in children}
    if actual_files != expected_files:
        raise ModalityLineageError(
            "transcription run outputs must contain exactly one JSON transcript per "
            "anonymous student"
        )
    for student_id in student_ids:
        source = transcript_outputs / f"{student_id}.json"
        actual = _sha256_file(source)
        if text_source_hashes.get(student_id) != actual:
            raise ModalityLineageError(
                f"transcript-first packet source hash does not match transcription "
                f"output for {student_id}"
            )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
