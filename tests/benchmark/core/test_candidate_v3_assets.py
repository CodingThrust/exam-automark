import re
import unittest
from pathlib import Path


PROMPT = Path("experiments/prompt_templates/grade_candidate_v3.txt")
STRICT_SNAPSHOT = Path(
    "experiments/records/DSAA3071-week5-candidate-v3-dev-plan/"
    "prompts/grade_candidate_v3_strict_schema.txt"
)
SKILL = Path(".agents/skills/grade-homework/SKILL.md")
REFERENCE = Path(".agents/skills/grade-homework/references/grading-prompt.md")
CLAUDE_SKILL = Path(".claude/skills/grade-homework/SKILL.md")
CLAUDE_REFERENCE = Path(".claude/skills/grade-homework/references/grading-prompt.md")


class CandidateV3AssetTests(unittest.TestCase):
    def test_candidate_v3_contract_is_present_in_all_model_facing_assets(self):
        required = (
            "key_term_evidence",
            "concept_evidence",
            "relation_evidence",
            "mentioned_only",
            "partial_understanding",
            "demonstrated",
            "misused_or_contradicted",
            "Do not award duplicate credit",
            "semantic equivalent",
            "question type",
        )
        expected = (
            PROMPT,
            STRICT_SNAPSHOT,
            SKILL,
            REFERENCE,
        )

        for path in expected:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                for phrase in required:
                    self.assertIn(phrase, text)

    def test_candidate_v3_preserves_required_safeguards(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (PROMPT, STRICT_SNAPSHOT, SKILL, REFERENCE)
        ).lower()

        for phrase in (
            "integer",
            "evidence before score",
            "final answer is wrong",
            "process credit",
            "second-pass",
            "recompute",
            "confidence",
            "high, medium, or low",
            "exact total",
            "score band",
            "material-error cap",
            "cannot raise the subtotal",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, combined)

    def test_candidate_v3_assets_are_generic_and_private(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (PROMPT, SKILL, REFERENCE)
        )

        self.assertNotRegex(combined, r"\bS\d{3}\b")
        self.assertNotIn("DSAA3071", combined)

    def test_updated_model_facing_mirrors_match(self):
        self.assertEqual(
            SKILL.read_text(encoding="utf-8"),
            CLAUDE_SKILL.read_text(encoding="utf-8"),
        )
        self.assertEqual(
            REFERENCE.read_text(encoding="utf-8"),
            CLAUDE_REFERENCE.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
