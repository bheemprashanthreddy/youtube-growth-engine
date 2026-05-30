from app.providers.trends.manual_seed_provider import ManualSeedProvider
from app.providers.trends.youtube_search_provider import YouTubeSearchProvider
from app.schemas.content import TrendItem
from app.services.scoring import score_opportunity
from app.services.trend_ingestion import deduplicate_trends


def test_youtube_search_missing_key_fallback(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    assert YouTubeSearchProvider().fetch() == []


def test_manual_seed_provider_returns_normalized_trends() -> None:
    items = ManualSeedProvider().fetch()
    assert items
    assert all(isinstance(item, TrendItem) for item in items)
    assert all(item.normalized_topic for item in items)


def test_deduplication_merges_sources() -> None:
    items = [
        TrendItem(
            source="manual_seed",
            raw_title="Why AI Search Is Replacing Blue Links",
            normalized_topic="ai search replacing blue links",
            source_score=55,
            search_terms=["ai search"],
            category_guess="Technology and AI shifts",
        ),
        TrendItem(
            source="youtube_suggestions",
            raw_title="AI search replacing blue links explained",
            normalized_topic="ai search replacing blue links explained",
            source_score=65,
            search_terms=["ai search replacing blue links"],
            category_guess="Technology and AI shifts",
        ),
    ]
    merged = deduplicate_trends(items)
    assert len(merged) == 1
    assert merged[0].source_count == 2
    assert set(merged[0].source_names) == {"manual_seed", "youtube_suggestions"}


def test_opportunity_score_creation() -> None:
    trend = deduplicate_trends(ManualSeedProvider().fetch())[0]
    score = score_opportunity(trend)
    assert 0 <= score.final_score <= 100
    assert score.explanation
