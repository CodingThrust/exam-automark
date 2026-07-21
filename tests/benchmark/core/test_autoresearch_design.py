import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "experiments/records/autoresearch-design/run_experiment.py"


class AutoresearchDesignScriptTests(unittest.TestCase):
    def test_dry_run_from_single_prompt_writes_accept_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dry-run-result.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--mode",
                    "dry-run",
                    "--record-id",
                    "autoresearch-mvp-test",
                    "--prompt",
                    "experiments/records/autoresearch-design/single-prompt.md",
                    "--course-spec",
                    "experiments/course_specs/physics_week9.json",
                    "--data-inventory",
                    "experiments/data_inventory/physics.json",
                    "--baseline-skill",
                    "experiments/skill_versions/skill_baseline_v1.json",
                    "--candidate-skill",
                    "experiments/skill_versions/skill_candidate_v2.json",
                    "--baseline-metric",
                    "2.25",
                    "--candidate-metric",
                    "2.00",
                    "--generated-at",
                    "2026-07-21T00:00:00Z",
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["mode"], "dry-run")
        self.assertEqual(payload["single_prompt"]["path"], "experiments/records/autoresearch-design/single-prompt.md")
        self.assertEqual(payload["decision"]["status"], "accept")
        self.assertEqual(payload["decision"]["primary_metric"], "total_score_mae")
        self.assertEqual(payload["decision"]["baseline_metric"], 2.25)
        self.assertEqual(payload["decision"]["candidate_metric"], 2.0)
        self.assertLess(payload["decision"]["delta"], 0)

    def test_dry_run_rejects_candidate_when_metric_does_not_improve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dry-run-result.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--mode",
                    "dry-run",
                    "--record-id",
                    "autoresearch-mvp-test-reject",
                    "--prompt",
                    "experiments/records/autoresearch-design/single-prompt.md",
                    "--course-spec",
                    "experiments/course_specs/physics_week9.json",
                    "--data-inventory",
                    "experiments/data_inventory/physics.json",
                    "--baseline-skill",
                    "experiments/skill_versions/skill_baseline_v1.json",
                    "--candidate-skill",
                    "experiments/skill_versions/skill_candidate_v2.json",
                    "--baseline-metric",
                    "2.00",
                    "--candidate-metric",
                    "2.25",
                    "--generated-at",
                    "2026-07-21T00:00:00Z",
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["decision"]["status"], "reject")
        self.assertGreater(payload["decision"]["delta"], 0)


if __name__ == "__main__":
    unittest.main()
