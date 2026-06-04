import json
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.content import VideoJob, YouTubeUpload
from app.services.youtube.auth import youtube_auth_status
from app.services.youtube.metadata import build_youtube_metadata
from app.services.youtube.quota import enforce_quota, quota_status
from app.services.youtube.upload_checks import run_upload_checks
from app.services.youtube.upload_review import build_upload_checklist
from app.services.youtube.uploader import FakeYouTubeUploader, YouTubeUploader


def youtube_status(db: Session | None = None) -> dict[str, object]:
    settings = get_settings()
    auth = youtube_auth_status()
    quota = quota_status(db) if db is not None else {"daily_limit": settings.youtube_daily_upload_limit}
    return {
        "upload_enabled": settings.youtube_upload_enabled,
        "client_secret_file_exists": auth["client_secret_exists"],
        "token_file_exists": auth["token_exists"],
        "authenticated": auth["authenticated"],
        "privacy_status": settings.youtube_privacy_status,
        "daily_upload_limit": settings.youtube_daily_upload_limit,
        "quota": quota,
        "private_required": settings.youtube_require_private,
    }


def upload_video(db: Session, job_id: int, uploader=None, *, bypass_review: bool = False) -> dict[str, object]:
    job = db.get(VideoJob, job_id)
    if job is None:
        raise ValueError("Video job not found.")
    checks = run_upload_checks(db, job, bypass_review=bypass_review)
    if not checks["passed"]:
        upload = _record_upload(db, job, "failed", "", "", False, {}, "; ".join(checks["blockers"]))
        return _write_upload_report(job, upload, checks, {}, errors=checks["blockers"])
    quota_ok, quota_error = enforce_quota(db)
    if not quota_ok:
        upload = _record_upload(db, job, "failed", "", "", False, {}, quota_error)
        return _write_upload_report(job, upload, checks, {}, errors=[quota_error])
    metadata = build_youtube_metadata(job)
    active_uploader = uploader or YouTubeUploader()
    upload = _record_upload(db, job, "uploading", "", "", False, metadata, "")
    try:
        result = active_uploader.upload_private(job, metadata, str(checks["thumbnail_path"]))
        upload = _record_upload(
            db,
            job,
            "uploaded_private",
            str(result["youtube_video_id"]),
            str(result["youtube_upload_url"]),
            bool(result.get("thumbnail_uploaded")),
            metadata,
            "",
        )
        report = _write_upload_report(job, upload, checks, metadata, errors=[])
        upload.youtube_upload_report_path = str(report["report_path"])
        db.add(upload)
        db.commit()
        return report
    except Exception as exc:
        upload = _record_upload(db, job, "failed", "", "", False, metadata, str(exc))
        return _write_upload_report(job, upload, checks, metadata, errors=[str(exc)])


def upload_ready(db: Session, limit: int = 1, uploader=None, *, bypass_review: bool = False) -> dict[str, object]:
    jobs = db.execute(select(VideoJob).where(VideoJob.status == "rendered").order_by(VideoJob.created_at).limit(limit)).scalars().all()
    results = []
    for job in jobs:
        results.append(upload_video(db, job.id, uploader=uploader, bypass_review=bypass_review))
    return {"processed": len(results), "results": results}


def list_uploads(db: Session) -> list[YouTubeUpload]:
    return list(db.execute(select(YouTubeUpload).order_by(YouTubeUpload.created_at.desc())).scalars().all())


def _record_upload(
    db: Session,
    job: VideoJob,
    status: str,
    video_id: str,
    url: str,
    thumbnail_uploaded: bool,
    metadata: dict[str, object],
    error: str,
) -> YouTubeUpload:
    upload = db.execute(select(YouTubeUpload).where(YouTubeUpload.job_id == job.id)).scalar_one_or_none()
    if upload is None:
        upload = YouTubeUpload(job_id=job.id)
    upload.youtube_upload_status = status
    upload.youtube_privacy_status = "private"
    upload.youtube_video_id = video_id
    upload.youtube_upload_url = url
    upload.youtube_thumbnail_uploaded = thumbnail_uploaded
    upload.youtube_metadata_json = json.dumps(metadata)
    upload.youtube_upload_error = error
    upload.youtube_uploaded_at = datetime.now(UTC) if status == "uploaded_private" else None
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload


def _write_upload_report(job: VideoJob, upload: YouTubeUpload, checks: dict[str, object], metadata: dict[str, object], errors: list[str]) -> dict[str, object]:
    output_dir = Path("outputs") / date.today().isoformat() / "uploads"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{job.id}.json"
    payload = {
        "job_id": job.id,
        "video_path": job.render_output_path,
        "thumbnail_path": checks.get("thumbnail_path", ""),
        "title": job.title,
        "description": job.description,
        "tags": metadata.get("snippet", {}).get("tags", []) if metadata else [],
        "privacy_status": "private",
        "youtube_video_id": upload.youtube_video_id,
        "upload_status": upload.youtube_upload_status,
        "uploaded_at": upload.youtube_uploaded_at.isoformat() if upload.youtube_uploaded_at else "",
        "errors": errors,
        "warnings": checks.get("warnings", []),
        "upload_checklist": build_upload_checklist(None, job),
        "quota_estimate": {"upload_cost_units": 1600},
        "report_path": str(path),
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload
