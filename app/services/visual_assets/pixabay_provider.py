import json
from datetime import UTC, datetime
from urllib import parse, request

from app.core.config import get_settings
from app.services.visual_assets.asset_cache import download_to_cache
from app.services.visual_assets.base import VisualAsset
from app.services.visual_assets.safety import is_safe_asset_query


class PixabayVisualProvider:
    name = "pixabay"

    def search(self, query: str, *, asset_type: str = "image") -> VisualAsset | None:
        settings = get_settings()
        if not settings.pixabay_api_key or not settings.allow_stock_assets or not is_safe_asset_query(query):
            return None
        try:
            if asset_type == "video":
                url = f"https://pixabay.com/api/videos/?key={settings.pixabay_api_key}&q={parse.quote(query)}&per_page=3&safesearch=true"
            else:
                url = f"https://pixabay.com/api/?key={settings.pixabay_api_key}&q={parse.quote(query)}&per_page=3&safesearch=true&image_type=photo"
            with request.urlopen(url, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            row = (payload.get("hits") or [None])[0]
            if not row:
                return None
            if asset_type == "video":
                videos = row.get("videos", {})
                video = videos.get("large") or videos.get("medium") or videos.get("small")
                if not video:
                    return None
                local_path = download_to_cache(video["url"], "pixabay", query, ".mp4")
                return _asset(query, "video", row.get("pageURL", ""), local_path, int(video.get("width") or 0), int(video.get("height") or 0), float(row.get("duration") or 0))
            local_path = download_to_cache(row.get("largeImageURL") or row.get("webformatURL"), "pixabay", query, ".jpg")
            return _asset(query, "image", row.get("pageURL", ""), local_path, int(row.get("imageWidth") or 0), int(row.get("imageHeight") or 0), 0)
        except Exception:
            return None


def _asset(query: str, asset_type: str, source_url: str, local_path: str, width: int, height: int, duration: float) -> VisualAsset:
    return VisualAsset(
        provider="pixabay",
        asset_type=asset_type,
        query=query,
        title=query.title(),
        source_url=source_url,
        local_path=local_path,
        license_note="Pixabay free media. Verify current license terms before publishing.",
        attribution_required=False,
        width=width,
        height=height,
        duration=duration,
        relevance_score=0.82,
        safety_status="safe",
        created_at=datetime.now(UTC).isoformat(),
    )
