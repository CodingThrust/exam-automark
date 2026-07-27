"""Run one public test suite and reject false-green zero-test discovery."""

from __future__ import annotations

import argparse
import os
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SuiteSpec:
    start_dir: Path
    minimum_tests: int


REPO_ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "core": SuiteSpec(
        start_dir=REPO_ROOT / "tests" / "benchmark" / "core",
        minimum_tests=246,
    ),
    "physics": SuiteSpec(
        start_dir=REPO_ROOT / "tests" / "benchmark" / "physics",
        minimum_tests=85,
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a public unittest suite with a minimum test-count gate."
    )
    parser.add_argument("suite", choices=sorted(SUITES))
    args = parser.parse_args(argv)

    spec = SUITES[args.suite]
    os.chdir(REPO_ROOT)
    sys.path.insert(0, str(REPO_ROOT))
    discovered = unittest.defaultTestLoader.discover(
        str(spec.start_dir),
        pattern="test_*.py",
    )
    test_count = discovered.countTestCases()
    print(
        f"Discovered {test_count} {args.suite} tests "
        f"(required minimum: {spec.minimum_tests}).",
        flush=True,
    )
    if test_count < spec.minimum_tests:
        print(
            "Refusing a false-green CI result: test discovery returned fewer "
            "tests than the reviewed baseline.",
            file=sys.stderr,
        )
        return 2

    result = unittest.TextTestRunner(verbosity=2).run(discovered)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
