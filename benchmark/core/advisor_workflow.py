"""Automate an advisor's local grading run and privacy-safe PR handoff."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = 1
SUPPORTED_ENGINES = {"kimi", "claude", "codex"}
SUPPORTED_INPUT_MODES = {"text-only", "multimodal"}
ALLOWED_IMAGE_SUFFIXES = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
SAFE_RECORD_SUFFIXES = {".json", ".md"}
SECRET_KEY_PARTS = ("api_key", "apikey", "password", "secret", "token")
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
)
ANONYMOUS_STUDENT_ID = re.compile(r"\bS\d{3,}\b")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")


class WorkflowError(ValueError):
    """An actionable workflow error safe to show to the user."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise WorkflowError(f"missing JSON file: {path}") from error
    except json.JSONDecodeError as error:
        raise WorkflowError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(payload, dict):
        raise WorkflowError(f"JSON object required: {path}")
    return payload


def _run(
    argv: Sequence[str],
    *,
    cwd: Path,
    capture: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        capture_output=capture,
        text=True,
        encoding="utf-8",
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise WorkflowError(
            f"command failed ({completed.returncode}): {' '.join(argv)}"
            + (f"\n{detail}" if detail else "")
        )
    return completed


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() and (candidate / "benchmark").is_dir():
            return candidate
    raise WorkflowError("run this command inside the exam-automark repository")


def _logical_absolute(path: Path) -> Path:
    """Return an absolute path without dereferencing a Data/ junction."""
    return Path(os.path.abspath(path))


def _repo_path(repo: Path, raw: str, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise WorkflowError(f"{label} must be a non-empty path")
    path = Path(raw)
    resolved = _logical_absolute(repo / path) if not path.is_absolute() else _logical_absolute(path)
    try:
        resolved.relative_to(_logical_absolute(repo))
    except ValueError as error:
        raise WorkflowError(f"{label} must stay inside the repository: {raw}") from error
    return resolved


def _relative(repo: Path, path: Path) -> str:
    return _logical_absolute(path).relative_to(_logical_absolute(repo)).as_posix()


def _assert_below(repo: Path, path: Path, prefix: str, *, label: str) -> None:
    relative = _relative(repo, path)
    normalized = prefix.rstrip("/") + "/"
    if relative != prefix.rstrip("/") and not relative.startswith(normalized):
        raise WorkflowError(f"{label} must be below {prefix}: {relative}")


def _reject_secret_keys(value: Any, *, location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in SECRET_KEY_PARTS):
                raise WorkflowError(
                    f"secret-like config key is forbidden at {location}.{key}; "
                    "keep credentials in CLI login or environment variables"
                )
            _reject_secret_keys(child, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_keys(child, location=f"{location}[{index}]")


def load_config(config_path: Path, repo: Path | None = None) -> tuple[Path, dict[str, Any]]:
    root = repo or find_repo_root(config_path)
    config = _read_json(config_path)
    _reject_secret_keys(config)
    validate_config(config, root)
    return root, config


def validate_config(config: dict[str, Any], repo: Path) -> None:
    if config.get("schema_version") != SCHEMA_VERSION:
        raise WorkflowError(f"schema_version must be {SCHEMA_VERSION}")

    experiment_id = config.get("experiment_id")
    if not isinstance(experiment_id, str) or not ID_PATTERN.fullmatch(experiment_id):
        raise WorkflowError("experiment_id must be unique lowercase kebab-case")

    split = config.get("split")
    if split not in {"development", "heldout", "test"}:
        raise WorkflowError("split must be development, heldout, or test")

    benchmark_root = _repo_path(
        repo, config.get("benchmark_root", ""), label="benchmark_root"
    )
    _assert_below(repo, benchmark_root, "Data", label="benchmark_root")
    state_path = _repo_path(repo, config.get("state_path", ""), label="state_path")
    state_relative = _relative(repo, state_path)
    if not (state_relative.startswith("Data/") or state_relative.startswith("local/")):
        raise WorkflowError("state_path must be below ignored Data/ or local/")
    record_dir = _repo_path(repo, config.get("record_dir", ""), label="record_dir")
    _assert_below(repo, record_dir, "experiments/records", label="record_dir")

    required_engines = config.get("required_engines")
    required_modes = config.get("required_input_modes")
    required_conditions = config.get("required_conditions", ["baseline", "candidate"])
    if not isinstance(required_engines, list) or not required_engines:
        raise WorkflowError("required_engines must be a non-empty list")
    if not set(required_engines) <= SUPPORTED_ENGINES:
        raise WorkflowError("required_engines contains an unsupported engine")
    if not isinstance(required_modes, list) or not required_modes:
        raise WorkflowError("required_input_modes must be a non-empty list")
    if not set(required_modes) <= SUPPORTED_INPUT_MODES:
        raise WorkflowError("required_input_modes contains an unsupported mode")
    if not isinstance(required_conditions, list) or not required_conditions:
        raise WorkflowError("required_conditions must be a non-empty list")

    runs = config.get("runs")
    if not isinstance(runs, list) or not runs:
        raise WorkflowError("runs must be a non-empty list")
    run_ids: set[str] = set()
    output_paths: set[Path] = set()
    coverage: set[tuple[str, str, str]] = set()
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise WorkflowError(f"runs[{index}] must be an object")
        run_id = run.get("id")
        if not isinstance(run_id, str) or not ID_PATTERN.fullmatch(run_id):
            raise WorkflowError(f"runs[{index}].id must be lowercase kebab-case")
        if run_id in run_ids:
            raise WorkflowError(f"duplicate run id: {run_id}")
        run_ids.add(run_id)

        engine = run.get("engine")
        mode = run.get("input_mode")
        condition = run.get("condition")
        model = run.get("model")
        if engine not in SUPPORTED_ENGINES:
            raise WorkflowError(f"unsupported engine in {run_id}: {engine}")
        if mode not in SUPPORTED_INPUT_MODES:
            raise WorkflowError(f"unsupported input_mode in {run_id}: {mode}")
        if not isinstance(condition, str) or not condition:
            raise WorkflowError(f"missing condition in {run_id}")
        if not isinstance(model, str) or not model.strip():
            raise WorkflowError(f"missing model in {run_id}")
        max_retries = run.get("max_retries", 2)
        if not isinstance(max_retries, int) or max_retries < 0:
            raise WorkflowError(f"max_retries must be non-negative in {run_id}")
        timeout_seconds = run.get("timeout_seconds", 600)
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            raise WorkflowError(f"timeout_seconds must be positive in {run_id}")

        packet = _repo_path(repo, run.get("packet", ""), label=f"{run_id}.packet")
        output = _repo_path(repo, run.get("output", ""), label=f"{run_id}.output")
        _assert_below(repo, packet, "Data", label=f"{run_id}.packet")
        _assert_below(repo, output, "Data", label=f"{run_id}.output")
        if output in output_paths:
            raise WorkflowError(f"duplicate output path: {_relative(repo, output)}")
        output_paths.add(output)
        coverage.add((engine, mode, condition))

    missing_coverage = sorted(
        (engine, mode, condition)
        for engine in required_engines
        for mode in required_modes
        for condition in required_conditions
        if (engine, mode, condition) not in coverage
    )
    if missing_coverage:
        raise WorkflowError(f"missing required run arms: {missing_coverage}")

    builds = config.get("packet_builds", [])
    if not isinstance(builds, list):
        raise WorkflowError("packet_builds must be a list")
    build_ids: set[str] = set()
    for index, build in enumerate(builds):
        if not isinstance(build, dict):
            raise WorkflowError(f"packet_builds[{index}] must be an object")
        build_id = build.get("id")
        if not isinstance(build_id, str) or not ID_PATTERN.fullmatch(build_id):
            raise WorkflowError(f"packet_builds[{index}].id must be kebab-case")
        if build_id in build_ids:
            raise WorkflowError(f"duplicate packet build id: {build_id}")
        build_ids.add(build_id)
        for field in ("source_text_packet", "input_root", "privacy_review", "output_root"):
            path = _repo_path(repo, build.get(field, ""), label=f"{build_id}.{field}")
            _assert_below(repo, path, "Data", label=f"{build_id}.{field}")

    comparisons = config.get("comparisons", [])
    if not isinstance(comparisons, list):
        raise WorkflowError("comparisons must be a list")
    comparison_ids: set[str] = set()
    for index, comparison in enumerate(comparisons):
        if not isinstance(comparison, dict):
            raise WorkflowError(f"comparisons[{index}] must be an object")
        comparison_id = comparison.get("id")
        if not isinstance(comparison_id, str) or not ID_PATTERN.fullmatch(comparison_id):
            raise WorkflowError(f"comparisons[{index}].id must be kebab-case")
        if comparison_id in comparison_ids:
            raise WorkflowError(f"duplicate comparison id: {comparison_id}")
        comparison_ids.add(comparison_id)
        for field in ("baseline_run", "candidate_run"):
            if comparison.get(field) not in run_ids:
                raise WorkflowError(
                    f"{comparison_id}.{field} references unknown run "
                    f"{comparison.get(field)}"
                )
        for field in ("output_json", "output_md"):
            path = _repo_path(
                repo, comparison.get(field, ""), label=f"{comparison_id}.{field}"
            )
            _assert_below(repo, path, "Data", label=f"{comparison_id}.{field}")

    submission = config.get("submission")
    if not isinstance(submission, dict):
        raise WorkflowError("submission must be an object")
    branch = submission.get("branch")
    if not isinstance(branch, str) or not branch.startswith("advisor-results/"):
        raise WorkflowError("submission.branch must start with advisor-results/")
    for field in ("base", "title", "commit_message"):
        if not isinstance(submission.get(field), str) or not submission[field].strip():
            raise WorkflowError(f"submission.{field} is required")


def build_preset_config(
    *,
    experiment_id: str,
    kimi_model: str,
    claude_model: str,
    split: str = "development",
) -> dict[str, Any]:
    if not ID_PATTERN.fullmatch(experiment_id):
        raise WorkflowError("generated experiment_id is invalid")
    if split not in {"development", "test"}:
        raise WorkflowError("generated preset split must be development or test")
    benchmark_root = "Data/physics/benchmark"
    packet_id = "G1-dev-r1" if split == "development" else "G1-test-r1"
    baseline_text = (
        f"{benchmark_root}/text_packets/"
        f"physics-week9-baseline-text-strict-schema/{packet_id}"
    )
    candidate_text = (
        f"{benchmark_root}/text_packets/"
        f"physics-week9-candidate-v2-text-strict-schema/{packet_id}"
    )
    image_root = f"{benchmark_root}/image_packets/{experiment_id}"
    baseline_image = f"{image_root}/baseline/{packet_id}"
    candidate_image = f"{image_root}/candidate/{packet_id}"
    run_root = f"{benchmark_root}/runs/{experiment_id}"
    metrics_root = f"{run_root}/metrics"

    packet_builds = [
        {
            "id": f"baseline-image-{split}",
            "source_text_packet": baseline_text,
            "input_root": f"{benchmark_root}/anonymized",
            "privacy_review": f"{benchmark_root}/manifest/privacy_review.csv",
            "output_root": f"{image_root}/baseline",
        },
        {
            "id": f"candidate-image-{split}",
            "source_text_packet": candidate_text,
            "input_root": f"{benchmark_root}/anonymized",
            "privacy_review": f"{benchmark_root}/manifest/privacy_review.csv",
            "output_root": f"{image_root}/candidate",
        },
    ]
    runs: list[dict[str, Any]] = []
    for engine, model in (("kimi", kimi_model), ("claude", claude_model)):
        for mode, baseline_packet, candidate_packet in (
            ("text-only", baseline_text, candidate_text),
            ("multimodal", baseline_image, candidate_image),
        ):
            short_mode = "text" if mode == "text-only" else "image"
            for condition, packet in (
                ("baseline", baseline_packet),
                ("candidate", candidate_packet),
            ):
                run_id = f"{engine}-{short_mode}-{condition}"
                runs.append(
                    {
                        "id": run_id,
                        "engine": engine,
                        "model": model,
                        "input_mode": mode,
                        "condition": condition,
                        "packet": packet,
                        "output": f"{run_root}/{run_id}",
                        "max_retries": 2,
                        "timeout_seconds": 600,
                    }
                )

    comparison_pairs = [
        (
            "kimi-text-baseline-vs-candidate",
            "kimi-text-baseline",
            "kimi-text-candidate",
        ),
        (
            "kimi-image-baseline-vs-candidate",
            "kimi-image-baseline",
            "kimi-image-candidate",
        ),
        (
            "claude-text-baseline-vs-candidate",
            "claude-text-baseline",
            "claude-text-candidate",
        ),
        (
            "claude-image-baseline-vs-candidate",
            "claude-image-baseline",
            "claude-image-candidate",
        ),
        (
            "kimi-candidate-text-vs-image",
            "kimi-text-candidate",
            "kimi-image-candidate",
        ),
        (
            "claude-candidate-text-vs-image",
            "claude-text-candidate",
            "claude-image-candidate",
        ),
        (
            "candidate-text-kimi-vs-claude",
            "kimi-text-candidate",
            "claude-text-candidate",
        ),
        (
            "candidate-image-kimi-vs-claude",
            "kimi-image-candidate",
            "claude-image-candidate",
        ),
    ]
    comparisons = [
        {
            "id": comparison_id,
            "baseline_run": baseline,
            "candidate_run": candidate,
            "output_json": f"{metrics_root}/{comparison_id}.json",
            "output_md": f"{metrics_root}/{comparison_id}.md",
        }
        for comparison_id, baseline, candidate in comparison_pairs
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "split": split,
        "benchmark_root": benchmark_root,
        "state_path": f"{run_root}/advisor-state.json",
        "record_dir": f"experiments/records/{experiment_id}",
        "required_engines": ["kimi", "claude"],
        "required_input_modes": ["text-only", "multimodal"],
        "required_conditions": ["baseline", "candidate"],
        "packet_builds": packet_builds,
        "runs": runs,
        "comparisons": comparisons,
        "submission": {
            "base": "main",
            "branch": f"advisor-results/{experiment_id}",
            "title": f"Advisor benchmark results: {experiment_id}",
            "commit_message": f"Add advisor benchmark results for {experiment_id}",
        },
    }


def init_config(
    repo: Path,
    output: Path,
    *,
    preset: str,
    experiment_id: str | None,
    kimi_model: str,
    claude_model: str,
    split: str = "development",
) -> dict[str, Any]:
    if preset != "physics-week9":
        raise WorkflowError(f"unsupported preset: {preset}")
    resolved = _repo_path(repo, str(output), label="output")
    relative = _relative(repo, resolved)
    if not (relative.startswith("local/") or relative.startswith("Data/")):
        raise WorkflowError("generated configs must stay under ignored local/ or Data/")
    if resolved.exists():
        raise WorkflowError(f"refusing to overwrite existing config: {relative}")
    generated_id = experiment_id or (
        f"physics-week9-advisor-{_slug_timestamp()}"
        if split == "development"
        else f"physics-week9-advisor-test-{_slug_timestamp()}"
    )
    config = build_preset_config(
        experiment_id=generated_id,
        kimi_model=kimi_model,
        claude_model=claude_model,
        split=split,
    )
    validate_config(config, repo)
    _write_json(resolved, config)
    return {
        "status": "created",
        "config": relative,
        "experiment_id": generated_id,
        "next_command": f"python scripts/advisor_experiment.py doctor --config {relative}",
    }


def _check(
    check_id: str,
    status: str,
    detail: str,
    *,
    scope: str,
    remediation: str | None = None,
) -> dict[str, Any]:
    result = {"id": check_id, "status": status, "scope": scope, "detail": detail}
    if remediation:
        result["remediation"] = remediation
    return result


def _engine_binary(run: dict[str, Any]) -> str:
    if run.get("engine_bin"):
        return str(run["engine_bin"])
    if run["engine"] == "codex" and os.name == "nt":
        return "codex.cmd"
    return str(run["engine"])


def _command_version(binary: str, repo: Path) -> str | None:
    resolved = shutil.which(binary)
    if not resolved:
        return None
    completed = _run([resolved, "--version"], cwd=repo, capture=True)
    output = (completed.stdout or completed.stderr).strip()
    return output or resolved


def _required_engine_models(
    config: dict[str, Any],
) -> list[tuple[str, str, str]]:
    required = {
        (str(run["engine"]), str(run["model"]), _engine_binary(run))
        for run in config["runs"]
    }
    return sorted(required)


def _probe_state_path(repo: Path, config: dict[str, Any]) -> Path:
    state = _repo_path(repo, config["state_path"], label="state_path")
    return state.with_name(state.stem + "-model-probes" + state.suffix)


def _probe_output_is_ok(engine: str, stdout: str) -> bool:
    try:
        if engine == "kimi":
            from .headless_runner import _extract_headless_cli_raw_text

            text = _extract_headless_cli_raw_text(
                "kimi",
                stdout,
                Path("<zero-data-probe>"),
            )
            return text.strip() == "OK"
        if engine == "claude":
            payload = json.loads(stdout)
            return bool(
                isinstance(payload, dict)
                and payload.get("is_error") is not True
                and str(payload.get("result", "")).strip() == "OK"
            )
        return bool(stdout.strip())
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _probe_receipt_matches(
    repo: Path,
    config: dict[str, Any],
    *,
    run_commit: str,
) -> bool:
    path = _probe_state_path(repo, config)
    if not path.is_file():
        return False
    try:
        receipt = _read_json(path)
    except WorkflowError:
        return False
    if receipt.get("status") != "passed" or receipt.get("run_commit") != run_commit:
        return False
    actual = {
        (
            str(item.get("engine")),
            str(item.get("model")),
            str(item.get("engine_binary")),
        )
        for item in receipt.get("probes", [])
        if isinstance(item, dict) and item.get("status") == "passed"
    }
    return set(_required_engine_models(config)) <= actual


def probe_models(
    repo: Path,
    config: dict[str, Any],
    *,
    approved: bool = False,
) -> dict[str, Any]:
    if not approved:
        raise WorkflowError(
            "zero-data model probes may consume subscription quota; rerun with "
            "--approve-model-probes after the user approves"
        )
    prompt = (
        "This is a zero-data authentication and capability probe. "
        "Return exactly the word OK. Do not inspect any files or use tools."
    )
    run_commit = _git(repo, "rev-parse", "--short", "HEAD", check=True).stdout.strip()
    probes: list[dict[str, Any]] = []
    for engine, model, binary in _required_engine_models(config):
        resolved = shutil.which(binary)
        if not resolved and Path(binary).is_file():
            resolved = str(Path(binary))
        if not resolved:
            probes.append(
                {
                    "engine": engine,
                    "model": model,
                    "engine_binary": binary,
                    "status": "failed",
                    "failure_category": "environment/authentication",
                    "reason": "engine-cli-unavailable",
                }
            )
            continue
        input_text: str | None = None
        if engine == "kimi":
            argv = [
                resolved,
                "--model",
                model,
                "--output-format",
                "stream-json",
                "--prompt",
                prompt,
            ]
        elif engine == "claude":
            argv = [
                resolved,
                "-p",
                "--output-format",
                "json",
                "--max-turns",
                "1",
                "--tools",
                "",
                "--strict-mcp-config",
                "--model",
                model,
            ]
            input_text = prompt
        else:
            argv = [
                resolved,
                "exec",
                "--json",
                "--sandbox",
                "read-only",
                "--model",
                model,
                "-",
            ]
            input_text = prompt
        try:
            completed = subprocess.run(
                argv,
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                input=input_text,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            probes.append(
                {
                    "engine": engine,
                    "model": model,
                    "engine_binary": binary,
                    "status": "failed",
                    "failure_category": "quota/timeout",
                    "reason": "probe-timeout",
                }
            )
            continue
        if completed.returncode == 0 and _probe_output_is_ok(
            engine,
            completed.stdout,
        ):
            probes.append(
                {
                    "engine": engine,
                    "model": model,
                    "engine_binary": binary,
                    "status": "passed",
                }
            )
        else:
            from .headless_runner import _cli_failure_category

            detail = "\n".join((completed.stderr, completed.stdout))
            category = (
                _cli_failure_category(detail)
                if completed.returncode != 0
                else "output-json/schema"
            )
            probes.append(
                {
                    "engine": engine,
                    "model": model,
                    "engine_binary": binary,
                    "status": "failed",
                    "failure_category": category,
                    "reason": (
                        "zero-data-probe-failed"
                        if completed.returncode != 0
                        else "zero-data-probe-output-invalid"
                    ),
                }
            )
    receipt = {
        "report_type": "advisor_zero_data_model_probes",
        "generated_at": _utc_now(),
        "experiment_id": config["experiment_id"],
        "run_commit": run_commit,
        "status": (
            "passed"
            if probes and all(item["status"] == "passed" for item in probes)
            else "failed"
        ),
        "student_data_sent": False,
        "probes": probes,
    }
    _write_json(_probe_state_path(repo, config), receipt)
    return receipt


def _git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return _run(
        ["git", "-c", f"safe.directory={repo.as_posix()}", *args],
        cwd=repo,
        capture=True,
        check=check,
    )


def _reproducibility_dirty_paths(repo: Path) -> list[str]:
    completed = _git(
        repo,
        "status",
        "--porcelain",
        "--",
        "benchmark",
        "scripts",
        ".agents/skills/grade-homework",
        ".claude/skills/grade-homework",
        "experiments/prompt_templates",
    )
    if completed.returncode != 0:
        return ["git-status-unavailable"]
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _packet_manifest(packet: Path) -> dict[str, Any]:
    manifest = _read_json(packet / "manifest.json")
    students = manifest.get("student_ids")
    if not isinstance(students, list) or not students:
        raise WorkflowError(f"packet has no student_ids: {packet}")
    return manifest


def _text_provenance(manifest: dict[str, Any]) -> tuple[str, list[str]]:
    metadata = manifest.get("metadata", {})
    if not isinstance(metadata, dict):
        return "unknown", ["packet metadata must be an object"]
    source_kind = str(metadata.get("text_source_kind", "")).strip()
    source_path = str(metadata.get("text_source_path", "")).strip()
    source_run_id = str(metadata.get("source_run_id", "")).strip()
    findings = []
    if not source_kind:
        findings.append("text_source_kind is missing")
    if not source_path:
        findings.append("text_source_path is missing")
    if not source_run_id:
        findings.append("source_run_id is missing")
    lowered = f"{source_kind} {source_path}".lower()
    if "reviewed" in lowered or "human" in lowered:
        provenance = "human-reviewed-transcript"
    elif "automatic" in lowered or "ocr" in lowered:
        provenance = "automatic-transcript"
    elif source_kind:
        provenance = source_kind
    else:
        provenance = "unknown"
    return provenance, findings


def _packet_mode_findings(packet: Path, mode: str) -> list[str]:
    findings: list[str] = []
    try:
        manifest = _packet_manifest(packet)
    except WorkflowError as error:
        return [str(error)]
    metadata = manifest.get("metadata", {})
    declared_mode = metadata.get("input_mode") if isinstance(metadata, dict) else None
    if declared_mode and declared_mode != mode:
        findings.append(
            f"packet input_mode {declared_mode!r} does not match requested {mode!r}"
        )
    for student_id in manifest["student_ids"]:
        input_dir = packet / "inputs" / str(student_id)
        if not input_dir.is_dir():
            findings.append(f"missing input directory for {student_id}")
            continue
        files = sorted(path for path in input_dir.rglob("*") if path.is_file())
        if not files:
            findings.append(f"no inputs for {student_id}")
            continue
        if mode == "multimodal":
            invalid = [
                path.name
                for path in files
                if path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES
            ]
            if invalid:
                findings.append(f"non-image multimodal inputs for {student_id}: {invalid}")
        else:
            invalid = [
                path.name
                for path in files
                if path.suffix.lower() not in {".json", ".txt"}
            ]
            if invalid:
                findings.append(f"non-text inputs for {student_id}: {invalid}")
    if mode == "text-only":
        _, provenance_findings = _text_provenance(manifest)
        findings.extend(provenance_findings)
    return findings


def _find_gh() -> str | None:
    resolved = shutil.which("gh") or shutil.which("gh.exe")
    if resolved:
        return resolved
    if os.name != "nt":
        return None
    candidates = []
    for variable in ("ProgramFiles", "LOCALAPPDATA"):
        root = os.environ.get(variable)
        if root:
            candidates.append(Path(root) / "GitHub CLI" / "gh.exe")
            candidates.append(Path(root) / "Programs" / "GitHub CLI" / "gh.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _pr_method(repo: Path) -> tuple[str | None, str]:
    gh = _find_gh()
    if gh:
        auth = _run([gh, "auth", "status"], cwd=repo, capture=True)
        if auth.returncode == 0:
            return "gh", "authenticated GitHub CLI"
    if os.environ.get("GITHUB_TOKEN"):
        return (
            "token",
            "environment-only GITHUB_TOKEN for the PR API; git push must already "
            "be authenticated",
        )
    return None, "no authenticated gh CLI or environment-only GITHUB_TOKEN"


def _private_roots_ignored(repo: Path) -> bool:
    return all(
        _git(repo, "check-ignore", "--no-index", "--quiet", "--", root).returncode == 0
        for root in ("Data/", ".private-data/")
    )


def doctor(repo: Path, config: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(
        _check(
            "python-version",
            "passed" if sys.version_info >= (3, 10) else "failed",
            sys.version.split()[0],
            scope="core",
            remediation="Install Python 3.10 or newer.",
        )
    )
    git_version = _command_version("git", repo)
    checks.append(
        _check(
            "git-cli",
            "passed" if git_version else "failed",
            git_version or "git executable not found",
            scope="core",
            remediation="Install Git, then reopen the terminal.",
        )
    )
    if git_version:
        private_roots_ignored = _private_roots_ignored(repo)
        checks.append(
            _check(
                "private-data-ignored",
                "passed" if private_roots_ignored else "failed",
                (
                    "Data/ and .private-data/ are ignored"
                    if private_roots_ignored
                    else "Data/ or .private-data/ is not ignored"
                ),
                scope="core",
                remediation="Restore the repository .gitignore before using private data.",
            )
        )
        tracked = _git(repo, "ls-files", "--", "Data", ".private-data")
        tracked_paths = [line for line in tracked.stdout.splitlines() if line.strip()]
        checks.append(
            _check(
                "no-private-data-tracked",
                "passed" if not tracked_paths else "failed",
                "no tracked private paths"
                if not tracked_paths
                else f"tracked private paths: {len(tracked_paths)}",
                scope="submit",
                remediation="Remove private files from Git history/index before continuing.",
            )
        )
        remote = _git(repo, "remote", "get-url", "origin")
        checks.append(
            _check(
                "origin-remote",
                "passed" if remote.returncode == 0 and remote.stdout.strip() else "failed",
                remote.stdout.strip() or "origin remote missing",
                scope="submit",
                remediation="Configure the intended GitHub repository as origin.",
            )
        )
        dirty_paths = _reproducibility_dirty_paths(repo)
        checks.append(
            _check(
                "reproducibility-code-clean",
                "passed" if not dirty_paths else "failed",
                "benchmark code and grading prompts match HEAD"
                if not dirty_paths
                else f"uncommitted reproducibility paths: {len(dirty_paths)}",
                scope="run",
                remediation=(
                    "Commit or intentionally stash benchmark, runner, and grading "
                    "prompt changes before the real model run."
                ),
            )
        )

    binaries: dict[str, str] = {}
    for run in config["runs"]:
        binaries.setdefault(run["engine"], _engine_binary(run))
    for engine, binary in sorted(binaries.items()):
        version = _command_version(binary, repo)
        checks.append(
            _check(
                f"{engine}-cli",
                "passed" if version else "failed",
                version or f"{binary} executable not found",
                scope="run",
                remediation=(
                    f"Ask permission to install and authenticate the official {engine} CLI."
                ),
            )
        )
    head = _git(repo, "rev-parse", "--short", "HEAD")
    probe_ready = bool(
        head.returncode == 0
        and head.stdout.strip()
        and _probe_receipt_matches(
            repo,
            config,
            run_commit=head.stdout.strip(),
        )
    )
    checks.append(
        _check(
            "zero-data-model-probes",
            "passed" if probe_ready else "action_required",
            "all configured engine/model probes passed for this commit"
            if probe_ready
            else "zero-data engine/model probes have not passed for this commit",
            scope="run",
            remediation=(
                "Ask once for permission because probes may consume quota, then run "
                "`advisor_experiment.py probe --approve-model-probes`."
            ),
        )
    )

    build_targets = _build_target_paths(repo, config)
    for run in config["runs"]:
        packet = _repo_path(repo, run["packet"], label=f"{run['id']}.packet")
        if not packet.is_dir():
            status = "action_required" if packet in build_targets else "failed"
            checks.append(
                _check(
                    f"packet-{run['id']}",
                    status,
                    f"missing packet: {_relative(repo, packet)}",
                    scope="prepare" if status == "action_required" else "run",
                    remediation=(
                        "Run the prepare command."
                        if status == "action_required"
                        else "Restore or generate the required private packet."
                    ),
                )
            )
            continue
        findings = _packet_mode_findings(packet, run["input_mode"])
        try:
            manifest = _packet_manifest(packet)
            packet_split = manifest.get("metadata", {}).get("split")
            if packet_split and _normalize_split(packet_split) != _normalize_split(
                config["split"]
            ):
                findings.append(
                    f"packet split {packet_split!r} does not match {config['split']!r}"
                )
            provenance = (
                _text_provenance(manifest)[0]
                if run["input_mode"] == "text-only"
                else "approved-anonymized-images"
            )
            if run["input_mode"] == "multimodal":
                findings.extend(
                    _multimodal_privacy_findings(repo, config, packet, manifest)
                )
        except WorkflowError as error:
            findings.append(str(error))
            provenance = "unknown"
        checks.append(
            _check(
                f"packet-{run['id']}",
                "passed" if not findings else "failed",
                f"packet inputs and split are ready; provenance={provenance}"
                if not findings
                else "; ".join(findings[:4]),
                scope="run",
                remediation="Repair or rebuild this immutable packet.",
            )
        )

    method, detail = _pr_method(repo)
    checks.append(
        _check(
            "github-pr-auth",
            "passed" if method else "failed",
            detail,
            scope="submit",
            remediation=(
                "Ask permission to install/login with gh (preferred), or combine "
                "separately authenticated Git transport with an environment-only "
                "GITHUB_TOKEN for PR creation."
            ),
        )
    )
    failed_core = [
        check["id"]
        for check in checks
        if check["status"] == "failed" and check["scope"] == "core"
    ]
    failed_prepare = [
        check["id"]
        for check in checks
        if check["status"] == "failed" and check["scope"] == "prepare"
    ]
    failed_run = [
        check["id"]
        for check in checks
        if check["status"] == "failed" and check["scope"] == "run"
    ]
    failed_submit = [
        check["id"]
        for check in checks
        if check["status"] == "failed" and check["scope"] == "submit"
    ]
    actions = [check["id"] for check in checks if check["status"] == "action_required"]
    return {
        "report_type": "advisor_environment_doctor",
        "generated_at": _utc_now(),
        "experiment_id": config["experiment_id"],
        "status": (
            "ready"
            if not failed_core
            and not failed_prepare
            and not failed_run
            and not failed_submit
            and not actions
            else "not_ready"
        ),
        "ready_for_prepare": not failed_core and not failed_prepare,
        "ready_for_run": (
            not failed_core and not failed_prepare and not failed_run and not actions
        ),
        "ready_for_submit": not failed_core and not failed_submit,
        "failed_core_checks": failed_core,
        "failed_prepare_checks": failed_prepare,
        "failed_run_checks": failed_run,
        "failed_submit_checks": failed_submit,
        "required_actions": actions,
        "checks": checks,
    }


def _build_target_paths(repo: Path, config: dict[str, Any]) -> set[Path]:
    return set(_build_target_map(repo, config))


def _build_target_map(
    repo: Path, config: dict[str, Any]
) -> dict[Path, dict[str, Any]]:
    targets: dict[Path, dict[str, Any]] = {}
    for build in config.get("packet_builds", []):
        source = _repo_path(
            repo, build["source_text_packet"], label=f"{build['id']}.source"
        )
        packet_id = source.name
        if (source / "manifest.json").exists():
            packet_id = str(_packet_manifest(source).get("packet_id", packet_id))
        output_root = _repo_path(
            repo, build["output_root"], label=f"{build['id']}.output_root"
        )
        targets[_logical_absolute(output_root / packet_id)] = build
    return targets


def _normalize_split(split: Any) -> str:
    value = str(split).strip().lower().replace("-", "_")
    return "heldout" if value in {"held_out", "heldout", "test"} else value


def _multimodal_privacy_findings(
    repo: Path,
    config: dict[str, Any],
    packet: Path,
    manifest: dict[str, Any],
) -> list[str]:
    build = _build_target_map(repo, config).get(_logical_absolute(packet))
    if build is None:
        return ["multimodal packet has no packet_build privacy provenance"]
    privacy_review = _repo_path(
        repo, build["privacy_review"], label=f"{build['id']}.privacy_review"
    )
    try:
        approvals = _privacy_approvals(privacy_review)
        _approved_images(packet / "inputs", manifest["student_ids"], approvals)
    except WorkflowError as error:
        return [str(error)]
    return []


def _comparison_contract(
    left: dict[str, Any],
    right: dict[str, Any],
    left_manifest: dict[str, Any],
    right_manifest: dict[str, Any],
    *,
    split: str,
) -> tuple[bool, str]:
    if left_manifest["student_ids"] != right_manifest["student_ids"]:
        return False, "anonymous student IDs differ"
    for field in ("course_id", "assessment_id", "rubric_hash"):
        if left_manifest.get(field) != right_manifest.get(field):
            return False, f"packet {field} differs"

    left_split = left_manifest.get("metadata", {}).get("split")
    right_split = right_manifest.get("metadata", {}).get("split")
    if _normalize_split(left_split) != _normalize_split(right_split):
        return False, "packet splits differ"
    if left_split and _normalize_split(left_split) != _normalize_split(split):
        return False, "packet split does not match experiment split"

    engine_differs = left["engine"] != right["engine"]
    model_differs = left["model"] != right["model"]
    mode_differs = left["input_mode"] != right["input_mode"]
    condition_differs = left["condition"] != right["condition"]
    if condition_differs:
        if engine_differs or model_differs or mode_differs:
            return False, "baseline/candidate comparison changes another axis"
        axis = "condition"
    elif mode_differs:
        if engine_differs or model_differs:
            return False, "text/multimodal comparison changes engine or model"
        axis = "input_mode"
    elif engine_differs:
        axis = "engine_model"
    elif model_differs:
        axis = "model"
    else:
        return False, "comparison does not change a named axis"

    if axis in {"input_mode", "engine_model", "model"} and (
        left_manifest.get("prompt_hash") != right_manifest.get("prompt_hash")
    ):
        return False, f"{axis} comparison changes prompt hash"
    return True, f"matched students, split, rubric, and axis={axis}"


def plan(repo: Path, config: dict[str, Any]) -> dict[str, Any]:
    run_rows = []
    missing_packets: list[str] = []
    manifest_cache: dict[Path, dict[str, Any]] = {}
    for run in config["runs"]:
        packet = _repo_path(repo, run["packet"], label=f"{run['id']}.packet")
        manifest = _packet_manifest(packet) if packet.is_dir() else None
        if manifest:
            manifest_cache[packet] = manifest
        if manifest and run["input_mode"] == "text-only":
            provenance = _text_provenance(manifest)[0]
        elif manifest:
            provenance = (
                "approved-anonymized-images"
                if not _multimodal_privacy_findings(repo, config, packet, manifest)
                else "unverified-images"
            )
        else:
            provenance = None
        run_rows.append(
            {
                "id": run["id"],
                "engine": run["engine"],
                "model": run["model"],
                "input_mode": run["input_mode"],
                "condition": run["condition"],
                "packet": _relative(repo, packet),
                "packet_ready": manifest is not None,
                "student_count": len(manifest["student_ids"]) if manifest else None,
                "input_provenance": provenance,
            }
        )
        if manifest is None:
            missing_packets.append(run["id"])

    runs_by_id = {run["id"]: run for run in config["runs"]}
    comparison_rows = []
    blocking: list[str] = []
    for comparison in config["comparisons"]:
        left = runs_by_id[comparison["baseline_run"]]
        right = runs_by_id[comparison["candidate_run"]]
        left_packet = _repo_path(repo, left["packet"], label=f"{left['id']}.packet")
        right_packet = _repo_path(repo, right["packet"], label=f"{right['id']}.packet")
        matched = False
        reason = "packet not prepared"
        if left_packet.is_dir() and right_packet.is_dir():
            left_manifest = manifest_cache.get(left_packet) or _packet_manifest(
                left_packet
            )
            right_manifest = manifest_cache.get(right_packet) or _packet_manifest(
                right_packet
            )
            matched, reason = _comparison_contract(
                left,
                right,
                left_manifest,
                right_manifest,
                split=config["split"],
            )
        if not matched and reason != "packet not prepared":
            blocking.append(f"{comparison['id']}: {reason}")
        comparison_rows.append(
            {
                "id": comparison["id"],
                "left": left["id"],
                "right": right["id"],
                "matched": matched,
                "reason": reason,
            }
        )
    return {
        "report_type": "advisor_experiment_plan",
        "generated_at": _utc_now(),
        "experiment_id": config["experiment_id"],
        "split": config["split"],
        "status": (
            "blocked"
            if blocking
            else "action_required"
            if missing_packets
            else "planned"
        ),
        "missing_packets": missing_packets,
        "blocking_mismatches": blocking,
        "run_order": run_rows,
        "comparisons": comparison_rows,
        "heldout_requires_explicit_approval": config["split"] in {"heldout", "test"},
    }


def _privacy_approvals(path: Path) -> dict[str, bool]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
    except FileNotFoundError as error:
        raise WorkflowError(f"privacy review is missing: {path}") from error
    if not rows or "page" not in rows[0] or "approved" not in rows[0]:
        raise WorkflowError(f"privacy review requires page and approved columns: {path}")
    return {
        str(row["page"]): str(row["approved"]).strip().lower() in {"1", "true", "yes"}
        for row in rows
    }


def _approved_images(
    input_root: Path,
    student_ids: Iterable[str],
    approvals: dict[str, bool],
) -> list[Path]:
    selected: list[Path] = []
    for student_id in student_ids:
        student_dir = input_root / student_id
        if not student_dir.is_dir():
            raise WorkflowError(f"missing anonymized image directory: {student_dir}")
        files = sorted(path for path in student_dir.rglob("*") if path.is_file())
        if not files:
            raise WorkflowError(f"no image pages found for {student_id}")
        for path in files:
            if path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
                raise WorkflowError(f"non-image file in multimodal input: {path}")
            if approvals.get(path.name) is not True:
                raise WorkflowError(f"image page lacks explicit privacy approval: {path.name}")
            selected.append(path)
    return selected


def prepare(
    repo: Path,
    config: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    results = []
    for build in config.get("packet_builds", []):
        source = _repo_path(
            repo, build["source_text_packet"], label=f"{build['id']}.source"
        )
        manifest = _packet_manifest(source)
        input_root = _repo_path(
            repo, build["input_root"], label=f"{build['id']}.input_root"
        )
        privacy_review = _repo_path(
            repo, build["privacy_review"], label=f"{build['id']}.privacy_review"
        )
        approvals = _privacy_approvals(privacy_review)
        images = _approved_images(input_root, manifest["student_ids"], approvals)
        output_root = _repo_path(
            repo, build["output_root"], label=f"{build['id']}.output_root"
        )
        target = output_root / str(manifest["packet_id"])

        if target.exists():
            target_manifest = _packet_manifest(target)
            if (
                target_manifest["student_ids"] != manifest["student_ids"]
                or target_manifest.get("condition") != manifest.get("condition")
                or target_manifest.get("metadata", {}).get("input_mode")
                != "multimodal"
            ):
                raise WorkflowError(
                    f"existing immutable packet differs: {_relative(repo, target)}"
                )
            audit = _run(
                [
                    sys.executable,
                    "-m",
                    "benchmark.core.cli",
                    "audit-packet",
                    "--packet",
                    str(target),
                ],
                cwd=repo,
            )
            if audit.returncode != 0:
                raise WorkflowError(f"existing packet failed audit: {target}")
            _approved_images(target / "inputs", manifest["student_ids"], approvals)
            results.append(
                {
                    "id": build["id"],
                    "status": "reused",
                    "packet": _relative(repo, target),
                    "student_count": len(manifest["student_ids"]),
                    "image_count": len(images),
                }
            )
            continue

        argv = [
            sys.executable,
            "-m",
            "benchmark.core.cli",
            "build-packet",
            "--course",
            str(source / "course.json"),
            "--packet-id",
            str(manifest["packet_id"]),
            "--condition",
            str(manifest["condition"]),
            "--task",
            "grade",
            "--prompt",
            str(source / "prompt.txt"),
            "--rubric",
            str(source / "rubric.json"),
            "--input-root",
            str(input_root),
            "--output-root",
            str(output_root),
        ]
        for student_id in manifest["student_ids"]:
            argv.extend(["--student-id", str(student_id)])
        metadata = manifest.get("metadata", {})
        if isinstance(metadata, dict):
            for key, value in sorted(metadata.items()):
                if key == "input_mode" or key == "source_run_id" or key.startswith(
                    "text_source"
                ):
                    continue
                if isinstance(value, (str, int, float, bool)):
                    argv.extend(["--metadata", f"{key}={value}"])
        argv.extend(
            [
                "--metadata",
                "input_mode=multimodal",
                "--metadata",
                "image_source_kind=approved_anonymized_pages",
                "--metadata",
                f"source_prompt_packet={_relative(repo, source)}",
            ]
        )
        if dry_run:
            results.append(
                {
                    "id": build["id"],
                    "status": "would_build",
                    "packet": _relative(repo, target),
                    "student_count": len(manifest["student_ids"]),
                    "image_count": len(images),
                }
            )
            continue

        _run(argv, cwd=repo, capture=True, check=True)
        audit = _run(
            [
                sys.executable,
                "-m",
                "benchmark.core.cli",
                "audit-packet",
                "--packet",
                str(target),
            ],
            cwd=repo,
            capture=True,
        )
        if audit.returncode != 0:
            raise WorkflowError(f"new packet failed isolation audit: {target}")
        results.append(
            {
                "id": build["id"],
                "status": "built",
                "packet": _relative(repo, target),
                "student_count": len(manifest["student_ids"]),
                "image_count": len(images),
            }
        )
    return {
        "report_type": "advisor_packet_preparation",
        "generated_at": _utc_now(),
        "experiment_id": config["experiment_id"],
        "dry_run": dry_run,
        "status": "passed",
        "packet_builds": results,
    }


def _run_metadata_matches(
    repo: Path,
    run: dict[str, Any],
    output: Path,
    *,
    run_commit: str,
) -> bool:
    try:
        validation = _read_json(output / "validation.json")
        metadata = _read_json(output / "run-metadata.json")
    except WorkflowError:
        return False
    if validation.get("status") != "passed":
        return False
    packet = _repo_path(repo, run["packet"], label=f"{run['id']}.packet")
    metadata_packet = Path(str(metadata.get("packet", "")))
    if not metadata_packet.is_absolute():
        metadata_packet = repo / metadata_packet
    return (
        metadata.get("engine") == run["engine"]
        and metadata.get("model") == run["model"]
        and metadata.get("input_mode") == run["input_mode"]
        and metadata.get("experiment_condition") == run["condition"]
        and metadata.get("max_retries") == run.get("max_retries", 2)
        and metadata.get("timeout_seconds") == run.get("timeout_seconds", 600)
        and metadata.get("run_commit") == run_commit
        and os.path.normcase(str(_logical_absolute(metadata_packet)))
        == os.path.normcase(str(_logical_absolute(packet)))
    )


def _state_path(repo: Path, config: dict[str, Any], dry_run: bool) -> Path:
    path = _repo_path(repo, config["state_path"], label="state_path")
    if dry_run:
        return path.with_name(path.stem + "-dry-run" + path.suffix)
    return path


def _run_output(repo: Path, run: dict[str, Any], dry_run: bool) -> Path:
    output = _repo_path(repo, run["output"], label=f"{run['id']}.output")
    return output.with_name(output.name + "-dry-run") if dry_run else output


def _technical_failure_counts(validation: dict[str, Any]) -> dict[str, int]:
    counts = Counter(
        str(
            row.get("error_category")
            or row.get("error_type")
            or "unknown-technical-failure"
        )
        for row in validation.get("rows", [])
        if isinstance(row, dict) and row.get("status") == "failed"
    )
    return dict(sorted(counts.items()))


def run_experiment(
    repo: Path,
    config: dict[str, Any],
    *,
    dry_run: bool = False,
    approve_heldout: bool = False,
) -> dict[str, Any]:
    if config["split"] in {"heldout", "test"} and not approve_heldout:
        raise WorkflowError(
            "held-out/test execution requires explicit --approve-heldout after "
            "development arms pass"
        )
    blockers: list[dict[str, str]] = []
    for run in config["runs"]:
        packet = _repo_path(repo, run["packet"], label=f"{run['id']}.packet")
        if not packet.is_dir():
            blockers.append(
                {
                    "gate": f"packet-{run['id']}",
                    "category": "packet/input",
                    "reason": "missing-packet",
                }
            )
            continue
        findings = _packet_mode_findings(packet, run["input_mode"])
        if run["input_mode"] == "multimodal":
            findings.extend(
                _multimodal_privacy_findings(
                    repo, config, packet, _packet_manifest(packet)
                )
            )
        if findings:
            blockers.append(
                {
                    "gate": f"packet-{run['id']}",
                    "category": "packet/input",
                    "reason": "packet-validation-failed",
                }
            )
    frozen_plan = plan(repo, config)
    for comparison in frozen_plan["comparisons"]:
        if not comparison["matched"] and comparison["reason"] != "packet not prepared":
            blockers.append(
                {
                    "gate": f"comparison-{comparison['id']}",
                    "category": "packet/input",
                    "reason": "comparison-contract-mismatch",
                }
            )

    tracked = _git(repo, "ls-files", "--", "Data", ".private-data")
    if tracked.returncode != 0 or tracked.stdout.strip():
        blockers.append(
            {
                "gate": "private-data-index",
                "category": "environment/authentication",
                "reason": "private-data-tracked",
            }
        )

    run_commit = _git(repo, "rev-parse", "--short", "HEAD", check=True).stdout.strip()
    if not dry_run:
        if _reproducibility_dirty_paths(repo):
            blockers.append(
                {
                    "gate": "reproducibility-code-clean",
                    "category": "environment/authentication",
                    "reason": "uncommitted-run-code",
                }
            )
        binaries: dict[str, str] = {}
        for run in config["runs"]:
            binaries.setdefault(run["engine"], _engine_binary(run))
        for engine, binary in sorted(binaries.items()):
            if _command_version(binary, repo) is None:
                blockers.append(
                    {
                        "gate": f"{engine}-cli",
                        "category": "environment/authentication",
                        "reason": "engine-cli-unavailable",
                    }
                )
        method, _ = _pr_method(repo)
        if method is None:
            blockers.append(
                {
                    "gate": "github-pr-auth",
                    "category": "environment/authentication",
                    "reason": "github-pr-auth-unavailable",
                }
            )
        if not _probe_receipt_matches(
            repo,
            config,
            run_commit=run_commit,
        ):
            blockers.append(
                {
                    "gate": "zero-data-model-probes",
                    "category": "environment/authentication",
                    "reason": "model-probes-not-passed",
                }
            )

    state_path = _state_path(repo, config, dry_run)
    state: dict[str, Any] = {
        "report_type": "advisor_experiment_state",
        "experiment_id": config["experiment_id"],
        "split": config["split"],
        "dry_run": dry_run,
        "run_commit": run_commit,
        "started_at": _utc_now(),
        "status": "running",
        "runs": {},
        "comparisons": {},
    }
    if blockers:
        state["status"] = "blocked"
        state["blockers"] = list(
            {
                (item["gate"], item["category"], item["reason"]): item
                for item in blockers
            }.values()
        )
        state["ended_at"] = _utc_now()
        _write_json(state_path, state)
        return state
    _write_json(state_path, state)

    all_runs_passed = True
    for run in config["runs"]:
        run_id = run["id"]
        output = _run_output(repo, run, dry_run)
        packet = _repo_path(repo, run["packet"], label=f"{run_id}.packet")
        if output.exists():
            if _run_metadata_matches(
                repo,
                run,
                output,
                run_commit=run_commit,
            ):
                validation = _read_json(output / "validation.json")
                state["runs"][run_id] = {
                    "status": "reused",
                    "validation_status": "passed",
                    "students_expected": validation.get("students_expected"),
                    "students_passed": validation.get("students_passed"),
                    "output": _relative(repo, output),
                }
                _write_json(state_path, state)
                continue
            state["runs"][run_id] = {
                "status": "failed",
                "failure_category": "output_collision",
                "detail": "existing output is failed, incomplete, or mismatched",
                "output": _relative(repo, output),
            }
            all_runs_passed = False
            _write_json(state_path, state)
            continue

        argv = [
            sys.executable,
            str(repo / "scripts" / "run_headless_packet.py"),
            "--engine",
            run["engine"],
            "--model",
            run["model"],
            "--input-mode",
            run["input_mode"],
            "--packet",
            str(packet),
            "--output",
            str(output),
            "--max-retries",
            str(run.get("max_retries", 2)),
            "--timeout-seconds",
            str(run.get("timeout_seconds", 600)),
            "--run-commit",
            run_commit,
            "--experiment-condition",
            run["condition"],
        ]
        if run.get("engine_bin"):
            argv.extend(["--engine-bin", str(run["engine_bin"])])
        if dry_run:
            argv.append("--dry-run")

        completed = _run(argv, cwd=repo, capture=True)
        validation: dict[str, Any] = {}
        if (output / "validation.json").exists():
            validation = _read_json(output / "validation.json")
        passed = completed.returncode == 0 and validation.get("status") == "passed"
        state["runs"][run_id] = {
            "status": "passed" if passed else "failed",
            "validation_status": validation.get("status", "missing"),
            "students_expected": validation.get("students_expected"),
            "students_passed": validation.get("students_passed"),
            "technical_failure_types": _technical_failure_counts(validation),
            "output": _relative(repo, output),
        }
        _write_json(state_path, state)
        if not passed:
            all_runs_passed = False

    runs_by_id = {run["id"]: run for run in config["runs"]}
    if not dry_run:
        for comparison in config["comparisons"]:
            left_id = comparison["baseline_run"]
            right_id = comparison["candidate_run"]
            left_state = state["runs"].get(left_id, {})
            right_state = state["runs"].get(right_id, {})
            if left_state.get("validation_status") != "passed" or right_state.get(
                "validation_status"
            ) != "passed":
                state["comparisons"][comparison["id"]] = {
                    "status": "blocked",
                    "reason": "both referenced runs must pass",
                }
                continue
            left_output = _run_output(repo, runs_by_id[left_id], False)
            right_output = _run_output(repo, runs_by_id[right_id], False)
            output_json = _repo_path(
                repo,
                comparison["output_json"],
                label=f"{comparison['id']}.output_json",
            )
            output_md = _repo_path(
                repo,
                comparison["output_md"],
                label=f"{comparison['id']}.output_md",
            )
            argv = [
                sys.executable,
                "-m",
                "benchmark.physics.cli",
                "metrics",
                "--root",
                str(_repo_path(repo, config["benchmark_root"], label="benchmark_root")),
                "--baseline-run",
                str(left_output),
                "--candidate-run",
                str(right_output),
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
            ]
            completed = _run(argv, cwd=repo, capture=True)
            passed = (
                completed.returncode == 0
                and output_json.is_file()
                and output_md.is_file()
            )
            state["comparisons"][comparison["id"]] = {
                "status": "passed" if passed else "failed",
                "output_json": _relative(repo, output_json),
                "output_md": _relative(repo, output_md),
            }
            if not passed:
                all_runs_passed = False
            _write_json(state_path, state)

    state["status"] = "passed" if all_runs_passed else "failed"
    state["ended_at"] = _utc_now()
    _write_json(state_path, state)
    return state


def _safe_run_summary(repo: Path, run: dict[str, Any]) -> dict[str, Any]:
    output = _repo_path(repo, run["output"], label=f"{run['id']}.output")
    packet = _repo_path(repo, run["packet"], label=f"{run['id']}.packet")
    input_provenance = (
        _text_provenance(_packet_manifest(packet))[0]
        if run["input_mode"] == "text-only" and packet.is_dir()
        else "approved-anonymized-images"
        if packet.is_dir()
        else "unknown"
    )
    result: dict[str, Any] = {
        "engine": run["engine"],
        "model": run["model"],
        "input_mode": run["input_mode"],
        "condition": run["condition"],
        "status": "not_run",
        "validation_status": "missing",
        "students_expected": None,
        "students_passed": None,
        "technical_failure_types": {},
        "input_provenance": input_provenance,
    }
    if not output.exists():
        return result
    try:
        validation = _read_json(output / "validation.json")
    except WorkflowError:
        result["status"] = "failed"
        result["technical_failure_types"] = {"MissingValidation": 1}
        return result
    result.update(
        {
            "status": "passed" if validation.get("status") == "passed" else "failed",
            "validation_status": validation.get("status", "missing"),
            "students_expected": validation.get("students_expected"),
            "students_passed": validation.get("students_passed"),
            "technical_failure_types": _technical_failure_counts(validation),
        }
    )
    metadata_path = output / "run-metadata.json"
    if metadata_path.exists():
        metadata = _read_json(metadata_path)
        for field in (
            "provider",
            "engine_version",
            "packet_hash",
            "prompt_hash",
            "rubric_hash",
            "run_commit",
            "skill_version_id",
            "source_run_id",
            "text_source_kind",
        ):
            if metadata.get(field) is not None:
                result[field] = metadata[field]
    return result


def _scan_secret_text(text: str, *, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise WorkflowError(f"secret-like value detected in {label}")


def _scan_public_json(value: Any, *, label: str, location: str = "$") -> None:
    forbidden_keys = {
        "student_id",
        "student_ids",
        "raw_text",
        "extracted_evidence",
        "feedback",
        "input_images",
        "prompt",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            lowered_key = key_text.lower()
            if lowered_key in forbidden_keys:
                raise WorkflowError(f"private key {key!r} detected in {label} at {location}")
            if any(part in lowered_key for part in SECRET_KEY_PARTS):
                raise WorkflowError(
                    f"secret-like key {key!r} detected in {label} at {location}"
                )
            _scan_secret_text(key_text, label=label)
            if ANONYMOUS_STUDENT_ID.search(key_text):
                raise WorkflowError(
                    f"anonymous student ID detected in public {label} key"
                )
            _scan_public_json(child, label=label, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_public_json(child, label=label, location=f"{location}[{index}]")
    elif isinstance(value, str):
        _scan_secret_text(value, label=label)
        if ANONYMOUS_STUDENT_ID.search(value):
            raise WorkflowError(f"anonymous student ID detected in public {label}")


def _public_metric_payload(metric: dict[str, Any]) -> dict[str, Any]:
    run_fields = {
        "provider",
        "model",
        "input_mode",
        "validation_status",
        "packet_hash",
        "prompt_hash",
        "rubric_hash",
        "run_commit",
        "validation",
    }

    def safe_run(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        return {key: value[key] for key in sorted(run_fields) if key in value}

    return {
        "record_type": metric.get("record_type"),
        "generated_at": metric.get("generated_at"),
        "student_count": metric.get("student_count"),
        "score_count": metric.get("score_count"),
        "baseline_run": safe_run(metric.get("baseline_run")),
        "candidate_run": safe_run(metric.get("candidate_run")),
        "bootstrap": metric.get("bootstrap", {}),
        "baseline": metric.get("baseline", {}),
        "candidate": metric.get("candidate", {}),
        "candidate_minus_baseline": metric.get("candidate_minus_baseline", {}),
    }


def _render_public_metric_markdown(
    comparison_id: str,
    metric: dict[str, Any],
) -> str:
    baseline = metric.get("baseline", {})
    candidate = metric.get("candidate", {})
    deltas = metric.get("candidate_minus_baseline", {})
    metric_names = sorted(
        key
        for key in set(baseline) & set(candidate) & set(deltas)
        if all(
            isinstance(values.get(key), (int, float))
            for values in (baseline, candidate, deltas)
        )
    )
    lines = [
        f"# Aggregate comparison: {comparison_id}",
        "",
        f"- Students: `{metric.get('student_count', 'not available')}`",
        f"- Score rows: `{metric.get('score_count', 'not available')}`",
        "",
        "| Metric | Left | Right | Right - Left |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name in metric_names:
        lines.append(
            f"| `{name}` | {baseline[name]:.4f} | {candidate[name]:.4f} "
            f"| {deltas[name]:.4f} |"
        )
    interval = (
        metric.get("bootstrap", {})
        .get("exact_agreement_candidate_minus_baseline", {})
    )
    if isinstance(interval, dict) and all(
        isinstance(interval.get(key), (int, float))
        for key in ("mean_difference", "lower", "upper")
    ):
        lines.extend(
            [
                "",
                "## Paired bootstrap",
                "",
                f"- Mean difference: `{interval['mean_difference']:.4f}`",
                f"- 95% interval: `[{interval['lower']:.4f}, "
                f"{interval['upper']:.4f}]`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def package_results(
    repo: Path,
    config: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    record_dir = _repo_path(repo, config["record_dir"], label="record_dir")
    if record_dir.exists():
        raise WorkflowError(
            f"immutable record already exists: {_relative(repo, record_dir)}; "
            "use a new experiment_id"
        )
    workflow_blockers: list[dict[str, str]] = []
    state_path = _state_path(repo, config, False)
    if state_path.is_file():
        state = _read_json(state_path)
        for blocker in state.get("blockers", []):
            if not isinstance(blocker, dict):
                continue
            workflow_blockers.append(
                {
                    key: str(blocker[key])
                    for key in ("gate", "category", "reason")
                    if blocker.get(key) is not None
                }
            )

    run_summaries = {
        run["id"]: _safe_run_summary(repo, run) for run in config["runs"]
    }
    statuses = [summary["status"] for summary in run_summaries.values()]
    if workflow_blockers:
        experiment_status = "blocked"
    elif statuses and all(status == "passed" for status in statuses):
        experiment_status = "completed"
    elif any(status == "failed" for status in statuses):
        experiment_status = "failed"
    else:
        experiment_status = "blocked"

    comparison_summaries: dict[str, Any] = {}
    metric_artifacts: list[tuple[str, str]] = []
    for comparison in config["comparisons"]:
        json_path = _repo_path(
            repo,
            comparison["output_json"],
            label=f"{comparison['id']}.output_json",
        )
        if json_path.is_file():
            metric = _public_metric_payload(_read_json(json_path))
            _scan_public_json(metric, label=comparison["id"])
            comparison_summaries[comparison["id"]] = {
                "status": "passed",
                "metrics": metric.get("candidate_minus_baseline", {}),
                "student_count": metric.get("student_count"),
                "score_count": metric.get("score_count"),
                "json": f"metrics/{comparison['id']}.json",
                "markdown": f"metrics/{comparison['id']}.md",
            }
            metric_artifacts.append(
                (
                    f"metrics/{comparison['id']}.json",
                    json.dumps(
                        metric,
                        indent=2,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n",
                )
            )
            metric_artifacts.append(
                (
                    f"metrics/{comparison['id']}.md",
                    _render_public_metric_markdown(comparison["id"], metric),
                )
            )
        else:
            comparison_summaries[comparison["id"]] = {
                "status": "blocked",
                "reason": "aggregate metrics were not produced",
            }

    summary = {
        "report_type": "advisor_grading_benchmark",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "experiment_id": config["experiment_id"],
        "status": experiment_status,
        "split": config["split"],
        "runs": run_summaries,
        "comparisons": comparison_summaries,
        "workflow_blockers": workflow_blockers,
        "failure_policy": (
            "technical failures are reported separately from scoring accuracy"
        ),
        "project_improvement": (
            "creates a repeatable matched Kimi/Claude and text/multimodal "
            "benchmark with a privacy-safe PR handoff"
        ),
        "privacy": {
            "raw_student_data_tracked": False,
            "raw_model_responses_tracked": False,
            "per_student_outputs_tracked": False,
            "aggregate_results_only": True,
        },
    }
    _scan_public_json(summary, label="summary")
    markdown = _render_report(summary)
    snapshot = json.loads(json.dumps(config))
    _scan_public_json(snapshot, label="config snapshot")

    if dry_run:
        return {
            "report_type": "advisor_result_package_preview",
            "experiment_id": config["experiment_id"],
            "status": experiment_status,
            "record_dir": _relative(repo, record_dir),
            "metric_files": [target for target, _ in metric_artifacts],
        }

    record_dir.mkdir(parents=True)
    _write_json(record_dir / "summary.json", summary)
    _write_json(record_dir / "config.snapshot.json", snapshot)
    (record_dir / "RUN-REPORT.md").write_text(
        markdown, encoding="utf-8", newline="\n"
    )
    for target, content in metric_artifacts:
        destination = record_dir / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")
    privacy_scan_record(repo, record_dir)
    return {
        "report_type": "advisor_result_package",
        "experiment_id": config["experiment_id"],
        "status": experiment_status,
        "record_dir": _relative(repo, record_dir),
        "files": sorted(
            path.relative_to(record_dir).as_posix()
            for path in record_dir.rglob("*")
            if path.is_file()
        ),
    }


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# Advisor grading benchmark: {summary['experiment_id']}",
        "",
        f"Status: **{summary['status']}**",
        "",
        "## What this run did",
        "",
        "This experiment used the repository's headless packet runner to compare "
        "Kimi Code and Claude Code across frozen transcript-first and direct-image "
        f"grading on the `{summary['split']}` split.",
        "",
    ]
    blockers = summary.get("workflow_blockers", [])
    if blockers:
        lines.extend(
            [
                "## Blocked gates",
                "",
                "| Gate | Category | Reason |",
                "| --- | --- | --- |",
            ]
        )
        for blocker in blockers:
            lines.append(
                f"| `{blocker.get('gate', 'unknown')}` "
                f"| `{blocker.get('category', 'unknown')}` "
                f"| `{blocker.get('reason', 'unknown')}` |"
            )
        lines.append("")
    lines.extend(
        [
        "## Run validation",
        "",
        "| Run | Engine | Mode | Condition | Status | Students | Technical failures |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for run_id, run in summary["runs"].items():
        passed = run.get("students_passed")
        expected = run.get("students_expected")
        students = (
            f"{passed}/{expected}"
            if passed is not None and expected is not None
            else "not available"
        )
        failures = ", ".join(
            f"{key}: {value}"
            for key, value in run.get("technical_failure_types", {}).items()
        ) or "none"
        lines.append(
            f"| `{run_id}` | `{run['engine']}` | `{run['input_mode']}` "
            f"({run['input_provenance']}) | "
            f"`{run['condition']}` | `{run['status']}` | {students} | {failures} |"
        )

    lines.extend(
        [
            "",
            "## Aggregate comparisons",
            "",
            "| Comparison | Status | Exact agreement Δ | Subquestion MAE Δ | Total-score MAE Δ |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for comparison_id, comparison in summary["comparisons"].items():
        metrics = comparison.get("metrics", {})
        lines.append(
            f"| `{comparison_id}` | `{comparison['status']}` | "
            f"{_format_metric(metrics.get('exact_agreement'))} | "
            f"{_format_metric(metrics.get('subquestion_mae'))} | "
            f"{_format_metric(metrics.get('total_score_mae'))} |"
        )

    next_action = (
        "Review the matched aggregate effects, then explicitly approve a frozen "
        "held-out run if the development evidence is adequate."
        if summary["status"] == "completed"
        else "Fix the first failed or blocked gate, create a new immutable retry "
        "identity, and retain this record as failure evidence."
    )
    lines.extend(
        [
            "",
            "## How this improves the project",
            "",
            "- Replaces private-chat handoff with a reproducible pull request.",
            "- Keeps text and multimodal evidence separate and matched.",
            "- Separates technical failures from scoring/accuracy differences.",
            "- Preserves aggregate confidence-accuracy fields when the metric "
            "runner provides them.",
            "",
            "## Privacy and limitations",
            "",
            "- No raw transcript, page image, prompt body, model response, CLI log, "
            "or per-student output is included.",
            f"- This is a `{summary['split']}` result and must not be generalized beyond "
            "the frozen packets and models.",
            "",
            "## Next action",
            "",
            next_action,
            "",
        ]
    )
    return "\n".join(lines)


def _format_metric(value: Any) -> str:
    return f"{value:.4f}" if isinstance(value, (int, float)) else "—"


def privacy_scan_record(repo: Path, record_dir: Path) -> dict[str, Any]:
    _assert_below(repo, record_dir, "experiments/records", label="record_dir")
    files = sorted(path for path in record_dir.rglob("*") if path.is_file())
    if not files:
        raise WorkflowError("record directory is empty")
    for path in files:
        if path.suffix.lower() not in SAFE_RECORD_SUFFIXES:
            raise WorkflowError(f"unsafe record file type: {_relative(repo, path)}")
        if path.stat().st_size > 2_000_000:
            raise WorkflowError(f"record file is unexpectedly large: {_relative(repo, path)}")
        text = path.read_text(encoding="utf-8")
        _scan_secret_text(text, label=_relative(repo, path))
        if ANONYMOUS_STUDENT_ID.search(text):
            raise WorkflowError(
                f"anonymous student ID detected in public record: {_relative(repo, path)}"
            )
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as error:
                raise WorkflowError(f"invalid public JSON: {path}") from error
            _scan_public_json(payload, label=_relative(repo, path))
    tracked = _git(repo, "ls-files", "--", "Data", ".private-data")
    if tracked.returncode != 0 or tracked.stdout.strip():
        raise WorkflowError("private Data/ or .private-data/ paths are tracked")
    return {
        "status": "passed",
        "record_dir": _relative(repo, record_dir),
        "file_count": len(files),
    }


def _github_repo_slug(origin: str) -> tuple[str, str]:
    patterns = (
        re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$"),
        re.compile(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"),
        re.compile(r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"),
    )
    for pattern in patterns:
        match = pattern.match(origin.strip())
        if match:
            return match.group(1), match.group(2)
    raise WorkflowError("automatic token PR creation currently requires a github.com origin")


def _create_pr_with_token(
    *,
    owner: str,
    repo_name: str,
    branch: str,
    base: str,
    title: str,
    body: str,
) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise WorkflowError("GITHUB_TOKEN is missing from the current environment")
    url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls"
    payload = json.dumps(
        {
            "title": title,
            "head": branch,
            "base": base,
            "body": body,
            "draft": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "exam-automark-advisor-workflow",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise WorkflowError(f"GitHub PR API failed with HTTP {error.code}: {detail}") from error
    html_url = result.get("html_url")
    if not isinstance(html_url, str):
        raise WorkflowError("GitHub PR API response did not include html_url")
    return html_url


def submit_results(
    repo: Path,
    config: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    record_dir = _repo_path(repo, config["record_dir"], label="record_dir")
    scan = privacy_scan_record(repo, record_dir)
    submission = config["submission"]
    branch = submission["branch"]
    base = submission["base"]
    method, method_detail = _pr_method(repo)
    origin_result = _git(repo, "remote", "get-url", "origin", check=True)
    origin = origin_result.stdout.strip()
    current = _git(repo, "branch", "--show-current", check=True).stdout.strip()
    if current not in {base, branch}:
        raise WorkflowError(
            f"current branch {current!r} is neither base {base!r} nor target {branch!r}"
        )
    if not method:
        raise WorkflowError(
            f"automatic PR submission is not configured: {method_detail}"
        )
    preview = {
        "report_type": "advisor_submission_preview" if dry_run else "advisor_submission",
        "status": "ready" if dry_run else "submitting",
        "record_dir": scan["record_dir"],
        "branch": branch,
        "base": base,
        "origin": origin,
        "pr_method": method,
        "files": scan["file_count"],
    }
    if dry_run:
        return preview

    _git(repo, "fetch", "origin", base, check=True)
    if current == base:
        exists = _git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
        if exists.returncode == 0:
            _git(repo, "switch", branch, check=True)
        else:
            remote_exists = _git(
                repo,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/remotes/origin/{branch}",
            )
            if remote_exists.returncode == 0:
                _git(repo, "switch", "--track", f"origin/{branch}", check=True)
            else:
                _git(repo, "switch", "-c", branch, f"origin/{base}", check=True)

    _git(repo, "add", "--", _relative(repo, record_dir), check=True)
    staged = _git(
        repo,
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=ACMR",
        check=True,
    )
    staged_paths = [
        line.strip().replace("\\", "/")
        for line in staged.stdout.splitlines()
        if line.strip()
    ]
    record_prefix = _relative(repo, record_dir).rstrip("/") + "/"
    unsafe_staged = [path for path in staged_paths if not path.startswith(record_prefix)]
    if unsafe_staged:
        raise WorkflowError(f"refusing to commit unrelated staged files: {unsafe_staged}")
    if staged_paths:
        _git(repo, "commit", "-m", submission["commit_message"], check=True)

    _git(repo, "push", "-u", "origin", branch, check=True)
    body_file = record_dir / "RUN-REPORT.md"
    body = body_file.read_text(encoding="utf-8")
    if method == "gh":
        gh = _find_gh()
        assert gh is not None
        completed = _run(
            [
                gh,
                "pr",
                "create",
                "--base",
                base,
                "--head",
                branch,
                "--title",
                submission["title"],
                "--body-file",
                str(body_file),
                "--draft",
            ],
            cwd=repo,
            capture=True,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            existing = _run(
                [gh, "pr", "view", branch, "--json", "url", "--jq", ".url"],
                cwd=repo,
                capture=True,
            )
            if existing.returncode != 0 or not existing.stdout.strip():
                raise WorkflowError(f"gh pr create failed: {detail}")
            pr_url = existing.stdout.strip()
        else:
            pr_url = completed.stdout.strip().splitlines()[-1]
    else:
        owner, repo_name = _github_repo_slug(origin)
        pr_url = _create_pr_with_token(
            owner=owner,
            repo_name=repo_name,
            branch=branch,
            base=base,
            title=submission["title"],
            body=body,
        )

    commit = _git(repo, "rev-parse", "HEAD", check=True).stdout.strip()
    preview.update(
        {
            "status": "submitted",
            "commit": commit,
            "pr_url": pr_url,
        }
    )
    return preview


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="advisor-experiment",
        description=(
            "Configure, run, package, and submit a matched Kimi/Claude "
            "text-plus-multimodal grading benchmark."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="generate a private local config")
    init.add_argument("--preset", default="physics-week9", choices=("physics-week9",))
    init.add_argument("--output", type=Path, required=True)
    init.add_argument("--experiment-id")
    init.add_argument("--split", choices=("development", "test"), default="development")
    init.add_argument("--kimi-model", default="kimi-code/k3")
    init.add_argument("--claude-model", default="sonnet")

    for name, help_text in (
        ("doctor", "check environment, packets, privacy, and PR authentication"),
        ("probe", "run approved zero-data engine/model authentication probes"),
        ("plan", "show the frozen run and comparison matrix"),
        ("prepare", "build missing approved multimodal packets"),
        ("run", "execute headless runs and paired metrics"),
        ("package", "create a privacy-safe public experiment record"),
        ("submit", "commit, push, and open the result PR"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--config", type=Path, required=True)
        if name == "probe":
            command.add_argument("--approve-model-probes", action="store_true")
        if name in {"prepare", "package", "submit"}:
            command.add_argument("--dry-run", action="store_true")
        if name == "run":
            command.add_argument("--dry-run", action="store_true")
            command.add_argument("--approve-heldout", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        repo = find_repo_root()
        if args.command == "init":
            result = init_config(
                repo,
                args.output,
                preset=args.preset,
                experiment_id=args.experiment_id,
                kimi_model=args.kimi_model,
                claude_model=args.claude_model,
                split=args.split,
            )
        else:
            repo, config = load_config(args.config, repo)
            if args.command == "doctor":
                result = doctor(repo, config)
            elif args.command == "probe":
                result = probe_models(
                    repo,
                    config,
                    approved=args.approve_model_probes,
                )
            elif args.command == "plan":
                result = plan(repo, config)
            elif args.command == "prepare":
                result = prepare(repo, config, dry_run=args.dry_run)
            elif args.command == "run":
                result = run_experiment(
                    repo,
                    config,
                    dry_run=args.dry_run,
                    approve_heldout=args.approve_heldout,
                )
            elif args.command == "package":
                result = package_results(repo, config, dry_run=args.dry_run)
            elif args.command == "submit":
                result = submit_results(repo, config, dry_run=args.dry_run)
            else:
                raise WorkflowError(f"unsupported command: {args.command}")
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        if args.command == "doctor":
            return 0 if result["status"] == "ready" else 1
        if args.command == "probe":
            return 0 if result["status"] == "passed" else 1
        if args.command in {"plan", "run"}:
            return 0 if result["status"] in {"planned", "passed"} else 1
        return 0
    except WorkflowError as error:
        print(str(error), file=sys.stderr)
        return 1
