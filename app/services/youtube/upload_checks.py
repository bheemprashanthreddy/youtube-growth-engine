from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.content import VideoJob, YouTubeUpload
from app.services.youtube.auth import youtube_auth_status
from app.services.youtube.upload_review import load_render_report, selected_thumbnail_path


def run_upload_checks(db: Session, job: VideoJob, *, bypass_review: bool = False) -> dict[str, object]:
    settings = get_settings()
    blockers: list[str] = []
    warnings: list[str] = []
    if not settings.youtube_upload_enabled:
        blockers.append("YouTube upload disabled.")
    if settings.youtube_require_private and settings.youtube_privacy_status != "private":
        blockers.append("Privacy status must be private.")
    if job.status != "rendered":
        blockers.append("Job must be rendered before upload.")
    if not job.render_output_path or not Path(job.render_output_path).exists():
        blockers.append("Rendered video file missing.")
    if not job.title.strip():
        blockers.append("Title missing.")
    if not job.description.strip():
        blockers.append("Description missing.")
    thumbnail = selected_thumbnail_path(job)
    if not thumbnail or not Path(thumbnail).exists():
        blockers.append("Thumbnail missing.")
    if not bypass_review and not job.upload_review_approved:
        blockers.append("Final upload review is not approved.")
    if not bypass_review and not job.metadata_reviewed:
        blockers.append("Upload metadata has not been reviewed.")
    if not bypass_review and not job.source_license_reviewed:
        blockers.append("Source/license review is not complete.")
    if not bypass_review and not job.voice_audio_reviewed:
        blockers.append("Voice/audio review is not complete.")
    existing = db.execute(
        select(YouTubeUpload).where(YouTubeUpload.job_id == job.id, YouTubeUpload.youtube_upload_status == "uploaded_private")
    ).scalar_one_or_none()
    if existing:
        blockers.append("Job is already uploaded.")
    if job.render_output_path and Path(job.render_output_path).exists() and Path(job.render_output_path).stat().st_size < 1024:
        blockers.append("Rendered video file is too small.")
    report = load_render_report(job)
    if report.get("fallback_used"):
        warnings.append("Generated/fallback visuals were used.")
    voice = report.get("voice") or {}
    if isinstance(voice, dict) and voice.get("fallback_used"):
        warnings.append("Silent voice fallback was used.")
    if report.get("ai_visuals_used"):
        warnings.append("AI disclosure review required for generated visual assets.")
        if not bypass_review and not job.ai_disclosure_reviewed:
            blockers.append("AI disclosure review is not complete.")
    if "rejected" in str(job.description).lower():
        blockers.append("Quality gate rejected content cannot be uploaded.")
    if settings.youtube_upload_enabled and not youtube_auth_status()["authenticated"]:
        blockers.append("YouTube authentication is missing.")
    return {"passed": not blockers, "blockers": blockers, "warnings": warnings, "thumbnail_path": thumbnail}
