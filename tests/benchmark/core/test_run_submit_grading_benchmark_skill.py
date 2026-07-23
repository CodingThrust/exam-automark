import unittest
from pathlib import Path


AGENT_SKILL = Path(".agents/skills/run-submit-grading-benchmark")
CLAUDE_SKILL = Path(".claude/skills/run-submit-grading-benchmark")


class RunSubmitGradingBenchmarkSkillTests(unittest.TestCase):
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
        self.assertEqual(claude_files, agent_files)

    def test_skill_owns_environment_run_and_pr_handoff(self):
        text = (AGENT_SKILL / "SKILL.md").read_text(encoding="utf-8").lower()
        normalized = " ".join(text.split())
        for phrase in (
            "python scripts/advisor_experiment.py doctor",
            "python scripts/advisor_experiment.py plan",
            "python scripts/advisor_experiment.py prepare",
            "python scripts/advisor_experiment.py run",
            "python scripts/advisor_experiment.py package",
            "python scripts/advisor_experiment.py submit",
            "kimi code membership is not a moonshot platform api key",
            "automatic-transcript",
            "human-reviewed-transcript",
            "human-approved anonymized page images",
            "failed experiment is still an experiment result",
            "github pull request",
            "explicit user approval",
        ):
            self.assertIn(phrase, normalized)

    def test_skill_has_low_ambiguity_decision_table(self):
        text = (AGENT_SKILL / "references" / "decision-table.md").read_text(
            encoding="utf-8"
        ).lower()
        for phrase in (
            "run matched `text-only` and `multimodal` development arms",
            "mark text arm blocked",
            "mark multimodal arm blocked",
            "stay on development and package failures",
            "technical failure",
            "scoring/accuracy error",
            "block submission",
        ):
            self.assertIn(phrase, text)

    def test_github_page_leads_with_skill_and_automatic_pr(self):
        handoff = Path("docs/ai-grading-test-handoff.md").read_text(encoding="utf-8")
        self.assertIn("## Preferred Agent Workflow", handoff)
        self.assertIn("run-submit-grading-benchmark", handoff)
        self.assertIn("Kimi/Claude × text/multimodal × baseline/candidate", handoff)
        self.assertIn("GitHub PR URL", handoff)
        self.assertIn("does not require a", handoff)
        self.assertIn("`MOONSHOT_API_KEY`", handoff)


if __name__ == "__main__":
    unittest.main()
