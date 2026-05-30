import logging

from app.core.config_loader import load_yaml_config
from app.providers.trends.base import TrendProvider, normalize_topic_text
from app.providers.trends.hackernews_provider import HackerNewsProvider
from app.providers.trends.manual_seed_provider import ManualSeedProvider
from app.providers.trends.pytrends_provider import PytrendsProvider
from app.providers.trends.reddit_provider import RedditProvider
from app.providers.trends.rss_provider import RSSProvider
from app.providers.trends.wikipedia_current_events_provider import WikipediaCurrentEventsProvider
from app.providers.trends.youtube_search_provider import YouTubeSearchProvider
from app.providers.trends.youtube_suggestions_provider import YouTubeSuggestionsProvider
from app.schemas.content import MergedTrend, TrendItem

logger = logging.getLogger(__name__)


PROVIDER_CLASSES: dict[str, type[TrendProvider]] = {
    "manual_seed": ManualSeedProvider,
    "youtube_search": YouTubeSearchProvider,
    "youtube_suggestions": YouTubeSuggestionsProvider,
    "reddit": RedditProvider,
    "rss": RSSProvider,
    "pytrends": PytrendsProvider,
    "wikipedia_current_events": WikipediaCurrentEventsProvider,
    "hackernews": HackerNewsProvider,
}


def collect_trends() -> list[TrendItem]:
    config = load_yaml_config("trend_sources.yaml")["trend_sources"]
    items: list[TrendItem] = []
    for name, provider_class in PROVIDER_CLASSES.items():
        if not config.get(name, {}).get("enabled", False):
            logger.info("Skipping %s: disabled in trend_sources.yaml.", name)
            continue
        try:
            provider = provider_class()
            items.extend(provider.fetch())
        except Exception as exc:
            logger.warning("Skipping %s after provider error: %s", name, exc)
    return [item for item in items if item.normalized_topic]


def deduplicate_trends(items: list[TrendItem]) -> list[MergedTrend]:
    grouped: dict[str, list[TrendItem]] = {}
    for item in items:
        key_source = item.expanded_topic or item.cleaned_phrase or item.normalized_topic
        key = _matching_key(key_source, grouped) or _dedupe_key(key_source)
        grouped.setdefault(key, []).append(item)

    merged: list[MergedTrend] = []
    for _, group in grouped.items():
        best = max(group, key=lambda item: (item.quality_score, item.source_score, len(item.expanded_topic or item.raw_title)))
        source_names = sorted({item.source for item in group})
        search_terms = sorted({term for item in group for term in item.search_terms if term})
        metadata = {
            "items": [item.model_dump() for item in group],
            "source_boost": max(0, len(source_names) - 1) * 6,
        }
        merged.append(
            MergedTrend(
                normalized_topic=best.normalized_topic,
                display_topic=best.expanded_topic or best.raw_title,
                raw_phrase=best.raw_phrase or best.raw_title,
                cleaned_phrase=best.cleaned_phrase or best.normalized_topic,
                expanded_topic=best.expanded_topic or best.raw_title,
                viewer_question=best.viewer_question,
                quality_score=max(item.quality_score for item in group),
                quality_status="transformed" if any(item.quality_status == "transformed" for item in group) else best.quality_status,
                quality_reasons=sorted({reason for item in group for reason in item.quality_reasons}),
                content_pillar=best.content_pillar or best.category_guess,
                risk_flags=sorted({flag for item in group for flag in item.risk_flags}),
                curiosity_angle=best.curiosity_angle,
                short_format_angle=best.short_format_angle,
                long_format_angle=best.long_format_angle,
                source_count=len(source_names),
                source_names=source_names,
                source_score=round(sum(item.source_score for item in group) / len(group), 2),
                search_terms=search_terms or [best.raw_title],
                category_guess=best.content_pillar or best.category_guess,
                language=best.language,
                region=best.region,
                url=best.url,
                published_at=best.published_at,
                raw_titles=sorted({item.raw_title for item in group}),
                metadata=metadata,
            )
        )
    merged.sort(key=lambda item: (item.source_count, item.source_score), reverse=True)
    return merged


def _dedupe_key(value: str) -> str:
    normalized = normalize_topic_text(value)
    tokens = [token for token in normalized.split() if len(token) > 2]
    return " ".join(tokens[:8])


def _matching_key(value: str, grouped: dict[str, list[TrendItem]]) -> str | None:
    candidate_tokens = set(_dedupe_key(value).split())
    if not candidate_tokens:
        return None
    for key in grouped:
        key_tokens = set(key.split())
        overlap = len(candidate_tokens & key_tokens)
        ratio = overlap / max(len(candidate_tokens), len(key_tokens), 1)
        if ratio >= 0.72 or (overlap >= 4 and min(len(candidate_tokens), len(key_tokens)) >= 4):
            return key
    return None
