"""Versioned release-policy checks for reproducible provider model selection."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


MODEL_RELEASE_CHANNELS = {"stable", "provisional"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def load_model_release_policy(path: Path) -> dict[str, Any]:
    """Load and validate a public model-release policy file."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("model release policy must be readable JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("model release policy must be a JSON object")
    findings = validate_model_release_policy(payload)
    if findings:
        raise ValueError("invalid model release policy: " + "; ".join(findings))
    return payload


def validate_model_release_policy(payload: dict[str, Any]) -> list[str]:
    """Return stable findings for the public model-release policy schema."""

    findings: list[str] = []
    required = {
        "schema_version",
        "record_type",
        "policy_id",
        "provider",
        "models",
    }
    missing = sorted(required - set(payload))
    if missing:
        findings.append("model policy missing field(s): " + ", ".join(missing))
    if payload.get("schema_version") != 1:
        findings.append("model policy schema_version must be 1")
    if payload.get("record_type") != "model_release_policy":
        findings.append("model policy record_type must be model_release_policy")
    for field in ("policy_id", "provider"):
        value = payload.get(field)
        if not isinstance(value, str) or SAFE_ID.fullmatch(value) is None:
            findings.append(f"model policy {field} must be a safe identifier")

    models = payload.get("models")
    if not isinstance(models, dict) or not models:
        return sorted(set(findings + ["model policy models must be a non-empty object"]))

    defaults: list[str] = []
    for model_id, definition in models.items():
        label = f"model policy model {model_id}"
        if not isinstance(model_id, str) or SAFE_ID.fullmatch(model_id) is None:
            findings.append("model policy model IDs must be safe identifiers")
            continue
        if not isinstance(definition, dict):
            findings.append(f"{label} must be an object")
            continue
        channel = definition.get("release_channel")
        if channel not in MODEL_RELEASE_CHANNELS:
            findings.append(f"{label} release_channel must be stable or provisional")
        default = definition.get("default_for_new_runs")
        if not isinstance(default, bool):
            findings.append(f"{label} default_for_new_runs must be boolean")
        elif default:
            defaults.append(model_id)
            if channel != "stable":
                findings.append(f"{label} default model must use the stable channel")
        if channel == "provisional":
            trigger = definition.get("retest_required_on")
            if not isinstance(trigger, str) or not trigger.strip():
                findings.append(f"{label} provisional model requires retest_required_on")

    if len(defaults) != 1:
        findings.append("model policy must declare exactly one default_for_new_runs model")
    return sorted(set(findings))


def bind_model_release_policy(
    *,
    policy_path: Path,
    provider: str,
    model: str,
    allow_provisional: bool = False,
) -> dict[str, str]:
    """Validate a requested provider/model pair and return auditable bindings."""

    policy = load_model_release_policy(policy_path)
    if provider != policy["provider"]:
        raise ValueError(
            "model release policy provider does not match requested provider"
        )
    definition = policy["models"].get(model)
    if not isinstance(definition, dict):
        raise ValueError("requested model is not approved by the model release policy")
    channel = definition["release_channel"]
    if channel == "provisional" and not allow_provisional:
        raise ValueError(
            "provisional model requires explicit --allow-provisional-model acknowledgement"
        )
    return {
        "model_release_policy_id": policy["policy_id"],
        "model_release_policy_sha256": hashlib.sha256(
            policy_path.read_bytes()
        ).hexdigest(),
        "model_release_channel": channel,
    }
