from app.core.config import get_settings
from app.providers.base import LLMProvider
from app.providers.http_utils import post_json


class OllamaProvider(LLMProvider):
    name = "ollama"

    def generate_text(self, prompt: str, *, purpose: str) -> str:
        base_url = get_settings().ollama_base_url.rstrip("/")
        if not base_url:
            raise RuntimeError("OLLAMA_BASE_URL is not configured.")
        payload = {
            "model": "llama3.1",
            "prompt": (
                "You are a careful YouTube explainer content strategist for CuriousSignal. "
                "Avoid unsupported claims, hype, spam, and policy-risky framing.\n\n"
                f"Purpose: {purpose}\n\n{prompt}"
            ),
            "stream": False,
            "options": {"temperature": 0.55},
        }
        response = post_json(f"{base_url}/api/generate", payload)
        text = str(response.get("response", "")).strip()
        if not text:
            raise RuntimeError("Ollama returned an empty response.")
        return text
