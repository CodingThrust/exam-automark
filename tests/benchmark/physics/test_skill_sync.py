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

    def test_skill_requires_frozen_course_package_and_evidence_first_workflow(self):
        text = Path(".claude/skills/grade-homework/SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        for phrase in (
            "course package",
            "rubric",
            "evidence",
            "confidence",
            "review.csv",
            "do not infer",
        ):
            self.assertIn(phrase, text)

    def test_skill_includes_generic_delivery_safeguards_without_course_overlays(self):
        text = Path(".claude/skills/grade-homework/SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        normalized = " ".join(text.split())
        for phrase in (
            "private roster",
            "grades/grades.csv",
            "marked pdf",
            "deduction trace",
            "flagged, medium-confidence, or low-confidence",
            "spot-check",
            "not a teacher replacement",
        ):
            self.assertIn(phrase, normalized)
        for forbidden in (
            "benchmark-informed safeguards",
            "physics week",
            "dsaa3071",
        ):
            self.assertNotIn(forbidden, normalized)


if __name__ == "__main__":
    unittest.main()
