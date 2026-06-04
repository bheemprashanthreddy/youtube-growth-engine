import logging

from app.core.config import get_settings
from app.providers.base import LLMProvider, ProviderStatus
from app.providers.gemini_provider import GeminiProvider
from app.providers.mock import MockLLMProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


def get_llm_provider() -> LLMProvider:
    status = get_provider_status()
    provider = status.selected_provider
    if status.using_mock_fallback:
        if provider != "mock":
            logger.warning("%s is selected but not configured; falling back to mock LLM provider.", provider)
        return MockLLMProvider()
    if provider == "openai":
        return OpenAIProvider()
    if provider == "gemini":
        return GeminiProvider()
    if provider == "ollama":
        return OllamaProvider()
    return MockLLMProvider()


def get_provider_status() -> ProviderStatus:
    settings = get_settings()
    provider = settings.model_provider.lower().strip() or "mock"
    if provider == "mock":
        return ProviderStatus("mock", True, True, True, "Deterministic mock provider selected.")
    if provider == "gemini":
        configured = bool(settings.gemini_api_key)
        return ProviderStatus(provider, configured, configured, not configured, _detail(provider, configured, "GEMINI_API_KEY"))
    if provider == "openai":
        configured = bool(settings.openai_api_key)
        return ProviderStatus(provider, configured, configured, not configured, _detail(provider, configured, "OPENAI_API_KEY"))
    if provider == "ollama":
        configured = bool(settings.ollama_base_url)
        return ProviderStatus(provider, configured, configured, not configured, _detail(provider, configured, "OLLAMA_BASE_URL"))
    return ProviderStatus(provider, False, False, True, f"Unknown MODEL_PROVIDER={provider}; using mock fallback.")


def safe_generate_text(provider: LLMProvider, prompt: str, *, purpose: str, fallback: str) -> str:
    try:
        text = provider.generate_text(prompt, purpose=purpose).strip()
        return text or fallback
    except Exception as exc:
        logger.warning("LLM provider %s failed for %s; using deterministic fallback. Error: %s", provider.name, purpose, exc)
        return fallback


def _detail(provider: str, configured: bool, env_name: str) -> str:
    if configured:
        return f"{provider} is configured via {env_name}."
    return f"{provider} selected but {env_name} is missing; using mock fallback."
