"""Run a reproducible headless grading packet.

This script is intentionally thin: it keeps the reproducing command stable while
delegating validation and metadata writing to the package CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.core.cli import main


def _argv(argv: list[str]) -> list[str]:
    if argv and argv[0] == "run-headless-packet":
        return argv
    return ["run-headless-packet", *argv]


if __name__ == "__main__":
    raise SystemExit(main(_argv(sys.argv[1:])))
