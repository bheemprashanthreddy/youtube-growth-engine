from app.core.config_loader import load_yaml_config
from app.schemas.content import MergedTrend, OpportunityScore, TopicScore


def score_topic(topic: dict[str, object]) -> TopicScore:
    text = " ".join([str(topic.get("topic", "")), str(topic.get("trend_reason", "")), str(topic.get("pillar", ""))]).lower()
    scores = {
        "search_velocity": _score_keywords(text, ["sudden", "spike", "search", "racing", "changing"], 58),
        "curiosity_gap": _score_keywords(text, ["hidden", "why", "system", "reason"], 65),
        "novelty": _score_keywords(text, ["new", "sudden", "unexpected", "future"], 55),
        "emotional_pull": _score_keywords(text, ["money", "private", "instant", "old", "replacing"], 54),
        "saturation_risk": _score_keywords(text, ["ai", "viral"], 35),
        "monetization_fit": _score_keywords(text, ["business", "money", "technology", "delivery"], 58),
        "format_fit_short": 75,
        "format_fit_long": 72,
        "policy_risk": _score_keywords(text, ["private", "fear", "misleading"], 18),
        "originality_potential": _score_keywords(text, ["hidden", "system", "infrastructure", "logistics"], 64),
    }
    weighted_score = _weighted_score(scores)
    return TopicScore(**scores, weighted_score=round(weighted_score, 2))


def pick_top_opportunities(topics: list[dict[str, object]]) -> list[tuple[dict[str, object], TopicScore]]:
    config = load_yaml_config("scoring.yaml")
    limit = int(config["scoring"]["selected_topic_count"])
    scored = [(topic, score_topic(topic)) for topic in topics]
    scored.sort(key=lambda item: item[1].weighted_score, reverse=True)
    return scored[:limit]


def score_opportunity(trend: MergedTrend) -> OpportunityScore:
    text = " ".join(
        [
            trend.expanded_topic or trend.display_topic,
            trend.cleaned_phrase or "",
            trend.normalized_topic,
            trend.category_guess,
            " ".join(trend.search_terms),
        ]
    ).lower()
    penalties = _quality_penalty(trend)
    scores = {
        "trend_velocity": min(100, int(trend.source_score) + _score_keywords(text, ["sudden", "surge", "spike", "racing", "replacing"], 0)),
        "cross_source_validation": min(100, 35 + (trend.source_count * 18)),
        "curiosity_gap": _score_keywords(text, ["hidden", "why", "strange", "mystery", "behind", "nobody"], 52),
        "novelty": _score_keywords(text, ["new", "future", "unexpected", "first", "sudden"], 48),
        "emotional_pull": _score_keywords(text, ["money", "fear", "private", "mistake", "secret", "race"], 45),
        "search_intent_strength": _score_keywords(text, ["why", "what", "how", "explained", "search"], 52),
        "saturation_risk": _score_keywords(text, ["viral", "celebrity", "drama", "reaction"], 22),
        "monetization_fit": _score_keywords(text, ["business", "money", "technology", "ai", "market", "delivery"], 54),
        "short_format_fit": _score_keywords(text, ["why", "hidden", "sudden", "strange", "mistake"], 62),
        "long_format_fit": _score_keywords(text, ["system", "business", "science", "infrastructure", "economy"], 60),
        "policy_risk": _score_keywords(text, ["war", "death", "crime", "medical", "election", "violence"], 12),
        "originality_potential": _score_keywords(text, ["hidden", "system", "behind", "future", "logistics"], 58),
    }
    if trend.quality_score < 70:
        scores["curiosity_gap"] = max(0, scores["curiosity_gap"] - 35)
        scores["originality_potential"] = max(0, scores["originality_potential"] - 35)
    if "current_event_source_support_needed" in trend.risk_flags:
        scores["policy_risk"] = min(100, scores["policy_risk"] + 25)
    final_score = max(0, _weighted_opportunity_score(scores) + _quality_bonus(trend) - penalties)
    explanation = _score_explanation(trend, scores, final_score)
    return OpportunityScore(**scores, final_score=round(final_score, 2), explanation=explanation)


def score_trends(trends: list[MergedTrend]) -> list[dict[str, object]]:
    scored = []
    for trend in trends:
        score = score_opportunity(trend)
        status = _selection_status(score)
        scored.append({"trend": trend.model_dump(), "score": score.model_dump(), "status": status})
    scored.sort(key=lambda item: item["score"]["final_score"], reverse=True)
    return scored


def pick_top_scored_trends(scored: list[dict[str, object]]) -> list[dict[str, object]]:
    limit = int(load_yaml_config("scoring.yaml")["scoring"]["selected_topic_count"])
    min_final = float(load_yaml_config("scoring.yaml")["scoring"].get("min_final_score", 75))
    return [item for item in scored if item["status"] != "rejected" and item["score"]["final_score"] >= min_final][:limit]


def _score_keywords(text: str, keywords: list[str], base: int) -> int:
    return min(100, base + sum(8 for keyword in keywords if keyword in text))


def _weighted_score(scores: dict[str, int]) -> float:
    weights = load_yaml_config("scoring.yaml")["scoring"]["dimensions"]
    positive_total = sum(max(weight, 0) for weight in weights.values()) * 100
    raw = sum(scores[name] * weight for name, weight in weights.items())
    negative_floor = sum(100 * weight for weight in weights.values() if weight < 0)
    return ((raw - negative_floor) / (positive_total - negative_floor)) * 100


def _weighted_opportunity_score(scores: dict[str, int]) -> float:
    weights = load_yaml_config("scoring.yaml")["scoring"]["dimensions"]
    positive_total = sum(max(weight, 0) for weight in weights.values()) * 100
    raw = sum(scores[name] * weight for name, weight in weights.items())
    negative_floor = sum(100 * weight for weight in weights.values() if weight < 0)
    return ((raw - negative_floor) / (positive_total - negative_floor)) * 100


def _selection_status(score: OpportunityScore) -> str:
    min_final = float(load_yaml_config("scoring.yaml")["scoring"].get("min_final_score", 75))
    if score.policy_risk >= 80 or score.final_score < min_final:
        return "rejected"
    if score.final_score < 74 or score.policy_risk >= 40 or score.saturation_risk >= 65:
        return "needs_review"
    return "selected"


def _score_explanation(trend: MergedTrend, scores: dict[str, int], final_score: float) -> str:
    source_text = ", ".join(trend.source_names)
    strengths = []
    if trend.source_count > 1:
        strengths.append(f"validated by {trend.source_count} sources")
    if scores["curiosity_gap"] >= 60:
        strengths.append("has a clear curiosity gap")
    if scores["originality_potential"] >= 65:
        strengths.append("can become an original hidden-system explainer")
    if scores["policy_risk"] >= 40:
        strengths.append("needs careful policy review")
    if not strengths:
        strengths.append("has enough baseline signal for review")
    if trend.quality_score < 70:
        strengths.append(f"quality score {trend.quality_score} is below threshold")
    if trend.risk_flags:
        strengths.append("risk flags: " + ", ".join(trend.risk_flags))
    return f"{trend.display_topic} scored {final_score:.1f}/100 from {source_text}; " + "; ".join(strengths) + "."


def _quality_penalty(trend: MergedTrend) -> int:
    config = load_yaml_config("scoring.yaml")["scoring"]
    penalties = config.get("penalties", {})
    reason_map = {
        "known_vague_autocomplete_fragment": "vague_phrase",
        "unclear_subject": "unclear_subject",
        "incomplete_phrase": "incomplete_phrase",
        "low_explanatory_value": "low_explanatory_value",
        "unsupported_current_event_claim": "unsupported_current_event_claim",
    }
    total = 0
    for reason in trend.quality_reasons:
        key = reason_map.get(reason)
        if key:
            total += int(penalties.get(key, 0))
    if trend.quality_score < 70:
        total += int((70 - trend.quality_score) * 0.6)
    if "unsafe_sensitive_content" in trend.risk_flags:
        total += int(penalties.get("high_policy_risk", 45))
    return min(80, total)


def _quality_bonus(trend: MergedTrend) -> float:
    if trend.quality_score < 70:
        return 0
    bonus = min(12, (trend.quality_score - 70) * 0.4)
    expanded = trend.expanded_topic or trend.display_topic
    if len(expanded.split()) >= 5:
        bonus += 8
    if trend.quality_status == "transformed":
        bonus += 4
    return min(24, bonus)
