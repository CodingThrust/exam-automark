from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from roster import RosterError, load_roster


SUPPORTED_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
    ".docx",
}
SOLUTION_MARKERS = ("solution", "solutions", "answer", "answers", "rubric", "key")
SKIP_DIRS = {"grades", "rendered", "marked", "annotations", "__pycache__"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover a private grading batch.")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--roster", type=Path)
    namespace = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    root = Path(namespace.root)
    if not root.is_dir():
        print(json.dumps({"status": "error", "solutions_error": "not a directory"}))
        return 2

    files = list(_iter_files(root))
    candidates = [path for path in files if _is_supported(path)]
    submissions_root = root / "submissions"
    grouped_mode = submissions_root.is_dir()
    course_candidates = [
        path
        for path in candidates
        if not grouped_mode or not _is_under(path, submissions_root)
    ]
    solutions = [path for path in course_candidates if _looks_like_solution(path)]
    solutions_error = _solutions_error(solutions)
    submission_files = [
        path
        for path in candidates
        if path not in set(solutions) and (not grouped_mode or _is_under(path, submissions_root))
    ]
    grouped, ungrouped_count = _group_submission_files(
        root=root, submissions_root=submissions_root, files=submission_files, grouped_mode=grouped_mode
    )

    grouping_errors: list[str] = []
    if ungrouped_count:
        grouping_errors.append("submission_file_without_submission_id")
    roster_used = namespace.roster is not None
    roster_error = None
    if namespace.roster is not None:
        try:
            roster = load_roster(namespace.roster)
        except RosterError as error:
            roster = {}
            roster_error = str(error)
        if roster_error is None:
            unknown = set(grouped) - set(roster)
            missing = set(roster) - set(grouped)
            if unknown:
                grouping_errors.append("scan_group_not_in_roster")
            if missing:
                grouping_errors.append("roster_entry_without_scan_group")

    submissions = [
        {
            "student_id": student_id,
            "student": student_id,
            "files": [
                {
                    "source_id": f"source-{index:03d}",
                    "source_order": index,
                    "suffix": path.suffix.lower(),
                }
                for index, path in enumerate(paths, start=1)
            ],
            "late": any("_late_" in path.name.lower() for path in paths),
        }
        for student_id, paths in sorted(grouped.items())
    ]
    late_students = [
        item["student_id"] for item in submissions if item["late"]
    ]
    payload = {
        "status": "ok" if not solutions_error and not roster_error and not grouping_errors else "review_required",
        # A batch manifest must remain portable and must not reveal a local path.
        "root": ".",
        "solutions_error": solutions_error,
        "solutions_candidates": [_rel(root, path) for path in sorted(solutions)],
        "submissions": submissions,
        "late_students": late_students,
        "extension_counts": dict(
            sorted(Counter(path.suffix.lower() for path in submission_files).items())
        ),
        "grouping_mode": "submission_directories" if grouped_mode else "legacy_filename_prefix",
        "roster_used": roster_used,
        "grouping_errors": grouping_errors,
        "roster_error": roster_error,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "ok" else 3


def _iter_files(root: Path) -> list[Path]:
    results = []
    for path in root.rglob("*"):
        if any(part.startswith(".") or part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            results.append(path)
    return results


def _is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_SUFFIXES


def _looks_like_solution(path: Path) -> bool:
    name = path.stem.lower()
    return any(marker in name for marker in SOLUTION_MARKERS)


def _solutions_error(solutions: list[Path]) -> str | None:
    if not solutions:
        return "no solutions or rubric file found"
    if len(solutions) > 1:
        return "multiple solutions or rubric candidates found"
    return None


def _group_submission_files(
    *,
    root: Path,
    submissions_root: Path,
    files: list[Path],
    grouped_mode: bool,
) -> tuple[dict[str, list[Path]], int]:
    grouped: dict[str, list[Path]] = {}
    ungrouped_count = 0
    for path in files:
        if grouped_mode:
            relative = path.relative_to(submissions_root)
            if len(relative.parts) < 2:
                ungrouped_count += 1
                continue
            student_id = relative.parts[0]
        else:
            student_id = _student_id(path)
        grouped.setdefault(student_id, []).append(path)
    for paths in grouped.values():
        paths.sort(key=lambda path: _natural_path_key(_rel(root, path)))
    return grouped, ungrouped_count


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _natural_path_key(value: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", value.casefold())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def _student_id(path: Path) -> str:
    stem = path.stem
    return stem.split("_", 1)[0] if "_" in stem else stem


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
