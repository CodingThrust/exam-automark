import unittest
from pathlib import Path


AGENT_SKILL = Path(".agents/skills/grade-homework")
CLAUDE_SKILL = Path(".claude/skills/grade-homework")
CURRENT_PROMPT = Path("experiments/prompt_templates/grade_candidate_v5_2_r2.txt")


class GradeHomeworkSkillContractTests(unittest.TestCase):
    def test_agent_and_claude_skill_directories_match(self):
        agent_files = {
            path.relative_to(AGENT_SKILL).as_posix(): path.read_bytes()
            for path in AGENT_SKILL.rglob("*")
            if path.is_file()
        }
        claude_files = {
            path.relative_to(CLAUDE_SKILL).as_posix(): path.read_bytes()
            for path in CLAUDE_SKILL.rglob("*")
            if path.is_file()
        }

        self.assertEqual(agent_files, claude_files)

    def test_current_candidate_is_cross_course_and_type_first(self):
        text = CURRENT_PROMPT.read_text(encoding="utf-8").lower()
        expected_types = (
            "objective_selection",
            "calculation",
            "calculation_short_answer",
            "proof",
            "diagram",
            "essay",
        )
        for question_type in expected_types:
            with self.subTest(question_type=question_type):
                self.assertIn(question_type, text)

        for inherited_rule in (
            "q7 proof-locality",
            "q8 enumerator",
            "q9 conceptual essay",
            "church-turing",
            "power-of-two",
        ):
            with self.subTest(inherited_rule=inherited_rule):
                self.assertNotIn(inherited_rule, text)

    def test_current_candidate_preserves_key_calibration_safeguards(self):
        text = CURRENT_PROMPT.read_text(encoding="utf-8").lower()
        for safeguard in (
            "evidence before assigning points",
            "semantic equivalent",
            "official-style adequacy",
            "material-error cap",
            "local misconception",
            "second pass",
            "true/false",
            "answer-only allocation",
            "entire anonymous submission",
            "page-level marks",
            "page position",
            "never question numbers",
        ):
            with self.subTest(safeguard=safeguard):
                self.assertIn(safeguard, text)


if __name__ == "__main__":
    unittest.main()
