from app.providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def generate_text(self, prompt: str, *, purpose: str) -> str:
        raise NotImplementedError("OpenAI provider is intentionally stubbed for Phase 1 wiring.")

