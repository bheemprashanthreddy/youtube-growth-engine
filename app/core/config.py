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
    visual_asset_provider: str = "none"
    visual_asset_cache_dir: Path = BASE_DIR / "storage" / "assets"
    allow_stock_assets: bool = False
    voice_provider: str = "edge"
    voice_cache_dir: Path = BASE_DIR / "storage" / "voice"
    voice_profile: str = "curious_signal_default"
    openai_tts_model: str | None = None
    openai_tts_voice: str | None = None
    edge_tts_voice: str = "en-US-GuyNeural"
    edge_tts_rate: str = "+0%"
    edge_tts_pitch: str = "+0Hz"
    voice_force_regenerate: bool = False
    voice_max_short_seconds: int = 75
    voice_max_long_seconds: int = 180
    voice_max_preview_seconds: int = 30
    render_engine: str = "native"
    moneyprinterturbo_base_url: str = "http://127.0.0.1:8080"
    moneyprinterturbo_enabled: bool = False
    moneyprinterturbo_output_dir: Path = BASE_DIR / "renders" / "moneyprinterturbo"
    moneyprinterturbo_timeout_seconds: int = 1800
    moneyprinterturbo_use_background_music: bool = False
    moneyprinterturbo_create_endpoint: str = "/api/v1/videos"
    moneyprinterturbo_status_endpoint: str = "/api/v1/tasks/{task_id}"
    moneyprinterturbo_download_endpoint: str = "/api/v1/videos/{task_id}/download"
    youtube_upload_enabled: bool = False
    youtube_privacy_status: str = "private"
    youtube_client_secret_file: Path = BASE_DIR / "client_secret.json"
    youtube_token_file: Path = BASE_DIR / "storage" / "youtube" / "token.json"
    youtube_category_id: str = "28"
    youtube_made_for_kids: bool = False
    youtube_default_language: str = "en"
    youtube_notify_subscribers: bool = False
    youtube_daily_upload_limit: int = 3
    youtube_require_private: bool = True
    ai_visual_provider: str = "none"
    ai_visual_cache_dir: Path = BASE_DIR / "storage" / "ai_visuals"
    ai_image_model: str | None = None
    ai_video_model: str | None = None
    ai_visuals_enabled: bool = False
    ai_thumbnails_enabled: bool = False
    ai_scene_images_enabled: bool = False
    ai_video_clips_enabled: bool = False
    openai_image_model: str = "gpt-image-1"
    replicate_api_token: str | None = None
    replicate_image_model: str | None = None
    replicate_video_model: str | None = None
    database_url: str = "sqlite:///./storage/youtube_growth_engine.db"
    require_human_approval: bool = True
    output_root: Path = BASE_DIR / "outputs"
    config_root: Path = BASE_DIR / "configs"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
