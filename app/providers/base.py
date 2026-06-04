from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderStatus:
    selected_provider: str
    configured: bool
    active: bool
    using_mock_fallback: bool
    detail: str


class LLMProvider(ABC):
    name = "base"
    is_fallback = False

    @abstractmethod
    def generate_text(self, prompt: str, *, purpose: str) -> str:
        """Generate text for a specific content planning purpose."""
