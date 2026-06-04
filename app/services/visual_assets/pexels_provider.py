import json
from datetime import UTC, datetime
from urllib import parse, request

from app.core.config import get_settings
from app.services.visual_assets.asset_cache import download_to_cache
from app.services.visual_assets.base import VisualAsset
from app.services.visual_assets.safety import is_safe_asset_query


class PexelsVisualProvider:
    name = "pexels"

    def search(self, query: str, *, asset_type: str = "image") -> VisualAsset | None:
        settings = get_settings()
        if not settings.pexels_api_key or not settings.allow_stock_assets or not is_safe_asset_query(query):
            return None
        try:
            endpoint = "videos/search" if asset_type == "video" else "v1/search"
            url = f"https://api.pexels.com/{endpoint}?query={parse.quote(query)}&per_page=1&orientation=portrait"
            req = request.Request(url, headers={"Authorization": settings.pexels_api_key})
            with request.urlopen(req, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if asset_type == "video":
                row = (payload.get("videos") or [None])[0]
                if not row:
                    return None
                file_row = sorted(row.get("video_files") or [], key=lambda item: item.get("width", 0), reverse=True)[0]
                local_path = download_to_cache(file_row["link"], "pexels", query, ".mp4")
                return _asset(query, "video", row.get("url", ""), local_path, row.get("width", 0), row.get("height", 0), float(row.get("duration") or 0))
            row = (payload.get("photos") or [None])[0]
            if not row:
                return None
            src = row.get("src", {})
            local_path = download_to_cache(src.get("large2x") or src.get("large") or src.get("original"), "pexels", query, ".jpg")
            return _asset(query, "image", row.get("url", ""), local_path, int(row.get("width") or 0), int(row.get("height") or 0), 0)
        except Exception:
            return None


def _asset(query: str, asset_type: str, source_url: str, local_path: str, width: int, height: int, duration: float) -> VisualAsset:
    return VisualAsset(
        provider="pexels",
        asset_type=asset_type,
        query=query,
        title=query.title(),
        source_url=source_url,
        local_path=local_path,
        license_note="Pexels free media. Verify current license terms before publishing.",
        attribution_required=False,
        width=width,
        height=height,
        duration=duration,
        relevance_score=0.85,
        safety_status="safe",
        created_at=datetime.now(UTC).isoformat(),
    )
