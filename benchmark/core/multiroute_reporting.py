"""Strict aggregate-only reporting for matched M1/T1/G1 grading studies.

This module deliberately consumes only public aggregate comparison reports and
opaque SHA-256 lineage commitments.  Private submissions, gold, transcripts,
per-student scores, prompts, and model outputs never enter the rendered
dashboard.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .course_metrics import CourseMetricsError, assert_privacy_safe_comparison
from .route_lineage import canonicalize_public_route_lineage_binding


ROUTE_ORDER = ("M1", "G1-Codex", "G1-DeepSeek")
ROUTE_LABELS = {
    "M1": "Direct multimodal grading",
    "G1-Codex": "Transcript grading - Codex",
    "G1-DeepSeek": "Transcript grading - DeepSeek",
}
METRIC_FIELDS = (
    "exact_agreement",
    "macro_accuracy",
    "subquestion_mae",
    "total_score_mae",
    "within_1_point_rate",
    "severe_error_rate",
    "mean_signed_error",
)

_PRIVACY = {
    "aggregate_only": True,
    "student_ids_included": False,
    "per_student_scores_included": False,
    "raw_answers_included": False,
    "model_evidence_included": False,
    "private_paths_included": False,
}
_COMPARISON_PROVENANCE = {
    "run_validation": "passed",
    "course_metadata": "matched",
    "population": "matched_by_exact_question_coverage",
    "data_snapshot": "matched",
}
_SUPPLEMENTARY_NOTE = (
    "This dashboard is supplementary to the aggregate pairwise metric reports. "
    "Those reports retain the score unit, metric thresholds, and paired bootstrap "
    "confidence intervals for each comparison."
)
_STATIC_GUARDS = (
    "M1 and T1 may execute in parallel because both independently consume the same frozen images; G1 begins only after T1 passes validation.",
    "The route contract, snapshot commitment, and full T1-to-G1 lineage binding must all match before this dashboard can be rendered.",
    "This report is aggregate-only and contains no student identifiers, individual scores, answers, transcripts, evidence, prompts, responses, or private paths.",
    "Development or calibration evidence does not by itself authorize held-out or production grading.",
)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ANONYMOUS_STUDENT_ID = re.compile(r"\bS\d{3,}\b")
_ABSOLUTE_PATH = re.compile(r"(?:^[A-Za-z]:[\\/]|^[\\/]{2}|^/[A-Za-z]|[A-Za-z]:[\\/])")
_PRIVATE_PATH = re.compile(r"(?i)(?:^|[\\/])(?:data|\.private-data|local)(?:[\\/]|$)")
_FORBIDDEN_KEYS = frozenset(
    {
        "student_id",
        "student_ids",
        "individual_scores",
        "per_student_scores",
        "scores",
        "raw_text",
        "raw_answer",
        "raw_answers",
        "answer",
        "answers",
        "evidence",
        "extracted_evidence",
        "feedback",
        "prompt",
        "prompts",
        "transcript",
        "transcripts",
        "response",
        "responses",
        "input_images",
        "inputs",
        "path",
        "paths",
        "private_path",
        "source_path",
        "command",
        "commands",
        "packet",
        "packets",
    }
)
_SOURCE_TOP_LEVEL = {
    "schema_version",
    "record_type",
    "generated_at",
    "course",
    "population",
    "metric_policy",
    "comparison_provenance",
    "baseline_run",
    "candidate_run",
    "baseline",
    "candidate",
    "candidate_minus_baseline",
    "bootstrap",
    "privacy",
}
_SOURCE_RUN_FIELDS = {
    "source_kind",
    "validation_status",
    "course_metadata",
    "students_expected",
    "students_passed",
    "students_failed",
    "record_type",
    "provider",
    "engine",
    "model",
    "input_mode",
    "condition",
    "experiment_condition",
    "task",
    "split",
    "run_id",
    "source_run_id",
    "packet_hash",
    "prompt_hash",
    "rubric_hash",
    "data_snapshot_hash",
    "text_source_hash",
    "source_transcription_packet_hash",
}
_SOURCE_METRIC_FIELDS = set(METRIC_FIELDS) | {"per_question", "confidence_accuracy"}


class MultiRouteReportError(ValueError):
    """A display-safe error raised when a public report would be unsafe."""


def build_t1_readiness_summary(
    validation: Mapping[str, Any], *, run_metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Project private T1 validation and run metadata to an aggregate record.

    Runner validation normally contains a private ``rows`` list.  Only status
    and aggregate counts are selected; the separate run-metadata projection
    supplies the opaque binding required to prove the later G1 source chain.
    """

    status = _normalise_status(validation.get("status"))
    expected = _require_nonnegative_int(
        validation.get("students_expected"), "students_expected"
    )
    passed = _require_nonnegative_int(
        validation.get("students_passed"), "students_passed"
    )
    failed = _require_nonnegative_int(
        validation.get("students_failed"), "students_failed"
    )
    if expected == 0 or passed + failed != expected:
        raise MultiRouteReportError("T1 aggregate coverage is inconsistent")
    ready_for_g1 = status == "passed" and passed == expected and failed == 0
    if status == "passed" and not ready_for_g1:
        raise MultiRouteReportError("a passed T1 validation must have complete coverage")
    run = _project_t1_run_metadata(run_metadata, validation_status=status)
    result = {
        "schema_version": 1,
        "record_type": "aggregate_t1_readiness",
        "route": "T1",
        "status": status,
        "students_expected": expected,
        "students_passed": passed,
        "students_failed": failed,
        "ready_for_g1": ready_for_g1,
        "run": run,
        "privacy": dict(_PRIVACY),
    }
    return canonicalize_t1_readiness(result)


def write_t1_readiness_summary(
    validation_path: Path, output_path: Path, *, run_metadata_path: Path
) -> dict[str, Any]:
    """Write a public aggregate projection of one local T1 run."""

    summary = build_t1_readiness_summary(
        _read_json_object(validation_path, "T1 validation"),
        run_metadata=_read_json_object(run_metadata_path, "T1 run metadata"),
    )
    _write_json_atomic(output_path, summary)
    return summary


def canonicalize_t1_readiness(readiness: Mapping[str, Any]) -> dict[str, Any]:
    """Strictly validate and rebuild the public T1 readiness schema."""

    assert_privacy_safe_multi_route_report(readiness)
    payload = dict(readiness)
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "record_type",
            "route",
            "status",
            "students_expected",
            "students_passed",
            "students_failed",
            "ready_for_g1",
            "run",
            "privacy",
        },
        "T1 readiness",
    )
    if payload["schema_version"] != 1 or payload["record_type"] != "aggregate_t1_readiness":
        raise MultiRouteReportError("T1 readiness has an unsupported schema")
    if payload["route"] != "T1" or payload["privacy"] != _PRIVACY:
        raise MultiRouteReportError("T1 readiness route or privacy declaration is invalid")
    status = _normalise_status(payload["status"])
    expected = _require_nonnegative_int(payload["students_expected"], "students_expected")
    passed = _require_nonnegative_int(payload["students_passed"], "students_passed")
    failed = _require_nonnegative_int(payload["students_failed"], "students_failed")
    ready_for_g1 = payload["ready_for_g1"]
    if not isinstance(ready_for_g1, bool):
        raise MultiRouteReportError("T1 ready_for_g1 must be boolean")
    expected_ready = status == "passed" and expected > 0 and passed == expected and failed == 0
    if ready_for_g1 != expected_ready:
        raise MultiRouteReportError("T1 readiness does not match its aggregate coverage")
    return {
        "schema_version": 1,
        "record_type": "aggregate_t1_readiness",
        "route": "T1",
        "status": status,
        "students_expected": expected,
        "students_passed": passed,
        "students_failed": failed,
        "ready_for_g1": ready_for_g1,
        "run": _canonical_t1_run(
            _mapping(payload["run"], "T1 run"), expected_status=status
        ),
        "privacy": dict(_PRIVACY),
    }


def canonicalize_public_route_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the generic public execution contract for the three routes."""

    assert_privacy_safe_multi_route_report(contract)
    payload = dict(contract)
    _require_exact_keys(
        payload,
        {"schema_version", "record_type", "privacy", "course", "scope", "routes"},
        "route contract",
    )
    if payload["schema_version"] != 1 or payload["record_type"] != "public_multi_route_contract":
        raise MultiRouteReportError("route contract has an unsupported schema")
    if payload["privacy"] != _PRIVACY:
        raise MultiRouteReportError("route contract privacy declaration is invalid")
    course = _normalise_contract_course(_mapping(payload["course"], "contract course"))
    scope = _normalise_scope(_mapping(payload["scope"], "contract scope"))
    routes_payload = _mapping(payload["routes"], "contract routes")
    _require_exact_keys(routes_payload, set(ROUTE_ORDER), "contract routes")
    routes = {
        route: _normalise_contract_route(
            route, _mapping(routes_payload[route], f"{route} contract")
        )
        for route in ROUTE_ORDER
    }
    if (routes["G1-Codex"]["provider"], routes["G1-Codex"]["model"]) == (
        routes["G1-DeepSeek"]["provider"],
        routes["G1-DeepSeek"]["model"],
    ):
        raise MultiRouteReportError(
            "G1-Codex and G1-DeepSeek must declare distinct provider/model pairs"
        )
    return {
        "schema_version": 1,
        "record_type": "public_multi_route_contract",
        "privacy": dict(_PRIVACY),
        "course": course,
        "scope": scope,
        "routes": routes,
    }


def build_multi_route_report(
    *,
    m1_metrics: Mapping[str, Any],
    g1_codex_metrics: Mapping[str, Any],
    g1_deepseek_metrics: Mapping[str, Any],
    t1_readiness: Mapping[str, Any],
    route_contract: Mapping[str, Any],
    g1_codex_lineage: Mapping[str, Any],
    g1_deepseek_lineage: Mapping[str, Any],
    m1_side: str = "baseline",
    g1_codex_side: str = "candidate",
    g1_deepseek_side: str = "candidate",
) -> dict[str, Any]:
    """Build a strict public dashboard from completed aggregate artifacts."""

    contract = canonicalize_public_route_contract(route_contract)
    readiness = canonicalize_t1_readiness(t1_readiness)
    if not readiness["ready_for_g1"]:
        raise MultiRouteReportError("T1 readiness is not complete; G1 cannot be reported")
    routes = [
        _extract_route("M1", m1_metrics, m1_side, contract),
        _extract_route("G1-Codex", g1_codex_metrics, g1_codex_side, contract),
        _extract_route(
            "G1-DeepSeek", g1_deepseek_metrics, g1_deepseek_side, contract
        ),
    ]
    _require_shared_course_and_population(routes, contract)
    lineage = _bind_lineages(
        routes=routes,
        readiness=readiness,
        contract=contract,
        codex_lineage=g1_codex_lineage,
        deepseek_lineage=g1_deepseek_lineage,
    )
    report = {
        "schema_version": 1,
        "record_type": "aggregate_multi_route_grading_report",
        "privacy": dict(_PRIVACY),
        "course": routes[0]["course"],
        "population": routes[0]["population"],
        "route_contract": contract,
        "t1_readiness": readiness,
        "lineage": lineage,
        "routes": routes,
        "interpretation_guards": list(_STATIC_GUARDS),
        "supplementary_note": _SUPPLEMENTARY_NOTE,
    }
    return canonicalize_public_multi_route_report(report)


def build_multi_route_report_from_paths(
    *,
    m1_metrics_path: Path,
    g1_codex_metrics_path: Path,
    g1_deepseek_metrics_path: Path,
    t1_readiness_path: Path,
    route_contract_path: Path,
    g1_codex_lineage_path: Path,
    g1_deepseek_lineage_path: Path,
    m1_side: str = "baseline",
    g1_codex_side: str = "candidate",
    g1_deepseek_side: str = "candidate",
) -> dict[str, Any]:
    """Load safe aggregate artifacts and build the dashboard without a model call."""

    return build_multi_route_report(
        m1_metrics=_read_json_object(m1_metrics_path, "M1 aggregate metrics"),
        g1_codex_metrics=_read_json_object(
            g1_codex_metrics_path, "G1-Codex aggregate metrics"
        ),
        g1_deepseek_metrics=_read_json_object(
            g1_deepseek_metrics_path, "G1-DeepSeek aggregate metrics"
        ),
        t1_readiness=_read_json_object(t1_readiness_path, "T1 aggregate readiness"),
        route_contract=_read_json_object(route_contract_path, "route contract"),
        g1_codex_lineage=_read_json_object(
            g1_codex_lineage_path, "G1-Codex public lineage"
        ),
        g1_deepseek_lineage=_read_json_object(
            g1_deepseek_lineage_path, "G1-DeepSeek public lineage"
        ),
        m1_side=m1_side,
        g1_codex_side=g1_codex_side,
        g1_deepseek_side=g1_deepseek_side,
    )


def canonicalize_public_multi_route_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Reject unknown fields and rebuild the only serialisable report shape."""

    assert_privacy_safe_multi_route_report(report)
    payload = dict(report)
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "record_type",
            "privacy",
            "course",
            "population",
            "route_contract",
            "t1_readiness",
            "lineage",
            "routes",
            "interpretation_guards",
            "supplementary_note",
        },
        "multi-route report",
    )
    if payload["schema_version"] != 1 or payload["record_type"] != "aggregate_multi_route_grading_report":
        raise MultiRouteReportError("multi-route report has an unsupported schema")
    if payload["privacy"] != _PRIVACY:
        raise MultiRouteReportError("multi-route report privacy declaration is invalid")
    if payload["interpretation_guards"] != list(_STATIC_GUARDS):
        raise MultiRouteReportError("multi-route report interpretation guards are invalid")
    if payload["supplementary_note"] != _SUPPLEMENTARY_NOTE:
        raise MultiRouteReportError("multi-route report supplementary note is invalid")
    course = _normalise_course(_mapping(payload["course"], "report course"))
    population = _normalise_population(_mapping(payload["population"], "population"))
    contract = canonicalize_public_route_contract(
        _mapping(payload["route_contract"], "route contract")
    )
    readiness = canonicalize_t1_readiness(
        _mapping(payload["t1_readiness"], "T1 readiness")
    )
    lineage = _normalise_report_lineage(_mapping(payload["lineage"], "lineage"))
    route_values = payload["routes"]
    if not isinstance(route_values, list) or len(route_values) != len(ROUTE_ORDER):
        raise MultiRouteReportError("a complete ordered route list is required")
    routes = [
        _canonical_route(route, route_values[index])
        for index, route in enumerate(ROUTE_ORDER)
    ]
    _require_shared_course_and_population(routes, contract)
    if course != routes[0]["course"]:
        raise MultiRouteReportError("report course does not match the selected routes")
    if (
        course["course_id"] != contract["course"]["course_id"]
        or course["assessment_id"] != contract["course"]["assessment_id"]
    ):
        raise MultiRouteReportError("report course does not match the route contract")
    if population != routes[0]["population"]:
        raise MultiRouteReportError("report population does not match the selected routes")
    if not readiness["ready_for_g1"]:
        raise MultiRouteReportError("T1 readiness is not complete")
    _validate_canonical_bindings(routes, readiness, contract, lineage)
    return {
        "schema_version": 1,
        "record_type": "aggregate_multi_route_grading_report",
        "privacy": dict(_PRIVACY),
        "course": course,
        "population": population,
        "route_contract": contract,
        "t1_readiness": readiness,
        "lineage": lineage,
        "routes": routes,
        "interpretation_guards": list(_STATIC_GUARDS),
        "supplementary_note": _SUPPLEMENTARY_NOTE,
    }


def write_multi_route_report(
    report: Mapping[str, Any],
    *,
    output_json: Path,
    output_typst: Path,
    title: str | None = None,
) -> tuple[Path, Path]:
    """Validate/render first, then atomically stage the JSON and Typst pair."""

    canonical = canonicalize_public_multi_route_report(report)
    typst = _render_canonical_typst(canonical, title=title)
    json_text = json.dumps(canonical, indent=2, sort_keys=True) + "\n"
    _write_pair_after_render(output_json, json_text, output_typst, typst)
    return Path(output_json), Path(output_typst)


def render_multi_route_typst(
    report: Mapping[str, Any], *, title: str | None = None
) -> str:
    """Render the strict canonical report as a self-contained Typst dashboard."""

    return _render_canonical_typst(canonicalize_public_multi_route_report(report), title=title)


def assert_privacy_safe_multi_route_report(report: Mapping[str, Any]) -> None:
    """Reject individual, raw-content, and private-path data recursively."""

    def visit(value: Any, location: str = "$") -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_text = str(key)
                if key_text.lower() in _FORBIDDEN_KEYS:
                    raise MultiRouteReportError(
                        f"private key {key_text!r} detected at {location}"
                    )
                visit(child, f"{location}.{key_text}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{location}[{index}]")
        elif isinstance(value, str):
            if _ANONYMOUS_STUDENT_ID.search(value):
                raise MultiRouteReportError(
                    f"anonymous student ID detected at {location}"
                )
            if _ABSOLUTE_PATH.search(value) or _PRIVATE_PATH.search(value):
                raise MultiRouteReportError(f"private path detected at {location}")

    visit(report)


def _extract_route(
    route: str,
    metric_report: Mapping[str, Any],
    side: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    if side not in {"baseline", "candidate"}:
        raise MultiRouteReportError(f"{route} metric side must be baseline or candidate")
    report = dict(metric_report)
    try:
        assert_privacy_safe_comparison(report)
    except CourseMetricsError as error:
        raise MultiRouteReportError(str(error)) from error
    _require_allowed_keys(report, _SOURCE_TOP_LEVEL, f"{route} metric report")
    if report.get("schema_version") != 1 or report.get("record_type") != "course_generic_run_metrics_comparison":
        raise MultiRouteReportError(f"{route} source is not a course comparison report")
    if report.get("privacy") != _PRIVACY:
        raise MultiRouteReportError(f"{route} source privacy declaration is invalid")
    course = _normalise_course(_mapping(report.get("course"), f"{route} course"))
    population = _normalise_population(
        _mapping(report.get("population"), f"{route} population")
    )
    provenance = _normalise_provenance(
        _mapping(report.get("comparison_provenance"), f"{route} provenance")
    )
    if provenance != _COMPARISON_PROVENANCE:
        raise MultiRouteReportError(
            f"{route} pairwise comparison must have passed, matched provenance"
        )
    metrics = _normalise_metrics(
        _mapping(report.get(side), f"{route} selected metrics")
    )
    run = _normalise_source_run(
        _mapping(report.get(f"{side}_run"), f"{route} selected run")
    )
    _validate_route_run(route, run, contract)
    return {
        "route": route,
        "label": ROUTE_LABELS[route],
        "metric_side": side,
        "course": course,
        "population": population,
        "run": run,
        "comparison_provenance": dict(_COMPARISON_PROVENANCE),
        "metrics": metrics,
    }


def _bind_lineages(
    *,
    routes: list[dict[str, Any]],
    readiness: Mapping[str, Any],
    contract: Mapping[str, Any],
    codex_lineage: Mapping[str, Any],
    deepseek_lineage: Mapping[str, Any],
) -> dict[str, str]:
    try:
        codex = canonicalize_public_route_lineage_binding(codex_lineage)
        deepseek = canonicalize_public_route_lineage_binding(deepseek_lineage)
    except ValueError as error:
        raise MultiRouteReportError(str(error)) from error
    course = contract["course"]
    scope = contract["scope"]
    for label, binding in (("G1-Codex", codex), ("G1-DeepSeek", deepseek)):
        if binding["course"] != course:
            raise MultiRouteReportError(f"{label} lineage course does not match contract")
        if binding["scope"]["data_snapshot_hash"] != scope["data_snapshot_hash"]:
            raise MultiRouteReportError(f"{label} lineage snapshot does not match contract")
    for field in ("packet_hash", "data_snapshot_hash", "rubric_hash"):
        if codex["m1"][field] != deepseek["m1"][field]:
            raise MultiRouteReportError("G1 lineage bindings do not share the same M1")
    for field in (
        "packet_hash",
        "run_id",
        "data_snapshot_hash",
        "task",
        "input_mode",
        "condition",
        "validation_status",
    ):
        if codex["t1"][field] != deepseek["t1"][field]:
            raise MultiRouteReportError("G1 lineage bindings do not share the same T1")
    if codex["scope"]["roster_hash"] != deepseek["scope"]["roster_hash"]:
        raise MultiRouteReportError("G1 lineage bindings do not share the same anonymous roster")
    for field in (
        "data_snapshot_hash",
        "rubric_hash",
        "text_source_hash",
        "source_run_id",
        "source_transcription_packet_hash",
    ):
        if codex["g1"][field] != deepseek["g1"][field]:
            raise MultiRouteReportError("G1 lineage bindings do not share the same T1 source")
    result = {
        "data_snapshot_hash": scope["data_snapshot_hash"],
        "roster_hash": codex["scope"]["roster_hash"],
        "m1_packet_hash": codex["m1"]["packet_hash"],
        "t1_packet_hash": codex["t1"]["packet_hash"],
        "t1_run_id": codex["t1"]["run_id"],
        "g1_text_source_hash": codex["g1"]["text_source_hash"],
        "g1_source_run_id": codex["g1"]["source_run_id"],
        "g1_source_transcription_packet_hash": codex["g1"][
            "source_transcription_packet_hash"
        ],
        "rubric_hash": codex["g1"]["rubric_hash"],
        # Retain distinct G1 packet commitments; only their T1 source must
        # match.  They legitimately use different scoring prompts/packets.
        "g1_codex_packet_hash": codex["g1"]["packet_hash"],
        "g1_deepseek_packet_hash": deepseek["g1"]["packet_hash"],
    }
    _validate_canonical_bindings(routes, readiness, contract, result, codex, deepseek)
    return result


def _validate_canonical_bindings(
    routes: list[dict[str, Any]],
    readiness: Mapping[str, Any],
    contract: Mapping[str, Any],
    lineage: Mapping[str, Any],
    codex_binding: Mapping[str, Any] | None = None,
    deepseek_binding: Mapping[str, Any] | None = None,
) -> None:
    route_by_id = {route["route"]: route for route in routes}
    if set(route_by_id) != set(ROUTE_ORDER):
        raise MultiRouteReportError("canonical route identifiers are invalid")
    snapshot = contract["scope"]["data_snapshot_hash"]
    if lineage["data_snapshot_hash"] != snapshot:
        raise MultiRouteReportError("lineage snapshot does not match the route contract")
    t1_run = readiness["run"]
    for field, expected in (
        ("packet_hash", lineage["t1_packet_hash"]),
        ("run_id", lineage["t1_run_id"]),
        ("data_snapshot_hash", snapshot),
        ("task", "transcribe"),
        ("input_mode", "multimodal"),
        ("condition", "T1"),
        ("validation_status", "passed"),
    ):
        if t1_run[field] != expected:
            raise MultiRouteReportError(f"T1 readiness {field} does not match lineage")
    m1 = route_by_id["M1"]["run"]
    if m1["packet_hash"] != lineage["m1_packet_hash"]:
        raise MultiRouteReportError("M1 run packet_hash does not match lineage")
    if m1["data_snapshot_hash"] != snapshot:
        raise MultiRouteReportError("M1 run snapshot does not match contract")
    if m1["rubric_hash"] != lineage["rubric_hash"]:
        raise MultiRouteReportError("M1 run rubric_hash does not match lineage")
    g1_expected = {
        "G1-Codex": codex_binding["g1"] if codex_binding is not None else None,
        "G1-DeepSeek": deepseek_binding["g1"] if deepseek_binding is not None else None,
    }
    for route_name in ("G1-Codex", "G1-DeepSeek"):
        run = route_by_id[route_name]["run"]
        if run["data_snapshot_hash"] != snapshot:
            raise MultiRouteReportError(f"{route_name} snapshot does not match contract")
        if run["rubric_hash"] != lineage["rubric_hash"]:
            raise MultiRouteReportError(f"{route_name} rubric_hash does not match lineage")
        for field, expected in (
            ("text_source_hash", lineage["g1_text_source_hash"]),
            ("source_run_id", lineage["g1_source_run_id"]),
            (
                "source_transcription_packet_hash",
                lineage["g1_source_transcription_packet_hash"],
            ),
        ):
            if run[field] != expected:
                raise MultiRouteReportError(f"{route_name} {field} does not match T1 lineage")
        expected_binding = g1_expected[route_name]
        expected_packet = (
            expected_binding["packet_hash"]
            if expected_binding is not None
            else lineage[
                "g1_codex_packet_hash"
                if route_name == "G1-Codex"
                else "g1_deepseek_packet_hash"
            ]
        )
        if run["packet_hash"] != expected_packet:
            raise MultiRouteReportError(f"{route_name} packet_hash does not match its lineage")


def _canonical_route(route: str, value: Any) -> dict[str, Any]:
    payload = _mapping(value, f"{route} route")
    _require_exact_keys(
        payload,
        {"route", "label", "metric_side", "course", "population", "run", "comparison_provenance", "metrics"},
        f"{route} route",
    )
    if payload["route"] != route or payload["label"] != ROUTE_LABELS[route]:
        raise MultiRouteReportError(f"{route} route identity is invalid")
    if payload["metric_side"] not in {"baseline", "candidate"}:
        raise MultiRouteReportError(f"{route} metric_side is invalid")
    provenance = _normalise_provenance(
        _mapping(payload["comparison_provenance"], f"{route} provenance")
    )
    if provenance != _COMPARISON_PROVENANCE:
        raise MultiRouteReportError(f"{route} provenance is not a passed matched comparison")
    return {
        "route": route,
        "label": ROUTE_LABELS[route],
        "metric_side": payload["metric_side"],
        "course": _normalise_course(_mapping(payload["course"], f"{route} course")),
        "population": _normalise_population(
            _mapping(payload["population"], f"{route} population")
        ),
        "run": _canonical_report_run(_mapping(payload["run"], f"{route} run")),
        "comparison_provenance": dict(_COMPARISON_PROVENANCE),
        "metrics": _normalise_metrics(
            _mapping(payload["metrics"], f"{route} metrics"), strict=True
        ),
    }


def _normalise_report_lineage(lineage: Mapping[str, Any]) -> dict[str, str]:
    _require_exact_keys(
        lineage,
        {
            "data_snapshot_hash",
            "roster_hash",
            "m1_packet_hash",
            "t1_packet_hash",
            "t1_run_id",
            "g1_text_source_hash",
            "g1_source_run_id",
            "g1_source_transcription_packet_hash",
            "rubric_hash",
            "g1_codex_packet_hash",
            "g1_deepseek_packet_hash",
        },
        "report lineage",
    )
    return {
        "data_snapshot_hash": _sha256(lineage["data_snapshot_hash"], "snapshot"),
        "roster_hash": _sha256(lineage["roster_hash"], "roster_hash"),
        "m1_packet_hash": _sha256(lineage["m1_packet_hash"], "M1 packet_hash"),
        "t1_packet_hash": _sha256(lineage["t1_packet_hash"], "T1 packet_hash"),
        "t1_run_id": _safe_identifier(lineage["t1_run_id"], "T1 run_id"),
        "g1_text_source_hash": _sha256(
            lineage["g1_text_source_hash"], "G1 text_source_hash"
        ),
        "g1_source_run_id": _safe_identifier(
            lineage["g1_source_run_id"], "G1 source_run_id"
        ),
        "g1_source_transcription_packet_hash": _sha256(
            lineage["g1_source_transcription_packet_hash"],
            "G1 source_transcription_packet_hash",
        ),
        "rubric_hash": _sha256(lineage["rubric_hash"], "shared rubric_hash"),
        "g1_codex_packet_hash": _sha256(
            lineage["g1_codex_packet_hash"], "G1-Codex packet_hash"
        ),
        "g1_deepseek_packet_hash": _sha256(
            lineage["g1_deepseek_packet_hash"], "G1-DeepSeek packet_hash"
        ),
    }


def _normalise_contract_course(course: Mapping[str, Any]) -> dict[str, str]:
    _require_exact_keys(course, {"course_id", "assessment_id"}, "contract course")
    return {
        "course_id": _safe_identifier(course["course_id"], "course_id"),
        "assessment_id": _safe_identifier(course["assessment_id"], "assessment_id"),
    }


def _normalise_scope(scope: Mapping[str, Any]) -> dict[str, str]:
    _require_exact_keys(scope, {"split", "data_snapshot_hash"}, "contract scope")
    return {
        "split": _safe_identifier(scope["split"], "split"),
        "data_snapshot_hash": _sha256(scope["data_snapshot_hash"], "data_snapshot_hash"),
    }


def _normalise_contract_route(route: str, value: Mapping[str, Any]) -> dict[str, str]:
    _require_exact_keys(
        value,
        {"declared_route", "provider", "model", "condition", "task", "input_mode"},
        f"{route} contract",
    )
    if value["declared_route"] != route:
        raise MultiRouteReportError(f"{route} contract declared_route is invalid")
    result = {
        field: _safe_identifier(value[field], f"{route} {field}")
        for field in ("declared_route", "provider", "model", "condition", "task", "input_mode")
    }
    expected_mode = "multimodal" if route == "M1" else "text-only"
    if result["task"] != "grade" or result["input_mode"] != expected_mode:
        raise MultiRouteReportError(f"{route} contract has an invalid grading mode")
    expected_condition = "M1" if route == "M1" else "G1"
    if result["condition"] != expected_condition:
        raise MultiRouteReportError(
            f"{route} contract must declare condition {expected_condition}"
        )
    return result


def _normalise_course(course: Mapping[str, Any]) -> dict[str, Any]:
    _require_exact_keys(
        course,
        {"course_id", "assessment_id", "score_unit", "question_count", "max_total"},
        "course",
    )
    return {
        "course_id": _safe_identifier(course["course_id"], "course_id"),
        "assessment_id": _safe_identifier(course["assessment_id"], "assessment_id"),
        "score_unit": _safe_identifier(course["score_unit"], "score_unit"),
        "question_count": _require_positive_int(course["question_count"], "question_count"),
        "max_total": _number(course["max_total"], "max_total"),
    }


def _normalise_population(population: Mapping[str, Any]) -> dict[str, int]:
    _require_exact_keys(population, {"student_count", "score_row_count"}, "population")
    return {
        "student_count": _require_positive_int(
            population["student_count"], "student_count"
        ),
        "score_row_count": _require_positive_int(
            population["score_row_count"], "score_row_count"
        ),
    }


def _normalise_metrics(metrics: Mapping[str, Any], *, strict: bool = False) -> dict[str, float]:
    if strict:
        _require_exact_keys(metrics, set(METRIC_FIELDS), "route metrics")
    else:
        _require_allowed_keys(metrics, _SOURCE_METRIC_FIELDS, "source metrics")
    result: dict[str, float] = {}
    for field in METRIC_FIELDS:
        value = _number(metrics.get(field), field)
        if field in {
            "exact_agreement",
            "macro_accuracy",
            "within_1_point_rate",
            "severe_error_rate",
        }:
            _require_rate(value, field)
        result[field] = value
    return result


def _normalise_provenance(provenance: Mapping[str, Any]) -> dict[str, str]:
    _require_exact_keys(provenance, set(_COMPARISON_PROVENANCE), "comparison provenance")
    return {
        field: _safe_identifier(provenance[field], field)
        for field in _COMPARISON_PROVENANCE
    }


def _normalise_source_run(run: Mapping[str, Any]) -> dict[str, Any]:
    _require_allowed_keys(run, _SOURCE_RUN_FIELDS, "source run")
    return _build_canonical_run(run, allow_missing=True)


def _canonical_report_run(run: Mapping[str, Any]) -> dict[str, Any]:
    _require_exact_keys(run, _canonical_run_keys(), "report run")
    # The canonical public shape retains optional source-lineage fields as
    # explicit nulls for routes that cannot have them (for example M1 has no
    # transcription source).  Route-role validation below decides what is
    # required rather than accepting arbitrary missing keys.
    return _build_canonical_run(run, allow_missing=True)


def _build_canonical_run(run: Mapping[str, Any], *, allow_missing: bool) -> dict[str, Any]:
    def optional_identifier(field: str) -> str | None:
        value = run.get(field)
        if value is None and allow_missing:
            return None
        return _safe_identifier(value, field)

    def optional_hash(field: str) -> str | None:
        value = run.get(field)
        if value is None and allow_missing:
            return None
        return _sha256(value, field)

    result = {
        "source_kind": optional_identifier("source_kind"),
        "validation_status": optional_identifier("validation_status"),
        "course_metadata": optional_identifier("course_metadata"),
        "provider": optional_identifier("provider"),
        "engine": optional_identifier("engine"),
        "model": optional_identifier("model"),
        "condition": optional_identifier("condition"),
        "experiment_condition": optional_identifier("experiment_condition"),
        "task": optional_identifier("task"),
        "input_mode": optional_identifier("input_mode"),
        "split": optional_identifier("split"),
        "run_id": optional_identifier("run_id"),
        "source_run_id": optional_identifier("source_run_id"),
        "packet_hash": optional_hash("packet_hash"),
        "prompt_hash": optional_hash("prompt_hash"),
        "rubric_hash": optional_hash("rubric_hash"),
        "data_snapshot_hash": optional_hash("data_snapshot_hash"),
        "text_source_hash": optional_hash("text_source_hash"),
        "source_transcription_packet_hash": optional_hash(
            "source_transcription_packet_hash"
        ),
    }
    return result


def _canonical_run_keys() -> set[str]:
    return {
        "source_kind",
        "validation_status",
        "course_metadata",
        "provider",
        "engine",
        "model",
        "condition",
        "experiment_condition",
        "task",
        "input_mode",
        "split",
        "run_id",
        "source_run_id",
        "packet_hash",
        "prompt_hash",
        "rubric_hash",
        "data_snapshot_hash",
        "text_source_hash",
        "source_transcription_packet_hash",
    }


def _validate_route_run(
    route: str, run: Mapping[str, Any], contract: Mapping[str, Any]
) -> None:
    expected = contract["routes"][route]
    for field in ("provider", "model", "condition", "task", "input_mode"):
        if run[field] != expected[field]:
            raise MultiRouteReportError(f"{route} run {field} does not match contract")
    if run["validation_status"] != "passed" or run["course_metadata"] != "matched":
        raise MultiRouteReportError(f"{route} run is not a passed matching course run")
    if run["split"] != contract["scope"]["split"]:
        raise MultiRouteReportError(f"{route} run split does not match contract")
    if run["data_snapshot_hash"] != contract["scope"]["data_snapshot_hash"]:
        raise MultiRouteReportError(f"{route} run snapshot does not match contract")
    for field in ("run_id", "packet_hash", "prompt_hash", "rubric_hash"):
        if run[field] is None:
            raise MultiRouteReportError(f"{route} run is missing {field}")
    if route == "M1":
        if run["source_run_id"] is not None or run["source_transcription_packet_hash"] is not None:
            raise MultiRouteReportError("M1 must not declare a T1 transcript source")
    else:
        for field in (
            "text_source_hash",
            "source_run_id",
            "source_transcription_packet_hash",
        ):
            if run[field] is None:
                raise MultiRouteReportError(f"{route} run is missing {field}")


def _project_t1_run_metadata(
    metadata: Mapping[str, Any], *, validation_status: str
) -> dict[str, Any]:
    if metadata.get("record_type") != "model_packet_run" or metadata.get("dry_run") is not False:
        raise MultiRouteReportError("T1 run metadata must represent a non-dry model run")
    result = {
        "run_id": _safe_identifier(metadata.get("run_id"), "T1 run_id"),
        "packet_hash": _sha256(metadata.get("packet_hash"), "T1 packet_hash"),
        "data_snapshot_hash": _sha256(
            metadata.get("data_snapshot_hash"), "T1 data_snapshot_hash"
        ),
        "task": _safe_identifier(metadata.get("task"), "T1 task"),
        "input_mode": _safe_identifier(metadata.get("input_mode"), "T1 input_mode"),
        "condition": _safe_identifier(metadata.get("condition"), "T1 condition"),
        "validation_status": _safe_identifier(
            metadata.get("validation_status"), "T1 validation_status"
        ),
    }
    if result["task"] != "transcribe" or result["input_mode"] != "multimodal" or result["condition"] != "T1":
        raise MultiRouteReportError("T1 run metadata has an invalid route role")
    if result["validation_status"] != validation_status:
        raise MultiRouteReportError("T1 validation status does not match run metadata")
    return result


def _canonical_t1_run(
    run: Mapping[str, Any], *, expected_status: str = "passed"
) -> dict[str, str]:
    _require_exact_keys(
        run,
        {
            "run_id",
            "packet_hash",
            "data_snapshot_hash",
            "task",
            "input_mode",
            "condition",
            "validation_status",
        },
        "T1 run",
    )
    result = {
        "run_id": _safe_identifier(run["run_id"], "T1 run_id"),
        "packet_hash": _sha256(run["packet_hash"], "T1 packet_hash"),
        "data_snapshot_hash": _sha256(
            run["data_snapshot_hash"], "T1 data_snapshot_hash"
        ),
        "task": _safe_identifier(run["task"], "T1 task"),
        "input_mode": _safe_identifier(run["input_mode"], "T1 input_mode"),
        "condition": _safe_identifier(run["condition"], "T1 condition"),
        "validation_status": _safe_identifier(
            run["validation_status"], "T1 validation_status"
        ),
    }
    if result["task"] != "transcribe" or result["input_mode"] != "multimodal" or result["condition"] != "T1":
        raise MultiRouteReportError("T1 run has an invalid route role")
    if result["validation_status"] != expected_status:
        raise MultiRouteReportError("T1 run validation_status does not match readiness")
    return result


def _require_shared_course_and_population(
    routes: list[dict[str, Any]], contract: Mapping[str, Any]
) -> None:
    if len(routes) != len(ROUTE_ORDER):
        raise MultiRouteReportError("a complete route set is required")
    course = routes[0]["course"]
    population = routes[0]["population"]
    for route in routes[1:]:
        if route["course"] != course:
            raise MultiRouteReportError("all routes must bind the same course")
        if route["population"] != population:
            raise MultiRouteReportError("all routes must cover the same population")
    if course["course_id"] != contract["course"]["course_id"] or course["assessment_id"] != contract["course"]["assessment_id"]:
        raise MultiRouteReportError("route course does not match the contract")


def _render_canonical_typst(report: Mapping[str, Any], *, title: str | None) -> str:
    if title is not None:
        raise MultiRouteReportError(
            "custom Typst titles are disabled; the public title is derived from the canonical course identifiers"
        )
    title = (
        f"{report['course']['course_id']} {report['course']['assessment_id']} Multi-route Grading Report"
    )
    course = report["course"]
    population = report["population"]
    readiness = report["t1_readiness"]
    scope = report["route_contract"]["scope"]
    lineage = report["lineage"]
    routes = report["routes"]
    lines = [
        f'#set document(title: "{_escape_typst_string(title)}")',
        "#set page(margin: (x: 1.65cm, y: 1.30cm))",
        '#set text(font: "New Computer Modern", size: 9pt)',
        '#let ink = rgb("#17212b")',
        '#let accent = rgb("#256d85")',
        '#let green = rgb("#2d7a5b")',
        '#let soft = rgb("#edf5f7")',
        '#let line = rgb("#d8e4e8")',
        '#let muted = rgb("#63707a")',
        "",
        "#align(center)[",
        f"  #text(size: 18pt, weight: \"bold\", fill: ink)[{_escape_typst_markup(title)}]",
        "]",
        "#align(center)[",
        "  #text(size: 7.5pt, fill: muted)[Aggregate-only supplementary dashboard; detailed thresholds and confidence intervals remain in the pairwise reports.]",
        "]",
        "",
        "== Scope, question, and T1 gate",
        "",
        "#grid(columns: (1fr, 1fr), gutter: 8pt,",
        "  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[",
        f"    #strong[Course / assessment] #text(fill: muted)[{_escape_typst_markup(str(course['course_id']))} / {_escape_typst_markup(str(course['assessment_id']))}]",
        "    #linebreak()",
        f"    #strong[Scope] #text(fill: muted)[{_escape_typst_markup(scope['split'])}; {_short_hash(scope['data_snapshot_hash'])}]",
        "    #linebreak()",
        f"    #strong[Population] #text(fill: muted)[{population['student_count']} submissions; {population['score_row_count']} score rows; {course['score_unit']}]",
        "    #linebreak()",
        "    #strong[Research question] #text(size: 7.5pt, fill: muted)[On this frozen, matched split, how closely do direct multimodal and transcription-to-text grading routes agree with the same frozen reference scores?]",
        "  ],",
        "  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[",
        f"    #strong[T1 readiness] #text(fill: green)[{_escape_typst_markup(readiness['status'])}]",
        "    #linebreak()",
        f"    #text(fill: muted)[{readiness['students_passed']} / {readiness['students_expected']} complete; {readiness['students_failed']} failed]",
        "    #linebreak()",
        f"    #text(size: 8pt, fill: muted)[T1 packet {_short_hash(lineage['t1_packet_hash'])}; run {_escape_typst_markup(lineage['t1_run_id'])}]",
        "    #linebreak()",
        "    #text(size: 7.5pt, fill: muted)[A complete T1 route is required before either text-only G1 route can be reported.]",
        "  ],",
        ")",
        "",
        "== Exact-agreement comparison",
        "",
        "#grid(columns: (29mm, 1fr, 17mm), column-gutter: 6pt, row-gutter: 5pt,",
        "  [#strong[Route]], [#strong[Exact agreement]], [#align(right)[#strong[Value]]],",
    ]
    for route in routes:
        exact = route["metrics"]["exact_agreement"]
        lines.extend(
            [
                f"  [{_escape_typst_markup(route['route'])}],",
                "  [#box(width: 54mm, height: 7pt, fill: line, radius: 3pt)["
                f"#box(width: {54.0 * exact:.2f}mm, height: 7pt, fill: accent, radius: 3pt)[]"
                "]],",
                f"  [#align(right)[{_percent(exact)}]],",
            ]
        )
    lines.extend(
        [
            ")",
            "",
            "== Error and risk metrics",
            "",
            "#table(",
            "  columns: (29mm, 22mm, 22mm, 22mm, 22mm),",
            "  inset: 5pt, stroke: line, align: (left, right, right, right, right),",
            "  table.header([#strong[Route]], [#strong[Total MAE]], [#strong[Within 1]], [#strong[Severe]], [#strong[Bias]]),",
        ]
    )
    for route in routes:
        metrics = route["metrics"]
        lines.append(
            "  [{route}], [{mae}], [{within}], [{severe}], [{bias}],".format(
                route=_escape_typst_markup(route["route"]),
                mae=_decimal(metrics["total_score_mae"]),
                within=_percent(metrics["within_1_point_rate"]),
                severe=_percent(metrics["severe_error_rate"]),
                bias=_signed(metrics["mean_signed_error"]),
            )
        )
    lines.extend(
        [
            ")",
            "",
            "#text(size: 7.4pt, fill: muted)[Metric definitions: exact agreement = an exact score-row match; Total MAE = mean absolute error of submission totals; Within 1 = total error at most 1 point; Severe = total error above 2 points; Bias = mean signed score-row error (route minus reference).]",
            "",
            "== Reproducibility commitments",
            "",
            "#table(",
            "  columns: (25mm, 23mm, 30mm, 30mm, 1fr),",
            "  inset: 4pt, stroke: line, align: (left, left, left, left, left),",
            "  table.header([#strong[Route]], [#strong[Mode]], [#strong[Packet]], [#strong[Prompt]], [#strong[Model]]),",
        ]
    )
    for route in routes:
        run = route["run"]
        lines.append(
            "  [{route}], [{mode}], [{packet}], [{prompt}], [{model}],".format(
                route=_escape_typst_markup(route["route"]),
                mode=_escape_typst_markup(run["input_mode"]),
                packet=_short_hash(run["packet_hash"]),
                prompt=_short_hash(run["prompt_hash"]),
                model=_escape_typst_markup(f"{run['provider']} / {run['model']}"),
            )
        )
    lines.extend(
        [
            ")",
            "",
            "#grid(columns: (1fr, 1fr), gutter: 7pt,",
            "  box(fill: soft, stroke: line, inset: 6pt, radius: 4pt)[",
            "    #strong[Canonical commitments]",
            "    #linebreak()",
            f'    #text(size: 7.1pt, fill: muted)[Snapshot SHA-256: #raw("{scope["data_snapshot_hash"]}")]',
            "    #linebreak()",
            "    #text(size: 7.1pt, fill: muted)[Full packet and prompt SHA-256 commitments remain in canonical public JSON at #raw(\"routes[*].run.packet_hash\") and #raw(\"routes[*].run.prompt_hash\"). The short hashes above are display locators.]",
            "  ],",
            "  box(fill: soft, stroke: line, inset: 6pt, radius: 4pt)[",
            "    #strong[Reproduce / verify]",
            "    #linebreak()",
            "    #text(size: 7.1pt, fill: muted)[Rebuild from the seven aggregate-only inputs; the CLI flag reference is:]",
            "    #linebreak()",
            "    #text(font: \"Cascadia Mono\", size: 6.8pt)[python -m benchmark.core.cli render-multi-route-report --help]",
            "    #linebreak()",
            "    #text(font: \"Cascadia Mono\", size: 6.8pt)[typst compile report.typ report.pdf]",
            "  ],",
            ")",
            "",
            f"#text(size: 8pt, fill: muted)[Shared roster commitment: {_short_hash(lineage['roster_hash'])}. Shared G1 transcript source: {_short_hash(lineage['g1_text_source_hash'])}. M1 and the two G1 packet hashes are intentionally retained per route rather than forced equal.]",
            "",
            "== Limitations, safeguards, and operating rules",
            "",
        ]
    )
    for guard in _STATIC_GUARDS:
        lines.append(f"- {_escape_typst_markup(guard)}")
    lines.extend(["", f"#text(size: 8pt, fill: muted)[{_escape_typst_markup(_SUPPLEMENTARY_NOTE)}]", ""])
    return "\n".join(lines)


def _write_pair_after_render(
    output_json: Path, json_text: str, output_typst: Path, typst_text: str
) -> None:
    output_json = Path(output_json)
    output_typst = Path(output_typst)
    if output_json.resolve() == output_typst.resolve():
        raise MultiRouteReportError(
            "aggregate JSON and Typst outputs must be different paths"
        )
    if output_json.exists() or output_typst.exists():
        raise MultiRouteReportError(
            "refusing to overwrite an existing multi-route report output"
        )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_typst.parent.mkdir(parents=True, exist_ok=True)
    json_stage = _stage_text(output_json.parent, json_text)
    typst_stage = _stage_text(output_typst.parent, typst_text)
    try:
        # The destinations are required to be new.  If either publish fails,
        # remove any newly-published sibling so callers never see a mixed pair.
        os.replace(json_stage, output_json)
        json_stage = None
        os.replace(typst_stage, output_typst)
        typst_stage = None
    except OSError:
        for output in (output_json, output_typst):
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        for staged in (json_stage, typst_stage):
            if staged is None:
                continue
            try:
                Path(staged).unlink(missing_ok=True)
            except OSError:
                pass


def _stage_text(parent: Path, text: str) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", delete=False, dir=parent, suffix=".tmp"
    ) as handle:
        handle.write(text)
        return Path(handle.name)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    text = json.dumps(dict(payload), indent=2, sort_keys=True) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = _stage_text(path.parent, text)
    os.replace(staged, path)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise MultiRouteReportError(f"could not read {label}") from error
    except json.JSONDecodeError as error:
        raise MultiRouteReportError(f"{label} is not valid JSON") from error
    if not isinstance(payload, dict):
        raise MultiRouteReportError(f"{label} must be a JSON object")
    return payload


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MultiRouteReportError(f"{label} must be an object")
    return value


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        unexpected = sorted(observed - expected)
        missing = sorted(expected - observed)
        fragments = []
        if unexpected:
            fragments.append("unexpected " + ", ".join(unexpected))
        if missing:
            fragments.append("missing " + ", ".join(missing))
        raise MultiRouteReportError(f"{label} keys are invalid: " + "; ".join(fragments))


def _require_allowed_keys(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise MultiRouteReportError(
            f"{label} contains unsupported fields: " + ", ".join(unexpected)
        )


def _safe_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise MultiRouteReportError(f"{label} must be a compact public identifier")
    if _ANONYMOUS_STUDENT_ID.search(value) or _ABSOLUTE_PATH.search(value) or _PRIVATE_PATH.search(value):
        raise MultiRouteReportError(f"{label} is not safe for a public report")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise MultiRouteReportError(f"{label} must be a SHA-256 digest")
    return value


def _normalise_status(value: Any) -> str:
    if not isinstance(value, str) or value not in {"passed", "failed"}:
        raise MultiRouteReportError("T1 readiness status must be passed or failed")
    return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MultiRouteReportError(f"{label} must be a non-negative integer")
    return value


def _require_positive_int(value: Any, label: str) -> int:
    value = _require_nonnegative_int(value, label)
    if value == 0:
        raise MultiRouteReportError(f"{label} must be positive")
    return value


def _number(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise MultiRouteReportError(f"{label} must be a finite number")
    return float(value)


def _require_rate(value: Any, label: str) -> float:
    value = _number(value, label)
    if not 0.0 <= value <= 1.0:
        raise MultiRouteReportError(f"{label} must be between 0 and 1")
    return value


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _signed(value: float) -> str:
    return f"{value:+.2f}"


def _decimal(value: float) -> str:
    return f"{value:.2f}"


def _short_hash(value: str) -> str:
    return value[:12] + "..."


def _escape_typst_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_typst_markup(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("#", "\\#")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )
