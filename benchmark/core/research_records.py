"""Validate external-repository research records and their source snapshots."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Sequence


COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
FLOATING_GITHUB_REF = re.compile(
    r"https://(?:"
    r"github\.com/[^/\s)]+/[^/\s)]+/(?:blob|tree)/main(?:[/\s)]|$)"
    r"|raw\.githubusercontent\.com/[^/\s)]+/[^/\s)]+/main/"
    r")"
)
MOJIBAKE_FRAGMENTS = (
    "\ufffd",
    "鍙",
    "鐨勬",
    "鏄",
    "銆乣",
    "鈥",
    "锟斤拷",
    "â€™",
    "â€“",
    "â€”",
    "ï»¿",
)


def audit_research_records(
    manifest_path: Path,
    *,
    repo_root: Path | None = None,
) -> list[str]:
    """Return public-safe validation findings; an empty list means pass."""

    root = (repo_root or Path.cwd()).resolve()
    findings: list[str] = []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"manifest missing: {manifest_path}"]
    except UnicodeDecodeError as error:
        return [f"manifest is not valid UTF-8: {error}"]
    except json.JSONDecodeError as error:
        return [f"manifest is not valid JSON: {error}"]

    if not isinstance(payload, dict):
        return ["manifest must be a JSON object"]
    if payload.get("schema_version") != 1:
        findings.append("schema_version must be 1")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        findings.append("records must be a non-empty list")
        return findings

    seen_paths: set[str] = set()
    for index, record in enumerate(records):
        label = f"records[{index}]"
        if not isinstance(record, dict):
            findings.append(f"{label} must be a JSON object")
            continue
        findings.extend(
            _audit_record(record, label=label, root=root, seen_paths=seen_paths)
        )
    return findings


def _audit_record(
    record: dict[str, Any],
    *,
    label: str,
    root: Path,
    seen_paths: set[str],
) -> list[str]:
    findings: list[str] = []
    record_path = record.get("record_path")
    source_repository = record.get("source_repository")
    source_commit = record.get("source_commit")
    checked_date = record.get("checked_date")

    if not isinstance(record_path, str) or not record_path.endswith(".md"):
        findings.append(f"{label}.record_path must be a Markdown path")
        return findings
    if record_path in seen_paths:
        findings.append(f"{label}.record_path is duplicated: {record_path}")
    seen_paths.add(record_path)

    path = (root / record_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        findings.append(f"{label}.record_path escapes the repository")
        return findings
    if not record_path.startswith("experiments/records/"):
        findings.append(f"{label}.record_path must be below experiments/records/")

    if (
        not isinstance(source_repository, str)
        or not source_repository.startswith("https://github.com/")
    ):
        findings.append(
            f"{label}.source_repository must be a GitHub HTTPS repository URL"
        )
    if not isinstance(source_commit, str) or COMMIT_SHA.fullmatch(source_commit) is None:
        findings.append(f"{label}.source_commit must be a 40-character lowercase SHA")
    if not _is_iso_date(checked_date):
        findings.append(f"{label}.checked_date must be an ISO date")

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        findings.append(f"{label}.record_path is missing: {record_path}")
        return findings
    except UnicodeDecodeError as error:
        findings.append(f"{label}.record_path is not valid UTF-8: {error}")
        return findings

    for fragment in MOJIBAKE_FRAGMENTS:
        if fragment in text:
            findings.append(
                f"{label}.record_path contains mojibake marker {fragment!r}"
            )
    if isinstance(source_repository, str) and source_repository not in text:
        findings.append(f"{label}.record_path does not cite source_repository")
    if isinstance(source_commit, str) and source_commit not in text:
        findings.append(f"{label}.record_path does not cite source_commit")
    if FLOATING_GITHUB_REF.search(text):
        findings.append(
            f"{label}.record_path cites a floating GitHub main ref; pin the commit"
        )
    return findings


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check external research records for pinned sources and readable UTF-8."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/records/tooling-surveys/sources.json"),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    findings = audit_research_records(
        args.manifest,
        repo_root=args.repo_root,
    )
    if findings:
        for finding in findings:
            print(f"FAILED: {finding}")
        return 1
    print(f"passed: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
