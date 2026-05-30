import json
from collections import Counter
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.content import ReviewItem, VideoJob
from app.services.outputs import output_dir_for
from app.services.review import serialize_review_item
from app.services.scene_planner import create_long_scene_plan, create_short_scene_plan

JOB_READY_STATUSES = {"approved", "ready_for_render"}
VALID_JOB_STATUSES = {"queued", "preparing", "ready_for_render", "rendering", "rendered", "failed"}


def create_short_job(db: Session, review_item_id: int) -> VideoJob:
    return create_video_job(db, review_item_id, "short")


def create_long_job(db: Session, review_item_id: int) -> VideoJob:
    return create_video_job(db, review_item_id, "long")


def create_both_jobs(db: Session, review_item_id: int) -> list[VideoJob]:
    return [create_short_job(db, review_item_id), create_long_job(db, review_item_id)]


def create_video_job(db: Session, review_item_id: int, format_type: str) -> VideoJob:
    if format_type not in {"short", "long"}:
        raise ValueError("format_type must be short or long.")
    review_item = db.get(ReviewItem, review_item_id)
    if review_item is None:
        raise ValueError("Review item not found.")
    if review_item.approval_status not in JOB_READY_STATUSES:
        raise ValueError("Review item must be approved or ready_for_render before creating a video job.")
    existing = db.execute(
        select(VideoJob).where(VideoJob.review_item_id == review_item_id, VideoJob.format_type == format_type)
    ).scalar_one_or_none()
    if existing:
        return existing

    item = serialize_review_item(review_item)
    scene_plan = _scene_plan(review_item, format_type)
    title_options = item["title_options"] or [item["topic"]]
    thumbnail_ideas = item["thumbnail_ideas"] or ["WHY NOW?"]
    job = VideoJob(
        review_item_id=review_item.id,
        format_type=format_type,
        status="ready_for_render",
        title=title_options[0],
        script=item["short_script"] if format_type == "short" else "",
        outline=json.dumps(item["long_outline"] if format_type == "long" else []),
        description=item["description"],
        hashtags=json.dumps(item["hashtags"]),
        thumbnail_text=thumbnail_ideas[0],
        thumbnail_ideas=json.dumps(thumbnail_ideas),
        ai_disclosure_recommendation=item["ai_disclosure_recommendation"],
        duration_target_seconds=scene_plan["target_duration_seconds"],
        aspect_ratio=scene_plan["aspect_ratio"],
        voice_profile="curious_signal_clear_narrator",
        visual_style="clean documentary explainer",
        scene_plan_json=json.dumps(scene_plan),
    )
    db.add(job)
    db.flush()
    job.package_path = str(save_video_job_package(job, review_item))
    db.add(job)
    db.commit()
    db.refresh(job)
    save_video_job_package(job, review_item)
    return job


def regenerate_scene_plan(db: Session, job_id: int) -> VideoJob:
    job = require_video_job(db, job_id)
    review_item = db.get(ReviewItem, job.review_item_id)
    if review_item is None:
        raise ValueError("Source review item not found.")
    scene_plan = _scene_plan(review_item, job.format_type)
    job.scene_plan_json = json.dumps(scene_plan)
    job.duration_target_seconds = scene_plan["target_duration_seconds"]
    job.aspect_ratio = scene_plan["aspect_ratio"]
    job.status = "ready_for_render"
    db.add(job)
    db.commit()
    db.refresh(job)
    save_video_job_package(job, review_item)
    return job


def mark_job_ready_for_render(db: Session, job_id: int) -> VideoJob:
    job = require_video_job(db, job_id)
    job.status = "ready_for_render"
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def list_video_jobs(db: Session) -> list[VideoJob]:
    return list(db.execute(select(VideoJob).order_by(VideoJob.created_at.desc())).scalars().all())


def require_video_job(db: Session, job_id: int) -> VideoJob:
    job = db.get(VideoJob, job_id)
    if job is None:
        raise ValueError("Video job not found.")
    return job


def serialize_video_job(job: VideoJob) -> dict[str, object]:
    return {
        "id": job.id,
        "review_item_id": job.review_item_id,
        "format_type": job.format_type,
        "status": job.status,
        "title": job.title,
        "script": job.script,
        "outline": _loads(job.outline, []),
        "description": job.description,
        "hashtags": _loads(job.hashtags, []),
        "thumbnail_text": job.thumbnail_text,
        "thumbnail_ideas": _loads(job.thumbnail_ideas, []),
        "ai_disclosure_recommendation": job.ai_disclosure_recommendation,
        "duration_target_seconds": job.duration_target_seconds,
        "aspect_ratio": job.aspect_ratio,
        "voice_profile": job.voice_profile,
        "visual_style": job.visual_style,
        "scene_plan": _loads(job.scene_plan_json, {}),
        "render_output_path": job.render_output_path,
        "thumbnail_output_path": job.thumbnail_output_path,
        "error_message": job.error_message,
        "package_path": job.package_path,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def save_video_job_package(job: VideoJob, review_item: ReviewItem) -> Path:
    output_dir = output_dir_for(date.today()) / "video_jobs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{job.id}.json"
    payload = {
        "phase": "phase_1_7_production_queue_scene_plan",
        "job": serialize_video_job(job),
        "source_review_item": serialize_review_item(review_item),
        "renderer_note": "Phase 2 renderer consumes this package. No rendering or upload has occurred.",
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def jobs_summary(db: Session) -> dict[str, object]:
    jobs = list_video_jobs(db)
    counts = Counter(job.status for job in jobs)
    formats = Counter(job.format_type for job in jobs)
    duplicate_count = _duplicate_job_count(jobs)
    top_ready = [
        {"id": job.id, "review_item_id": job.review_item_id, "format_type": job.format_type, "title": job.title}
        for job in jobs
        if job.status == "ready_for_render"
    ][:5]
    return {
        "total_jobs": len(jobs),
        "short_jobs": formats["short"],
        "long_jobs": formats["long"],
        "ready_for_render": counts["ready_for_render"],
        "rendered": counts["rendered"],
        "failed": counts["failed"],
        "duplicate_job_count": duplicate_count,
        "top_ready_jobs": top_ready,
    }


def create_jobs_for_approved(db: Session, format_type: str | None = None) -> list[VideoJob]:
    if format_type not in {None, "short", "long"}:
        raise ValueError("format must be short, long, or omitted.")
    review_items = db.execute(select(ReviewItem).where(ReviewItem.approval_status.in_(JOB_READY_STATUSES))).scalars().all()
    jobs: list[VideoJob] = []
    for item in review_items:
        if format_type == "short":
            jobs.append(create_short_job(db, item.id))
        elif format_type == "long":
            jobs.append(create_long_job(db, item.id))
        else:
            jobs.extend(create_both_jobs(db, item.id))
    return jobs


def _scene_plan(review_item: ReviewItem, format_type: str) -> dict[str, object]:
    if format_type == "short":
        return create_short_scene_plan(review_item)
    return create_long_scene_plan(review_item)


def _loads(value: str, fallback: object) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _duplicate_job_count(jobs: list[VideoJob]) -> int:
    seen: set[tuple[int, str]] = set()
    duplicates = 0
    for job in jobs:
        key = (job.review_item_id, job.format_type)
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates
