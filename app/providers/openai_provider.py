from app.core.config import get_settings
from app.providers.base import LLMProvider
from app.providers.http_utils import post_json


class OpenAIProvider(LLMProvider):
    name = "openai"

    def generate_text(self, prompt: str, *, purpose: str) -> str:
        key = get_settings().openai_api_key
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a careful YouTube explainer content strategist for CuriousSignal. Avoid unsupported claims, hype, spam, and policy-risky framing.",
                },
                {"role": "user", "content": f"Purpose: {purpose}\n\n{prompt}"},
            ],
            "temperature": 0.55,
            "max_tokens": 1200,
        }
        response = post_json(
            "https://api.openai.com/v1/chat/completions",
            payload,
            headers={"Authorization": f"Bearer {key}"},
        )
        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI returned no choices.")
        message = choices[0].get("message", {})
        text = str(message.get("content", "")).strip()
        if not text:
            raise RuntimeError("OpenAI returned an empty response.")
        return text
