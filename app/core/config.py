from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    model_provider: str = "mock"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    youtube_api_key: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None
    news_rss_urls: str | None = None
    google_trends_region: str = "US"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    pexels_api_key: str | None = None
    pixabay_api_key: str | None = None
    database_url: str = "sqlite:///./storage/youtube_growth_engine.db"
    require_human_approval: bool = True
    output_root: Path = BASE_DIR / "outputs"
    config_root: Path = BASE_DIR / "configs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
