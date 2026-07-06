import base64
from typing import Any

from .schema import ProviderResult


GRADING_RESPONSE_FORMAT = {
    "type": "json_schema",
    "name": "physics_grading_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "pattern": "^S[0-9]{3}$"},
            "scores": {
                "type": "array",
                "minItems": 12,
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {
                            "type": "string",
                            "enum": [
                                "Q1a",
                                "Q1b",
                                "Q1c",
                                "Q1d",
                                "Q2a",
                                "Q2b",
                                "Q3a",
                                "Q3b",
                                "Q3c",
                                "Q3d",
                                "Q3e",
                                "Q3f",
                            ],
                        },
                        "extracted_evidence": {"type": "string"},
                        "score": {"type": "number", "minimum": 0, "maximum": 7},
                        "evidence": {"type": "string"},
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "flags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "question_id",
                        "extracted_evidence",
                        "score",
                        "evidence",
                        "confidence",
                        "flags",
                    ],
                    "additionalProperties": False,
                },
            },
            "total": {"type": "number", "minimum": 0, "maximum": 30},
        },
        "required": ["student_id", "scores", "total"],
        "additionalProperties": False,
    },
}


def _usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if hasattr(usage, "__dict__"):
        return dict(vars(usage))
    return {}


class OpenAIProvider:
    def __init__(self, client: Any, model: str):
        self.client = client
        self.model = model

    def complete_images(self, prompt: str, images: list[bytes]) -> ProviderResult:
        content = [{"type": "input_text", "text": prompt}]
        for image in images:
            encoded = base64.b64encode(image).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{encoded}",
                }
            )
        response = self.client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": content}],
            text={"format": GRADING_RESPONSE_FORMAT},
        )
        return _openai_result(response)

    def complete_text(self, prompt: str) -> ProviderResult:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
        )
        return _openai_result(response)


class DeepSeekProvider:
    def __init__(self, client: Any, model: str):
        self.client = client
        self.model = model

    @classmethod
    def from_api_key(
        cls, api_key: str, model: str, client_factory: Any | None = None
    ) -> "DeepSeekProvider":
        if client_factory is None:
            from openai import OpenAI

            client_factory = OpenAI
        client = client_factory(api_key=api_key, base_url="https://api.deepseek.com")
        return cls(client, model=model)

    def complete_text(self, prompt: str) -> ProviderResult:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return ProviderResult(
            raw_text=response.choices[0].message.content,
            model=response.model,
            usage=_usage_to_dict(getattr(response, "usage", None)),
        )


def _openai_result(response: Any) -> ProviderResult:
    return ProviderResult(
        raw_text=response.output_text,
        model=response.model,
        usage=_usage_to_dict(getattr(response, "usage", None)),
        system_fingerprint=getattr(response, "system_fingerprint", None),
    )
