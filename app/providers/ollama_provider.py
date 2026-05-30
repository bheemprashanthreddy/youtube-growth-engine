from app.providers.base import LLMProvider


class OllamaProvider(LLMProvider):
    def generate_text(self, prompt: str, *, purpose: str) -> str:
        raise NotImplementedError("Ollama provider is intentionally stubbed for Phase 1 wiring.")

