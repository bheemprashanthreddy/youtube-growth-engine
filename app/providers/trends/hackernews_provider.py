import json
import logging
from urllib.request import urlopen

from app.core.config_loader import load_yaml_config
from app.providers.trends.base import TrendProvider, make_trend_item
from app.schemas.content import TrendItem

logger = logging.getLogger(__name__)


class HackerNewsProvider(TrendProvider):
    name = "hackernews"

    def fetch(self) -> list[TrendItem]:
        limit = int(load_yaml_config("trend_sources.yaml")["trend_sources"][self.name].get("limit", 15))
        try:
            with urlopen("https://hn.algolia.com/api/v1/search?tags=front_page", timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("Skipping hackernews: %s", exc)
            return []
        items: list[TrendItem] = []
        for row in payload.get("hits", [])[:limit]:
            title = row.get("title") or row.get("story_title")
            if not title:
                continue
            items.append(
                make_trend_item(
                    source=self.name,
                    title=title,
                    source_score=min(85, 48 + int(row.get("points") or 0) // 20),
                    url=row.get("url") or row.get("story_url"),
                    published_at=row.get("created_at"),
                    search_terms=[title],
                    metadata={"points": row.get("points"), "comments": row.get("num_comments")},
                )
            )
        return items

