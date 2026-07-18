import hashlib
import json
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
    _check_same_field(checks, "same_output_schema", manifests, "output_schema_hash")
    _check_same_metadata(checks, "same_text_source", manifests, "text_source_hash")
    _check_same_metadata(
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
    if not manifest_path.is_file():
        raise FileNotFoundError(f"packet manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"packet manifest must be an object: {manifest_path}")
    return {
        "manifest": manifest,
        "packet_hash": directory_digest(path),
        "audit_findings": audit_prompt_packet(path),
    }


def _check_same_field(
    checks: list[dict[str, str]],
    check_id: str,
    manifests: dict[str, dict[str, Any]],
    field: str,
) -> None:
    values = {label: manifest.get(field) for label, manifest in manifests.items()}
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
    return value if isinstance(value, str) and value else None


def _skill_anchor(manifest: dict[str, Any]) -> tuple[str, str] | None:
    version = _metadata_value(manifest, "skill_version_id")
    skill_hash = _metadata_value(manifest, "skill_hash")
    if not isinstance(version, str) or not version:
        return None
    if not isinstance(skill_hash, str) or not skill_hash:
        return None
    return version, skill_hash


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
