from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DailyRun(Base):
    __tablename__ = "daily_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_date: Mapped[str] = mapped_column(String(10), index=True)
    output_dir: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    outputs: Mapped[list["ContentOutput"]] = relationship(back_populates="daily_run")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250), index=True)
    pillar: Mapped[str] = mapped_column(String(120))
    trend_reason: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default="candidate")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class ContentOutput(Base):
    __tablename__ = "content_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_run_id: Mapped[int] = mapped_column(ForeignKey("daily_runs.id"))
    topic_name: Mapped[str] = mapped_column(String(250), index=True)
    quality_gate_status: Mapped[str] = mapped_column(String(30))
    output_path: Mapped[str] = mapped_column(String(500))
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    daily_run: Mapped[DailyRun] = relationship(back_populates="outputs")


class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_run_id: Mapped[int | None] = mapped_column(ForeignKey("daily_runs.id"), nullable=True)
    content_key: Mapped[str] = mapped_column(String(128), default="", index=True)
    format_family: Mapped[str] = mapped_column(String(60), default="shorts_longform")
    topic: Mapped[str] = mapped_column(String(250), index=True)
    raw_phrase: Mapped[str] = mapped_column(Text, default="")
    expanded_topic: Mapped[str] = mapped_column(Text, default="")
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    quality_status: Mapped[str] = mapped_column(String(30), default="accepted", index=True)
    quality_reasons: Mapped[str] = mapped_column(Text, default="[]")
    risk_flags: Mapped[str] = mapped_column(Text, default="[]")
    pillar: Mapped[str] = mapped_column(String(120), index=True)
    trend_reason: Mapped[str] = mapped_column(Text)
    source_names: Mapped[str] = mapped_column(Text, default="[]")
    final_score: Mapped[float] = mapped_column(Float, default=0)
    scoring_explanation: Mapped[str] = mapped_column(Text)
    short_script: Mapped[str] = mapped_column(Text)
    long_outline: Mapped[str] = mapped_column(Text)
    title_options: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[str] = mapped_column(Text)
    thumbnail_ideas: Mapped[str] = mapped_column(Text)
    pinned_comment: Mapped[str] = mapped_column(Text)
    quality_gate_status: Mapped[str] = mapped_column(String(30), index=True)
    quality_gate_reasons: Mapped[str] = mapped_column(Text)
    ai_disclosure_recommendation: Mapped[str] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(String(30), default="generated", index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_item_id: Mapped[int] = mapped_column(ForeignKey("review_items.id"), index=True)
    format_type: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    title: Mapped[str] = mapped_column(Text)
    script: Mapped[str] = mapped_column(Text)
    outline: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[str] = mapped_column(Text)
    thumbnail_text: Mapped[str] = mapped_column(Text)
    thumbnail_ideas: Mapped[str] = mapped_column(Text)
    ai_disclosure_recommendation: Mapped[str] = mapped_column(Text)
    duration_target_seconds: Mapped[int] = mapped_column(Integer)
    aspect_ratio: Mapped[str] = mapped_column(String(20))
    voice_profile: Mapped[str] = mapped_column(String(120), default="curious_signal_clear_narrator")
    visual_style: Mapped[str] = mapped_column(String(160), default="clean documentary explainer")
    scene_plan_json: Mapped[str] = mapped_column(Text)
    render_output_path: Mapped[str] = mapped_column(Text, default="")
    thumbnail_output_path: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    package_path: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
