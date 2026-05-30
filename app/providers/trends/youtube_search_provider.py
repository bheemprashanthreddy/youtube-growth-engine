import json
import logging
from urllib.parse import urlencode
from urllib.request import urlopen

from app.core.config import get_settings
from app.core.config_loader import load_yaml_config
from app.providers.trends.base import TrendProvider, make_trend_item
from app.schemas.content import TrendItem

logger = logging.getLogger(__name__)


class YouTubeSearchProvider(TrendProvider):
    name = "youtube_search"

    def fetch(self) -> list[TrendItem]:
        settings = get_settings()
        if not settings.youtube_api_key:
            logger.warning("Skipping youtube_search: YOUTUBE_API_KEY is not configured.")
            return []

        config = load_yaml_config("trend_sources.yaml")["trend_sources"][self.name]
        items: list[TrendItem] = []
        for term in config.get("query_terms", [])[:5]:
            params = urlencode(
                {
                    "part": "snippet",
                    "type": "video",
                    "order": "relevance",
                    "maxResults": min(int(config.get("max_results", 10)), 10),
                    "q": term,
                    "key": settings.youtube_api_key,
                }
            )
            try:
                with urlopen(f"https://www.googleapis.com/youtube/v3/search?{params}", timeout=8) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                logger.warning("Skipping youtube_search query %s: %s", term, exc)
                continue
            for row in payload.get("items", []):
                snippet = row.get("snippet", {})
                title = snippet.get("title")
                if title:
                    items.append(
                        make_trend_item(
                            source=self.name,
                            title=title,
                            source_score=68,
                            url=f"https://www.youtube.com/watch?v={row.get('id', {}).get('videoId', '')}",
                            published_at=snippet.get("publishedAt"),
                            search_terms=[term],
                            metadata={"channel_title": snippet.get("channelTitle")},
                        )
                    )
        return items

