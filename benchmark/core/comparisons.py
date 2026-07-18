import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .packets import audit_prompt_packet, directory_digest


COMMON_CHECKS = (
    "same_course",
    "same_assessment",
    "same_students",
    "same_split",
    "same_task",
    "same_output_schema",
    "same_text_source",
    "same_data_snapshot",
    "packet_audits_pass",
    "b0_r1_prompt_and_skill_match",
    "b0_r1_rubric_differs",
    "r1_c3_rubric_matches",
    "r1_c3_prompt_and_skill_differ",
)
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
REQUIRED_PACKET_FILES = {
    "prompt_hash": "prompt.txt",
    "course_hash": "course.json",
    "rubric_hash": "rubric.json",
    "output_schema_hash": "output.schema.json",
}


def check_three_condition_ablation(
    b0: Path,
    r1: Path,
    c3: Path,
    *,
    provider: str,
    model: str,
    input_mode: str,
    repetition: int,
) -> dict[str, Any]:
    """Check that B0/R1/C3 differ only in the declared experimental factors."""
    if input_mode != "text-only":
        raise ValueError("input_mode must be text-only")
    if repetition < 1:
        raise ValueError("repetition must be at least 1")
    if not provider.strip():
        raise ValueError("provider must not be blank")
    if not model.strip():
        raise ValueError("model must not be blank")

    packets = {
        "B0": _load_packet(Path(b0)),
        "R1": _load_packet(Path(r1)),
        "C3": _load_packet(Path(c3)),
    }
    manifests = {label: packet["manifest"] for label, packet in packets.items()}
    checks: list[dict[str, str]] = []

    _check_same_field(checks, "same_course", manifests, "course_id")
    _check_same_field(checks, "same_assessment", manifests, "assessment_id")
    _check_same_field(checks, "same_students", manifests, "student_ids")
    _check_same_metadata(checks, "same_split", manifests, "split")
    _check_same_field(checks, "same_task", manifests, "task")
    _check_same_hash_field(
        checks,
        "same_output_schema",
        manifests,
        "output_schema_hash",
    )
    _check_same_metadata_hash(
        checks,
        "same_text_source",
        manifests,
        "text_source_hash",
    )
    _check_same_metadata_hash(
        checks,
        "same_data_snapshot",
        manifests,
        "data_snapshot_hash",
    )
    _check_packet_audits(checks, packets)
    _check_b0_r1_prompt_and_skill(checks, manifests)
    _check_b0_r1_rubric(checks, manifests)
    _check_r1_c3_rubric(checks, manifests)
    _check_r1_c3_prompt_and_skill(checks, manifests)

    failed_checks = [check["id"] for check in checks if check["status"] == "failed"]
    return {
        "schema_version": 1,
        "report_type": "three_condition_ablation_readiness",
        "readiness_level": "packet",
        "readiness_scope": (
            "Packet-level readiness verifies that the B0/R1/C3 comparison is "
            "controlled. It does not execute a model or establish score accuracy."
        ),
        "status": "not_ready" if failed_checks else "ready",
        "model_run_status": "not_started",
        "shared_run_settings": {
            "provider": provider,
            "model": model,
            "input_mode": input_mode,
            "repetition": repetition,
        },
        "packet_hashes": {
            label: packet["packet_hash"] for label, packet in packets.items()
        },
        "expected_differences": {
            "B0_R1": "rubric only; prompt and skill must match",
            "R1_C3": "prompt and skill only; rubric must match",
        },
        "checks": checks,
        "failed_checks": failed_checks,
    }


def write_three_condition_ablation_json(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_three_condition_ablation_markdown(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_three_condition_ablation_markdown(report),
        encoding="utf-8",
        newline="\n",
    )


def render_three_condition_ablation_markdown(report: dict[str, Any]) -> str:
    settings = report["shared_run_settings"]
    lines = [
        "# Three-Condition Ablation Readiness",
        "",
        f"Status: **{report['status']}**",
        "",
        "No model calls are recorded by this checklist.",
        "",
        "## Shared Run Settings",
        "",
        f"- Provider: `{settings['provider']}`",
        f"- Model: `{settings['model']}`",
        f"- Input mode: `{settings['input_mode']}`",
        f"- Repetition: `{settings['repetition']}`",
        "",
        "## Declared Differences",
        "",
        "- B0/R1: rubric only; prompt and skill must match.",
        "- R1/C3: prompt and skill only; rubric must match.",
        "",
        "## Packet Hashes",
        "",
    ]
    for label, packet_hash in report["packet_hashes"].items():
        lines.append(f"- {label}: `{packet_hash}`")
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in report["checks"]:
        lines.append(
            "| `{}` | {} | {} |".format(
                check["id"],
                check["status"],
                _escape_table(check["detail"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _load_packet(path: Path) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    if not path.is_dir():
        raise FileNotFoundError(f"packet directory missing: {path}")
    manifest, manifest_findings = _load_manifest(manifest_path)
    privacy_findings = audit_prompt_packet(path)
    integrity_findings = _audit_packet_integrity(path, manifest)
    return {
        "manifest": manifest,
        "packet_hash": directory_digest(path),
        "audit_findings": sorted(
            set(manifest_findings + privacy_findings + integrity_findings)
        ),
    }


def _check_same_field(
    checks: list[dict[str, str]],
    check_id: str,
    manifests: dict[str, dict[str, Any]],
    field: str,
) -> None:
    values = {label: manifest.get(field) for label, manifest in manifests.items()}
    _check(checks, check_id, _values_match(values), _value_detail(values))


def _check_same_hash_field(
    checks: list[dict[str, str]],
    check_id: str,
    manifests: dict[str, dict[str, Any]],
    field: str,
) -> None:
    values = {
        label: _required_hash(manifest, field)
        for label, manifest in manifests.items()
    }
    _check(checks, check_id, _values_match(values), _value_detail(values))


def _check_same_metadata(
    checks: list[dict[str, str]],
    check_id: str,
    manifests: dict[str, dict[str, Any]],
    key: str,
) -> None:
    values = {
        label: _metadata_value(manifest, key)
        for label, manifest in manifests.items()
    }
    _check(checks, check_id, _values_match(values), _value_detail(values))


def _check_same_metadata_hash(
    checks: list[dict[str, str]],
    check_id: str,
    manifests: dict[str, dict[str, Any]],
    key: str,
) -> None:
    values = {
        label: _metadata_hash(manifest, key)
        for label, manifest in manifests.items()
    }
    _check(checks, check_id, _values_match(values), _value_detail(values))


def _check_packet_audits(
    checks: list[dict[str, str]],
    packets: dict[str, dict[str, Any]],
) -> None:
    findings = {
        label: packet["audit_findings"] for label, packet in packets.items()
    }
    passed = all(not packet_findings for packet_findings in findings.values())
    detail = "; ".join(
        f"{label}={','.join(packet_findings) if packet_findings else 'passed'}"
        for label, packet_findings in findings.items()
    )
    _check(checks, "packet_audits_pass", passed, detail)


def _check_b0_r1_prompt_and_skill(
    checks: list[dict[str, str]], manifests: dict[str, dict[str, Any]]
) -> None:
    b0 = manifests["B0"]
    r1 = manifests["R1"]
    passed = (
        _required_hash(b0, "prompt_hash") == _required_hash(r1, "prompt_hash")
        and _skill_anchor(b0) == _skill_anchor(r1)
        and _skill_anchor(b0) is not None
    )
    detail = (
        f"prompt={_short(_required_hash(b0, 'prompt_hash'))}/"
        f"{_short(_required_hash(r1, 'prompt_hash'))}; "
        f"skill={_skill_anchor(b0)!r}/{_skill_anchor(r1)!r}"
    )
    _check(checks, "b0_r1_prompt_and_skill_match", passed, detail)


def _check_b0_r1_rubric(
    checks: list[dict[str, str]], manifests: dict[str, dict[str, Any]]
) -> None:
    b0_rubric = _required_hash(manifests["B0"], "rubric_hash")
    r1_rubric = _required_hash(manifests["R1"], "rubric_hash")
    _check(
        checks,
        "b0_r1_rubric_differs",
        b0_rubric is not None and r1_rubric is not None and b0_rubric != r1_rubric,
        f"B0={_short(b0_rubric)}; R1={_short(r1_rubric)}",
    )


def _check_r1_c3_rubric(
    checks: list[dict[str, str]], manifests: dict[str, dict[str, Any]]
) -> None:
    r1_rubric = _required_hash(manifests["R1"], "rubric_hash")
    c3_rubric = _required_hash(manifests["C3"], "rubric_hash")
    _check(
        checks,
        "r1_c3_rubric_matches",
        r1_rubric is not None and r1_rubric == c3_rubric,
        f"R1={_short(r1_rubric)}; C3={_short(c3_rubric)}",
    )


def _check_r1_c3_prompt_and_skill(
    checks: list[dict[str, str]], manifests: dict[str, dict[str, Any]]
) -> None:
    r1 = manifests["R1"]
    c3 = manifests["C3"]
    r1_skill = _skill_anchor(r1)
    c3_skill = _skill_anchor(c3)
    passed = (
        _required_hash(r1, "prompt_hash") is not None
        and _required_hash(r1, "prompt_hash") != _required_hash(c3, "prompt_hash")
        and r1_skill is not None
        and c3_skill is not None
        and r1_skill != c3_skill
    )
    detail = (
        f"prompt={_short(_required_hash(r1, 'prompt_hash'))}/"
        f"{_short(_required_hash(c3, 'prompt_hash'))}; "
        f"skill={r1_skill!r}/{c3_skill!r}"
    )
    _check(checks, "r1_c3_prompt_and_skill_differ", passed, detail)


def _metadata_value(manifest: dict[str, Any], key: str) -> Any:
    metadata = manifest.get("metadata")
    return metadata.get(key) if isinstance(metadata, dict) else None


def _required_hash(manifest: dict[str, Any], key: str) -> str | None:
    value = manifest.get(key)
    return value.lower() if _is_sha256(value) else None


def _metadata_hash(manifest: dict[str, Any], key: str) -> str | None:
    value = _metadata_value(manifest, key)
    return value.lower() if _is_sha256(value) else None


def _skill_anchor(manifest: dict[str, Any]) -> tuple[str, str] | None:
    version = _metadata_value(manifest, "skill_version_id")
    skill_hash = _metadata_hash(manifest, "skill_hash")
    if not isinstance(version, str) or not version:
        return None
    if not isinstance(skill_hash, str) or not skill_hash:
        return None
    return version, skill_hash


def _load_manifest(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.is_file():
        return {}, ["missing required file: manifest.json"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, ["manifest.json must contain a UTF-8 JSON object"]
    if not isinstance(manifest, dict):
        return {}, ["manifest.json must contain a UTF-8 JSON object"]
    return manifest, []


def _audit_packet_integrity(path: Path, manifest: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    schema_version = manifest.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version < 1
    ):
        findings.append("schema_version must be a positive integer")

    for field in ("packet_id", "course_id", "assessment_id", "condition", "task"):
        if not _is_nonempty_string(manifest.get(field)):
            findings.append(f"{field} must be a non-empty string")

    students = _validated_student_ids(manifest.get("student_ids"), findings)
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        findings.append("metadata must be an object")
        metadata = {}
    for key in ("split", "input_mode", "skill_version_id"):
        if not _is_nonempty_string(metadata.get(key)):
            findings.append(f"metadata.{key} must be a non-empty string")
    for key in ("data_snapshot_hash", "skill_hash", "text_source_hash"):
        if not _is_sha256(metadata.get(key)):
            findings.append(f"metadata.{key} must be a 64-hex SHA-256 value")

    for hash_field, relative_path in REQUIRED_PACKET_FILES.items():
        declared_hash = manifest.get(hash_field)
        if not _is_sha256(declared_hash):
            findings.append(f"{hash_field} must be a 64-hex SHA-256 value")
        artifact = path / relative_path
        if not artifact.is_file():
            findings.append(f"missing required file: {relative_path}")
        elif (
            _is_sha256(declared_hash)
            and declared_hash.lower() != _file_hash(artifact)
        ):
            findings.append(f"{hash_field} does not match {relative_path}")

    inputs = path / "inputs"
    if not inputs.is_dir():
        findings.append("missing required directory: inputs")
    elif students is not None:
        _audit_student_input_directories(inputs, students, findings)

    input_hashes = manifest.get("input_hashes")
    if not isinstance(input_hashes, dict):
        findings.append("input_hashes must be an object")
    elif students is not None:
        _audit_input_hashes(inputs, students, input_hashes, findings)

    text_source_hash = metadata.get("text_source_hash")
    if (
        inputs.is_dir()
        and _is_sha256(text_source_hash)
        and text_source_hash.lower() != directory_digest(inputs)
    ):
        findings.append("metadata.text_source_hash does not match inputs directory")
    return sorted(set(findings))


def _validated_student_ids(value: Any, findings: list[str]) -> list[str] | None:
    valid = (
        isinstance(value, list)
        and bool(value)
        and all(_is_nonempty_string(student_id) for student_id in value)
        and len(value) == len(set(value))
    )
    if not valid:
        findings.append(
            "student_ids must be a non-empty list of unique non-empty strings"
        )
        return None
    return value


def _audit_student_input_directories(
    inputs: Path,
    students: list[str],
    findings: list[str],
) -> None:
    declared = set(students)
    actual = {entry.name for entry in inputs.iterdir() if entry.is_dir()}
    for student_id in sorted(declared - actual):
        findings.append(f"missing student input directory: {student_id}")
    for student_id in sorted(actual - declared):
        findings.append(f"unexpected student input directory: {student_id}")
    for student_id in sorted(declared & actual):
        if not any(entry.is_file() for entry in (inputs / student_id).rglob("*")):
            findings.append(
                f"student input directory contains no files: {student_id}"
            )


def _audit_input_hashes(
    inputs: Path,
    students: list[str],
    input_hashes: dict[Any, Any],
    findings: list[str],
) -> None:
    declared = set(students)
    hash_keys = {key for key in input_hashes if isinstance(key, str)}
    if len(hash_keys) != len(input_hashes):
        findings.append("input_hashes keys must be non-empty strings")
    for student_id in sorted(declared - hash_keys):
        findings.append(f"missing input_hash for student: {student_id}")
    for student_id in sorted(hash_keys - declared):
        findings.append(f"unexpected input_hash for student: {student_id}")
    for student_id in sorted(declared & hash_keys):
        declared_hash = input_hashes[student_id]
        if not _is_sha256(declared_hash):
            findings.append(
                f"input_hashes.{student_id} must be a 64-hex SHA-256 value"
            )
            continue
        student_input = inputs / student_id
        if (
            student_input.is_dir()
            and declared_hash.lower() != directory_digest(student_input)
        ):
            findings.append(f"input_hash does not match input directory: {student_id}")


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _values_match(values: dict[str, Any]) -> bool:
    value_list = list(values.values())
    return all(value is not None for value in value_list) and len(
        {json.dumps(value, sort_keys=True) for value in value_list}
    ) == 1


def _value_detail(values: dict[str, Any]) -> str:
    return "; ".join(
        f"{label}={json.dumps(value, sort_keys=True)}"
        for label, value in values.items()
    )


def _check(checks: list[dict[str, str]], check_id: str, passed: bool, detail: str) -> None:
    checks.append(
        {
            "id": check_id,
            "status": "passed" if passed else "failed",
            "detail": detail,
        }
    )


def _short(value: str | None) -> str:
    return value[:12] if value is not None else "missing"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
