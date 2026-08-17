import hashlib
import json
import unittest
from pathlib import Path

from benchmark.core.error_book import audit_public_error_summary
from benchmark.core.model_policy import load_model_release_policy


REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = (
    REPO_ROOT
    / "experiments"
    / "records"
    / "linearalgebra-quiz1-v5-3-baseline-preflight"
    / "plan.json"
)


def _sha256(relative_path: str) -> str:
    return hashlib.sha256((REPO_ROOT / relative_path).read_bytes()).hexdigest()


class LinearAlgebraV53BaselinePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

    def test_plan_is_public_safe_development_only_and_explicitly_superseded(self):
        self.assertEqual(audit_public_error_summary(self.plan), [])
        self.assertEqual(self.plan["evaluation_status"], "superseded_not_run")
        self.assertFalse(self.plan["heldout_accessed"])
        self.assertEqual(
            self.plan["model_run_authorization"], "not_granted_by_this_preflight"
        )
        self.assertEqual(self.plan["scope"]["split"], "development")
        self.assertEqual(
            self.plan["superseded_by"],
            "experiments/records/linearalgebra-quiz1-v5-3-r2-rubric-candidate/plan.json",
        )

    def test_historical_preflight_retains_its_original_bindings_for_audit(self):
        baseline = self.plan["baseline"]

        self.assertEqual(baseline["skill"]["version_id"], "skill_candidate_v5_3")
        skill_snapshot = json.loads(
            (REPO_ROOT / baseline["skill"]["snapshot_path"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            baseline["skill"]["canonical_hash"], skill_snapshot["canonical_hash"]
        )
        for name in ("course_spec", "rubric", "prompt_template"):
            self.assertEqual(
                baseline[name]["sha256"], _sha256(baseline[name]["path"])
            )
        self.assertEqual(baseline["grading_output_contract"], "deduction_trace_v1")

    def test_route_matrix_uses_flash_and_excludes_provisional_pro(self):
        routes = self.plan["routes"]

        self.assertEqual(
            set(routes),
            {"M1-Codex", "T1-Codex", "G1-Codex", "G1-DeepSeek-Flash"},
        )
        flash = routes["G1-DeepSeek-Flash"]
        policy = load_model_release_policy(
            REPO_ROOT / flash["model_release_policy"]
        )
        self.assertEqual(flash["model"], "deepseek-v4-flash")
        self.assertTrue(policy["models"][flash["model"]]["default_for_new_runs"])
        self.assertNotIn("deepseek-v4-pro", json.dumps(routes, sort_keys=True))

    def test_analysis_requires_trace_quality_and_non_presumptive_taxonomy(self):
        protocol = self.plan["analysis_protocol"]

        self.assertIn(
            "deduction points close exactly to max_score minus score",
            protocol["trace_quality"],
        )
        self.assertEqual(
            protocol["disagreement_taxonomy"],
            [
                "clear_model_error",
                "representation_or_transcription_loss",
                "rubric_or_gold_conflict",
                "reasonable_strictness_difference",
                "insufficient_evidence",
            ],
        )


if __name__ == "__main__":
    unittest.main()
