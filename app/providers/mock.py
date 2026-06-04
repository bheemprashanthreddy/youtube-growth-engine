from app.providers.base import LLMProvider


class MockLLMProvider(LLMProvider):
    name = "mock"
    is_fallback = True

    def generate_text(self, prompt: str, *, purpose: str) -> str:
        return f"[draft:{purpose}] {prompt[:500]}"
