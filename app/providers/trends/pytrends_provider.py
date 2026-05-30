import logging

from app.core.config import get_settings
from app.providers.trends.base import TrendProvider
from app.schemas.content import TrendItem

logger = logging.getLogger(__name__)


class PytrendsProvider(TrendProvider):
    name = "pytrends"

    def fetch(self) -> list[TrendItem]:
        region = get_settings().google_trends_region
        logger.warning("Skipping pytrends for region %s: pytrends is optional and not installed by default.", region)
        return []

