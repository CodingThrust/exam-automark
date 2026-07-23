"""Advisor-facing entry point for a reproducible grading benchmark handoff."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.core.advisor_workflow import main


if __name__ == "__main__":
    raise SystemExit(main())
