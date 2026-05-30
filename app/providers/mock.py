from app.providers.base import LLMProvider


class MockLLMProvider(LLMProvider):
    def generate_text(self, prompt: str, *, purpose: str) -> str:
        return f"[draft:{purpose}] {prompt[:500]}"

