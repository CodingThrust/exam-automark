import unittest
from pathlib import Path


AGENT_SKILL = Path(".agents/skills/grade-homework")
CLAUDE_SKILL = Path(".claude/skills/grade-homework")
HISTORICAL_PROMPT = Path("experiments/prompt_templates/grade_candidate_v5_3.txt")


class GradeHomeworkSkillContractTests(unittest.TestCase):
    def test_agent_and_claude_skill_directories_match(self):
        agent_files = {
            path.relative_to(AGENT_SKILL).as_posix(): path.read_bytes()
            for path in AGENT_SKILL.rglob("*")
            if path.is_file() and "__pycache__" not in path.relative_to(AGENT_SKILL).parts
        }
        claude_files = {
            path.relative_to(CLAUDE_SKILL).as_posix(): path.read_bytes()
            for path in CLAUDE_SKILL.rglob("*")
            if path.is_file() and "__pycache__" not in path.relative_to(CLAUDE_SKILL).parts
        }

        self.assertEqual(agent_files, claude_files)

    def test_live_skill_is_generic_and_requires_a_current_course_package(self):
        combined = "\n".join(
            (
                (AGENT_SKILL / "SKILL.md").read_text(encoding="utf-8"),
                (AGENT_SKILL / "references" / "grading-prompt.md").read_text(
                    encoding="utf-8"
                ),
                (AGENT_SKILL / "references" / "course-package-template.json").read_text(
                    encoding="utf-8"
                ),
            )
        ).lower()
        combined = " ".join(combined.split())
        for safeguard in (
            "frozen course package",
            "complete anonymous submission",
            "deduction_trace",
            "attention_note",
            "review.csv",
            "marked-page annotations",
            "do not invent a universal point rule",
            "a teacher owns",
        ):
            with self.subTest(safeguard=safeguard):
                self.assertIn(safeguard, combined)
        for historical_overlay in ("physics week", "dsaa", "church-turing", "q7", "q8", "q9"):
            with self.subTest(historical_overlay=historical_overlay):
                self.assertNotIn(historical_overlay, combined)

    def test_historical_candidate_prompt_remains_an_explicitly_separate_artifact(self):
        text = HISTORICAL_PROMPT.read_text(encoding="utf-8")
        self.assertIn("deduction_trace", text)
        self.assertNotEqual(
            text,
            (AGENT_SKILL / "references" / "grading-prompt.md").read_text(
                encoding="utf-8"
            ),
        )


if __name__ == "__main__":
    unittest.main()
