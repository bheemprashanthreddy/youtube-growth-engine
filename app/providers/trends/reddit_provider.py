import logging

from app.core.config import get_settings
from app.providers.trends.base import TrendProvider
from app.schemas.content import TrendItem

logger = logging.getLogger(__name__)


class RedditProvider(TrendProvider):
    name = "reddit"

    def fetch(self) -> list[TrendItem]:
        settings = get_settings()
        if not (settings.reddit_client_id and settings.reddit_client_secret and settings.reddit_user_agent):
            logger.warning("Skipping reddit: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, or REDDIT_USER_AGENT is missing.")
            return []
        logger.warning("Skipping reddit: OAuth client wiring is intentionally deferred to avoid unsafe unauthenticated scraping.")
        return []

