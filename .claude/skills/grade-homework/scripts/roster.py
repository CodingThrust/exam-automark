from __future__ import annotations

import csv
import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REQUIRED_COLUMNS = ("submission_id", "student_name", "student_number")
SAFE_SUBMISSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class RosterError(ValueError):
    """A private roster does not meet the local delivery contract."""


@dataclass(frozen=True)
class RosterEntry:
    submission_id: str
    student_name: str
    student_number: str


def load_roster(path: Path) -> dict[str, RosterEntry]:
    """Load a private roster without exposing its contents in diagnostics."""

    if not path.is_file():
        raise RosterError("roster file is missing")
    require_private_path(path, label="roster file")

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            if set(fieldnames) != set(REQUIRED_COLUMNS) or len(fieldnames) != len(
                REQUIRED_COLUMNS
            ):
                raise RosterError(
                    "roster columns must be exactly submission_id,student_name,student_number"
                )
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise RosterError("roster could not be read") from error

    if not rows:
        raise RosterError("roster must contain at least one student")

    entries: dict[str, RosterEntry] = {}
    seen_numbers: set[str] = set()
    for row in rows:
        submission_id = _required_cell(row, "submission_id")
        student_name = _required_cell(row, "student_name")
        student_number = _required_cell(row, "student_number")
        if not SAFE_SUBMISSION_ID.fullmatch(submission_id):
            raise RosterError("roster submission_id contains unsupported characters")
        if len(student_name) > 256 or len(student_number) > 128:
            raise RosterError("roster field exceeds its supported length")
        if submission_id in entries:
            raise RosterError("roster contains duplicate submission_id")
        if student_number in seen_numbers:
            raise RosterError("roster contains duplicate student_number")
        entries[submission_id] = RosterEntry(
            submission_id=submission_id,
            student_name=student_name,
            student_number=student_number,
        )
        seen_numbers.add(student_number)
    return entries


def require_private_path(path: Path, *, label: str) -> None:
    """Reject private input or output under a tracked Git location."""

    resolved = path.resolve()
    repository_root = next(
        (
            parent
            for parent in (resolved, *resolved.parents)
            if (parent / ".git").exists()
        ),
        None,
    )
    if repository_root is None:
        return
    try:
        relative = resolved.relative_to(repository_root).as_posix()
    except ValueError:
        return
    check = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repository_root.as_posix()}",
            "-C",
            str(repository_root),
            "check-ignore",
            "--quiet",
            "--no-index",
            "--",
            relative,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        return
    if check.returncode == 1:
        raise RosterError(f"{label} inside a Git worktree must be private and ignored")
    raise RosterError(f"could not verify whether {label} is ignored")


def _required_cell(row: dict[str, str | None], key: str) -> str:
    value = row.get(key)
    if value is None:
        raise RosterError("roster row is missing a required value")
    normalized = value.strip()
    if not normalized:
        raise RosterError("roster row contains a blank required value")
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a private roster without printing its contents."
    )
    parser.add_argument("private_roster", type=Path)
    namespace = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        roster = load_roster(namespace.private_roster)
    except RosterError as error:
        print(f"invalid roster: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "ok", "student_count": len(roster)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
