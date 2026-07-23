import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .gold import validate_gold_table, write_gold_report
from .headless_runner import HeadlessPacketRunConfig, run_headless_packet
from .inventory import write_data_inventory
from .model_runner import INPUT_MODES, ModelPacketRunConfig, run_model_packet
from .comparisons import (
    check_three_condition_ablation,
    write_three_condition_ablation_json,
    write_three_condition_ablation_markdown,
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
from .rubrics import validate_concept_rubric
from .reporting import write_typst_note
from .schema import CourseSpec
from .skill_snapshots import build_skill_snapshot, write_skill_snapshot
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
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="optional packet metadata; may be provided multiple times",
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
    run_model.add_argument("--endpoint")
    run_model.add_argument("--run-commit")
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
    headless.add_argument("--experiment-condition")
    headless.add_argument(
        "--dry-run",
        action="store_true",
        help="exercise packet IO and validation without calling the headless CLI",
    )
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
            findings = validate_concept_rubric(rubric, course)
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
                    endpoint=args.endpoint,
                    dry_run=args.dry_run,
                    command_argv=raw_argv,
                    run_commit=args.run_commit,
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
                    experiment_condition=args.experiment_condition,
                )
            )
            print(json.dumps(result, sort_keys=True))
            return 0 if result["validation_status"] == "passed" else 1
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
