from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, *, purpose: str) -> str:
        """Generate text for a specific content planning purpose."""

