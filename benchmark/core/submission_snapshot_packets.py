from __future__ import annotations

"""Build blind packets directly from final-approved submission snapshots.

The regular packet builder accepts a pre-arranged ``inputs/<student>/`` tree.
Final-approved anonymous snapshots deliberately use a different layout and put
the page order in their manifest.  This adapter is the only bridge between the
two: it validates the immutable snapshot first, then copies every approved page
for a selected anonymous submission into one packet input directory.

It never interprets the images, assigns a mark, or authorizes a model run.
"""

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .anonymization import ANONYMOUS_ID_PATTERN, SHA256_PATTERN, sha256_file
from .anonymous_cohort_snapshot import (
    COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    COHORT_SNAPSHOT_RECORD_TYPE,
)
from .packets import (
    SAFE_TOKEN,
    PromptPacketResult,
    audit_prompt_packet,
    directory_digest,
    grading_output_schema,
    transcript_output_schema,
)
from .rubrics import require_valid_rubric
from .schema import CourseSpec
from .submission_scope_workflow import (
    SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    SUBMISSION_SNAPSHOT_RECORD_TYPE,
)


_SUPPORTED_MANIFESTS = {
    SUBMISSION_SNAPSHOT_RECORD_TYPE: SUBMISSION_SNAPSHOT_MANIFEST_RELATIVE_PATH,
    COHORT_SNAPSHOT_RECORD_TYPE: COHORT_SNAPSHOT_MANIFEST_RELATIVE_PATH,
}
SUBMISSION_SNAPSHOT_PACKET_INSTRUCTIONS = """# Blind Grading Experiment Packet

Work only with files inside this packet. Do not inspect parent directories or
any other workspace. Read `prompt.txt`, `manifest.json`, `course.json`, and the
files under `inputs/`.

For each anonymous student, read `inputs/<student_id>/submission.json` first.
It lists every approved page in source-page order. Treat all of those pages as
one submission before scoring any question. Never grade, total, or average
individual pages. The page list is evidence of scope only; do not invent work
that is absent from the listed pages.

Write exactly one JSON file per expected anonymous student under `outputs/`,
named `<student_id>.json`. Preserve every anonymous ID exactly. Return data that
matches `output.schema.json`.
"""


@dataclass(frozen=True)
class SubmissionSnapshotPacketSpec:
    """Parameters for a packet built from one immutable anonymous snapshot."""

    course: CourseSpec
    packet_id: str
    condition: str
    task: str
    prompt_text: str
    student_ids: tuple[str, ...]
    snapshot_root: Path
    output_root: Path
    rubric: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for label, value in (
            ("packet_id", self.packet_id),
            ("condition", self.condition),
            ("task", self.task),
        ):
            if not isinstance(value, str) or SAFE_TOKEN.fullmatch(value) is None:
                raise ValueError(f"{label} must be a safe token")
        if self.task not in {"transcribe", "grade"}:
            raise ValueError(f"unsupported packet task: {self.task}")
        if not self.prompt_text.strip():
            raise ValueError("prompt_text must not be blank")
        if not self.student_ids:
            raise ValueError("student_ids must not be empty")
        for student_id in self.student_ids:
            self.course.validate_student_id(student_id)
        if len(self.student_ids) != len(set(self.student_ids)):
            raise ValueError("student_ids must be unique")
        if self.task == "grade" and self.rubric is None:
            raise ValueError("grade packets require a rubric")
        object.__setattr__(self, "student_ids", tuple(self.student_ids))
        object.__setattr__(self, "snapshot_root", Path(self.snapshot_root))
        object.__setattr__(self, "output_root", Path(self.output_root))
        object.__setattr__(self, "metadata", dict(self.metadata))


def build_submission_snapshot_packet(
    spec: SubmissionSnapshotPacketSpec,
) -> PromptPacketResult:
    """Build and audit one packet from selected immutable snapshot entries.

    Output must remain inside the source snapshot's private ``Data`` boundary.
    This is deliberately stricter than the generic packet builder because the
    input tree contains real anonymous student work.
    """

    if spec.rubric is not None:
        require_valid_rubric(spec.rubric, spec.course)
    snapshot_root, manifest_path, manifest = _load_snapshot(spec)
    submissions = _index_submissions(
        manifest, snapshot_root=snapshot_root, course=spec.course
    )
    selected = _select_submissions(submissions, spec.student_ids)
    packet_path = _validate_output_root(
        snapshot_root=snapshot_root,
        output_root=spec.output_root,
        packet_id=spec.packet_id,
    )

    temporary = Path(
        tempfile.mkdtemp(prefix=f".{spec.packet_id}.tmp-", dir=packet_path.parent)
    )
    try:
        _write_packet(
            packet_path=temporary,
            spec=spec,
            manifest=manifest,
            manifest_path=manifest_path,
            snapshot_root=snapshot_root,
            selected=selected,
        )
        findings = audit_prompt_packet(temporary)
        if findings:
            raise ValueError("prompt packet audit failed: " + "; ".join(findings))
        temporary.replace(packet_path)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    return PromptPacketResult(
        packet_path=packet_path,
        packet_hash=directory_digest(packet_path),
        manifest=json.loads((packet_path / "manifest.json").read_text(encoding="utf-8")),
    )


def _load_snapshot(
    spec: SubmissionSnapshotPacketSpec,
) -> tuple[Path, Path, dict[str, Any]]:
    if spec.snapshot_root.is_symlink() or not spec.snapshot_root.is_dir():
        raise ValueError("snapshot_root must be a real directory")
    root = spec.snapshot_root.resolve()
    candidates = [
        (record_type, root / relative)
        for record_type, relative in _SUPPORTED_MANIFESTS.items()
        if (root / relative).is_file()
    ]
    if len(candidates) != 1:
        raise ValueError("snapshot must contain exactly one supported manifest")
    expected_record_type, manifest_path = candidates[0]
    if manifest_path.is_symlink():
        raise ValueError("snapshot manifest must be a regular file")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("snapshot manifest is not readable JSON") from error
    if not isinstance(manifest, dict) or manifest.get("record_type") != expected_record_type:
        raise ValueError("snapshot manifest has an unexpected record_type")
    if manifest.get("assessment_id") != spec.course.assessment_id:
        raise ValueError("snapshot assessment_id does not match course specification")
    if manifest.get("grading_unit") != "anonymous_submission":
        raise ValueError("snapshot grading_unit must be anonymous_submission")
    if manifest.get("model_run_allowed") is not False:
        raise ValueError("snapshot must remain model-blocked before packet creation")
    return root, manifest_path, manifest


def _index_submissions(
    manifest: Mapping[str, Any], *, snapshot_root: Path, course: CourseSpec
) -> dict[str, dict[str, Any]]:
    raw_submissions = manifest.get("submissions")
    if not isinstance(raw_submissions, list) or not raw_submissions:
        raise ValueError("snapshot manifest must contain submissions")
    expected_files = {
        _SUPPORTED_MANIFESTS[str(manifest["record_type"])].as_posix()
    }
    indexed: dict[str, dict[str, Any]] = {}
    image_count = 0
    for raw_submission in raw_submissions:
        if not isinstance(raw_submission, Mapping):
            raise ValueError("snapshot submission must be an object")
        anonymous_id = raw_submission.get("anonymous_id")
        if (
            not isinstance(anonymous_id, str)
            or ANONYMOUS_ID_PATTERN.fullmatch(anonymous_id) is None
            or anonymous_id in indexed
        ):
            raise ValueError("snapshot has a duplicate or invalid anonymous_id")
        course.validate_student_id(anonymous_id)
        if raw_submission.get("grading_unit") != "anonymous_submission":
            raise ValueError("snapshot submission must use anonymous_submission grading")
        missing_question_ids = raw_submission.get("missing_question_ids")
        if (
            not isinstance(missing_question_ids, list)
            or any(item not in course.question_ids for item in missing_question_ids)
            or len(set(missing_question_ids)) != len(missing_question_ids)
        ):
            raise ValueError("missing_question_ids must be unique course question IDs")
        raw_images = raw_submission.get("images")
        if not isinstance(raw_images, list) or not raw_images:
            raise ValueError("snapshot submission must contain images")
        images: list[dict[str, Any]] = []
        prior_page = 0
        for raw_image in raw_images:
            image = _validate_snapshot_image(
                raw_image,
                snapshot_root=snapshot_root,
                prior_page=prior_page,
                expected_files=expected_files,
            )
            prior_page = image["source_page"]
            images.append(image)
            image_count += 1
        indexed[anonymous_id] = {
            "anonymous_id": anonymous_id,
            "missing_question_ids": list(missing_question_ids),
            "images": images,
        }

    if manifest.get("student_count") != len(indexed):
        raise ValueError("snapshot student_count does not match submissions")
    if manifest.get("image_count") != image_count:
        raise ValueError("snapshot image_count does not match submissions")
    actual_files = {
        path.relative_to(snapshot_root).as_posix()
        for path in snapshot_root.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("snapshot has unexpected or missing files")
    return indexed


def _validate_snapshot_image(
    raw_image: object,
    *,
    snapshot_root: Path,
    prior_page: int,
    expected_files: set[str],
) -> dict[str, Any]:
    if not isinstance(raw_image, Mapping):
        raise ValueError("snapshot image must be an object")
    source_page = raw_image.get("source_page")
    if type(source_page) is not int or source_page < 1 or source_page <= prior_page:
        raise ValueError("snapshot source_page values must be positive and ordered")
    relative = _safe_relative_png(raw_image.get("snapshot_image"))
    if relative in expected_files:
        raise ValueError("snapshot has a duplicate image path")
    digest = raw_image.get("sha256")
    byte_count = raw_image.get("bytes")
    if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
        raise ValueError("snapshot image sha256 is invalid")
    if type(byte_count) is not int or byte_count < 1:
        raise ValueError("snapshot image bytes must be a positive integer")
    image_path = (snapshot_root / relative).resolve()
    if (
        not _is_within(image_path, snapshot_root)
        or not image_path.is_file()
        or image_path.is_symlink()
        or sha256_file(image_path) != digest
        or image_path.stat().st_size != byte_count
    ):
        raise ValueError("snapshot image does not match its manifest")
    expected_files.add(relative)
    return {
        "source_page": source_page,
        "snapshot_image": relative,
        "sha256": digest,
        "bytes": byte_count,
    }


def _select_submissions(
    submissions: Mapping[str, dict[str, Any]], student_ids: Sequence[str]
) -> tuple[dict[str, Any], ...]:
    selected = []
    for student_id in student_ids:
        submission = submissions.get(student_id)
        if submission is None:
            raise ValueError(f"selected anonymous student is missing from snapshot: {student_id}")
        selected.append(submission)
    return tuple(selected)


def _validate_output_root(
    *, snapshot_root: Path, output_root: Path, packet_id: str
) -> Path:
    target_parent = output_root.resolve()
    private_root = _nearest_data_ancestor(snapshot_root)
    if private_root is None or not _is_within(target_parent, private_root):
        raise ValueError("packet output must stay inside the snapshot private Data boundary")
    packet_path = target_parent / packet_id
    if packet_path.exists() or packet_path.is_symlink():
        raise FileExistsError(f"packet already exists: {packet_path}")
    if _is_within(packet_path, snapshot_root) or _is_within(snapshot_root, packet_path):
        raise ValueError("packet output must not overlap the immutable snapshot")
    target_parent.mkdir(parents=True, exist_ok=True)
    return packet_path


def _write_packet(
    *,
    packet_path: Path,
    spec: SubmissionSnapshotPacketSpec,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    snapshot_root: Path,
    selected: Sequence[Mapping[str, Any]],
) -> None:
    (packet_path / "inputs").mkdir()
    (packet_path / "outputs").mkdir()
    for submission in selected:
        student_id = str(submission["anonymous_id"])
        student_root = packet_path / "inputs" / student_id
        pages_root = student_root / "pages"
        pages_root.mkdir(parents=True)
        page_records = []
        for image in submission["images"]:
            source_page = int(image["source_page"])
            filename = f"p{source_page:04d}.png"
            source = snapshot_root / str(image["snapshot_image"])
            destination = pages_root / filename
            shutil.copyfile(source, destination)
            if sha256_file(destination) != image["sha256"]:
                raise ValueError("copied packet image hash mismatch")
            page_records.append(
                {
                    "source_page": source_page,
                    "file": f"pages/{filename}",
                    "sha256": image["sha256"],
                    "bytes": image["bytes"],
                }
            )
        _write_json(
            student_root / "submission.json",
            {
                "schema_version": 1,
                "grading_unit": "anonymous_submission",
                "student_id": student_id,
                "missing_question_ids": submission["missing_question_ids"],
                "pages": page_records,
            },
        )

    _write_json(packet_path / "course.json", spec.course.to_dict())
    (packet_path / "prompt.txt").write_text(
        _normalize_text(spec.prompt_text), encoding="utf-8", newline="\n"
    )
    (packet_path / "INSTRUCTIONS.md").write_text(
        SUBMISSION_SNAPSHOT_PACKET_INSTRUCTIONS,
        encoding="utf-8",
        newline="\n",
    )
    schema = (
        transcript_output_schema(spec.course)
        if spec.task == "transcribe"
        else grading_output_schema(spec.course)
    )
    _write_json(packet_path / "output.schema.json", schema)

    rubric_hash = None
    if spec.rubric is not None:
        _write_json(packet_path / "rubric.json", spec.rubric)
        rubric_hash = _file_hash(packet_path / "rubric.json")

    metadata = dict(spec.metadata)
    metadata.update(
        {
            "input_mode": "anonymous_submission_snapshot",
            "snapshot_record_type": manifest["record_type"],
            "snapshot_manifest_sha256": sha256_file(manifest_path),
            "input_snapshot_manifest_sha256": sha256_file(manifest_path),
            "snapshot_grading_unit": "anonymous_submission",
        }
    )
    if isinstance(manifest.get("cohort_id"), str):
        metadata["snapshot_cohort_id"] = manifest["cohort_id"]
    if isinstance(manifest.get("scope_id"), str):
        metadata["snapshot_scope_id"] = manifest["scope_id"]

    packet_manifest = {
        "schema_version": 1,
        "packet_id": spec.packet_id,
        "course_id": spec.course.course_id,
        "assessment_id": spec.course.assessment_id,
        "condition": spec.condition,
        "task": spec.task,
        "student_ids": list(spec.student_ids),
        "prompt_hash": _file_hash(packet_path / "prompt.txt"),
        "course_hash": _file_hash(packet_path / "course.json"),
        "output_schema_hash": _file_hash(packet_path / "output.schema.json"),
        "rubric_hash": rubric_hash,
        "input_hashes": {
            student_id: directory_digest(packet_path / "inputs" / student_id)
            for student_id in spec.student_ids
        },
        "metadata": metadata,
    }
    _write_json(packet_path / "manifest.json", packet_manifest)


def _safe_relative_png(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("snapshot_image must be a non-empty POSIX relative PNG path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".png":
        raise ValueError("snapshot_image must be a safe relative PNG path")
    normalized = path.as_posix()
    if normalized != value or normalized == ".":
        raise ValueError("snapshot_image must be normalized")
    return normalized


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


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
