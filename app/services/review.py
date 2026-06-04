import json
import re
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agents.planner import ContentPlanner
from app.models.content import ReviewItem
from app.providers.factory import get_llm_provider
from app.schemas.content import ContentPlan

VALID_STATUSES = {"generated", "needs_review", "approved", "rejected", "ready_for_render"}
RENDERABLE_STATUS = "ready_for_render"
FORMAT_FAMILY = "shorts_longform"


def create_review_item(
    db: Session,
    plan: ContentPlan,
    daily_run_id: int | None,
    source_names: list[str],
    quality_metadata: dict[str, object] | None = None,
) -> ReviewItem:
    quality_metadata = quality_metadata or {}
    content_key = build_content_key(str(quality_metadata.get("expanded_topic") or plan.topic), plan.pillar)
    for pending in db.new:
        if isinstance(pending, ReviewItem) and pending.content_key == content_key:
            return pending
    existing = db.execute(select(ReviewItem).where(ReviewItem.content_key == content_key)).scalar_one_or_none()
    payload = {
        "daily_run_id": daily_run_id,
        "topic": plan.topic,
        "raw_phrase": str(quality_metadata.get("raw_phrase") or plan.topic),
        "expanded_topic": str(quality_metadata.get("expanded_topic") or plan.topic),
        "quality_score": float(quality_metadata.get("quality_score") or 0),
        "quality_status": str(quality_metadata.get("quality_status") or "accepted"),
        "quality_reasons": json.dumps(quality_metadata.get("quality_reasons") or []),
        "risk_flags": json.dumps(quality_metadata.get("risk_flags") or []),
        "pillar": plan.pillar,
        "trend_reason": plan.trend_reason,
        "source_names": json.dumps(source_names),
        "final_score": plan.score.final_score,
        "scoring_explanation": plan.score.explanation,
        "short_script": plan.shorts_script,
        "long_outline": json.dumps(plan.long_form_outline),
        "title_options": json.dumps(plan.title_options),
        "description": plan.description,
        "hashtags": json.dumps(plan.hashtags),
        "thumbnail_ideas": json.dumps(plan.thumbnail_text_ideas),
        "pinned_comment": plan.pinned_comment_idea,
        "quality_gate_status": _source_supported_quality_gate(plan.quality_gate.final_status, source_names, quality_metadata),
        "quality_gate_reasons": json.dumps(_quality_gate_reasons(plan.quality_gate.notes, source_names, quality_metadata)),
        "ai_disclosure_recommendation": plan.ai_disclosure_recommendation,
    }
    if existing:
        _update_existing_review_item(existing, payload)
        db.add(existing)
        return existing

    item = ReviewItem(
        content_key=content_key,
        format_family=FORMAT_FAMILY,
        **payload,
        approval_status=_initial_status(plan.quality_gate.final_status),
    )
    db.add(item)
    return item


def list_review_items(db: Session, status: str | None = None) -> list[ReviewItem]:
    stmt = select(ReviewItem).order_by(ReviewItem.final_score.desc(), ReviewItem.created_at.desc())
    if status:
        stmt = stmt.where(ReviewItem.approval_status == status)
    return list(db.execute(stmt).scalars().all())


def get_review_item(db: Session, item_id: int) -> ReviewItem | None:
    return db.get(ReviewItem, item_id)


def set_approval_status(db: Session, item: ReviewItem, status: str) -> ReviewItem:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid approval status: {status}")
    if status == RENDERABLE_STATUS and item.approval_status != "approved" and item.approved_at is None:
        raise ValueError("Only approved review items can be marked ready_for_render.")
    item.approval_status = status
    if status == "approved":
        item.approved_at = datetime.now(UTC)
    item.updated_at = datetime.now(UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_notes(db: Session, item: ReviewItem, notes: str) -> ReviewItem:
    item.reviewer_notes = notes
    item.updated_at = datetime.now(UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def regenerate_script(db: Session, item: ReviewItem) -> ReviewItem:
    planner = ContentPlanner(get_llm_provider())
    item.short_script = planner._shorts_script(item.topic, f"why {item.topic.lower()} matters now", item.trend_reason)
    item.updated_at = datetime.now(UTC)
    item.approval_status = "needs_review"
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def regenerate_metadata(db: Session, item: ReviewItem) -> ReviewItem:
    topic = item.topic
    item.title_options = json.dumps(
        [
            topic if topic.lower().startswith(("why ", "how ", "what ")) else f"Why {topic} Is Changing Faster Than People Realize",
            f"The Hidden Signal Behind {topic}",
            f"What People Miss About {topic}",
            f"{topic}: The Shift Underneath",
            f"The System Behind {topic}",
        ]
    )
    item.description = (
        f"CuriousSignal investigates {topic}, why it is gaining attention, "
        "and what should be verified before accepting the trend at face value."
    )
    item.hashtags = json.dumps(["#CuriousSignal", "#Trends", "#Explained", "#InternetCulture"])
    item.thumbnail_ideas = json.dumps(["WHAT CHANGED?", "THE HIDDEN SHIFT", "FOLLOW THE SIGNAL"])
    item.updated_at = datetime.now(UTC)
    item.approval_status = "needs_review"
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def review_summary(db: Session) -> dict[str, object]:
    from app.models.content import VideoJob

    rows = db.execute(select(ReviewItem)).scalars().all()
    job_review_ids = {row[0] for row in db.execute(select(VideoJob.review_item_id)).all()}
    counts = Counter(row.approval_status for row in rows)
    duplicates = duplicate_groups(rows)
    invalid_lifecycle = invalid_lifecycle_items(rows)
    top = sorted(rows, key=lambda row: row.final_score, reverse=True)[:5]
    return {
        "total_generated": len({row.content_key or build_content_key(row.expanded_topic or row.topic, row.pillar) for row in rows}),
        "duplicates_detected": sum(len(group) - 1 for group in duplicates),
        "invalid_lifecycle_count": len(invalid_lifecycle),
        "approved": counts["approved"] + sum(1 for row in rows if row.approval_status == RENDERABLE_STATUS and row.approved_at is not None),
        "rejected": counts["rejected"],
        "ready_for_render": counts["ready_for_render"],
        "approved_without_jobs": sum(1 for row in rows if row.approval_status in {"approved", "ready_for_render"} and row.id not in job_review_ids),
        "top_5": [{"id": row.id, "topic": row.topic, "score": row.final_score, "status": row.approval_status} for row in top],
    }


def serialize_review_item(item: ReviewItem) -> dict[str, object]:
    return {
        "id": item.id,
        "content_key": item.content_key,
        "duplicate_status": "duplicate_candidate" if _is_duplicate_candidate(item) else "unique",
        "lifecycle_warning": _lifecycle_warning(item),
        "source_support_warning": _source_support_warning(item),
        "topic": item.topic,
        "raw_phrase": item.raw_phrase,
        "expanded_topic": item.expanded_topic,
        "quality_score": item.quality_score,
        "quality_status": item.quality_status,
        "quality_reasons": _loads(item.quality_reasons, []),
        "risk_flags": _loads(item.risk_flags, []),
        "pillar": item.pillar,
        "trend_reason": item.trend_reason,
        "source_names": _loads(item.source_names, []),
        "final_score": item.final_score,
        "scoring_explanation": item.scoring_explanation,
        "short_script": item.short_script,
        "long_outline": _loads(item.long_outline, []),
        "title_options": _loads(item.title_options, []),
        "description": item.description,
        "hashtags": _loads(item.hashtags, []),
        "thumbnail_ideas": _loads(item.thumbnail_ideas, []),
        "pinned_comment": item.pinned_comment,
        "quality_gate_status": item.quality_gate_status,
        "quality_gate_reasons": _loads(item.quality_gate_reasons, []),
        "ai_disclosure_recommendation": item.ai_disclosure_recommendation,
        "approval_status": item.approval_status,
        "approved_at": item.approved_at.isoformat() if item.approved_at else None,
        "reviewer_notes": item.reviewer_notes,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _initial_status(quality_gate_status: str) -> str:
    return "needs_review"


def _loads(value: str, fallback: object) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def build_content_key(expanded_topic: str, pillar: str, format_family: str = FORMAT_FAMILY) -> str:
    base = f"{expanded_topic} {pillar} {format_family}".lower()
    base = re.sub(r"[^a-z0-9\s]", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base


def reset_invalid_ready_for_render(db: Session) -> int:
    rows = db.execute(select(ReviewItem).where(ReviewItem.approval_status == RENDERABLE_STATUS)).scalars().all()
    corrected = 0
    for row in rows:
        if row.approved_at is None:
            row.approval_status = "needs_review"
            row.updated_at = datetime.now(UTC)
            db.add(row)
            corrected += 1
    db.commit()
    return corrected


def clear_dev_data(db: Session) -> dict[str, int]:
    from app.models.content import ContentOutput, DailyRun, Topic, VideoJob, YouTubeUpload

    counts = {
        "youtube_uploads": len(db.execute(select(YouTubeUpload)).scalars().all()),
        "video_jobs": len(db.execute(select(VideoJob)).scalars().all()),
        "review_items": len(db.execute(select(ReviewItem)).scalars().all()),
        "content_outputs": len(db.execute(select(ContentOutput)).scalars().all()),
        "topics": len(db.execute(select(Topic)).scalars().all()),
        "daily_runs": len(db.execute(select(DailyRun)).scalars().all()),
    }
    db.execute(delete(YouTubeUpload))
    db.execute(delete(VideoJob))
    db.execute(delete(ReviewItem))
    db.execute(delete(ContentOutput))
    db.execute(delete(Topic))
    db.execute(delete(DailyRun))
    db.commit()
    return counts


def dedupe_review_items(db: Session) -> dict[str, object]:
    rows = db.execute(select(ReviewItem)).scalars().all()
    groups = duplicate_groups(rows)
    removed = 0
    details = []
    for group in groups:
        keep = max(group, key=lambda row: (row.final_score, _status_rank(row.approval_status), row.updated_at or row.created_at))
        details.append({"key": keep.content_key or keep.expanded_topic, "kept_id": keep.id, "removed_ids": [row.id for row in group if row.id != keep.id]})
        for row in group:
            if row.id != keep.id:
                db.delete(row)
                removed += 1
    db.commit()
    return {"groups": len(groups), "removed": removed, "details": details}


def duplicate_groups(rows: list[ReviewItem]) -> list[list[ReviewItem]]:
    buckets: dict[str, list[ReviewItem]] = {}
    for row in rows:
        key = row.content_key or build_content_key(row.expanded_topic or row.topic, row.pillar)
        alt = _normalized_topic(row.expanded_topic or row.topic)
        buckets.setdefault(key, []).append(row)
        if alt != key:
            buckets.setdefault(f"topic:{alt}", []).append(row)
    seen_group_keys: set[tuple[int, ...]] = set()
    groups = []
    for group in buckets.values():
        unique = list({row.id: row for row in group}.values())
        if len(unique) < 2:
            continue
        ids = tuple(sorted(row.id for row in unique))
        if ids in seen_group_keys:
            continue
        seen_group_keys.add(ids)
        groups.append(unique)
    return groups


def invalid_lifecycle_items(rows: list[ReviewItem]) -> list[ReviewItem]:
    return [row for row in rows if row.approval_status == RENDERABLE_STATUS and row.approved_at is None]


def _update_existing_review_item(item: ReviewItem, payload: dict[str, object]) -> None:
    if float(payload["final_score"]) >= item.final_score:
        for key, value in payload.items():
            if key == "approval_status":
                continue
            setattr(item, key, value)
        item.updated_at = datetime.now(UTC)


def _source_supported_quality_gate(status: str, source_names: list[str], quality_metadata: dict[str, object]) -> str:
    if _needs_source_support(quality_metadata) and not _has_real_source(source_names):
        return "needs_review"
    return status


def _quality_gate_reasons(notes: list[str], source_names: list[str], quality_metadata: dict[str, object]) -> list[str]:
    reasons = list(notes)
    if _needs_source_support(quality_metadata) and not _has_real_source(source_names):
        reasons.append("Source support required: current/political/breaking-news risk uses manual_seed only.")
    return reasons


def _needs_source_support(quality_metadata: dict[str, object]) -> bool:
    flags = set(quality_metadata.get("risk_flags") or [])
    return bool(flags & {"current_event_source_support_needed", "political_context", "breaking_news_context"})


def _has_real_source(source_names: list[str]) -> bool:
    return any(source != "manual_seed" for source in source_names)


def _source_support_warning(item: ReviewItem) -> str:
    flags = set(_loads(item.risk_flags, []))
    sources = set(_loads(item.source_names, []))
    if flags & {"current_event_source_support_needed", "political_context", "breaking_news_context"} and sources <= {"manual_seed"}:
        return "Needs non-manual source support before approval."
    return ""


def _lifecycle_warning(item: ReviewItem) -> str:
    if item.approval_status == RENDERABLE_STATUS and item.approved_at is None:
        return "Invalid lifecycle: ready_for_render without approval history."
    return ""


def _is_duplicate_candidate(item: ReviewItem) -> bool:
    return not bool(item.content_key)


def _normalized_topic(value: str) -> str:
    text = value.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _status_rank(status: str) -> int:
    return {"ready_for_render": 4, "approved": 3, "needs_review": 2, "generated": 1, "rejected": 0}.get(status, 0)
