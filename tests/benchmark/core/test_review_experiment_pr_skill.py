import unittest
from pathlib import Path


AGENT_SKILL = Path(".agents/skills/review-experiment-pr/SKILL.md")
CLAUDE_SKILL = Path(".claude/skills/review-experiment-pr/SKILL.md")


class ReviewExperimentPrSkillTests(unittest.TestCase):
    def test_agent_and_claude_skill_mirrors_match(self):
        self.assertEqual(
            CLAUDE_SKILL.read_text(encoding="utf-8"),
            AGENT_SKILL.read_text(encoding="utf-8"),
        )

    def test_skill_trains_reproducible_pr_review(self):
        text = CLAUDE_SKILL.read_text(encoding="utf-8").lower()
        normalized = " ".join(text.split())
        for phrase in (
            "git status --short --branch",
            "git check-ignore -v data",
            "prompt.txt",
            "manifest.json",
            "output.schema.json",
            "plan.json",
            "skill_version_id",
            "skill_hashes",
            "prompt_template_hashes",
            "planned_packets",
            "experiment.json",
            "data_snapshot_hash",
            "prompt_packet_hashes",
            "typst note",
            "python -m benchmark.core.cli audit-packet",
            "synthetic fixtures",
            "do not require model calls",
        ):
            self.assertIn(phrase, normalized)

    def test_skill_blocks_privacy_leaks_and_pilot_overclaims(self):
        text = CLAUDE_SKILL.read_text(encoding="utf-8").lower()
        normalized = " ".join(text.split())
        for phrase in (
            "reject the pr if it force-adds `data/`",
            "student_map",
            "primary_scores",
            "reviewer_scores",
            "physics week 9 pilot",
            "general claim",
            "transcript-based grading is better than direct-image grading",
        ):
            self.assertIn(phrase, normalized)


if __name__ == "__main__":
    unittest.main()
