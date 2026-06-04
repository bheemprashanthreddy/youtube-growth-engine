from pathlib import Path

from app.services.visual_assets.asset_cache import cache_root
from app.services.visual_assets.base import VisualAsset, generated_asset
from app.services.visual_assets.safety import is_safe_asset_query


class LocalVisualProvider:
    name = "local"

    def search(self, query: str, *, asset_type: str = "image") -> VisualAsset | None:
        if not is_safe_asset_query(query):
            return None
        for path in _local_files():
            if any(token in path.stem.lower() for token in query.lower().split() if len(token) > 3):
                return VisualAsset(
                    provider="local",
                    asset_type="image" if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else "video",
                    query=query,
                    title=path.stem.replace("-", " ").replace("_", " ").title(),
                    source_url="",
                    local_path=str(path),
                    license_note="Local asset supplied by project owner. Verify rights before publishing.",
                    attribution_required=False,
                    width=0,
                    height=0,
                    duration=0,
                    relevance_score=0.75,
                    safety_status="safe",
                    created_at=generated_asset(query).created_at,
                )
        return generated_asset(query, provider="local")


def _local_files() -> list[Path]:
    root = cache_root() / "local"
    if not root.exists():
        return []
    return [
        path
        for path in root.rglob("*")
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"}
    ]
