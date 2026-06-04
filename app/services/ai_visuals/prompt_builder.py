from app.models.content import VideoJob
from app.services.ai_visuals.safety import sanitize_visual_prompt


STYLE_GUIDE = (
    "Dark premium tech explainer style, high contrast, cinematic lighting, abstract conceptual visual, "
    "clean composition, vertical-friendly, leave room for overlay text"
)


def build_scene_image_prompt(scene: dict[str, object], video_job: VideoJob) -> str:
    keywords = scene.get("broll_keywords", [])
    keyword_text = ", ".join(str(item) for item in keywords[:5]) if isinstance(keywords, list) else ""
    base = (
        f"{STYLE_GUIDE}. Topic: {video_job.title}. Scene visual: {scene.get('visual_prompt') or scene.get('on_screen_text')}. "
        f"Keywords: {keyword_text}."
    )
    return sanitize_visual_prompt(base)


def build_thumbnail_prompt(video_job: VideoJob, variant: str) -> str:
    variant_styles = {
        "a": "bold visual metaphor, dramatic abstract object, no text baked into image",
        "b": "conceptual background with strong focal point, room for large text overlay",
        "c": "minimal premium brand background, elegant abstract signal pattern",
    }
    base = f"{STYLE_GUIDE}. YouTube thumbnail background for: {video_job.title}. {variant_styles.get(variant, variant_styles['a'])}."
    return sanitize_visual_prompt(base)
