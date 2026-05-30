import logging
import xml.etree.ElementTree as ET
from urllib.request import urlopen

from app.core.config import get_settings
from app.core.config_loader import load_yaml_config
from app.providers.trends.base import TrendProvider, make_trend_item
from app.schemas.content import TrendItem

logger = logging.getLogger(__name__)


class RSSProvider(TrendProvider):
    name = "rss"

    def fetch(self) -> list[TrendItem]:
        settings = get_settings()
        if not settings.news_rss_urls:
            logger.warning("Skipping rss: NEWS_RSS_URLS is not configured.")
            return []
        limit = int(load_yaml_config("trend_sources.yaml")["trend_sources"][self.name].get("limit_per_feed", 10))
        items: list[TrendItem] = []
        for feed_url in [url.strip() for url in settings.news_rss_urls.split(",") if url.strip()]:
            try:
                with urlopen(feed_url, timeout=8) as response:
                    root = ET.fromstring(response.read())
            except Exception as exc:
                logger.warning("Skipping RSS feed %s: %s", feed_url, exc)
                continue
            for item in root.findall(".//item")[:limit]:
                title = item.findtext("title")
                if not title:
                    continue
                items.append(
                    make_trend_item(
                        source=self.name,
                        title=title,
                        source_score=58,
                        url=item.findtext("link"),
                        published_at=item.findtext("pubDate"),
                        search_terms=[title],
                        metadata={"feed_url": feed_url},
                    )
                )
        return items

