import json
import logging

from app.core.config import get_settings
from app.models.content import VideoJob
from app.services.visual_assets.asset_cache import cache_root
from app.services.visual_assets.base import VisualAsset, VisualProviderStatus, generated_asset
from app.services.visual_assets.local_provider import LocalVisualProvider
from app.services.visual_assets.pexels_provider import PexelsVisualProvider
from app.services.visual_assets.pixabay_provider import PixabayVisualProvider
from app.services.visual_assets.safety import is_safe_asset_query
from app.services.ai_visuals.visual_service import generate_scene_images

logger = logging.getLogger(__name__)


def visual_provider_status() -> VisualProviderStatus:
    settings = get_settings()
    provider = (settings.visual_asset_provider or "none").lower()
    configured = provider == "local" or (
        provider == "pexels" and bool(settings.pexels_api_key) and settings.allow_stock_assets
    ) or (
        provider == "pixabay" and bool(settings.pixabay_api_key) and settings.allow_stock_assets
    )
    active = configured and provider in {"local", "pexels", "pixabay"}
    fallback = not active
    detail = "Using generated motion graphics fallback."
    if provider == "pexels" and not settings.allow_stock_assets:
        detail = "Pexels selected but ALLOW_STOCK_ASSETS=false; using generated fallback."
    elif provider == "pixabay" and not settings.allow_stock_assets:
        detail = "Pixabay selected but ALLOW_STOCK_ASSETS=false; using generated fallback."
    elif provider in {"pexels", "pixabay"} and not configured:
        detail = f"{provider} selected but API key is missing; using generated fallback."
    elif active:
        detail = f"{provider} visual asset provider is active."
    return VisualProviderStatus(provider, configured, active, str(cache_root()), fallback, detail)


def build_asset_query(scene: dict[str, object], video_job: VideoJob, *, risk_flags: list[str] | None = None) -> str:
    text = " ".join(
        [
            str(scene.get("visual_prompt") or ""),
            " ".join(str(item) for item in scene.get("broll_keywords", [])[:5]) if isinstance(scene.get("broll_keywords"), list) else "",
            video_job.title,
        ]
    ).lower()
    if "ai" in text and "search" in text:
        query = "AI search interface technology data network"
    elif "delivery" in text or "package" in text:
        query = "delivery warehouse packages logistics"
    elif "retro" in text or "internet" in text:
        query = "retro internet computer screen"
    elif "electronics" in text or "resale" in text:
        query = "electronics resale market devices"
    elif "science" in text:
        query = "science laboratory abstract technology"
    else:
        query = "technology data network abstract"
    if not is_safe_asset_query(query, risk_flags):
        return "technology data network abstract"
    return query


def select_assets_for_job(video_job: VideoJob, scenes: list[dict[str, object]]) -> list[VisualAsset]:
    provider = _provider()
    selected: list[VisualAsset] = []
    risk_flags = _risk_flags(video_job)
    ai_assets = generate_scene_images(video_job, scenes)
    ai_by_index = {index: asset for index, asset in enumerate(ai_assets)}
    for index, scene in enumerate(scenes):
        query = build_asset_query(scene, video_job, risk_flags=risk_flags)
        if index in ai_by_index:
            selected.append(_ai_to_visual_asset(ai_by_index[index], query))
            continue
        asset = None
        if provider:
            try:
                asset = provider.search(query, asset_type="image")
            except Exception as exc:
                logger.warning("Visual provider failed for query '%s': %s", query, exc)
        selected.append(asset or generated_asset(query))
    return selected


def _ai_to_visual_asset(asset, query: str) -> VisualAsset:
    return VisualAsset(
        provider=f"ai_{asset.provider}",
        asset_type="image",
        query=query,
        title="AI generated scene image",
        source_url="",
        local_path=asset.local_path,
        license_note="AI-generated visual. Review disclosure requirements before publishing.",
        attribution_required=False,
        width=0,
        height=0,
        duration=0,
        relevance_score=0.95,
        safety_status=asset.safety_status,
        created_at=asset.created_at,
    )


def _provider():
    status = visual_provider_status()
    if not status.active:
        return None
    if status.selected_provider == "pexels":
        return PexelsVisualProvider()
    if status.selected_provider == "pixabay":
        return PixabayVisualProvider()
    if status.selected_provider == "local":
        return LocalVisualProvider()
    return None


def _risk_flags(video_job: VideoJob) -> list[str]:
    try:
        scene_plan = json.loads(video_job.scene_plan_json)
        flags = scene_plan.get("risk_flags", [])
        return flags if isinstance(flags, list) else []
    except Exception:
        return []
