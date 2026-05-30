from abc import ABC, abstractmethod
import logging
import re

from app.schemas.content import TrendItem

logger = logging.getLogger(__name__)


class TrendProvider(ABC):
    name: str

    @abstractmethod
    def fetch(self) -> list[TrendItem]:
        """Return normalized trend items without raising for optional-source failures."""


def normalize_topic_text(value: str) -> str:
    text = value.lower().strip()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\b(the|a|an|why|what|how|is|are|was|were|this|that|these|those)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def guess_category(value: str) -> str:
    text = value.lower()
    if any(word in text for word in ["ai", "technology", "software", "robot", "search"]):
        return "Technology and AI shifts"
    if any(word in text for word in ["money", "business", "market", "economy", "startup"]):
        return "Money/business curiosity"
    if any(word in text for word in ["science", "space", "climate", "future", "discovery"]):
        return "Science/future discoveries"
    if any(word in text for word in ["internet", "creator", "viral", "meme", "platform"]):
        return "Internet trends explained"
    if any(word in text for word in ["global", "country", "tourism", "city", "world"]):
        return "Strange global stories"
    return "Hidden systems behind everyday things"


def make_trend_item(
    *,
    source: str,
    title: str,
    source_score: int,
    url: str | None = None,
    published_at: str | None = None,
    search_terms: list[str] | None = None,
    region: str = "US",
    metadata: dict[str, object] | None = None,
) -> TrendItem:
    return TrendItem(
        source=source,
        raw_title=title.strip(),
        normalized_topic=normalize_topic_text(title),
        raw_phrase=title.strip(),
        cleaned_phrase=normalize_topic_text(title),
        expanded_topic=title.strip(),
        viewer_question=None,
        quality_score=0,
        quality_status="accepted",
        quality_reasons=[],
        content_pillar=guess_category(title),
        risk_flags=[],
        url=url,
        published_at=published_at,
        source_score=source_score,
        search_terms=search_terms or [],
        category_guess=guess_category(title),
        language="en",
        region=region,
        metadata=metadata or {},
    )
