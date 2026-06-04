import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.content import VideoJob
from app.services.youtube.auth import youtube_auth_status
from app.services.youtube.metadata import build_youtube_metadata


def build_upload_checklist(db: Session, job: VideoJob) -> dict[str, object]:
    settings = get_settings()
    report = load_render_report(job)
    thumbnail_path = selected_thumbnail_path(job)
    metadata = build_youtube_metadata(job)
    video_path = Path(job.render_output_path) if job.render_output_path else None
    thumb_path = Path(thumbnail_path) if thumbnail_path else None
    auth = youtube_auth_status()
    ai_visuals_used = bool(report.get("ai_visuals_used"))
    ai_disclosure_needed = ai_visuals_used or bool(job.ai_disclosure_recommendation.strip())
    voice = report.get("voice") if isinstance(report.get("voice"), dict) else {}
    assets = report.get("assets_used") if isinstance(report.get("assets_used"), list) else []
    report_warnings = [str(warning) for warning in report.get("warnings", [])] if isinstance(report.get("warnings"), list) else []
    source_warning_terms = ("source_support", "copyright", "license", "policy", "blocked")
    source_warnings = [warning for warning in report_warnings if any(term in warning.lower() for term in source_warning_terms)]

    checks = [
        _check("rendered_video_exists", "Rendered video exists", bool(video_path and video_path.exists() and video_path.stat().st_size > 1024)),
        _check("thumbnail_selected", "Thumbnail selected", bool(thumb_path and thumb_path.exists())),
        _check("title_exists", "Title exists", bool(job.title.strip())),
        _check("description_exists", "Description exists", bool(job.description.strip())),
        _check("metadata_reviewed", "Title and description reviewed", bool(job.metadata_reviewed)),
        _check("voice_metadata_exists", "Voice metadata exists", bool(voice)),
        _check("voice_audio_reviewed", "Voice/audio reviewed", bool(job.voice_audio_reviewed)),
        _check("visual_license_metadata_exists", "Visual asset/license metadata exists", _assets_have_license_metadata(assets, report)),
        _check("source_license_reviewed", "Source/license warnings reviewed", bool(job.source_license_reviewed)),
        _check("ai_disclosure_reviewed", "AI disclosure reviewed", bool(job.ai_disclosure_reviewed) or not ai_disclosure_needed),
        _check("rendered_video_inspected", "Rendered video inspection passed", bool(report.get("width") and report.get("height") and report.get("has_audio") is not False)),
        _check("privacy_private", "Privacy is private", settings.youtube_privacy_status == "private"),
        _check("source_warnings_resolved", "Source warnings resolved", bool(job.source_license_reviewed) or not source_warnings),
        _check("upload_enabled", "YouTube upload enabled", bool(settings.youtube_upload_enabled)),
        _check("authenticated", "YouTube authenticated", bool(auth["authenticated"])),
        _check("final_upload_review_approved", "Final upload review approved", bool(job.upload_review_approved)),
    ]
    blockers = [str(item["label"]) for item in checks if item["required"] and not item["passed"]]
    warnings = []
    if report.get("fallback_used"):
        warnings.append("Generated/fallback visuals were used.")
    if isinstance(voice, dict) and voice.get("fallback_used"):
        warnings.append("Silent voice fallback was used.")
    if ai_visuals_used:
        warnings.append("AI disclosure review required for generated visual assets.")
    warnings.extend(source_warnings)
    return {
        "job_id": job.id,
        "passed": not blockers,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "thumbnail_path": thumbnail_path,
        "selected_thumbnail_path": job.selected_thumbnail_path,
        "metadata_preview": metadata,
        "voice_metadata": voice,
        "assets_used": assets,
        "ai_disclosure_needed": ai_disclosure_needed,
        "ai_visuals_used": ai_visuals_used,
        "privacy_status": settings.youtube_privacy_status,
        "upload_enabled": settings.youtube_upload_enabled,
        "authenticated": auth["authenticated"],
        "final_review_approved": bool(job.upload_review_approved),
        "reviewed_at": job.upload_reviewed_at.isoformat() if job.upload_reviewed_at else "",
        "review_notes": job.upload_review_notes,
    }


def mark_upload_reviewed(db: Session, job_id: int, notes: str = "") -> VideoJob:
    job = _require_job(db, job_id)
    job.metadata_reviewed = True
    job.ai_disclosure_reviewed = True
    job.source_license_reviewed = True
    job.voice_audio_reviewed = True
    job.upload_review_approved = True
    job.upload_reviewed_at = datetime.now(UTC)
    job.upload_review_notes = notes
    if not job.selected_thumbnail_path:
        job.selected_thumbnail_path = selected_thumbnail_path(job)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def select_thumbnail_variant(db: Session, job_id: int, variant: str) -> VideoJob:
    job = _require_job(db, job_id)
    variant = variant.lower().strip()
    variants = thumbnail_variant_paths(job)
    if variant not in variants:
        raise ValueError("Thumbnail variant must be one of: a, b, c.")
    path = Path(variants[variant])
    if not path.exists():
        raise ValueError(f"Thumbnail variant {variant} does not exist: {path}")
    job.selected_thumbnail_path = str(path)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def selected_thumbnail_path(job: VideoJob) -> str:
    if job.selected_thumbnail_path:
        return job.selected_thumbnail_path
    if job.thumbnail_output_path:
        return job.thumbnail_output_path
    for path in thumbnail_variant_paths(job).values():
        if Path(path).exists():
            return path
    return ""


def thumbnail_variant_paths(job: VideoJob) -> dict[str, str]:
    return {suffix: str(Path("renders") / "thumbnails" / f"{job.id}_{suffix}.png") for suffix in ["a", "b", "c"]}


def load_render_report(job: VideoJob) -> dict[str, object]:
    candidates = [
        Path("renders") / "reports" / f"{job.id}.json",
        Path("renders") / "reports" / f"{job.id}_preview.json",
    ]
    existing = [path for path in candidates if path.exists()]
    existing.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in existing:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _assets_have_license_metadata(assets: list[object], report: dict[str, object]) -> bool:
    if not assets:
        return bool(report)
    for asset in assets:
        if isinstance(asset, dict) and (asset.get("license_note") or asset.get("provider") == "generated"):
            continue
        return False
    return True


def _check(name: str, label: str, passed: bool, *, required: bool = True) -> dict[str, object]:
    return {"name": name, "label": label, "passed": bool(passed), "required": required}


def _require_job(db: Session, job_id: int) -> VideoJob:
    job = db.get(VideoJob, job_id)
    if job is None:
        raise ValueError("Video job not found.")
    return job
