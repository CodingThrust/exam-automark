"""Validate external-repository research records and their source snapshots."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Sequence


COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
ARXIV_ID = re.compile(r"^\d{4}\.\d{5}$")
BIB_ENTRY = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)
TYPST_CITATION = re.compile(r"@([A-Za-z0-9_:-]+)")
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
LITERATURE_SURVEY_RECORD_TYPE = "sci_brain_survey_run"
KNOWN_LEGACY_LITERATURE_EXCEPTIONS = {
    "sci-brain-2026-07-19-unrecorded-provenance": {
        "run_date": "2026-07-19",
        "missing_fields": {
            "tool.source_commit",
            "discovery.queries",
            "discovery.selection_log",
        },
    }
}


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
    if payload.get("record_type") == LITERATURE_SURVEY_RECORD_TYPE:
        return _audit_literature_survey_run(payload, root=root)
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


def _audit_literature_survey_run(
    payload: dict[str, Any],
    *,
    root: Path,
) -> list[str]:
    findings: list[str] = []
    if payload.get("schema_version") != 1:
        findings.append("schema_version must be 1")
    run_date = payload.get("run_date")
    if not _is_iso_date(run_date):
        findings.append("run_date must be an ISO date")

    _audit_literature_provenance(payload, findings=findings)

    knowledge = payload.get("knowledge_base")
    if not isinstance(knowledge, dict):
        findings.append("knowledge_base must be a JSON object")
        return findings

    text_by_field: dict[str, str] = {}
    for field in ("notes_path", "index_path", "bib_path", "report_bib_path"):
        path = _resolve_repo_path(
            root,
            knowledge.get(field),
            label=f"knowledge_base.{field}",
            findings=findings,
        )
        if path is None:
            continue
        text = _read_utf8_record(
            path,
            label=f"knowledge_base.{field}",
            findings=findings,
        )
        if text is not None:
            text_by_field[field] = text

    bib_text = text_by_field.get("bib_path")
    report_bib_text = text_by_field.get("report_bib_path")
    bib_keys = _bib_keys(bib_text) if bib_text is not None else set()
    if bib_text is not None and report_bib_text is not None:
        report_bib_keys = _bib_keys(report_bib_text)
        if bib_keys != report_bib_keys:
            findings.append(
                "knowledge_base bib_path and report_bib_path contain different cite keys"
            )
        if bib_text != report_bib_text:
            findings.append(
                "knowledge_base bib_path and report_bib_path must be byte-for-byte equivalent text"
            )

    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        findings.append("outputs must be a JSON object")
    else:
        expected_entries = outputs.get("bibtex_entries")
        if not isinstance(expected_entries, int) or expected_entries <= 0:
            findings.append("outputs.bibtex_entries must be a positive integer")
        elif bib_text is not None and expected_entries != len(bib_keys):
            findings.append(
                "outputs.bibtex_entries does not match the bibliography cite-key count"
            )

    report_records = payload.get("report_records")
    report_citations: set[str] = set()
    declared_report_citations: set[str] = set()
    if not isinstance(report_records, list) or not report_records:
        findings.append("report_records must be a non-empty list")
    else:
        seen_sources: set[str] = set()
        for index, record in enumerate(report_records):
            label = f"report_records[{index}]"
            if not isinstance(record, dict):
                findings.append(f"{label} must be a JSON object")
                continue
            source_path = record.get("source_path")
            if isinstance(source_path, str):
                if source_path in seen_sources:
                    findings.append(f"{label}.source_path is duplicated: {source_path}")
                seen_sources.add(source_path)
            source = _resolve_repo_path(
                root,
                source_path,
                label=f"{label}.source_path",
                findings=findings,
                suffix=".typ",
            )
            rendered = _resolve_repo_path(
                root,
                record.get("rendered_path"),
                label=f"{label}.rendered_path",
                findings=findings,
                suffix=".pdf",
            )
            if rendered is not None:
                try:
                    if rendered.stat().st_size <= 0:
                        findings.append(f"{label}.rendered_path is empty")
                except FileNotFoundError:
                    findings.append(f"{label}.rendered_path is missing")

            declared = record.get("scoped_cite_keys")
            if (
                not isinstance(declared, list)
                or not declared
                or not all(isinstance(key, str) and key for key in declared)
            ):
                findings.append(
                    f"{label}.scoped_cite_keys must be a non-empty string list"
                )
                declared_keys: set[str] = set()
            else:
                declared_keys = set(declared)
                declared_report_citations.update(declared_keys)
                if declared != sorted(declared_keys):
                    findings.append(
                        f"{label}.scoped_cite_keys must be sorted and unique"
                    )

            if source is not None:
                text = _read_utf8_record(
                    source,
                    label=f"{label}.source_path",
                    findings=findings,
                )
                if text is not None:
                    actual_keys = set(TYPST_CITATION.findall(text))
                    if actual_keys != declared_keys:
                        findings.append(
                            f"{label}.scoped_cite_keys do not match citations in source_path"
                        )
                    missing = sorted(actual_keys - bib_keys)
                    if missing:
                        findings.append(
                            f"{label}.source_path has unresolved cite keys: {missing}"
                        )
                    report_citations.update(actual_keys)

    notes_text = text_by_field.get("notes_path")
    if notes_text is not None:
        notes_keys = set(TYPST_CITATION.findall(notes_text))
        missing_notes = sorted(notes_keys - bib_keys)
        if missing_notes:
            findings.append(
                f"knowledge_base.notes_path has unresolved cite keys: {missing_notes}"
            )
        if payload.get("citation_scope_policy") == "reports_partition_full_bibliography":
            if notes_keys != bib_keys:
                findings.append(
                    "knowledge_base.notes_path cite keys must equal the bibliography scope"
                )

    if payload.get("citation_scope_policy") != "reports_partition_full_bibliography":
        findings.append(
            "citation_scope_policy must be reports_partition_full_bibliography"
        )
    elif bib_keys and report_citations != bib_keys:
        findings.append(
            "the union of report scoped cite keys must equal the bibliography scope"
        )
    if (
        payload.get("citation_scope_policy")
        == "reports_partition_full_bibliography"
        and bib_keys
        and declared_report_citations != bib_keys
    ):
        findings.append(
            "the union of declared report scoped cite keys must equal the bibliography scope"
        )

    _audit_literature_topics(payload.get("topics"), findings=findings)
    return findings


def _audit_literature_provenance(
    payload: dict[str, Any],
    *,
    findings: list[str],
) -> None:
    tool = payload.get("tool")
    discovery = payload.get("discovery")
    if not isinstance(tool, dict):
        findings.append("tool must be a JSON object")
        tool = {}
    if not isinstance(discovery, dict):
        findings.append("discovery must be a JSON object")
        discovery = {}

    repository = tool.get("repository")
    if (
        not isinstance(repository, str)
        or not repository.startswith("https://github.com/")
    ):
        findings.append("tool.repository must be a GitHub HTTPS repository URL")

    status = payload.get("provenance_status")
    if status == "complete":
        source_commit = tool.get("source_commit")
        if (
            not isinstance(source_commit, str)
            or COMMIT_SHA.fullmatch(source_commit) is None
        ):
            findings.append(
                "complete provenance requires tool.source_commit as a lowercase 40-character SHA"
            )
        if tool.get("source_commit_status") != "recorded_at_run_time":
            findings.append(
                "complete provenance requires tool.source_commit_status=recorded_at_run_time"
            )
        queries = discovery.get("queries")
        if (
            not isinstance(queries, list)
            or not queries
            or not all(isinstance(query, str) and query.strip() for query in queries)
        ):
            findings.append(
                "complete provenance requires non-empty discovery.queries"
            )
        if discovery.get("queries_status") != "recorded_at_run_time":
            findings.append(
                "complete provenance requires discovery.queries_status=recorded_at_run_time"
            )
        selection_log = discovery.get("selection_log")
        if not isinstance(selection_log, list) or not selection_log:
            findings.append(
                "complete provenance requires non-empty discovery.selection_log"
            )
        else:
            for index, decision in enumerate(selection_log):
                label = f"discovery.selection_log[{index}]"
                if not isinstance(decision, dict):
                    findings.append(f"{label} must be a JSON object")
                    continue
                if not isinstance(decision.get("source_id"), str) or not decision[
                    "source_id"
                ].strip():
                    findings.append(f"{label}.source_id must be a non-empty string")
                if decision.get("decision") not in {"include", "exclude"}:
                    findings.append(
                        f"{label}.decision must be include or exclude"
                    )
                if not isinstance(decision.get("reason"), str) or not decision[
                    "reason"
                ].strip():
                    findings.append(f"{label}.reason must be a non-empty string")
        if discovery.get("selection_log_status") != "recorded_at_run_time":
            findings.append(
                "complete provenance requires "
                "discovery.selection_log_status=recorded_at_run_time"
            )
        if payload.get("legacy_exception") is not None:
            findings.append("complete provenance must not declare legacy_exception")
        return

    if status != "legacy_incomplete":
        findings.append("provenance_status must be complete or legacy_incomplete")
        return

    exception = payload.get("legacy_exception")
    if not isinstance(exception, dict):
        findings.append("legacy_incomplete provenance requires legacy_exception")
        return
    exception_id = exception.get("id")
    expected = KNOWN_LEGACY_LITERATURE_EXCEPTIONS.get(exception_id)
    if expected is None:
        findings.append(
            "legacy_exception.id is not an approved historical exception"
        )
        return
    if payload.get("run_date") != expected["run_date"]:
        findings.append(
            "legacy_exception applies only to its recorded historical run_date"
        )
    missing_fields = exception.get("missing_fields")
    if not isinstance(missing_fields, list) or set(missing_fields) != expected[
        "missing_fields"
    ]:
        findings.append(
            "legacy_exception.missing_fields does not match the approved exception"
        )
    if not isinstance(exception.get("reason"), str) or not exception["reason"].strip():
        findings.append("legacy_exception.reason must be a non-empty string")
    if tool.get("source_commit") is not None:
        findings.append(
            "legacy exception must keep unknown tool.source_commit as null"
        )
    if tool.get("source_commit_status") != "not_recorded_at_run_time":
        findings.append(
            "legacy exception requires tool.source_commit_status=not_recorded_at_run_time"
        )
    if discovery.get("queries") is not None:
        findings.append("legacy exception must keep unknown discovery.queries as null")
    if discovery.get("queries_status") != "not_recorded_at_run_time":
        findings.append(
            "legacy exception requires "
            "discovery.queries_status=not_recorded_at_run_time"
        )
    if discovery.get("selection_log") is not None:
        findings.append(
            "legacy exception must keep unknown discovery.selection_log as null"
        )
    if discovery.get("selection_log_status") != "not_recorded_at_run_time":
        findings.append(
            "legacy exception requires "
            "discovery.selection_log_status=not_recorded_at_run_time"
        )
    future_requirements = payload.get("future_run_requirements")
    if (
        not isinstance(future_requirements, list)
        or not expected["missing_fields"].issubset(set(future_requirements))
    ):
        findings.append(
            "future_run_requirements must require every field missing from the legacy run"
        )


def _audit_literature_topics(
    topics: Any,
    *,
    findings: list[str],
) -> None:
    if not isinstance(topics, list) or not topics:
        findings.append("topics must be a non-empty list")
        return
    seen_slugs: set[str] = set()
    seen_arxiv: set[str] = set()
    for index, topic in enumerate(topics):
        label = f"topics[{index}]"
        if not isinstance(topic, dict):
            findings.append(f"{label} must be a JSON object")
            continue
        slug = topic.get("slug")
        if not isinstance(slug, str) or not slug:
            findings.append(f"{label}.slug must be a non-empty string")
        elif slug in seen_slugs:
            findings.append(f"{label}.slug is duplicated: {slug}")
        else:
            seen_slugs.add(slug)
        arxiv_ids = topic.get("arxiv")
        if (
            not isinstance(arxiv_ids, list)
            or not arxiv_ids
            or not all(
                isinstance(identifier, str) and ARXIV_ID.fullmatch(identifier)
                for identifier in arxiv_ids
            )
        ):
            findings.append(f"{label}.arxiv must be a non-empty list of arXiv IDs")
            continue
        duplicates = seen_arxiv.intersection(arxiv_ids)
        if duplicates:
            findings.append(
                f"{label}.arxiv duplicates IDs from another topic: {sorted(duplicates)}"
            )
        seen_arxiv.update(arxiv_ids)


def _resolve_repo_path(
    root: Path,
    value: Any,
    *,
    label: str,
    findings: list[str],
    suffix: str | None = None,
) -> Path | None:
    if not isinstance(value, str) or not value:
        findings.append(f"{label} must be a non-empty repository-relative path")
        return None
    if suffix is not None and not value.endswith(suffix):
        findings.append(f"{label} must end with {suffix}")
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        findings.append(f"{label} escapes the repository")
        return None
    if not value.startswith((".knowledge/", "experiments/records/")):
        findings.append(
            f"{label} must be below .knowledge/ or experiments/records/"
        )
    return path


def _read_utf8_record(
    path: Path,
    *,
    label: str,
    findings: list[str],
) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        findings.append(f"{label} is missing: {path}")
        return None
    except UnicodeDecodeError as error:
        findings.append(f"{label} is not valid UTF-8: {error}")
        return None
    for fragment in MOJIBAKE_FRAGMENTS:
        if fragment in text:
            findings.append(f"{label} contains mojibake marker {fragment!r}")
    if FLOATING_GITHUB_REF.search(text):
        findings.append(f"{label} cites a floating GitHub main ref; pin the commit")
    return text


def _bib_keys(text: str) -> set[str]:
    return set(BIB_ENTRY.findall(text))


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
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    if (
        payload.get("record_type") == LITERATURE_SURVEY_RECORD_TYPE
        and payload.get("provenance_status") == "legacy_incomplete"
    ):
        exception = payload.get("legacy_exception", {})
        print(
            "passed with approved legacy provenance exception "
            f"{exception.get('id')}: {args.manifest}"
        )
    else:
        print(f"passed: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
