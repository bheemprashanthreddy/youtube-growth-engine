import json
import logging
from urllib.parse import urlencode
from urllib.request import urlopen

from app.core.config_loader import load_yaml_config
from app.providers.trends.base import TrendProvider, make_trend_item
from app.schemas.content import TrendItem

logger = logging.getLogger(__name__)


class YouTubeSuggestionsProvider(TrendProvider):
    name = "youtube_suggestions"

    def fetch(self) -> list[TrendItem]:
        config = load_yaml_config("trend_sources.yaml")["trend_sources"][self.name]
        items: list[TrendItem] = []
        for seed in config.get("seed_terms", [])[:8]:
            params = urlencode({"client": "firefox", "ds": "yt", "q": seed})
            try:
                with urlopen(f"https://suggestqueries.google.com/complete/search?{params}", timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                logger.warning("Skipping youtube_suggestions seed %s: %s", seed, exc)
                continue
            for suggestion in payload[1][:8]:
                items.append(
                    make_trend_item(
                        source=self.name,
                        title=suggestion,
                        source_score=62,
                        search_terms=[seed, suggestion],
                        metadata={"seed": seed},
                    )
                )
        return items

