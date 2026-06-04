import json

from app.core.config import get_settings
from app.models.content import VideoJob


def build_youtube_metadata(job: VideoJob) -> dict[str, object]:
    settings = get_settings()
    tags = [tag.strip("#") for tag in _loads(job.hashtags, []) if str(tag).strip("#")]
    description = job.description.strip()
    hashtags = " ".join(f"#{tag}" for tag in tags[:8])
    if hashtags and hashtags not in description:
        description = f"{description}\n\n{hashtags}"
    return {
        "snippet": {
            "title": job.title[:100],
            "description": description,
            "tags": tags[:15],
            "categoryId": settings.youtube_category_id,
            "defaultLanguage": settings.youtube_default_language,
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": settings.youtube_made_for_kids,
        },
        "notifySubscribers": settings.youtube_notify_subscribers,
        "ai_disclosure_recommendation": job.ai_disclosure_recommendation,
    }


def _loads(value: str, fallback: object) -> object:
    try:
        return json.loads(value)
    except Exception:
        return fallback
