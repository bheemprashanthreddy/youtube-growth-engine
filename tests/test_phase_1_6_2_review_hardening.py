import pytest

from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.models.content import ReviewItem
from app.providers.trends.base import make_trend_item
from app.schemas.content import ContentPlan, OpportunityScore, QualityGateResult
from app.services.review import (
    build_content_key,
    clear_dev_data,
    create_review_item,
    dedupe_review_items,
    list_review_items,
    reset_invalid_ready_for_render,
    set_approval_status,
)
from app.services.topic_expander import expand_trend_item


def test_run_daily_twice_does_not_create_duplicate_review_items() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        first_count = len(list_review_items(db))
    run_daily_job()
    with SessionLocal() as db:
        second_count = len(list_review_items(db))
    assert second_count == first_count


def test_same_expanded_topic_creates_one_review_item() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
        plan = _plan("Why AI search engines are changing how people find information online")
        create_review_item(db, plan, None, ["manual_seed"], {"expanded_topic": plan.topic, "quality_score": 100})
        create_review_item(db, plan, None, ["youtube_suggestions"], {"expanded_topic": plan.topic, "quality_score": 100})
        db.commit()
        assert len(list_review_items(db)) == 1


def test_ready_for_render_requires_approval() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        item = list_review_items(db)[0]
        with pytest.raises(ValueError):
            set_approval_status(db, item, "ready_for_render")
        set_approval_status(db, item, "approved")
        ready = set_approval_status(db, item, "ready_for_render")
        assert ready.approval_status == "ready_for_render"


def test_reset_review_statuses_fixes_invalid_ready_rows() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
        row = _review_row("Invalid Ready", 80)
        row.approval_status = "ready_for_render"
        row.approved_at = None
        db.add(row)
        db.commit()
        assert reset_invalid_ready_for_render(db) == 1
        fixed = list_review_items(db)[0]
        assert fixed.approval_status == "needs_review"


def test_dedupe_review_items_keeps_highest_score() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
        low = _review_row("Duplicate Topic", 50)
        high = _review_row("Duplicate Topic", 91)
        db.add_all([low, high])
        db.commit()
        result = dedupe_review_items(db)
        rows = list_review_items(db)
        assert result["removed"] == 1
        assert len(rows) == 1
        assert rows[0].final_score == 91


def test_lyric_meme_phrase_rejected() -> None:
    item = expand_trend_item(make_trend_item(source="test", title="What Love Haddaway Reveals About A Larger Trend", source_score=50))
    assert item.quality_status == "rejected"
    assert "lyric_or_meme_fragment_without_trend_context" in item.quality_reasons

    meme = expand_trend_item(make_trend_item(source="test", title="Why Everybody Always Pickin On Me Is Becoming A Bigger Question Right Now", source_score=50))
    assert meme.quality_status == "rejected"


def test_deadly_topic_rejected_or_risk_blocked() -> None:
    item = expand_trend_item(make_trend_item(source="test", title="Internet Trends That Were Deadly", source_score=50))
    assert item.quality_status == "rejected"
    assert "unsafe_sensitive_content" in item.risk_flags


def test_ai_search_phrase_transforms_to_specific_explainer() -> None:
    item = expand_trend_item(make_trend_item(source="test", title="AI Search Replacing Blue Links", source_score=60))
    assert item.quality_status == "transformed"
    assert item.expanded_topic == "Why AI search engines are changing how people find information online"


def test_current_political_manual_seed_cannot_pass_quality_gate() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
        plan = _plan("Why government shutdowns happen and how they affect everyday people")
        item = create_review_item(
            db,
            plan,
            None,
            ["manual_seed"],
            {
                "expanded_topic": plan.topic,
                "quality_score": 100,
                "risk_flags": ["current_event_source_support_needed", "political_context"],
                "quality_reasons": ["passes_minimum_topic_quality"],
            },
        )
        db.commit()
        assert item.quality_gate_status == "needs_review"
        assert "Source support required" in item.quality_gate_reasons


def _plan(topic: str) -> ContentPlan:
    score = OpportunityScore(
        trend_velocity=80,
        cross_source_validation=80,
        curiosity_gap=80,
        novelty=80,
        emotional_pull=70,
        search_intent_strength=80,
        saturation_risk=20,
        monetization_fit=70,
        short_format_fit=80,
        long_format_fit=80,
        policy_risk=10,
        originality_potential=80,
        final_score=82,
        explanation=f"{topic} scored 82.0/100.",
    )
    gate = QualityGateResult(
        repetitive_content_risk="low",
        low_effort_ai_content_risk="low",
        unsupported_claim_risk="low",
        misleading_title_risk="low",
        copyright_reused_content_risk="low",
        sensitive_topic_risk="low",
        monetization_risk="low",
        ai_disclosure_needed=True,
        final_status="approved",
        notes=["passes"],
    )
    return ContentPlan(
        topic=topic,
        pillar="Technology and AI shifts",
        trend_reason="test trend reason",
        viewer_curiosity_trigger="test trigger",
        target_viewer="test viewer",
        short_video_angle="short angle",
        long_video_angle="long angle",
        research_brief="brief",
        hook_options=["hook"],
        shorts_script="script",
        long_form_outline=["outline"],
        title_options=["title"],
        description="description",
        hashtags=["#test"],
        thumbnail_text_ideas=["WHY NOW?"],
        pinned_comment_idea="comment",
        ai_disclosure_recommendation="disclose if synthetic media is used",
        score=score,
        quality_gate=gate,
    )


def _review_row(topic: str, score: float) -> ReviewItem:
    key = build_content_key(topic, "Technology and AI shifts")
    return ReviewItem(
        content_key=key,
        format_family="shorts_longform",
        topic=topic,
        raw_phrase=topic,
        expanded_topic=topic,
        quality_score=100,
        quality_status="accepted",
        quality_reasons="[]",
        risk_flags="[]",
        pillar="Technology and AI shifts",
        trend_reason="reason",
        source_names='["manual_seed"]',
        final_score=score,
        scoring_explanation="explanation",
        short_script="script",
        long_outline="[]",
        title_options="[]",
        description="description",
        hashtags="[]",
        thumbnail_ideas="[]",
        pinned_comment="comment",
        quality_gate_status="needs_review",
        quality_gate_reasons="[]",
        ai_disclosure_recommendation="disclose if synthetic media is used",
        approval_status="needs_review",
    )
