import unittest
from pathlib import Path


class SkillSyncTests(unittest.TestCase):
    def test_claude_and_agent_skills_match(self):
        agent_path = Path(".agents/skills/grade-homework/SKILL.md")
        if not agent_path.exists():
            self.skipTest("local Codex skill mirror is not installed")
        claude = Path(".claude/skills/grade-homework/SKILL.md").read_text(
            encoding="utf-8"
        )
        agent = agent_path.read_text(encoding="utf-8")
        self.assertEqual(claude, agent)

    def test_skill_requires_frozen_evidence_first_workflow(self):
        text = Path(".claude/skills/grade-homework/SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        for phrase in (
            "page ordering",
            "rubric",
            "evidence",
            "confidence",
            "second-pass",
            "do not guess",
        ):
            self.assertIn(phrase, text)

    def test_skill_includes_benchmark_informed_safeguards(self):
        text = Path(".claude/skills/grade-homework/SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        normalized = " ".join(text.split())
        for phrase in (
            "benchmark-informed safeguards",
            "does not prove that transcript workflows are generally better",
            "direct-image baseline",
            "blank or apparently missing answers",
            "high-impact deductions",
            "flagged items",
            "spot-check",
        ):
            self.assertIn(phrase, normalized)
        for forbidden in (
            "therefore transcript-based grading is generally better",
            "transcript grading is generally better than direct image grading",
        ):
            self.assertNotIn(forbidden, normalized)


if __name__ == "__main__":
    unittest.main()
