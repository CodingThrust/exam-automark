from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import fitz
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymization import (
    expected_review_pairs,
    expected_review_outputs,
    load_page_layout,
    masks_for_group_page,
    review_rows_for_layout,
    sha256_file,
    validate_anonymization_review,
    validate_page_layout,
    write_json,
    write_review_csv,
)
from benchmark.core.grading_mask_workflow import (
    MASK_CANDIDATE_DECISION_COLUMNS,
    PAGE_SWEEP_COLUMNS,
    build_artifact_manifest,
    build_candidate_manifest,
    build_render_spec,
    candidate_decision_rows,
    canonical_json_sha256,
    compile_approved_page_masks,
    load_csv_rows,
    page_sweep_rows,
    propose_red_ink_candidates,
    validate_artifact_manifest,
    validate_compiled_mask_provenance,
    write_csv,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "propose-grading-masks":
        return _propose_grading_masks(args)
    if args.command == "compile-approved-masks":
        return _compile_approved_masks(args)
    if args.command == "validate-review":
        return _validate_review(args)
    raise ValueError(f"unsupported command: {args.command}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare anonymous, blind-scoring image inputs from a combined scanned "
            "assessment PDF. This tool never marks the result model-ready."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser(
        "prepare",
        help="render a private page-layout manifest into anonymous PNG and PDF inputs",
    )
    prepare.add_argument("--source-pdf", type=Path, required=True)
    prepare.add_argument(
        "--layout",
        type=Path,
        required=True,
        help="private JSON layout with anonymous page groups and page-specific masks",
    )
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument(
        "--identity-redaction-rect",
        action="append",
        required=True,
        metavar="LEFT,TOP,RIGHT,BOTTOM",
        help="normalized identity rectangle; provide every required header mask",
    )
    prepare.add_argument("--scale", type=float, default=2.0)

    propose = commands.add_parser(
        "propose-grading-masks",
        help=(
            "privately propose red-ink grading-mark masks and create mandatory "
            "candidate-decision/page-sweep review templates"
        ),
    )
    propose.add_argument("--source-pdf", type=Path, required=True)
    propose.add_argument("--layout", type=Path, required=True)
    propose.add_argument("--output-root", type=Path, required=True)
    propose.add_argument(
        "--identity-redaction-rect",
        action="append",
        required=True,
        metavar="LEFT,TOP,RIGHT,BOTTOM",
        help="normalized identity rectangle excluded from detector input",
    )
    propose.add_argument("--scale", type=float, default=1.0)
    propose.add_argument("--min-red", type=int, default=90)
    propose.add_argument("--dominance", type=int, default=30)

    compile_masks = commands.add_parser(
        "compile-approved-masks",
        help=(
            "compile resolved candidate decisions and mandatory page sweeps into "
            "a new private layout; this never edits an existing layout"
        ),
    )
    compile_masks.add_argument("--base-layout", type=Path, required=True)
    compile_masks.add_argument("--candidate-manifest", type=Path, required=True)
    compile_masks.add_argument("--candidate-decisions", type=Path, required=True)
    compile_masks.add_argument("--page-sweeps", type=Path, required=True)
    compile_masks.add_argument("--output-layout", type=Path, required=True)

    review = commands.add_parser(
        "validate-review",
        help="check that every prepared page has human privacy, blindness, and content approval",
    )
    review.add_argument("--layout", type=Path, required=True)
    review.add_argument(
        "--prep-metadata",
        type=Path,
        required=True,
        help="prep-metadata.json emitted by the matching prepare command",
    )
    review.add_argument("--review", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)
    review.add_argument(
        "--base-layout",
        type=Path,
        help=(
            "base layout used by compile-approved-masks; required when validating "
            "a compiled grading-mask layout"
        ),
    )
    review.add_argument("--candidate-manifest", type=Path)
    review.add_argument("--candidate-decisions", type=Path)
    review.add_argument("--page-sweeps", type=Path)
    return parser


def _prepare(args: argparse.Namespace) -> int:
    source_pdf = args.source_pdf
    if not source_pdf.is_file():
        raise FileNotFoundError(source_pdf)
    if args.scale <= 0:
        raise ValueError("--scale must be positive")
    if args.output_root.exists() and any(args.output_root.iterdir()):
        raise FileExistsError(
            f"output root is not empty: {args.output_root}; create a new versioned root"
        )

    identity_rectangles = [_parse_rectangle(value) for value in args.identity_redaction_rect]
    layout = load_page_layout(args.layout)
    source_hash = sha256_file(source_pdf)
    layout_hash = sha256_file(args.layout)
    render_spec = build_render_spec(
        layout=layout,
        layout_sha256=layout_hash,
        identity_rectangles=identity_rectangles,
        render_scale=args.scale,
    )
    render_spec_sha256 = canonical_json_sha256(render_spec)
    with fitz.open(source_pdf) as document:
        layout_report = validate_page_layout(
            layout,
            source_page_count=len(document),
            source_sha256=source_hash,
        )
        if layout_report["status"] != "ready":
            raise ValueError(
                "private page layout is not ready: "
                + json.dumps(layout_report["failed_checks"], sort_keys=True)
            )

        args.output_root.mkdir(parents=True, exist_ok=True)
        image_root = args.output_root / "anonymized_pages"
        pdf_root = args.output_root / "anonymized_pdfs"
        manifest_root = args.output_root / "manifest"
        image_root.mkdir(parents=True, exist_ok=True)
        pdf_root.mkdir(parents=True, exist_ok=True)
        manifest_root.mkdir(parents=True, exist_ok=True)

        for group in layout["page_groups"]:
            anonymous_id = group["anonymous_id"]
            source_pages = group["source_pages"]
            student_image_root = image_root / anonymous_id
            student_image_root.mkdir(parents=True, exist_ok=True)
            images: list[Image.Image] = []
            for local_page, source_page in enumerate(source_pages, start=1):
                pixmap = document.load_page(source_page - 1).get_pixmap(
                    matrix=fitz.Matrix(args.scale, args.scale),
                    alpha=False,
                )
                image = Image.frombytes(
                    "RGB",
                    (pixmap.width, pixmap.height),
                    pixmap.samples,
                )
                rectangles = [
                    *identity_rectangles,
                    *masks_for_group_page(group, source_page),
                ]
                _apply_rectangles(image, rectangles)
                image_path = student_image_root / f"{anonymous_id}-p{local_page:02d}.png"
                image.save(image_path, format="PNG")
                images.append(image)
            _write_pdf(pdf_root / f"{anonymous_id}.pdf", images)

    artifact_manifest = build_artifact_manifest(
        output_root=args.output_root,
        layout=layout,
        render_spec_sha256=render_spec_sha256,
    )
    artifact_manifest_path = manifest_root / "output-artifacts.json"
    write_json(artifact_manifest_path, artifact_manifest)
    artifact_manifest_sha256 = sha256_file(artifact_manifest_path)
    review_rows = review_rows_for_layout(
        layout,
        identity_rectangles=identity_rectangles,
        render_spec_sha256=render_spec_sha256,
        artifact_manifest_sha256=artifact_manifest_sha256,
    )
    review_path = manifest_root / "anonymization_review.csv"
    write_review_csv(review_path, review_rows)
    metadata = {
        "schema_version": 2,
        "record_type": "anonymized_assessment_preparation",
        "assessment_id": layout["assessment_id"],
        "source_pdf": source_pdf.name,
        "source_sha256": source_hash,
        "source_page_count": layout_report["source_page_count"],
        "anonymous_group_count": layout_report["anonymous_group_count"],
        "layout_sha256": layout_hash,
        "render_spec": render_spec,
        "render_spec_sha256": render_spec_sha256,
        "layout_validation_path": "manifest/page-layout-validation.json",
        "review_path": "manifest/anonymization_review.csv",
        "artifact_manifest_path": "manifest/output-artifacts.json",
        "artifact_manifest_sha256": artifact_manifest_sha256,
        "identity_redaction_rectangles": identity_rectangles,
        "render_scale": args.scale,
        "outputs": {
            "images": "anonymized_pages/S###/S###-pNN.png",
            "pdfs": "anonymized_pdfs/S###.pdf",
        },
        "privacy_review_status": "pending",
        "blindness_review_status": "pending",
        "answer_content_review_status": "pending",
        "model_run_allowed": False,
        "model_run_blockers": [
            "Every prepared page requires privacy approval.",
            "Every prepared page requires blindness approval: no score, tick/cross, total, or grader comment may leak gold.",
            "Every prepared page requires content-preservation approval for the declared question scope.",
            "A frozen split, reviewed transcripts, question-level gold, rubric, packet audit, and separate run-readiness approval are still required.",
        ],
    }
    write_json(manifest_root / "page-layout-validation.json", layout_report)
    write_json(manifest_root / "prep-metadata.json", metadata)
    print(
        json.dumps(
            {
                "status": "prepared_pending_human_review",
                "anonymous_group_count": layout_report["anonymous_group_count"],
                "review_rows": len(review_rows),
                "output_root": str(args.output_root),
                "model_run_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _propose_grading_masks(args: argparse.Namespace) -> int:
    source_pdf = args.source_pdf
    if not source_pdf.is_file():
        raise FileNotFoundError(source_pdf)
    if args.scale <= 0:
        raise ValueError("--scale must be positive")
    if args.output_root.exists() and any(args.output_root.iterdir()):
        raise FileExistsError(
            f"output root is not empty: {args.output_root}; create a new versioned root"
        )
    identity_rectangles = [_parse_rectangle(value) for value in args.identity_redaction_rect]
    layout = load_page_layout(args.layout)
    layout_hash = sha256_file(args.layout)
    source_hash = sha256_file(source_pdf)
    candidates: list[dict[str, Any]] = []
    candidate_counter = 1
    with fitz.open(source_pdf) as document:
        layout_report = validate_page_layout(
            layout,
            source_page_count=len(document),
            source_sha256=source_hash,
        )
        if layout_report["status"] != "ready":
            raise ValueError(
                "private page layout is not ready: "
                + json.dumps(layout_report["failed_checks"], sort_keys=True)
            )
        for group in layout["page_groups"]:
            anonymous_id = group["anonymous_id"]
            for source_page in group["source_pages"]:
                pixmap = document.load_page(source_page - 1).get_pixmap(
                    matrix=fitz.Matrix(args.scale, args.scale),
                    alpha=False,
                )
                image = Image.frombytes(
                    "RGB",
                    (pixmap.width, pixmap.height),
                    pixmap.samples,
                )
                rectangles = propose_red_ink_candidates(
                    image,
                    excluded_rectangles=identity_rectangles,
                    min_red=args.min_red,
                    dominance=args.dominance,
                )
                for rectangle in rectangles:
                    candidates.append(
                        {
                            "candidate_id": f"C{candidate_counter:04d}",
                            "anonymous_id": anonymous_id,
                            "source_page": source_page,
                            "rectangles": [rectangle],
                            "detector": "red_ink_components_v1",
                            "confidence": 0.65,
                            "rationale": (
                                "red-dominant connected component; must be reviewed "
                                "with the whole-page grayscale sweep"
                            ),
                        }
                    )
                    candidate_counter += 1
    manifest = build_candidate_manifest(
        layout=layout,
        layout_sha256=layout_hash,
        candidates=candidates,
        detector={
            "name": "red_ink_components_v1",
            "scale": args.scale,
            "min_red": args.min_red,
            "dominance": args.dominance,
            "limitation": (
                "detects red-dominant pixels only; grayscale marks require the "
                "mandatory manual page sweep"
            ),
        },
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_root / "candidate-manifest.json"
    decisions_path = args.output_root / "candidate-decisions.csv"
    sweeps_path = args.output_root / "page-sweeps.csv"
    write_json(manifest_path, manifest)
    write_csv(
        decisions_path,
        columns=MASK_CANDIDATE_DECISION_COLUMNS,
        rows=candidate_decision_rows(manifest),
    )
    write_csv(
        sweeps_path,
        columns=PAGE_SWEEP_COLUMNS,
        rows=page_sweep_rows(layout),
    )
    print(
        json.dumps(
            {
                "status": "candidates_prepared_pending_human_review",
                "candidate_count": len(candidates),
                "page_sweep_count": len(expected_review_pairs(layout)),
                "output_root": str(args.output_root),
                "model_run_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _compile_approved_masks(args: argparse.Namespace) -> int:
    if args.output_layout.exists():
        raise FileExistsError(
            f"output layout already exists: {args.output_layout}; create a new versioned layout"
        )
    base_layout = load_page_layout(args.base_layout)
    candidate_manifest = _load_json_object(args.candidate_manifest)
    decision_columns, decision_rows = load_csv_rows(args.candidate_decisions)
    sweep_columns, sweep_rows = load_csv_rows(args.page_sweeps)
    compiled = compile_approved_page_masks(
        base_layout=base_layout,
        base_layout_sha256=sha256_file(args.base_layout),
        candidate_manifest=candidate_manifest,
        decision_rows=decision_rows,
        decision_columns=decision_columns,
        sweep_rows=sweep_rows,
        sweep_columns=sweep_columns,
        candidate_manifest_sha256=sha256_file(args.candidate_manifest),
        decision_sha256=sha256_file(args.candidate_decisions),
        sweep_sha256=sha256_file(args.page_sweeps),
    )
    write_json(args.output_layout, compiled)
    print(
        json.dumps(
            {
                "status": "approved_masks_compiled_pending_rerender",
                "output_layout": str(args.output_layout),
                "model_run_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _validate_review(args: argparse.Namespace) -> int:
    layout = load_page_layout(args.layout)
    metadata = _load_json_object(args.prep_metadata)
    current_layout_hash = sha256_file(args.layout)
    declared_review_path = _resolve_declared_output_path(
        prep_metadata_path=args.prep_metadata,
        relative_path=metadata.get("review_path"),
        field_name="review_path",
    )
    requested_review_path = args.review.resolve()
    report = validate_anonymization_review(
        declared_review_path,
        expected_pairs=expected_review_pairs(layout),
        expected_outputs=expected_review_outputs(layout),
        expected_render_spec_sha256=_optional_text(metadata.get("render_spec_sha256")),
        expected_artifact_manifest_sha256=_optional_text(
            metadata.get("artifact_manifest_sha256")
        ),
    )
    metadata_layout_hash = metadata.get("layout_sha256")
    layout_hash_matches = metadata_layout_hash == current_layout_hash
    report["preparation_metadata_path"] = str(args.prep_metadata)
    report["requested_review_path"] = str(args.review)
    report["declared_review_path"] = str(declared_review_path)
    report["layout_hash_matches_preparation"] = layout_hash_matches
    _append_check(
        report,
        "layout_hash_matches_preparation",
        layout_hash_matches,
        "private layout matches the layout used to render anonymous inputs",
        "layout changed after anonymous inputs were rendered",
    )
    review_path_matches = requested_review_path == declared_review_path.resolve()
    _append_check(
        report,
        "review_path_matches_preparation_metadata",
        review_path_matches,
        "requested review file is the review file declared by matching preparation metadata",
        "requested review file differs from the review file declared by matching preparation metadata",
    )
    mask_review_inputs = (
        args.base_layout,
        args.candidate_manifest,
        args.candidate_decisions,
        args.page_sweeps,
    )
    if any(mask_review_inputs) and not all(mask_review_inputs):
        _append_check(
            report,
            "grading_mask_review_inputs_complete",
            False,
            "base layout and all grading mask review inputs are supplied",
            (
                "base layout, candidate manifest, decisions, and page sweeps must be "
                "supplied together"
            ),
        )
    elif all(mask_review_inputs):
        provenance = validate_compiled_mask_provenance(
            layout=layout,
            base_layout_path=args.base_layout,
            candidate_manifest_path=args.candidate_manifest,
            decision_path=args.candidate_decisions,
            sweep_path=args.page_sweeps,
        )
        for check in provenance["checks"]:
            _append_check(
                report,
                str(check["id"]),
                check["status"] == "passed",
                str(check["detail"]),
                str(check["detail"]),
            )
    elif isinstance(layout.get("grading_mask_review"), Mapping):
        _append_check(
            report,
            "grading_mask_review_inputs_complete",
            False,
            "base layout and all grading mask review inputs are supplied",
            (
                "compiled layout requires --base-layout, candidate manifest, decisions, "
                "and page sweeps"
            ),
        )
    else:
        _append_check(
            report,
            "grading_mask_review_provenance_present",
            False,
            "compiled grading-mask review provenance is present",
            (
                "identity-only/base layout cannot become model-ready; run candidate "
                "review, compile a new layout, and rerender"
            ),
        )

    render_integrity = _validate_render_integrity(
        prep_metadata_path=args.prep_metadata,
        metadata=metadata,
        layout=layout,
        layout_hash=current_layout_hash,
    )
    for check in render_integrity["checks"]:
        _append_check(
            report,
            str(check["id"]),
            check["status"] == "passed",
            str(check["detail"]),
            str(check["detail"]),
        )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "failed_checks": report["failed_checks"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "ready" else 1


def _validate_render_integrity(
    *,
    prep_metadata_path: Path,
    metadata: Mapping[str, Any],
    layout: Mapping[str, Any],
    layout_hash: str,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    if metadata.get("schema_version") != 2:
        checks.append(
            {
                "id": "render_integrity_metadata_v2",
                "status": "failed",
                "detail": "preparation metadata predates render-integrity binding; rerender required",
            }
        )
        return {"checks": checks}
    identity_rectangles = metadata.get("identity_redaction_rectangles")
    try:
        expected_spec = build_render_spec(
            layout=layout,
            layout_sha256=layout_hash,
            identity_rectangles=identity_rectangles,
            render_scale=float(metadata.get("render_scale")),
        )
        expected_spec_hash = canonical_json_sha256(expected_spec)
    except (TypeError, ValueError, KeyError):
        expected_spec_hash = ""
    actual_spec_hash = metadata.get("render_spec_sha256")
    checks.append(
        {
            "id": "render_spec_matches_preparation",
            "status": "passed" if expected_spec_hash and actual_spec_hash == expected_spec_hash else "failed",
            "detail": (
                "layout, identity masks, and render scale match preparation"
                if expected_spec_hash and actual_spec_hash == expected_spec_hash
                else "layout, identity masks, or render scale differ from preparation"
            ),
        }
    )
    relative_manifest = metadata.get("artifact_manifest_path")
    output_root = prep_metadata_path.parent.parent
    artifact_path: Path | None = None
    if isinstance(relative_manifest, str) and relative_manifest:
        candidate = output_root / relative_manifest
        try:
            candidate.resolve().relative_to(output_root.resolve())
        except ValueError:
            artifact_path = None
        else:
            artifact_path = candidate
    manifest_hash_matches = (
        artifact_path is not None
        and artifact_path.is_file()
        and metadata.get("artifact_manifest_sha256") == sha256_file(artifact_path)
    )
    checks.append(
        {
            "id": "artifact_manifest_hash_matches_preparation",
            "status": "passed" if manifest_hash_matches else "failed",
            "detail": (
                "artifact manifest matches preparation metadata"
                if manifest_hash_matches
                else "artifact manifest is missing or differs from preparation metadata"
            ),
        }
    )
    if manifest_hash_matches and artifact_path is not None:
        artifact_report = validate_artifact_manifest(
            output_root=output_root,
            layout=layout,
            manifest=_load_json_object(artifact_path),
            render_spec_sha256=str(actual_spec_hash),
        )
        checks.extend(artifact_report["checks"])
    return {"checks": checks}


def _resolve_declared_output_path(
    *,
    prep_metadata_path: Path,
    relative_path: object,
    field_name: str,
) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError(f"preparation metadata must contain a non-empty {field_name}")
    output_root = prep_metadata_path.resolve().parent.parent
    candidate = (output_root / relative_path).resolve()
    try:
        candidate.relative_to(output_root)
    except ValueError as error:
        raise ValueError(
            f"preparation metadata {field_name} must resolve inside its output root"
        ) from error
    return candidate


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _append_check(
    report: dict[str, Any],
    check_id: str,
    passed: bool,
    passed_detail: str,
    failed_detail: str,
) -> None:
    report["checks"].append(
        {
            "id": check_id,
            "status": "passed" if passed else "failed",
            "detail": passed_detail if passed else failed_detail,
        }
    )
    if not passed:
        report["failed_checks"].append(check_id)
        report["status"] = "not_ready"


def _parse_rectangle(value: str) -> dict[str, float]:
    try:
        left, top, right, bottom = [float(part.strip()) for part in value.split(",")]
    except ValueError as error:
        raise ValueError(
            "redaction rectangle must use LEFT,TOP,RIGHT,BOTTOM"
        ) from error
    rectangle = {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
    }
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError(f"redaction rectangle is outside normalized page bounds: {value}")
    return rectangle


def _apply_rectangles(
    image: Image.Image,
    rectangles: Sequence[Mapping[str, float]],
) -> None:
    draw = ImageDraw.Draw(image)
    for rectangle in rectangles:
        draw.rectangle(
            (
                int(image.width * float(rectangle["left"])),
                int(image.height * float(rectangle["top"])),
                int(image.width * float(rectangle["right"])),
                int(image.height * float(rectangle["bottom"])),
            ),
            fill="white",
        )


def _write_pdf(path: Path, images: Sequence[Image.Image]) -> None:
    if not images:
        raise ValueError(f"no pages were rendered for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        path,
        "PDF",
        save_all=True,
        append_images=list(images[1:]),
        resolution=144,
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
