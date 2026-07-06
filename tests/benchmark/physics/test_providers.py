import json
import unittest
from pathlib import Path

from benchmark.physics.providers import DeepSeekProvider, OpenAIProvider


class FakeResponses:
    def create(self, **kwargs):
        self.kwargs = kwargs
        return type(
            "Response",
            (),
            {
                "output_text": '{"student_id":"S001","scores":[]}',
                "model": kwargs["model"],
                "usage": {"input_tokens": 10},
                "system_fingerprint": "fp-test",
            },
        )()


class FakeCompletions:
    def create(self, **kwargs):
        self.kwargs = kwargs
        message = type(
            "Message", (), {"content": '{"student_id":"S001","scores":[]}'}
        )()
        choice = type("Choice", (), {"message": message})()
        return type(
            "ChatResponse",
            (),
            {
                "choices": [choice],
                "model": kwargs["model"],
                "usage": {"prompt_tokens": 7},
            },
        )()


class ProviderTests(unittest.TestCase):
    def test_openai_image_request_uses_input_image(self):
        responses = FakeResponses()
        client = type("Client", (), {"responses": responses})()
        provider = OpenAIProvider(client, model="gpt-5.4")

        result = provider.complete_images("grade", [b"jpeg-bytes"])

        content = responses.kwargs["input"][0]["content"]
        self.assertEqual(content[0], {"type": "input_text", "text": "grade"})
        self.assertEqual(content[1]["type"], "input_image")
        self.assertTrue(
            content[1]["image_url"].startswith("data:image/jpeg;base64,")
        )
        self.assertEqual(result.raw_text, '{"student_id":"S001","scores":[]}')
        self.assertEqual(result.model, "gpt-5.4")
        self.assertEqual(result.system_fingerprint, "fp-test")
        output_format = responses.kwargs["text"]["format"]
        self.assertEqual(output_format["type"], "json_schema")
        self.assertTrue(output_format["strict"])
        self.assertEqual(output_format["schema"]["required"], [
            "student_id",
            "scores",
            "total",
        ])

    def test_openai_text_request_uses_input_text_only(self):
        responses = FakeResponses()
        client = type("Client", (), {"responses": responses})()
        provider = OpenAIProvider(client, model="gpt-5.4")

        provider.complete_text("grade transcript")

        content = responses.kwargs["input"][0]["content"]
        self.assertEqual(content, [{"type": "input_text", "text": "grade transcript"}])

    def test_deepseek_request_is_text_only_json_chat(self):
        completions = FakeCompletions()
        chat = type("Chat", (), {"completions": completions})()
        client = type("Client", (), {"chat": chat})()
        provider = DeepSeekProvider(client, model="deepseek-v4-pro")

        result = provider.complete_text("grade transcript")

        self.assertEqual(
            completions.kwargs["messages"],
            [{"role": "user", "content": "grade transcript"}],
        )
        self.assertEqual(
            completions.kwargs["response_format"], {"type": "json_object"}
        )
        self.assertNotIn("image", json.dumps(completions.kwargs).lower())
        self.assertEqual(result.raw_text, '{"student_id":"S001","scores":[]}')
        self.assertEqual(result.model, "deepseek-v4-pro")

    def test_deepseek_factory_pins_official_base_url(self):
        calls = []

        def fake_factory(**kwargs):
            calls.append(kwargs)
            completions = FakeCompletions()
            chat = type("Chat", (), {"completions": completions})()
            return type("Client", (), {"chat": chat})()

        provider = DeepSeekProvider.from_api_key(
            "secret", model="deepseek-v4-pro", client_factory=fake_factory
        )

        self.assertIsInstance(provider, DeepSeekProvider)
        self.assertEqual(calls, [{"api_key": "secret", "base_url": "https://api.deepseek.com"}])

    def test_revised_config_uses_interactive_gpt_and_one_run(self):
        path = Path("benchmark/physics/configs/physics_week9.json")
        config = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(config["dataset"], "physics_week9")
        self.assertEqual(config["gpt_execution"], "codex-plus-interactive")
        self.assertEqual(config["gpt_display_model"], "GPT-5.5")
        self.assertEqual(config["deepseek_model"], "deepseek-v4-pro")
        self.assertEqual(config["runs_per_condition"], 1)
        self.assertEqual(config["bootstrap_samples"], 10000)
        self.assertEqual(config["excluded_run_ids"], ["G1-dev-r1"])
        self.assertNotIn("openai_model", config)

    def test_prompts_require_structured_outputs_without_guessing(self):
        prompt_dir = Path("benchmark/physics/prompts")
        transcribe = (prompt_dir / "transcribe.txt").read_text(encoding="utf-8")
        grade_prompts = [
            (prompt_dir / "grade_minimal.txt").read_text(encoding="utf-8"),
            (prompt_dir / "grade_structured.txt").read_text(encoding="utf-8"),
            (prompt_dir / "review.txt").read_text(encoding="utf-8"),
        ]

        for question_id in ("Q1a", "Q1b", "Q1c", "Q1d", "Q2a", "Q2b", "Q3f"):
            self.assertIn(question_id, transcribe)
        self.assertIn("[UNCLEAR]", transcribe)
        self.assertIn("equations", transcribe.lower())
        self.assertIn("units", transcribe.lower())

        for prompt in grade_prompts:
            lowered = prompt.lower()
            self.assertIn("valid json", lowered)
            self.assertIn("quarter-point", lowered)
            self.assertIn("evidence", lowered)
            self.assertIn("confidence", lowered)
            self.assertIn("flags", lowered)
            self.assertIn("total", lowered)
            for question_id in ("Q1a", "Q1b", "Q1c", "Q1d", "Q2a", "Q2b", "Q3f"):
                self.assertIn(question_id, prompt)


if __name__ == "__main__":
    unittest.main()
