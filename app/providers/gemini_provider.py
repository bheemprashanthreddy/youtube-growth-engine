from app.providers.base import LLMProvider


class GeminiProvider(LLMProvider):
    def generate_text(self, prompt: str, *, purpose: str) -> str:
        raise NotImplementedError("Gemini provider is intentionally stubbed for Phase 1 wiring.")

