from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}
SOLUTION_MARKERS = ("solution", "solutions", "answer", "answers", "rubric", "key")
SKIP_DIRS = {"grades", "__pycache__"}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]) if args else Path.cwd()
    if not root.is_dir():
        print(json.dumps({"solutions_error": f"not a directory: {root}"}))
        return 2

    files = list(_iter_files(root))
    candidates = [path for path in files if _is_supported(path)]
    solutions = [path for path in candidates if _looks_like_solution(path)]
    submissions = [path for path in candidates if path not in set(solutions)]
    late_students = sorted(
        {
            _student_id(path)
            for path in submissions
            if "_late_" in path.name.lower()
        }
    )
    solutions_error = None
    if not solutions:
        solutions_error = "no solutions or rubric file found"
    elif len(solutions) > 1:
        solutions_error = "multiple solutions or rubric candidates found"

    payload = {
        "root": root.resolve().as_posix(),
        "solutions_error": solutions_error,
        "solutions_candidates": [_rel(root, path) for path in sorted(solutions)],
        "submissions": [
            {
                "student": _student_id(path),
                "path": _rel(root, path),
                "suffix": path.suffix.lower(),
                "late": "_late_" in path.name.lower(),
            }
            for path in sorted(submissions, key=lambda path: (_student_id(path), _rel(root, path)))
        ],
        "late_students": late_students,
        "extension_counts": dict(sorted(Counter(path.suffix.lower() for path in submissions).items())),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


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


def _student_id(path: Path) -> str:
    stem = path.stem
    return stem.split("_", 1)[0] if "_" in stem else stem


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
