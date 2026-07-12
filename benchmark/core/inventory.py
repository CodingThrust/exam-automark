import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SYSTEM_ARTIFACT_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
SENSITIVE_DIRECTORY_NAMES = {
    "grades",
    "report",
    "reports",
    "runs",
    "student_map",
}


def build_data_inventory(data_root: Path, course_id: str) -> dict[str, Any]:
    """Summarize a local course data folder without recording raw filenames."""
    course_root = Path(data_root) / course_id
    if not course_root.is_dir():
        raise FileNotFoundError(f"course data directory missing: {course_root}")

    files = _data_files(course_root)
    submission_root = course_root / "submissions"
    submission_files = (
        _data_files(submission_root) if submission_root.is_dir() else []
    )
    top_level_files = [
        path
        for path in files
        if path.parent == course_root and path.name not in SYSTEM_ARTIFACT_NAMES
    ]
    directory_count = sum(1 for path in course_root.rglob("*") if path.is_dir())

    inventory = {
        "schema_version": 1,
        "course_id": course_id,
        "source_root": f"Data/{course_id}",
        "snapshot_hash": directory_digest(course_root),
        "privacy_policy": {
            "raw_filenames_recorded": False,
            "student_identity_maps_recorded": False,
            "git_tracking_allowed": False,
        },
        "counts": {
            "files": len(files),
            "directories": directory_count,
            "top_level_files": len(top_level_files),
            "submission_files": len(submission_files),
        },
        "extension_counts": _extension_counts(files),
        "submission_extension_counts": _extension_counts(submission_files),
        "layout": {
            "has_submissions_dir": submission_root.is_dir(),
            "has_benchmark_dir": (course_root / "benchmark").is_dir(),
            "has_grades_dir": (course_root / "grades").is_dir(),
            "has_report_dir": (course_root / "report").is_dir(),
        },
        "packet_exclusion_policy": _packet_exclusion_policy(course_root),
        "notes": _inventory_notes(course_id, course_root, submission_root),
    }
    return inventory


def write_data_inventory(
    data_root: Path,
    course_id: str,
    output_path: Path,
) -> dict[str, Any]:
    inventory = build_data_inventory(data_root, course_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return inventory


def directory_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in _data_files(path):
        relative = file_path.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _data_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(
        item
        for item in path.rglob("*")
        if item.is_file() and item.name not in SYSTEM_ARTIFACT_NAMES
    )


def _extension_counts(files: list[Path]) -> dict[str, int]:
    counts = Counter(_extension(path) for path in files)
    return dict(sorted(counts.items()))


def _extension(path: Path) -> str:
    suffix = path.suffix.lower()
    return suffix if suffix else "[no extension]"


def _packet_exclusion_policy(course_root: Path) -> list[str]:
    exclusions = []
    for path in sorted(item for item in course_root.rglob("*") if item.is_dir()):
        name = path.name.lower()
        if name in SENSITIVE_DIRECTORY_NAMES:
            exclusions.append(path.relative_to(course_root).as_posix() + "/")
    for sensitive_file in (
        course_root / "benchmark" / "manifest" / "student_map.csv",
        course_root / "grades" / "grades.csv",
    ):
        if sensitive_file.exists():
            exclusions.append(sensitive_file.relative_to(course_root).as_posix())
    return sorted(set(exclusions))


def _inventory_notes(
    course_id: str,
    course_root: Path,
    submission_root: Path,
) -> list[str]:
    notes = [
        "Inventory is local-only; private anonymous data snapshots should live in HKUST-GZ GitLab.",
        "Raw filenames are intentionally omitted because they may contain student identifiers.",
    ]
    if submission_root.is_dir():
        notes.append(
            "Submissions directory exists; create an anonymous packet input tree before model runs."
        )
    if (course_root / "grades").exists() or (course_root / "report").exists():
        notes.append(
            "Reference scores, feedback, reports, and identity maps must never be copied into prompt packets."
        )
    if course_id.upper() == "DSAA3073":
        notes.append(
            "Local file names appear to use DSAA3071 labels; confirm the course identifier before freezing."
        )
    return notes
