from app.providers.trends.base import normalize_topic_text
from app.schemas.content import TrendItem
from app.services.topic_quality_filter import TRANSFORMABLE_PATTERNS, TopicQualityResult, evaluate_trend_quality


def expand_trend_item(item: TrendItem) -> TrendItem:
    quality = evaluate_trend_quality(item)
    expanded_topic = _expanded_topic(quality)
    viewer_question = _viewer_question(expanded_topic)
    curiosity_angle = _curiosity_angle(expanded_topic, quality)
    content_pillar = _pillar(expanded_topic, quality)

    return item.model_copy(
        update={
            "raw_phrase": quality.raw_phrase,
            "cleaned_phrase": quality.cleaned_phrase,
            "normalized_topic": normalize_topic_text(expanded_topic),
            "expanded_topic": expanded_topic,
            "viewer_question": viewer_question,
            "quality_score": quality.quality_score,
            "quality_status": quality.quality_status,
            "quality_reasons": quality.quality_reasons,
            "content_pillar": content_pillar,
            "risk_flags": quality.risk_flags,
            "curiosity_angle": curiosity_angle,
            "short_format_angle": f"Explain the surprising reason behind {expanded_topic.lower()}.",
            "long_format_angle": f"Unpack the systems, incentives, and consequences behind {expanded_topic.lower()}.",
            "category_guess": content_pillar,
        }
    )


def expand_trend_items(items: list[TrendItem]) -> tuple[list[TrendItem], list[TrendItem]]:
    expanded = [expand_trend_item(item) for item in items]
    accepted = [item for item in expanded if item.quality_status != "rejected"]
    rejected = [item for item in expanded if item.quality_status == "rejected"]
    return accepted, rejected


def _expanded_topic(quality: TopicQualityResult) -> str:
    if quality.quality_status == "rejected":
        return quality.cleaned_phrase
    if quality.cleaned_phrase in TRANSFORMABLE_PATTERNS:
        return TRANSFORMABLE_PATTERNS[quality.cleaned_phrase]
    phrase = quality.cleaned_phrase
    if phrase.startswith("why is "):
        subject = phrase.removeprefix("why is ").strip()
        return f"Why {subject} is becoming a bigger question right now".title()
    if phrase.startswith("why are "):
        subject = phrase.removeprefix("why are ").strip()
        return f"Why {subject} is becoming a bigger trend right now".title()
    if phrase.startswith("what is "):
        subject = phrase.removeprefix("what is ").strip()
        return f"What {subject} reveals about a larger trend".title()
    return " ".join(word.capitalize() for word in phrase.split())


def _viewer_question(expanded_topic: str) -> str:
    return f"What is really driving {expanded_topic.lower()}?"


def _curiosity_angle(expanded_topic: str, quality: TopicQualityResult) -> str:
    if "current_event_source_support_needed" in quality.risk_flags:
        return "Turn the breaking-news phrase into a source-backed evergreen explainer."
    return f"Reveal the hidden reason {expanded_topic.lower()} is getting attention."


def _pillar(expanded_topic: str, quality: TopicQualityResult) -> str:
    text = expanded_topic.lower()
    if "ai" in text or "technology" in text:
        return "Technology and AI shifts"
    if "gold" in text or "economy" in text or "business" in text:
        return "Money/business curiosity"
    if "government" in text or "global" in text:
        return "Hidden systems behind everyday things"
    if "english" in text:
        return "Hidden systems behind everyday things"
    return quality.content_pillar
