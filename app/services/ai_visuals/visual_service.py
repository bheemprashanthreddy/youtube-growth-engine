from app.core.config import get_settings
from app.models.content import VideoJob
from app.services.ai_visuals.base import AIVisualAsset, AIVisualStatus
from app.services.ai_visuals.cache import ai_visual_cache_dir, scene_image_path, thumbnail_concept_path
from app.services.ai_visuals.fallback_provider import FallbackAIVisualProvider
from app.services.ai_visuals.openai_image_provider import OpenAIImageProvider
from app.services.ai_visuals.prompt_builder import build_scene_image_prompt, build_thumbnail_prompt
from app.services.ai_visuals.replicate_provider import ReplicateVisualProvider
from app.services.ai_visuals.safety import visual_prompt_safety_status


def ai_visual_status() -> AIVisualStatus:
    settings = get_settings()
    provider = settings.ai_visual_provider.lower()
    image_model = settings.ai_image_model or settings.openai_image_model or settings.replicate_image_model or ""
    video_model = settings.ai_video_model or settings.replicate_video_model or ""
    configured = provider == "fallback" or (
        provider == "openai" and bool(settings.openai_api_key)
    ) or (
        provider == "replicate" and bool(settings.replicate_api_token)
    )
    enabled = settings.ai_visuals_enabled
    fallback = not enabled or not configured
    detail = "AI visuals disabled; using stock/local/motion fallback."
    if enabled and provider == "openai" and not settings.openai_api_key:
        detail = "OpenAI visual provider selected but OPENAI_API_KEY is missing."
    elif enabled and provider == "replicate" and not settings.replicate_api_token:
        detail = "Replicate visual provider selected but REPLICATE_API_TOKEN is missing."
    elif enabled and configured:
        detail = f"{provider} AI visual provider is active."
    return AIVisualStatus(
        enabled=enabled,
        provider=provider,
        image_model=image_model,
        video_model=video_model,
        scene_images_enabled=settings.ai_scene_images_enabled,
        thumbnails_enabled=settings.ai_thumbnails_enabled,
        cache_dir=str(ai_visual_cache_dir()),
        fallback_mode=fallback,
        detail=detail,
    )


def generate_scene_images(video_job: VideoJob, scenes: list[dict[str, object]], *, force: bool = False) -> list[AIVisualAsset]:
    settings = get_settings()
    if not (settings.ai_visuals_enabled and settings.ai_scene_images_enabled):
        return []
    provider = _provider()
    assets: list[AIVisualAsset] = []
    for scene in scenes:
        scene_number = int(scene.get("scene_number") or len(assets) + 1)
        prompt = build_scene_image_prompt(scene, video_job)
        path = scene_image_path(video_job.id, scene_number, prompt)
        if force or not path.exists():
            ok = provider.generate_image(prompt, str(path))
            if not ok:
                continue
        assets.append(_asset(provider.name, prompt, str(path), settings.ai_image_model or settings.openai_image_model or settings.replicate_image_model or "fallback"))
    return assets


def generate_ai_thumbnail_concepts(video_job: VideoJob, *, force: bool = False) -> list[AIVisualAsset]:
    settings = get_settings()
    if not (settings.ai_visuals_enabled and settings.ai_thumbnails_enabled):
        return []
    provider = _provider()
    assets: list[AIVisualAsset] = []
    for variant in ["a", "b", "c"]:
        prompt = build_thumbnail_prompt(video_job, variant)
        path = thumbnail_concept_path(video_job.id, variant, prompt)
        if force or not path.exists():
            ok = provider.generate_image(prompt, str(path))
            if not ok:
                continue
        assets.append(_asset(provider.name, prompt, str(path), settings.ai_image_model or settings.openai_image_model or settings.replicate_image_model or "fallback"))
    return assets


def _provider():
    provider = get_settings().ai_visual_provider.lower()
    if provider == "openai":
        return OpenAIImageProvider()
    if provider == "replicate":
        return ReplicateVisualProvider()
    return FallbackAIVisualProvider()


def _asset(provider: str, prompt: str, local_path: str, model: str) -> AIVisualAsset:
    return AIVisualAsset(
        provider=provider,
        asset_type="image",
        prompt=prompt,
        model=model,
        local_path=local_path,
        safety_status=visual_prompt_safety_status(prompt),
    )
