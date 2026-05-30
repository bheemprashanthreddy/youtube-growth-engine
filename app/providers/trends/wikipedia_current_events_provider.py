import json
import logging
import re
from urllib.parse import urlencode
from urllib.request import urlopen

from app.core.config_loader import load_yaml_config
from app.providers.trends.base import TrendProvider, make_trend_item
from app.schemas.content import TrendItem

logger = logging.getLogger(__name__)


class WikipediaCurrentEventsProvider(TrendProvider):
    name = "wikipedia_current_events"

    def fetch(self) -> list[TrendItem]:
        page_title = load_yaml_config("trend_sources.yaml")["trend_sources"][self.name].get("page_title", "Portal:Current_events")
        params = urlencode({"action": "parse", "page": page_title, "prop": "text", "format": "json", "formatversion": "2"})
        try:
            with urlopen(f"https://en.wikipedia.org/w/api.php?{params}", timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("Skipping wikipedia_current_events: %s", exc)
            return []
        html = payload.get("parse", {}).get("text", "")
        titles = re.findall(r'title="([^"]+)"', html)
        items: list[TrendItem] = []
        for title in titles[:30]:
            if ":" in title or len(title) < 6:
                continue
            items.append(
                make_trend_item(
                    source=self.name,
                    title=title,
                    source_score=52,
                    url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    search_terms=[title],
                    metadata={"page_title": page_title},
                )
            )
        return items

