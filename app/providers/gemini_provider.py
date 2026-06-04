from app.core.config import get_settings
from app.providers.base import LLMProvider
from app.providers.http_utils import post_json


class GeminiProvider(LLMProvider):
    name = "gemini"

    def generate_text(self, prompt: str, *, purpose: str) -> str:
        key = get_settings().gemini_api_key
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"Purpose: {purpose}\n\n{prompt}"}],
                }
            ],
            "generationConfig": {"temperature": 0.55, "maxOutputTokens": 1200},
        }
        response = post_json(url, payload)
        candidates = response.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates.")
        content = candidates[0].get("content", {})
        parts = content.get("parts") or []
        text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text
