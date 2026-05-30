import subprocess
import sys

from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.providers.trends.base import make_trend_item
from app.schemas.content import TrendItem
from app.services.review import list_review_items
from app.services.scoring import score_opportunity
from app.services.topic_expander import expand_trend_item, expand_trend_items
from app.services.trend_ingestion import deduplicate_trends


def _trend(phrase: str) -> TrendItem:
    return make_trend_item(source="test", title=phrase, source_score=60, search_terms=[phrase])


def test_vague_pronoun_phrase_rejected() -> None:
    item = expand_trend_item(_trend("why is he lying"))
    assert item.quality_status == "rejected"
    assert "unclear_subject" in item.quality_reasons


def test_typo_noise_phrase_rejected() -> None:
    item = expand_trend_item(_trend("why is he lying wong"))
    assert item.quality_status == "rejected"
    assert "typo_heavy_or_nonsensical" in item.quality_reasons


def test_english_phrase_transformed_to_stronger_topic() -> None:
    item = expand_trend_item(_trend("why is english so hard"))
    assert item.quality_status == "transformed"
    assert item.expanded_topic == "Why English feels so difficult even for advanced learners"


def test_government_shutdown_gets_evergreen_transform_and_risk_flag() -> None:
    item = expand_trend_item(_trend("why is the government shutdown"))
    assert item.quality_status == "transformed"
    assert item.expanded_topic == "Why government shutdowns happen and how they affect everyday people"
    assert "current_event_source_support_needed" in item.risk_flags


def test_scoring_penalizes_low_quality() -> None:
    rejected = expand_trend_item(_trend("why is it spicy"))
    merged = deduplicate_trends([rejected])
    score = score_opportunity(merged[0])
    assert score.final_score < 75


def test_daily_run_excludes_rejected_topics_from_review_items() -> None:
    init_db()
    run_daily_job()
    with SessionLocal() as db:
        items = list_review_items(db)
        assert items
        rejected_phrases = {"why is it spicy", "why is he lying", "why is he lying wong"}
        assert not any(item.raw_phrase in rejected_phrases for item in items)


def test_expand_trend_items_splits_cleaned_and_rejected() -> None:
    cleaned, rejected = expand_trend_items([_trend("why is english so hard"), _trend("who is he")])
    assert len(cleaned) == 1
    assert len(rejected) == 1


def test_quality_report_cli_works() -> None:
    run_daily_job()
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "quality-report"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "total raw phrases:" in result.stdout
    assert "top 10 expanded topics:" in result.stdout
