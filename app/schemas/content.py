from typing import Any

from pydantic import BaseModel, Field


class TrendItem(BaseModel):
    source: str
    raw_title: str
    normalized_topic: str
    raw_phrase: str | None = None
    cleaned_phrase: str | None = None
    expanded_topic: str | None = None
    viewer_question: str | None = None
    quality_score: int = Field(default=0, ge=0, le=100)
    quality_status: str = "accepted"
    quality_reasons: list[str] = Field(default_factory=list)
    content_pillar: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    curiosity_angle: str | None = None
    short_format_angle: str | None = None
    long_format_angle: str | None = None
    url: str | None = None
    published_at: str | None = None
    source_score: int = Field(ge=0, le=100)
    search_terms: list[str] = Field(default_factory=list)
    category_guess: str = "general"
    language: str = "en"
    region: str = "US"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MergedTrend(BaseModel):
    normalized_topic: str
    display_topic: str
    raw_phrase: str | None = None
    cleaned_phrase: str | None = None
    expanded_topic: str | None = None
    viewer_question: str | None = None
    quality_score: int = Field(default=0, ge=0, le=100)
    quality_status: str = "accepted"
    quality_reasons: list[str] = Field(default_factory=list)
    content_pillar: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    curiosity_angle: str | None = None
    short_format_angle: str | None = None
    long_format_angle: str | None = None
    source_count: int
    source_names: list[str]
    source_score: float
    search_terms: list[str]
    category_guess: str
    language: str = "en"
    region: str = "US"
    url: str | None = None
    published_at: str | None = None
    raw_titles: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopicScore(BaseModel):
    search_velocity: int = Field(ge=0, le=100)
    curiosity_gap: int = Field(ge=0, le=100)
    novelty: int = Field(ge=0, le=100)
    emotional_pull: int = Field(ge=0, le=100)
    saturation_risk: int = Field(ge=0, le=100)
    monetization_fit: int = Field(ge=0, le=100)
    format_fit_short: int = Field(ge=0, le=100)
    format_fit_long: int = Field(ge=0, le=100)
    policy_risk: int = Field(ge=0, le=100)
    originality_potential: int = Field(ge=0, le=100)
    weighted_score: float


class OpportunityScore(BaseModel):
    trend_velocity: int = Field(ge=0, le=100)
    cross_source_validation: int = Field(ge=0, le=100)
    curiosity_gap: int = Field(ge=0, le=100)
    novelty: int = Field(ge=0, le=100)
    emotional_pull: int = Field(ge=0, le=100)
    search_intent_strength: int = Field(ge=0, le=100)
    saturation_risk: int = Field(ge=0, le=100)
    monetization_fit: int = Field(ge=0, le=100)
    short_format_fit: int = Field(ge=0, le=100)
    long_format_fit: int = Field(ge=0, le=100)
    policy_risk: int = Field(ge=0, le=100)
    originality_potential: int = Field(ge=0, le=100)
    final_score: float
    explanation: str


class QualityGateResult(BaseModel):
    repetitive_content_risk: str
    low_effort_ai_content_risk: str
    unsupported_claim_risk: str
    misleading_title_risk: str
    copyright_reused_content_risk: str
    sensitive_topic_risk: str
    monetization_risk: str
    ai_disclosure_needed: bool
    final_status: str
    notes: list[str]


class ContentPlan(BaseModel):
    topic: str
    pillar: str
    trend_reason: str
    viewer_curiosity_trigger: str
    target_viewer: str
    short_video_angle: str
    long_video_angle: str
    research_brief: str
    hook_options: list[str]
    shorts_script: str
    long_form_outline: list[str]
    title_options: list[str]
    description: str
    hashtags: list[str]
    thumbnail_text_ideas: list[str]
    pinned_comment_idea: str
    ai_disclosure_recommendation: str
    score: OpportunityScore
    quality_gate: QualityGateResult


class DailyRunResult(BaseModel):
    run_date: str
    output_dir: str
    selected_count: int
    outputs: list[str]
    status: str = "completed"
