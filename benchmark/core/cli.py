import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .error_audit import write_error_confidence_audit
from .error_book import write_error_book, write_public_diagnosis_summary
from .error_book_iteration import (
    validate_error_book_registry,
    write_error_book_delta,
    write_private_typical_case_report,
)
from .error_regressions import (
    write_regression_evaluation,
    write_regression_suite,
)
from .gold import validate_gold_subset_table, validate_gold_table, write_gold_report
from .headless_runner import HeadlessPacketRunConfig, run_headless_packet
from .inventory import write_data_inventory
from .model_runner import (
    INPUT_MODES,
    MODEL_TRANSPORTS,
    ModelPacketRunConfig,
    run_model_packet,
)
from .multiroute_reporting import (
    build_multi_route_report_from_paths,
    write_multi_route_report,
    write_t1_readiness_summary,
)
from .comparisons import (
    check_three_condition_ablation,
    write_three_condition_ablation_json,
    write_three_condition_ablation_markdown,
)
from .course_metrics import (
    compare_course_runs,
    write_course_metrics_json,
    write_course_metrics_markdown,
)
from .packets import (
    PromptPacketSpec,
    TextGradingPacketSpec,
    audit_prompt_packet,
    build_prompt_packet,
    build_text_grading_packet,
)
from .plans import (
    ExperimentPlan,
    build_standard_experiment_plan,
    record_built_packet,
    write_experiment_plan,
)
from .readiness import (
    build_run_readiness_report,
    write_readiness_json,
    write_readiness_markdown,
)
from .route_lineage import (
    check_m1_t1_g1_lineage,
    write_public_route_lineage_binding,
    write_route_lineage_report,
)
from .rubrics import validate_rubric
from .reporting import write_typst_note
from .schema import (
    GRADING_OUTPUT_CONTRACT_V1,
    GRADING_OUTPUT_CONTRACTS,
    CourseSpec,
)
from .skill_snapshots import build_skill_snapshot, write_skill_snapshot
from .submission_snapshot_packets import (
    SubmissionSnapshotPacketSpec,
    build_submission_snapshot_packet,
)
from .submission_snapshot_routes import (
    MatchedImageRouteSpec,
    build_matched_image_route_packets,
)
from .transcripts import validate_transcript_source, write_transcript_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="exam-benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)

    packet = subparsers.add_parser(
        "build-packet", help="build a reproducible prompt packet"
    )
    packet.add_argument("--course", type=Path, required=True)
    packet.add_argument("--packet-id", required=True)
    packet.add_argument("--condition", required=True)
    packet.add_argument("--task", choices=("transcribe", "grade"), required=True)
    packet.add_argument("--prompt", type=Path, required=True)
    packet.add_argument("--rubric", type=Path)
    packet.add_argument("--student-id", action="append", dest="student_ids")
    packet.add_argument("--students-file", type=Path)
    packet.add_argument("--input-root", type=Path, required=True)
    packet.add_argument("--output-root", type=Path, required=True)
    packet.add_argument(
        "--grading-output-contract",
        choices=sorted(GRADING_OUTPUT_CONTRACTS),
        default=GRADING_OUTPUT_CONTRACT_V1,
    )
    packet.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="optional packet metadata; may be provided multiple times",
    )

    snapshot_packet = subparsers.add_parser(
        "build-submission-snapshot-packet",
        help=(
            "build a packet from a final-approved anonymous submission snapshot "
            "without inferring page order from directories"
        ),
    )
    snapshot_packet.add_argument("--course", type=Path, required=True)
    snapshot_packet.add_argument("--packet-id", required=True)
    snapshot_packet.add_argument("--condition", required=True)
    snapshot_packet.add_argument(
        "--task", choices=("transcribe", "grade"), required=True
    )
    snapshot_packet.add_argument("--prompt", type=Path, required=True)
    snapshot_packet.add_argument("--rubric", type=Path)
    snapshot_packet.add_argument("--student-id", action="append", dest="student_ids")
    snapshot_packet.add_argument("--students-file", type=Path)
    snapshot_packet.add_argument("--snapshot-root", type=Path, required=True)
    snapshot_packet.add_argument("--output-root", type=Path, required=True)
    snapshot_packet.add_argument(
        "--grading-output-contract",
        choices=sorted(GRADING_OUTPUT_CONTRACTS),
        default=GRADING_OUTPUT_CONTRACT_V1,
    )
    snapshot_packet.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="optional packet metadata; may be provided multiple times",
    )

    matched_routes = subparsers.add_parser(
        "build-matched-image-route-packets",
        help="build and validate matched M1 direct-image and T1 transcription packets",
    )
    matched_routes.add_argument("--course", type=Path, required=True)
    matched_routes.add_argument("--snapshot-root", type=Path, required=True)
    matched_routes.add_argument("--output-root", type=Path, required=True)
    matched_routes.add_argument("--split", required=True)
    matched_routes.add_argument("--student-id", action="append", dest="student_ids")
    matched_routes.add_argument("--students-file", type=Path)
    matched_routes.add_argument("--m1-packet-id", required=True)
    matched_routes.add_argument("--t1-packet-id", required=True)
    matched_routes.add_argument("--grade-prompt", type=Path, required=True)
    matched_routes.add_argument("--transcribe-prompt", type=Path, required=True)
    matched_routes.add_argument("--rubric", type=Path, required=True)
    matched_routes.add_argument(
        "--grading-output-contract",
        choices=sorted(GRADING_OUTPUT_CONTRACTS),
        default=GRADING_OUTPUT_CONTRACT_V1,
    )
    matched_routes.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="optional shared packet metadata; may be provided multiple times",
    )

    text_packet = subparsers.add_parser(
        "build-text-grading-packet",
        help="build a text-only grading packet from recorded transcripts",
    )
    text_packet.add_argument("--course", type=Path, required=True)
    text_packet.add_argument("--packet-id", required=True)
    text_packet.add_argument("--condition", required=True)
    text_packet.add_argument("--prompt", type=Path, required=True)
    text_packet.add_argument("--rubric", type=Path, required=True)
    text_packet.add_argument("--student-id", action="append", dest="student_ids")
    text_packet.add_argument("--students-file", type=Path)
    text_packet.add_argument("--transcript-source", type=Path, required=True)
    text_packet.add_argument("--output-root", type=Path, required=True)
    text_packet.add_argument("--text-source-kind", default="transcript")
    text_packet.add_argument("--source-run-id")
    text_packet.add_argument(
        "--grading-output-contract",
        choices=sorted(GRADING_OUTPUT_CONTRACTS),
        default=GRADING_OUTPUT_CONTRACT_V1,
    )
    text_packet.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="optional packet metadata; may be provided multiple times",
    )

    audit = subparsers.add_parser("audit-packet", help="audit packet isolation")
    audit.add_argument("--packet", type=Path, required=True)

    rubric = subparsers.add_parser(
        "validate-rubric", help="validate a concept-keyterm grading rubric"
    )
    rubric.add_argument("--course", type=Path, required=True)
    rubric.add_argument("--rubric", type=Path, required=True)
    rubric.add_argument("--output", type=Path)

    note = subparsers.add_parser(
        "render-note", help="render a Typst reproducibility note"
    )
    note.add_argument("--record", type=Path, required=True)
    note.add_argument("--metrics", type=Path)
    note.add_argument("--output", type=Path)
    note.add_argument("--title")

    t1_readiness = subparsers.add_parser(
        "summarize-t1-readiness",
        help=(
            "project a local T1 validation file to a privacy-safe aggregate "
            "readiness record"
        ),
    )
    t1_readiness.add_argument("--validation", type=Path, required=True)
    t1_readiness.add_argument(
        "--run-metadata",
        type=Path,
        required=True,
        help="local T1 run metadata used only to project opaque lineage commitments",
    )
    t1_readiness.add_argument("--output", type=Path, required=True)

    multi_route_report = subparsers.add_parser(
        "render-multi-route-report",
        help=(
            "combine aggregate-only M1/G1 comparison metrics and T1 readiness "
            "into a public Typst dashboard"
        ),
    )
    multi_route_report.add_argument("--m1-metrics", type=Path, required=True)
    multi_route_report.add_argument(
        "--m1-side", choices=("baseline", "candidate"), default="baseline"
    )
    multi_route_report.add_argument(
        "--g1-codex-metrics", type=Path, required=True
    )
    multi_route_report.add_argument(
        "--g1-codex-side", choices=("baseline", "candidate"), default="candidate"
    )
    multi_route_report.add_argument(
        "--g1-deepseek-metrics", type=Path, required=True
    )
    multi_route_report.add_argument(
        "--g1-deepseek-side", choices=("baseline", "candidate"), default="candidate"
    )
    multi_route_report.add_argument("--t1-readiness", type=Path, required=True)
    multi_route_report.add_argument("--route-contract", type=Path, required=True)
    multi_route_report.add_argument(
        "--g1-codex-lineage", type=Path, required=True
    )
    multi_route_report.add_argument(
        "--g1-deepseek-lineage", type=Path, required=True
    )
    multi_route_report.add_argument("--output-json", type=Path, required=True)
    multi_route_report.add_argument("--output-typst", type=Path, required=True)

    inventory = subparsers.add_parser(
        "inventory-data",
        help="write a privacy-preserving local data inventory",
    )
    inventory.add_argument("--data-root", type=Path, required=True)
    inventory.add_argument("--course", required=True)
    inventory.add_argument("--output", type=Path, required=True)

    skill = subparsers.add_parser(
        "snapshot-skill",
        help="write a reproducible skill version snapshot",
    )
    skill.add_argument("--skill-version-id", required=True)
    skill.add_argument(
        "--source",
        action="append",
        required=True,
        metavar="LABEL=PATH",
        help="skill source path; may be provided multiple times",
    )
    skill.add_argument("--output", type=Path, required=True)

    plan = subparsers.add_parser(
        "plan-experiment",
        help="write a planned experiment record without running a model",
    )
    plan.add_argument("--experiment-id", required=True)
    plan.add_argument(
        "--status",
        choices=("planned", "data_inventory", "packets_built", "blocked"),
        default="planned",
    )
    plan.add_argument("--git-branch", required=True)
    plan.add_argument("--git-commit", required=True)
    plan.add_argument("--inventory", type=Path, required=True)
    plan.add_argument("--course-spec", type=Path, required=True)
    plan.add_argument("--skill-snapshot", type=Path, required=True)
    plan.add_argument("--transcribe-prompt", type=Path, required=True)
    plan.add_argument("--grade-prompt", type=Path, required=True)
    plan.add_argument("--transcribe-template-id", default="transcribe_standard_v1")
    plan.add_argument("--grade-template-id", default="grade_standard_v1")
    plan.add_argument("--note", action="append", default=[])
    plan.add_argument("--output", type=Path, required=True)

    built = subparsers.add_parser(
        "record-built-packet",
        help="record an audit-passed packet hash in an experiment plan",
    )
    built.add_argument("--plan", type=Path, required=True)
    built.add_argument("--packet", type=Path, required=True)
    built.add_argument("--output", type=Path)

    readiness = subparsers.add_parser(
        "check-run-readiness",
        help="check whether baseline and candidate plans are ready for model runs",
    )
    readiness.add_argument("--baseline-plan", type=Path, required=True)
    readiness.add_argument("--candidate-plan", type=Path, required=True)
    readiness.add_argument("--repo-root", type=Path)
    readiness.add_argument("--output", type=Path)
    readiness.add_argument("--markdown-output", type=Path)

    lineage = subparsers.add_parser(
        "check-route-lineage",
        help="verify matched M1 direct-image and T1-to-G1 transcription route bindings",
    )
    lineage.add_argument("--m1-packet", type=Path, required=True)
    lineage.add_argument("--t1-packet", type=Path, required=True)
    lineage.add_argument("--g1-packet", type=Path)
    lineage.add_argument("--t1-run", type=Path)
    lineage.add_argument("--output", type=Path)

    lineage_projection = subparsers.add_parser(
        "project-route-lineage-binding",
        help=(
            "project a ready full-route lineage report to a public opaque "
            "SHA-256 binding"
        ),
    )
    lineage_projection.add_argument("--lineage", type=Path, required=True)
    lineage_projection.add_argument("--output", type=Path, required=True)

    ablation = subparsers.add_parser(
        "check-ablation-readiness",
        help="check whether B0/R1/C3 packet differences are controlled",
    )
    ablation.add_argument("--b0-packet", type=Path, required=True)
    ablation.add_argument("--r1-packet", type=Path, required=True)
    ablation.add_argument("--c3-packet", type=Path, required=True)
    ablation.add_argument("--provider", required=True)
    ablation.add_argument("--model", required=True)
    ablation.add_argument("--input-mode", required=True)
    ablation.add_argument("--repetition", type=int, required=True)
    ablation.add_argument("--output", type=Path)
    ablation.add_argument("--markdown-output", type=Path)

    gold = subparsers.add_parser(
        "validate-gold",
        help="check whether a gold score CSV is complete for a course and student set",
    )
    gold.add_argument("--course", type=Path, required=True)
    gold.add_argument("--gold", type=Path, required=True)
    gold.add_argument("--student-id", action="append", dest="student_ids")
    gold.add_argument("--students-file", type=Path)
    gold.add_argument("--output", type=Path)

    gold_subset = subparsers.add_parser(
        "validate-gold-subset",
        help=(
            "strictly validate selected students from a shared private gold CSV "
            "without treating unfinished held-out rows as errors"
        ),
    )
    gold_subset.add_argument("--course", type=Path, required=True)
    gold_subset.add_argument("--gold", type=Path, required=True)
    gold_subset.add_argument("--student-id", action="append", dest="student_ids")
    gold_subset.add_argument("--students-file", type=Path)
    gold_subset.add_argument("--output", type=Path)

    course_metrics = subparsers.add_parser(
        "compare-course-runs",
        help=(
            "compare two completed grading runs against ready course gold and "
            "write aggregate-only metrics"
        ),
    )
    course_metrics.add_argument("--course", type=Path, required=True)
    course_metrics.add_argument("--gold", type=Path, required=True)
    course_metrics.add_argument("--baseline-run", type=Path, required=True)
    course_metrics.add_argument("--candidate-run", type=Path, required=True)
    course_metrics.add_argument(
        "--student-id", action="append", dest="student_ids"
    )
    course_metrics.add_argument("--students-file", type=Path)
    course_metrics.add_argument("--output-json", type=Path, required=True)
    course_metrics.add_argument("--output-md", type=Path, required=True)
    course_metrics.add_argument("--bootstrap-seed", type=int, default=20260701)
    course_metrics.add_argument("--bootstrap-samples", type=int, default=10_000)
    course_metrics.add_argument(
        "--require-same-data-snapshot",
        action="store_true",
        help="fail unless both run metadata files bind to the same source snapshot",
    )

    transcripts = subparsers.add_parser(
        "validate-transcripts",
        help="check whether transcript JSON files are complete for a course and student set",
    )
    transcripts.add_argument("--course", type=Path, required=True)
    transcripts.add_argument("--transcript-source", type=Path, required=True)
    transcripts.add_argument("--student-id", action="append", dest="student_ids")
    transcripts.add_argument("--students-file", type=Path)
    transcripts.add_argument("--output", type=Path)

    run_model = subparsers.add_parser(
        "run-model-packet",
        help="run a model provider against a prompt packet",
    )
    run_model.add_argument("--provider", choices=("deepseek", "kimi"), required=True)
    run_model.add_argument("--model", required=True)
    run_model.add_argument("--input-mode", choices=INPUT_MODES, required=True)
    run_model.add_argument("--packet", type=Path, required=True)
    run_model.add_argument("--output", type=Path, required=True)
    run_model.add_argument("--temperature", type=float)
    run_model.add_argument("--top-p", type=float)
    run_model.add_argument("--max-tokens", type=int)
    run_model.add_argument("--max-retries", type=int, default=0)
    run_model.add_argument("--response-format", default="json_object")
    run_model.add_argument(
        "--transport",
        choices=MODEL_TRANSPORTS,
        default="chat_completions_json_object",
        help=(
            "model API transport; deepseek_responses_json_schema binds the "
            "packet output.schema.json to DeepSeek's Responses API"
        ),
    )
    run_model.add_argument("--endpoint")
    run_model.add_argument("--run-commit")
    run_model.add_argument("--run-id")
    run_model.add_argument(
        "--model-release-policy",
        type=Path,
        help=(
            "public model-release policy that validates the provider/model pair "
            "and records its hash in run metadata"
        ),
    )
    run_model.add_argument(
        "--allow-provisional-model",
        action="store_true",
        help="explicitly acknowledge a provisional model allowed by the policy",
    )
    run_model.add_argument(
        "--dry-run",
        action="store_true",
        help="exercise packet IO and validation without calling the provider API",
    )

    headless = subparsers.add_parser(
        "run-headless-packet",
        help="run a grading packet through a headless CLI",
    )
    headless.add_argument("--engine", choices=("codex", "claude", "kimi"), required=True)
    headless.add_argument("--model", required=True)
    headless.add_argument("--input-mode", choices=INPUT_MODES, required=True)
    headless.add_argument("--packet", type=Path, required=True)
    headless.add_argument("--output", type=Path, required=True)
    headless.add_argument("--engine-bin")
    headless.add_argument("--max-retries", type=int, default=0)
    headless.add_argument("--timeout-seconds", type=int, default=600)
    headless.add_argument("--run-commit")
    headless.add_argument("--run-id")
    headless.add_argument("--experiment-condition")
    headless.add_argument(
        "--dry-run",
        action="store_true",
        help="exercise packet IO and validation without calling the headless CLI",
    )

    error_book = subparsers.add_parser(
        "build-error-book",
        help="build a private development error book and privacy-safe public summary",
    )
    error_book.add_argument("--run-dir", type=Path, required=True)
    error_book.add_argument("--gold", type=Path, required=True)
    error_book.add_argument("--packet", type=Path, required=True)
    error_book.add_argument("--private-output", type=Path, required=True)
    error_book.add_argument("--public-output", type=Path, required=True)

    diagnosis_summary = subparsers.add_parser(
        "summarize-error-book-diagnoses",
        help="validate complete private diagnoses and write a public aggregate",
    )
    diagnosis_summary.add_argument("--private-book", type=Path, required=True)
    diagnosis_summary.add_argument("--diagnoses", type=Path, required=True)
    diagnosis_summary.add_argument("--public-output", type=Path, required=True)

    typical_cases = subparsers.add_parser(
        "render-typical-error-cases",
        help="render a private human-readable typical-case error book",
    )
    typical_cases.add_argument("--private-book", type=Path, required=True)
    typical_cases.add_argument("--diagnoses", type=Path, required=True)
    typical_cases.add_argument("--output", type=Path, required=True)
    typical_cases.add_argument("--max-cases", type=int, default=12)

    error_delta = subparsers.add_parser(
        "compare-error-books",
        help="classify resolved, persistent, and regression cases across skills",
    )
    error_delta.add_argument("--previous-private-book", type=Path, required=True)
    error_delta.add_argument("--current-private-book", type=Path, required=True)
    error_delta.add_argument("--private-output", type=Path, required=True)
    error_delta.add_argument("--public-output", type=Path, required=True)

    error_registry = subparsers.add_parser(
        "check-error-book-registry",
        help="require complete error-book artifacts for the current grading skill",
    )
    error_registry.add_argument("--registry", type=Path, required=True)
    error_registry.add_argument("--repo-root", type=Path, default=Path("."))

    regression_suite = subparsers.add_parser(
        "build-error-regression-suite",
        help="freeze diagnosed development errors as private executable regressions",
    )
    regression_suite.add_argument("--private-book", type=Path, required=True)
    regression_suite.add_argument("--diagnoses", type=Path, required=True)
    regression_suite.add_argument("--policy", type=Path, required=True)
    regression_suite.add_argument("--private-output", type=Path, required=True)
    regression_suite.add_argument("--public-output", type=Path, required=True)

    regression_evaluation = subparsers.add_parser(
        "evaluate-error-regressions",
        help="evaluate a candidate private error book against frozen regressions",
    )
    regression_evaluation.add_argument("--suite", type=Path, required=True)
    regression_evaluation.add_argument(
        "--current-private-book", type=Path, required=True
    )
    regression_evaluation.add_argument(
        "--private-output", type=Path, required=True
    )
    regression_evaluation.add_argument(
        "--public-output", type=Path, required=True
    )

    confidence_audit = subparsers.add_parser(
        "audit-error-confidence",
        help="audit confidence, flags, and error mechanisms on development data",
    )
    confidence_audit.add_argument("--run-dir", type=Path, required=True)
    confidence_audit.add_argument("--private-book", type=Path, required=True)
    confidence_audit.add_argument("--diagnoses", type=Path, required=True)
    confidence_audit.add_argument(
        "--public-error-summary", type=Path, required=True
    )
    confidence_audit.add_argument("--public-output", type=Path, required=True)
    confidence_audit.add_argument("--markdown-output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        raw_argv = tuple(argv if argv is not None else sys.argv[1:])
        args = _build_parser().parse_args(argv)
        if args.command == "build-packet":
            result = _build_packet(args)
            print(
                json.dumps(
                    {
                        "packet_path": str(result.packet_path),
                        "packet_id": result.manifest["packet_id"],
                        "packet_hash": result.packet_hash,
                        "manifest": result.manifest,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "build-submission-snapshot-packet":
            result = _build_submission_snapshot_packet(args)
            print(
                json.dumps(
                    {
                        "packet_path": str(result.packet_path),
                        "packet_id": result.manifest["packet_id"],
                        "packet_hash": result.packet_hash,
                        "manifest": result.manifest,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "build-matched-image-route-packets":
            result = _build_matched_image_route_packets(args)
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command == "build-text-grading-packet":
            result = _build_text_grading_packet(args)
            print(
                json.dumps(
                    {
                        "packet_path": str(result.packet_path),
                        "packet_id": result.manifest["packet_id"],
                        "packet_hash": result.packet_hash,
                        "manifest": result.manifest,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "audit-packet":
            findings = audit_prompt_packet(args.packet)
            print(json.dumps({"findings": findings}, sort_keys=True))
            return 1 if findings else 0
        if args.command == "validate-rubric":
            course = CourseSpec.from_json_path(args.course)
            rubric = _read_json(args.rubric)
            findings = validate_rubric(rubric, course)
            report = {
                "course_id": course.course_id,
                "failed_checks": findings,
                "rubric_format": rubric.get("rubric_format"),
                "status": "ready" if not findings else "not_ready",
            }
            if args.output is not None:
                _write_json(args.output, report)
            print(json.dumps(report, sort_keys=True))
            return 0 if report["status"] == "ready" else 1
        if args.command == "render-note":
            output = write_typst_note(
                args.record,
                args.output,
                metrics_path=args.metrics,
                title=args.title,
            )
            print(json.dumps({"note_path": str(output)}, sort_keys=True))
            return 0
        if args.command == "summarize-t1-readiness":
            summary = write_t1_readiness_summary(
                args.validation,
                args.output,
                run_metadata_path=args.run_metadata,
            )
            print(
                json.dumps(
                    {
                        "record_type": summary["record_type"],
                        "status": summary["status"],
                        "students_expected": summary["students_expected"],
                        "students_passed": summary["students_passed"],
                        "students_failed": summary["students_failed"],
                        "ready_for_g1": summary["ready_for_g1"],
                        "privacy": "aggregate_only",
                    },
                    sort_keys=True,
                )
            )
            return 0 if summary["ready_for_g1"] else 1
        if args.command == "render-multi-route-report":
            report = build_multi_route_report_from_paths(
                m1_metrics_path=args.m1_metrics,
                g1_codex_metrics_path=args.g1_codex_metrics,
                g1_deepseek_metrics_path=args.g1_deepseek_metrics,
                t1_readiness_path=args.t1_readiness,
                route_contract_path=args.route_contract,
                g1_codex_lineage_path=args.g1_codex_lineage,
                g1_deepseek_lineage_path=args.g1_deepseek_lineage,
                m1_side=args.m1_side,
                g1_codex_side=args.g1_codex_side,
                g1_deepseek_side=args.g1_deepseek_side,
            )
            write_multi_route_report(
                report,
                output_json=args.output_json,
                output_typst=args.output_typst,
            )
            print(
                json.dumps(
                    {
                        "record_type": report["record_type"],
                        "course_id": report["course"]["course_id"],
                        "assessment_id": report["course"]["assessment_id"],
                        "student_count": report["population"]["student_count"],
                        "routes": [route["route"] for route in report["routes"]],
                        "t1_ready_for_g1": report["t1_readiness"]["ready_for_g1"],
                        "privacy": "aggregate_only",
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "inventory-data":
            inventory = write_data_inventory(
                args.data_root,
                args.course,
                args.output,
            )
            print(
                json.dumps(
                    {
                        "course_id": inventory["course_id"],
                        "output": str(args.output),
                        "snapshot_hash": inventory["snapshot_hash"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "snapshot-skill":
            snapshot = build_skill_snapshot(
                skill_version_id=args.skill_version_id,
                source_paths=_parse_source_paths(args.source),
            )
            write_skill_snapshot(snapshot, args.output)
            print(
                json.dumps(
                    {
                        "canonical_hash": snapshot.canonical_hash,
                        "mirror_synchronized": snapshot.mirror_synchronized,
                        "output": str(args.output),
                        "skill_version_id": snapshot.skill_version_id,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "plan-experiment":
            plan = build_standard_experiment_plan(
                experiment_id=args.experiment_id,
                status=args.status,
                git_branch=args.git_branch,
                git_commit=args.git_commit,
                inventory_path=args.inventory,
                course_spec_path=args.course_spec,
                skill_snapshot_path=args.skill_snapshot,
                transcribe_prompt_path=args.transcribe_prompt,
                grade_prompt_path=args.grade_prompt,
                transcribe_template_id=args.transcribe_template_id,
                grade_template_id=args.grade_template_id,
                notes=tuple(args.note),
            )
            write_experiment_plan(plan, args.output)
            print(
                json.dumps(
                    {
                        "course_id": plan.course_id,
                        "experiment_id": plan.experiment_id,
                        "output": str(args.output),
                        "status": plan.status,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "record-built-packet":
            plan = ExperimentPlan.from_json_path(args.plan)
            updated = record_built_packet(plan, args.packet)
            output = args.output or args.plan
            write_experiment_plan(updated, output)
            packet = next(
                packet
                for packet in updated.built_packets
                if packet.packet_path == args.packet.as_posix()
            )
            print(
                json.dumps(
                    {
                        "audit_status": packet.audit_status,
                        "output": str(output),
                        "packet_hash": packet.packet_hash,
                        "packet_id": packet.packet_id,
                        "prompt_path": packet.prompt_path,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "check-run-readiness":
            report = build_run_readiness_report(
                baseline_plan_path=args.baseline_plan,
                candidate_plan_path=args.candidate_plan,
                repo_root=args.repo_root,
            )
            if args.output is not None:
                write_readiness_json(report, args.output)
            if args.markdown_output is not None:
                write_readiness_markdown(report, args.markdown_output)
            print(
                json.dumps(
                    {
                        "status": report["status"],
                        "failed_checks": [
                            check["id"]
                            for check in report["checks"]
                            if check["status"] == "failed"
                        ],
                        "output": str(args.output) if args.output is not None else None,
                        "markdown_output": (
                            str(args.markdown_output)
                            if args.markdown_output is not None
                            else None
                        ),
                    },
                    sort_keys=True,
                )
            )
            return 0 if report["status"] == "ready" else 1
        if args.command == "check-route-lineage":
            report = check_m1_t1_g1_lineage(
                m1_packet=args.m1_packet,
                t1_packet=args.t1_packet,
                g1_packet=args.g1_packet,
                t1_run=args.t1_run,
            )
            if args.output is not None:
                write_route_lineage_report(report, args.output)
            print(
                json.dumps(
                    {
                        "status": report["status"],
                        "stage": report["stage"],
                        "student_count": report["student_count"],
                        "failed_checks": report["failed_checks"],
                        "model_run_allowed": report["model_run_allowed"],
                        "output": str(args.output) if args.output is not None else None,
                    },
                    sort_keys=True,
                )
            )
            return 0 if report["status"] == "ready" else 1
        if args.command == "project-route-lineage-binding":
            lineage_report = _read_json(args.lineage)
            binding = write_public_route_lineage_binding(
                lineage_report, args.output
            )
            print(
                json.dumps(
                    {
                        "record_type": binding["record_type"],
                        "status": binding["status"],
                        "privacy": "aggregate_only",
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "check-ablation-readiness":
            report = check_three_condition_ablation(
                args.b0_packet,
                args.r1_packet,
                args.c3_packet,
                provider=args.provider,
                model=args.model,
                input_mode=args.input_mode,
                repetition=args.repetition,
            )
            if args.output is not None:
                write_three_condition_ablation_json(report, args.output)
            if args.markdown_output is not None:
                write_three_condition_ablation_markdown(report, args.markdown_output)
            print(
                json.dumps(
                    {
                        "failed_checks": report["failed_checks"],
                        "markdown_output": (
                            str(args.markdown_output)
                            if args.markdown_output is not None
                            else None
                        ),
                        "output": str(args.output) if args.output is not None else None,
                        "status": report["status"],
                    },
                    sort_keys=True,
                )
            )
            return 0 if report["status"] == "ready" else 1
        if args.command == "validate-gold":
            course = CourseSpec.from_json_path(args.course)
            report = validate_gold_table(
                course,
                args.gold,
                _load_student_ids(args.student_ids, args.students_file),
            )
            if args.output is not None:
                write_gold_report(report, args.output)
            print(
                json.dumps(
                    {
                        "status": report["status"],
                        "failed_checks": report["failed_checks"],
                        "output": str(args.output) if args.output is not None else None,
                    },
                    sort_keys=True,
                )
            )
            return 0 if report["status"] == "ready" else 1
        if args.command == "validate-gold-subset":
            course = CourseSpec.from_json_path(args.course)
            report = validate_gold_subset_table(
                course,
                args.gold,
                _load_student_ids(args.student_ids, args.students_file),
            )
            if args.output is not None:
                write_gold_report(report, args.output)
            print(
                json.dumps(
                    {
                        "status": report["status"],
                        "report_type": report["report_type"],
                        "validation_scope": report["validation_scope"],
                        "failed_checks": report["failed_checks"],
                        "output": str(args.output) if args.output is not None else None,
                    },
                    sort_keys=True,
                )
            )
            return 0 if report["status"] == "ready" else 1
        if args.command == "compare-course-runs":
            course = CourseSpec.from_json_path(args.course)
            report = compare_course_runs(
                course,
                args.gold,
                _load_student_ids(args.student_ids, args.students_file),
                args.baseline_run,
                args.candidate_run,
                bootstrap_seed=args.bootstrap_seed,
                bootstrap_samples=args.bootstrap_samples,
                require_same_data_snapshot=args.require_same_data_snapshot,
            )
            write_course_metrics_json(args.output_json, report)
            write_course_metrics_markdown(args.output_md, report)
            print(
                json.dumps(
                    {
                        "record_type": report["record_type"],
                        "course_id": report["course"]["course_id"],
                        "assessment_id": report["course"]["assessment_id"],
                        "student_count": report["population"]["student_count"],
                        "score_row_count": report["population"]["score_row_count"],
                        "privacy": "aggregate_only",
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "validate-transcripts":
            course = CourseSpec.from_json_path(args.course)
            report = validate_transcript_source(
                course,
                args.transcript_source,
                _load_student_ids(args.student_ids, args.students_file),
            )
            if args.output is not None:
                write_transcript_report(report, args.output)
            print(
                json.dumps(
                    {
                        "status": report["status"],
                        "failed_checks": report["failed_checks"],
                        "output": str(args.output) if args.output is not None else None,
                    },
                    sort_keys=True,
                )
            )
            return 0 if report["status"] == "ready" else 1
        if args.command == "run-model-packet":
            result = run_model_packet(
                ModelPacketRunConfig(
                    provider=args.provider,
                    model=args.model,
                    input_mode=args.input_mode,
                    packet=args.packet,
                    output=args.output,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    max_tokens=args.max_tokens,
                    max_retries=args.max_retries,
                    response_format=args.response_format,
                    transport=args.transport,
                    endpoint=args.endpoint,
                    dry_run=args.dry_run,
                    command_argv=raw_argv,
                    run_commit=args.run_commit,
                    run_id=args.run_id,
                    model_release_policy=args.model_release_policy,
                    allow_provisional_model=args.allow_provisional_model,
                )
            )
            print(json.dumps(result, sort_keys=True))
            return 0 if result["validation_status"] == "passed" else 1
        if args.command == "run-headless-packet":
            result = run_headless_packet(
                HeadlessPacketRunConfig(
                    engine=args.engine,
                    model=args.model,
                    input_mode=args.input_mode,
                    packet=args.packet,
                    output=args.output,
                    engine_bin=args.engine_bin,
                    max_retries=args.max_retries,
                    timeout_seconds=args.timeout_seconds,
                    dry_run=args.dry_run,
                    command_argv=raw_argv,
                    run_commit=args.run_commit,
                    run_id=args.run_id,
                    experiment_condition=args.experiment_condition,
                )
            )
            print(json.dumps(result, sort_keys=True))
            return 0 if result["validation_status"] == "passed" else 1
        if args.command == "build-error-book":
            result = write_error_book(
                run_dir=args.run_dir,
                gold_path=args.gold,
                packet_dir=args.packet,
                private_output=args.private_output,
                public_output=args.public_output,
            )
            print(
                json.dumps(
                    {
                        "private_output": str(args.private_output),
                        "public_output": str(args.public_output),
                        "error_pairs": result.public_summary["population"][
                            "error_pairs"
                        ],
                        "severe_error_pairs": result.public_summary["population"][
                            "severe_error_pairs"
                        ],
                        "privacy_audit": "passed",
                        "split": result.public_summary["scope"]["split"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "summarize-error-book-diagnoses":
            summary = write_public_diagnosis_summary(
                private_book_path=args.private_book,
                diagnoses_path=args.diagnoses,
                public_output=args.public_output,
            )
            print(
                json.dumps(
                    {
                        "all_error_cases_reviewed": summary["review"][
                            "all_error_cases_reviewed"
                        ],
                        "case_count": summary["review"]["case_count"],
                        "privacy_audit": "passed",
                        "public_output": str(args.public_output),
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "render-typical-error-cases":
            output = write_private_typical_case_report(
                private_book_path=args.private_book,
                diagnoses_path=args.diagnoses,
                output_path=args.output,
                max_typical_cases=args.max_cases,
            )
            print(
                json.dumps(
                    {
                        "output": str(output),
                        "privacy": "private_gitignored_output",
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "compare-error-books":
            result = write_error_book_delta(
                previous_private_book_path=args.previous_private_book,
                current_private_book_path=args.current_private_book,
                private_output=args.private_output,
                public_output=args.public_output,
            )
            print(
                json.dumps(
                    {
                        "counts": result.public_summary["counts"],
                        "private_output": str(args.private_output),
                        "privacy_audit": "passed",
                        "public_output": str(args.public_output),
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "check-error-book-registry":
            findings = validate_error_book_registry(
                repo_root=args.repo_root,
                registry_path=args.registry,
            )
            result = {
                "findings": findings,
                "status": "passed" if not findings else "failed",
            }
            print(json.dumps(result, sort_keys=True))
            return 0 if not findings else 1
        if args.command == "build-error-regression-suite":
            result = write_regression_suite(
                private_book_path=args.private_book,
                diagnoses_path=args.diagnoses,
                policy_path=args.policy,
                private_output=args.private_output,
                public_output=args.public_output,
            )
            print(
                json.dumps(
                    {
                        "private_output": str(args.private_output),
                        "privacy_audit": "passed",
                        "public_output": str(args.public_output),
                        "suite_id": result.public_summary["suite_id"],
                        "target_cases": result.public_summary[
                            "target_case_count"
                        ],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "evaluate-error-regressions":
            result = write_regression_evaluation(
                private_suite_path=args.suite,
                current_private_book_path=args.current_private_book,
                private_output=args.private_output,
                public_output=args.public_output,
            )
            print(
                json.dumps(
                    {
                        "counts": result.public_summary["counts"],
                        "privacy_audit": "passed",
                        "private_output": str(args.private_output),
                        "public_output": str(args.public_output),
                        "status": result.public_summary["status"],
                        "suite_id": result.public_summary["suite_id"],
                    },
                    sort_keys=True,
                )
            )
            return 0 if result.public_summary["status"] == "passed" else 1
        if args.command == "audit-error-confidence":
            result = write_error_confidence_audit(
                run_dir=args.run_dir,
                private_book_path=args.private_book,
                diagnoses_path=args.diagnoses,
                public_error_summary_path=args.public_error_summary,
                public_output=args.public_output,
                markdown_output=args.markdown_output,
            )
            print(
                json.dumps(
                    {
                        "public_output": str(args.public_output),
                        "markdown_output": str(args.markdown_output),
                        "student_question_pairs": result["population"][
                            "student_question_pairs"
                        ],
                        "error_pairs": result["population"]["error_pairs"],
                        "severe_error_pairs": result["population"][
                            "severe_error_pairs"
                        ],
                        "privacy_audit": "passed",
                    },
                    sort_keys=True,
                )
            )
            return 0
        raise ValueError(f"unsupported command: {args.command}")
    except SystemExit as error:
        return int(error.code)
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


def _build_packet(args: argparse.Namespace) -> Any:
    course = CourseSpec.from_json_path(args.course)
    prompt = args.prompt.read_text(encoding="utf-8")
    rubric = None
    if args.rubric is not None:
        rubric = _read_json(args.rubric)
    elif args.task == "grade":
        raise ValueError("--rubric is required for grade packets")

    student_ids = _load_student_ids(args.student_ids, args.students_file)
    return build_prompt_packet(
        PromptPacketSpec(
            course=course,
            packet_id=args.packet_id,
            condition=args.condition,
            task=args.task,
            prompt_text=prompt,
            student_ids=tuple(student_ids),
            input_root=args.input_root,
            output_root=args.output_root,
            rubric=rubric,
            grading_output_contract=args.grading_output_contract,
            metadata=_parse_metadata(args.metadata),
        )
    )


def _build_submission_snapshot_packet(args: argparse.Namespace) -> Any:
    course = CourseSpec.from_json_path(args.course)
    rubric = None
    if args.rubric is not None:
        rubric = _read_json(args.rubric)
    elif args.task == "grade":
        raise ValueError("--rubric is required for grade packets")

    student_ids = _load_student_ids(args.student_ids, args.students_file)
    return build_submission_snapshot_packet(
        SubmissionSnapshotPacketSpec(
            course=course,
            packet_id=args.packet_id,
            condition=args.condition,
            task=args.task,
            prompt_text=args.prompt.read_text(encoding="utf-8"),
            student_ids=tuple(student_ids),
            snapshot_root=args.snapshot_root,
            output_root=args.output_root,
            rubric=rubric,
            grading_output_contract=args.grading_output_contract,
            metadata=_parse_metadata(args.metadata),
        )
    )


def _build_matched_image_route_packets(args: argparse.Namespace) -> Any:
    course = CourseSpec.from_json_path(args.course)
    student_ids = _load_student_ids(args.student_ids, args.students_file)
    return build_matched_image_route_packets(
        MatchedImageRouteSpec(
            course=course,
            snapshot_root=args.snapshot_root,
            output_root=args.output_root,
            split=args.split,
            student_ids=tuple(student_ids),
            m1_packet_id=args.m1_packet_id,
            t1_packet_id=args.t1_packet_id,
            grade_prompt_text=args.grade_prompt.read_text(encoding="utf-8"),
            transcribe_prompt_text=args.transcribe_prompt.read_text(encoding="utf-8"),
            rubric=_read_json(args.rubric),
            grading_output_contract=args.grading_output_contract,
            metadata=_parse_metadata(args.metadata),
        )
    )


def _build_text_grading_packet(args: argparse.Namespace) -> Any:
    course = CourseSpec.from_json_path(args.course)
    student_ids = _load_student_ids(args.student_ids, args.students_file)
    return build_text_grading_packet(
        TextGradingPacketSpec(
            course=course,
            packet_id=args.packet_id,
            condition=args.condition,
            prompt_text=args.prompt.read_text(encoding="utf-8"),
            student_ids=tuple(student_ids),
            transcript_source=args.transcript_source,
            output_root=args.output_root,
            rubric=_read_json(args.rubric),
            text_source_kind=args.text_source_kind,
            source_run_id=args.source_run_id,
            grading_output_contract=args.grading_output_contract,
            metadata=_parse_metadata(args.metadata),
        )
    )


def _load_student_ids(
    inline_student_ids: list[str] | None,
    students_file: Path | None,
) -> list[str]:
    student_ids = list(inline_student_ids or [])
    if students_file is not None:
        for line in students_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                student_ids.append(line)
    if not student_ids:
        raise ValueError("at least one --student-id or --students-file entry is required")
    if len(student_ids) != len(set(student_ids)):
        raise ValueError("student ids must be unique")
    return student_ids


def _parse_metadata(items: list[str]) -> dict[str, str]:
    metadata = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"metadata must use KEY=VALUE form: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("metadata key must not be blank")
        metadata[key] = value.strip()
    return metadata


def _parse_source_paths(items: list[str]) -> dict[str, Path]:
    source_paths = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"source must use LABEL=PATH form: {item}")
        label, value = item.split("=", 1)
        label = label.strip()
        path = Path(value.strip())
        if not label:
            raise ValueError("source label must not be blank")
        if label in source_paths:
            raise ValueError(f"duplicate source label: {label}")
        source_paths[label] = path
    return source_paths


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    raise SystemExit(main())
