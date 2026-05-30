import re
from dataclasses import dataclass, field

from app.core.config_loader import load_yaml_config
from app.providers.trends.base import guess_category, normalize_topic_text
from app.schemas.content import TrendItem

MIN_TOPIC_QUALITY_SCORE = 70

UNCLEAR_PRONOUNS = {"he", "she", "it", "they", "him", "her", "this", "that"}
VAGUE_PATTERNS = {
    "why is it spicy",
    "why is he lying",
    "why is he lying wong",
    "why is she mad",
    "what happened to him",
    "why is this happening",
    "who is he",
    "is it real",
    "why is it bad",
}
UNSAFE_TERMS = {"porn", "nude", "kill", "murder", "hate", "slur", "terrorist", "deadly", "death", "violent", "violence"}
CURRENT_EVENT_TERMS = {"government shutdown", "election", "war", "breaking", "attack", "trial", "congress", "senate", "president"}
LYRIC_MEME_FRAGMENTS = {
    "everybody always pickin on me",
    "love haddaway",
    "what is love haddaway",
}
TRANSFORMABLE_PATTERNS = {
    "why is english so hard": "Why English feels so difficult even for advanced learners",
    "why is the government shutdown": "Why government shutdowns happen and how they affect everyday people",
    "why are people buying gold": "Why people suddenly buy gold when the economy feels uncertain",
    "why are ai companions popular": "Why AI companion apps are becoming popular so quickly",
    "ai search replacing blue links": "Why AI search engines are changing how people find information online",
}


@dataclass
class TopicQualityResult:
    raw_phrase: str
    cleaned_phrase: str
    quality_score: int
    quality_status: str
    quality_reasons: list[str] = field(default_factory=list)
    content_pillar: str = "Hidden systems behind everyday things"
    risk_flags: list[str] = field(default_factory=list)


def evaluate_trend_quality(item: TrendItem) -> TopicQualityResult:
    raw_phrase = (item.raw_phrase or item.raw_title).strip()
    cleaned_phrase = clean_phrase(raw_phrase)
    reasons: list[str] = []
    risk_flags: list[str] = []
    score = 100

    token_count = len(cleaned_phrase.split())
    if token_count < 4:
        score -= 35
        reasons.append("too_short")
    if cleaned_phrase in VAGUE_PATTERNS:
        score -= 60
        reasons.append("known_vague_autocomplete_fragment")
    if _has_unclear_pronoun(cleaned_phrase):
        score -= 35
        reasons.append("unclear_subject")
    if _is_incomplete(cleaned_phrase):
        score -= 30
        reasons.append("incomplete_phrase")
    if _is_typo_heavy(cleaned_phrase):
        score -= 35
        reasons.append("typo_heavy_or_nonsensical")
    if _low_explanatory_value(cleaned_phrase):
        score -= 25
        reasons.append("low_explanatory_value")
    if _lyric_or_meme_fragment(cleaned_phrase):
        score -= 70
        reasons.append("lyric_or_meme_fragment_without_trend_context")
        risk_flags.append("weak_pop_culture_context")
    if any(term in cleaned_phrase for term in UNSAFE_TERMS):
        score -= 70
        reasons.append("unsafe_sensitive_content")
        risk_flags.append("unsafe_sensitive_content")
    if _specific_person_allegation(cleaned_phrase):
        score -= 50
        reasons.append("specific_person_allegation_without_verified_context")
        risk_flags.append("person_allegation")
    if any(term in cleaned_phrase for term in CURRENT_EVENT_TERMS):
        risk_flags.append("current_event_source_support_needed")
        if any(term in cleaned_phrase for term in ["government", "election", "congress", "senate", "president"]):
            risk_flags.append("political_context")
        if "breaking" in cleaned_phrase:
            risk_flags.append("breaking_news_context")
        if "government shutdown" not in cleaned_phrase:
            score -= 25
            reasons.append("unsupported_current_event_claim")
    if not _clear_viewer_question(cleaned_phrase):
        score -= 25
        reasons.append("no_clear_viewer_question")
    if not _aligned_with_pillars(cleaned_phrase):
        score -= 20
        reasons.append("weak_channel_alignment")

    score = max(0, min(100, score))
    threshold = int(load_yaml_config("scoring.yaml")["scoring"].get("min_topic_quality_score", MIN_TOPIC_QUALITY_SCORE))
    if score < threshold:
        status = "rejected"
    elif cleaned_phrase in TRANSFORMABLE_PATTERNS or _should_transform(cleaned_phrase):
        status = "transformed"
    else:
        status = "accepted"

    return TopicQualityResult(
        raw_phrase=raw_phrase,
        cleaned_phrase=cleaned_phrase,
        quality_score=score,
        quality_status=status,
        quality_reasons=reasons or ["passes_minimum_topic_quality"],
        content_pillar=guess_category(cleaned_phrase),
        risk_flags=risk_flags,
    )


def clean_phrase(value: str) -> str:
    text = value.lower().strip()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _has_unclear_pronoun(value: str) -> bool:
    tokens = value.split()
    return any(token in UNCLEAR_PRONOUNS for token in tokens) and not any(
        context in value for context in ["ai", "government", "english", "gold", "economy", "internet"]
    )


def _is_incomplete(value: str) -> bool:
    return value in {"why is", "what is", "how to", "who is"} or value.endswith((" why", " what", " how", " is"))


def _is_typo_heavy(value: str) -> bool:
    tokens = value.split()
    suspicious = sum(1 for token in tokens if len(token) > 2 and re.search(r"(.)\1\1|wong$|asdf|qwer", token))
    return suspicious > 0


def _low_explanatory_value(value: str) -> bool:
    low_value_terms = {"spicy", "mad", "bad", "real", "lying"}
    tokens = set(value.split())
    return bool(tokens & low_value_terms) and not any(term in value for term in ["government", "economy", "ai", "english"])


def _specific_person_allegation(value: str) -> bool:
    allegation_terms = {"lying", "fraud", "scam", "cheating"}
    return bool(set(value.split()) & allegation_terms) and _has_unclear_pronoun(value)


def _aligned_with_pillars(value: str) -> bool:
    pillar_terms = {
        "ai",
        "internet",
        "money",
        "business",
        "science",
        "future",
        "global",
        "government",
        "economy",
        "english",
        "gold",
        "delivery",
        "space",
        "technology",
        "trend",
        "system",
        "people",
        "aesthetics",
        "electronics",
        "logistics",
        "lunar",
        "search",
    }
    return bool(set(value.split()) & pillar_terms)


def _should_transform(value: str) -> bool:
    return value.startswith(("why is ", "why are ", "what is ", "how ")) and len(value.split()) <= 7


def _lyric_or_meme_fragment(value: str) -> bool:
    return any(fragment in value for fragment in LYRIC_MEME_FRAGMENTS) or (
        value.startswith("what ") and any(term in value for term in ["love", "song", "lyrics"]) and "trend" not in value
    )


def _clear_viewer_question(value: str) -> bool:
    if value in TRANSFORMABLE_PATTERNS:
        return True
    if value.startswith(("why ", "what ", "how ")):
        return len(value.split()) >= 4 and not _has_unclear_pronoun(value)
    return len(value.split()) >= 4 and _aligned_with_pillars(value)
