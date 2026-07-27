import re
import unittest
from pathlib import Path


PROMPT = Path("experiments/prompt_templates/grade_candidate_v3.txt")
PROMPT_V31 = Path("experiments/prompt_templates/grade_candidate_v3_1.txt")
PROMPT_V32 = Path("experiments/prompt_templates/grade_candidate_v3_2.txt")
PROMPT_V33 = Path("experiments/prompt_templates/grade_candidate_v3_3.txt")
STRICT_SNAPSHOT = Path(
    "experiments/records/DSAA3071-week5-candidate-v3-dev-plan/"
    "prompts/grade_candidate_v3_strict_schema.txt"
)
STRICT_SNAPSHOT_V31 = Path(
    "experiments/records/DSAA3071-week5-candidate-v31-dev-plan/"
    "prompts/grade_candidate_v3_1_open_ended_strict_schema.txt"
)
STRICT_SNAPSHOT_V32 = Path(
    "experiments/records/DSAA3071-week5-candidate-v31-dev-plan/"
    "prompts/grade_candidate_v3_2_strict_schema.txt"
)
STRICT_SNAPSHOT_V33 = Path(
    "experiments/records/DSAA3071-week5-candidate-v33-q9-precedence/"
    "prompts/grade_candidate_v3_3_strict_schema.txt"
)
RUBRIC_V2 = Path("experiments/records/DSAA3071-week5-prep/rubric_v2.json")
SKILL = Path(".agents/skills/grade-homework/SKILL.md")
REFERENCE = Path(".agents/skills/grade-homework/references/grading-prompt.md")
CLAUDE_SKILL = Path(".claude/skills/grade-homework/SKILL.md")
CLAUDE_REFERENCE = Path(".claude/skills/grade-homework/references/grading-prompt.md")

QUESTION_TYPE_RULES = (
    "`multiple_choice`: Require the selected option or an unambiguous equivalent.",
    "`short_answer`: Combine key-term and concept evidence; exact standard-answer "
    "wording is not required.",
    "`calculation`: Check the final numeric or symbolic answer, units, formula "
    "choice, substitutions, arithmetic, and physical or mathematical reasoning; "
    "retain justified method credit when the final answer is wrong.",
    "`algorithm`: Require a viable method plus relevant steps or relations; "
    "award credit to valid alternatives.",
    "`proof`: Check all required directions and logical links; a missing required "
    "direction blocks full credit but preserves credit for each completed direction.",
    "`essay`: Score distinct valid relevant claims; do not require fixed ordering "
    "or standard phrasing.",
)


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker) + len(marker)
    remainder = text[start:]
    next_heading = remainder.find("\n## ")
    if next_heading >= 0:
        remainder = remainder[:next_heading]
    return remainder.strip()


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

    def test_all_assets_define_the_six_question_type_rules(self):
        for path in (PROMPT, STRICT_SNAPSHOT, SKILL, REFERENCE):
            text = _normalize_whitespace(path.read_text(encoding="utf-8"))
            for rule in QUESTION_TYPE_RULES:
                with self.subTest(path=path, rule=rule):
                    self.assertIn(_normalize_whitespace(rule), text)

    def test_calculation_rule_preserves_physics_process_credit(self):
        combined = _normalize_whitespace(
            "\n".join(
                path.read_text(encoding="utf-8")
                for path in (PROMPT, STRICT_SNAPSHOT, SKILL, REFERENCE)
            )
        )

        for phrase in (
            "final numeric or symbolic answer",
            "units",
            "formula choice",
            "substitutions",
            "arithmetic",
            "method credit",
            "physics",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, combined)

    def test_evidence_fields_are_plain_strings_for_schema_compatibility(self):
        combined = _normalize_whitespace(
            "\n".join(
                path.read_text(encoding="utf-8")
                for path in (PROMPT, STRICT_SNAPSHOT, SKILL, REFERENCE)
            )
        )

        for phrase in (
            "`extracted_evidence` and `evidence` must be plain text strings",
            "Do not output arrays or objects for these fields",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, combined)

    def test_strict_prompt_preserves_the_generic_grading_algorithm_verbatim(self):
        generic = _markdown_section(
            PROMPT.read_text(encoding="utf-8"),
            "Candidate-v3 grading algorithm",
        )
        strict = _markdown_section(
            STRICT_SNAPSHOT.read_text(encoding="utf-8"),
            "Candidate-v3 grading algorithm",
        )

        self.assertEqual(strict, generic)

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

    def test_candidate_v31_calibration_rules_are_present(self):
        required = (
            "cap-locality",
            "contradiction-locality",
            "key-term semantics",
            "indirect-construction",
            "cap condition is directly visible and active",
            "preserve unrelated element credit",
            "key terms are evidence signals",
            "valid indirect constructions",
        )
        expected = (
            PROMPT_V31,
            STRICT_SNAPSHOT_V31,
            SKILL,
            REFERENCE,
        )

        for path in expected:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                for phrase in required:
                    self.assertIn(phrase, text)

    def test_candidate_v31_open_ended_adequacy_rule_is_present(self):
        required = (
            "open-ended adequacy",
            "score whether the answer satisfies the task requirement",
            "standard answer as an anchor, not as an exhaustive whitelist",
            "valid, relevant, non-contradictory approaches",
            "not listed in the expected answer or semantic equivalents",
        )
        expected = (
            PROMPT_V31,
            STRICT_SNAPSHOT_V31,
            SKILL,
            REFERENCE,
        )

        for path in expected:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                for phrase in required:
                    self.assertIn(phrase, text)

    def test_candidate_v31_strict_prompt_preserves_generic_algorithm_verbatim(self):
        generic = _markdown_section(
            PROMPT_V31.read_text(encoding="utf-8"),
            "Candidate-v3.1 grading algorithm",
        )
        strict = _markdown_section(
            STRICT_SNAPSHOT_V31.read_text(encoding="utf-8"),
            "Candidate-v3.1 grading algorithm",
        )

        self.assertEqual(strict, generic)

    def test_candidate_v32_official_style_tolerance_rule_is_present(self):
        required = (
            "official-style adequacy",
            "not ideal-answer completeness",
            "avoid being overly harsh",
            "missing ideal detail",
            "visible misconception",
            "large deductions only for material errors",
        )
        expected = (
            PROMPT_V32,
            STRICT_SNAPSHOT_V32,
            SKILL,
            REFERENCE,
        )

        for path in expected:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                for phrase in required:
                    self.assertIn(phrase, text)

    def test_candidate_v32_targeted_q7_q8_q9_rules_are_present(self):
        required = (
            "Q7 proof-locality",
            "preserve construction credit",
            "local nonmembership or rejection mistake",
            "Q8 enumerator policy",
            "2n versus 2^n",
            "invalid extra outputs",
            "Q9 conceptual essay policy",
            "broad valid evidence",
            "Church-Turing thesis",
        )
        expected = (
            PROMPT_V32,
            STRICT_SNAPSHOT_V32,
            SKILL,
            REFERENCE,
        )

        for path in expected:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                for phrase in required:
                    self.assertIn(phrase, text)

    def test_candidate_v32_strict_prompt_preserves_generic_algorithm_verbatim(self):
        generic = _markdown_section(
            PROMPT_V32.read_text(encoding="utf-8"),
            "Candidate-v3.2 grading algorithm",
        )
        strict = _markdown_section(
            STRICT_SNAPSHOT_V32.read_text(encoding="utf-8"),
            "Candidate-v3.2 grading algorithm",
        )

        self.assertEqual(strict, generic)

    def test_dsaa3071_rubric_v2_contains_targeted_q7_q8_q9_calibration(self):
        text = RUBRIC_V2.read_text(encoding="utf-8")

        required = (
            "official_style_tolerance",
            "proof_locality_calibration",
            "preserve construction credit",
            "invalid extra outputs",
            "linear_even_lengths",
            "conceptual_essay_calibration",
            "broad valid evidence",
            "avoid being overly harsh",
        )

        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_candidate_v33_rule_precedence_is_present_in_model_facing_assets(self):
        required = (
            "rule precedence and holistic sufficiency",
            "question-specific `full_credit_rule`",
            "evidence anchors",
            "checklist",
            "Brevity alone must not lower an evidence state",
            "missing required behavior, term, or relation",
        )
        expected = (
            PROMPT_V33,
            STRICT_SNAPSHOT_V33,
            SKILL,
            REFERENCE,
        )

        for path in expected:
            with self.subTest(path=path):
                text = _normalize_whitespace(path.read_text(encoding="utf-8"))
                for phrase in required:
                    self.assertIn(_normalize_whitespace(phrase), text)

    def test_candidate_v33_strict_prompt_preserves_generic_algorithm_verbatim(self):
        generic = _markdown_section(
            PROMPT_V33.read_text(encoding="utf-8"),
            "Candidate-v3.3 grading algorithm",
        )
        strict = _markdown_section(
            STRICT_SNAPSHOT_V33.read_text(encoding="utf-8"),
            "Candidate-v3.3 grading algorithm",
        )

        self.assertEqual(strict, generic)

    def test_candidate_v33_remains_generic_and_private(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (PROMPT_V33, SKILL, REFERENCE)
        )

        self.assertNotRegex(combined, r"\bS\d{3}\b")
        self.assertNotIn("DSAA3071", combined)


if __name__ == "__main__":
    unittest.main()
