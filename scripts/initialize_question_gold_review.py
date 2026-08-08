from __future__ import annotations

"""Initialize a private gold table and reviewer binding for one anonymous snapshot."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.core.anonymization import sha256_file  # noqa: E402
from benchmark.core.anonymous_cohort_snapshot import (  # noqa: E402
    COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    COHORT_SNAPSHOT_RECORD_TYPE,
)
from benchmark.core.readiness_scaffolding import initialize_blank_gold  # noqa: E402
from benchmark.core.schema import CourseSpec  # noqa: E402
from benchmark.core.scoped_anonymous_images import (  # noqa: E402
    SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SNAPSHOT_RECORD_TYPE,
)
from benchmark.core.submission_scope_workflow import (  # noqa: E402
    SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SUBMISSION_SNAPSHOT_RECORD_TYPE,
)


_SUPPORTED_MANIFESTS = {
    SNAPSHOT_RECORD_TYPE: SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SUBMISSION_SNAPSHOT_RECORD_TYPE: SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    COHORT_SNAPSHOT_RECORD_TYPE: COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH,
}


def initialize_question_gold_review(
    *, course_path: Path, snapshot_root: Path, output_root: Path
) -> dict[str, object]:
    """Create idempotent private gold and binding files without reading answers."""

    course_file = _require_regular_file(course_path, "course specification")
    course = CourseSpec.from_json_path(course_file)
    root = _require_regular_directory(snapshot_root, "anonymous snapshot root")
    manifest_path, manifest = _load_supported_manifest(root)
    if manifest.get("assessment_id") != course.assessment_id:
        raise ValueError("anonymous snapshot assessment_id does not match the course specification")
    if manifest.get("model_run_allowed") is not False:
        raise ValueError("question-gold initialization requires a model-free anonymous snapshot")
    student_ids = _student_ids_from_manifest(manifest, record_type=str(manifest["record_type"]))
    for student_id in student_ids:
        course.validate_student_id(student_id)

    target = Path(output_root).resolve()
    _validate_private_output_root(target=target, snapshot_root=root)
    gold_result = initialize_blank_gold(course, student_ids, target / "question-gold.csv")
    binding = {
        "schema_version": 2,
        "record_type": "question_gold_reviewer_binding",
        "course_id": course.course_id,
        "course_assessment_id": course.assessment_id,
        "course_spec_sha256": sha256_file(course_file),
        "scoped_snapshot_assessment_id": manifest["assessment_id"],
        "scoped_snapshot_manifest_sha256": sha256_file(manifest_path),
        "snapshot_record_type": manifest["record_type"],
        "snapshot_manifest_relative_path": manifest_path.relative_to(root).as_posix(),
    }
    binding_path = target / "reviewer-binding.json"
    binding_status = _write_only_if_empty_or_identical(binding_path, binding)
    return {
        "status": "ready",
        "gold_status": gold_result["status"],
        "binding_status": binding_status,
        "gold_path": str(target / "question-gold.csv"),
        "binding_path": str(binding_path),
        "student_count": len(student_ids),
        "question_count": len(course.question_ids),
        "model_run_allowed": False,
    }


def _load_supported_manifest(root: Path) -> tuple[Path, dict[str, Any]]:
    candidates = [
        (record_type, root / relative)
        for record_type, relative in _SUPPORTED_MANIFESTS.items()
        if (root / relative).is_file()
    ]
    if len(candidates) != 1:
        raise ValueError("anonymous snapshot root must contain exactly one supported manifest")
    expected_record_type, manifest_path = candidates[0]
    manifest_file = _require_regular_file(manifest_path, "anonymous snapshot manifest")
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("anonymous snapshot manifest is not readable JSON") from error
    if not isinstance(payload, dict) or payload.get("record_type") != expected_record_type:
        raise ValueError("anonymous snapshot manifest has an unexpected record_type")
    return manifest_file, payload


def _student_ids_from_manifest(payload: Mapping[str, Any], *, record_type: str) -> tuple[str, ...]:
    if record_type == SNAPSHOT_RECORD_TYPE:
        raw_images = payload.get("images")
        if not isinstance(raw_images, list) or not raw_images:
            raise ValueError("scoped snapshot manifest must contain images")
        student_ids = {
            item.get("anonymous_id")
            for item in raw_images
            if isinstance(item, Mapping) and isinstance(item.get("anonymous_id"), str)
        }
    else:
        raw_submissions = payload.get("submissions")
        if not isinstance(raw_submissions, list) or not raw_submissions:
            raise ValueError("submission snapshot manifest must contain submissions")
        student_ids = {
            item.get("anonymous_id")
            for item in raw_submissions
            if isinstance(item, Mapping) and isinstance(item.get("anonymous_id"), str)
        }
    if not student_ids or payload.get("student_count") != len(student_ids):
        raise ValueError("anonymous snapshot student_count does not match its entries")
    return tuple(sorted(student_ids))


def _validate_private_output_root(*, target: Path, snapshot_root: Path) -> None:
    if _is_within(target, snapshot_root):
        raise ValueError("gold-review output must not be written inside the immutable snapshot")
    private_root = _nearest_data_ancestor(snapshot_root) or snapshot_root.parent
    if not _is_within(target, private_root):
        raise ValueError("gold-review output must stay inside the snapshot private-data boundary")


def _require_regular_file(path: Path, label: str) -> Path:
    candidate = Path(path).resolve()
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError(f"{label} must be a regular file")
    return candidate


def _require_regular_directory(path: Path, label: str) -> Path:
    candidate = Path(path).resolve()
    if not candidate.is_dir() or candidate.is_symlink():
        raise ValueError(f"{label} must be a regular directory")
    return candidate


def _nearest_data_ancestor(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if candidate.name.lower() == "data":
            return candidate
    return None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _write_only_if_empty_or_identical(path: Path, payload: Mapping[str, Any]) -> str:
    encoded = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if not path.is_file() or path.read_bytes() != encoded:
            raise ValueError("refusing to overwrite divergent private reviewer binding")
        return "already_initialized"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return "initialized"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Initialize a private question-level gold CSV and hash-bound reviewer binding "
            "for a final-approved anonymous snapshot. No model is called."
        )
    )
    parser.add_argument("--course", type=Path, required=True)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--private-output-acknowledged", action="store_true")
    args = parser.parse_args(argv)
    if not args.private_output_acknowledged:
        parser.error("--private-output-acknowledged is required")
    try:
        result = initialize_question_gold_review(
            course_path=args.course,
            snapshot_root=args.snapshot_root,
            output_root=args.output_root,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
