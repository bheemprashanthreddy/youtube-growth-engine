import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.db.session import SessionLocal
from app.models.content import VideoJob
from app.services.rendering.inspect import inspect_media
from app.services.rendering.quality import render_quality_warnings
from app.services.rendering.reports import RenderResult, save_render_report
from app.services.rendering.thumbnails import generate_thumbnail, generate_thumbnail_variants
from app.services.rendering.visual_templates import create_long_scene_clip, create_short_scene_clip
from app.services.visual_assets.asset_selector import select_assets_for_job
from app.services.ai_visuals.visual_service import ai_visual_status, generate_ai_thumbnail_concepts
from app.services.voice.voice_service import generate_voice_for_job


def render_job(job_id: int) -> RenderResult:
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        if job is None:
            raise ValueError("Video job not found.")
        if job.status != "ready_for_render":
            raise ValueError(f"Video job must be ready_for_render, current status is {job.status}.")
        job.status = "rendering"
        job.error_message = ""
        db.add(job)
        db.commit()
        try:
            result = _render(job)
            job.status = "rendered"
            job.render_output_path = result.render_output_path
            job.thumbnail_output_path = result.thumbnail_output_path
            job.error_message = ""
            db.add(job)
            db.commit()
            return result
        except Exception as exc:
            report_path = _report_path(job)
            result = save_render_report(
                job_id=job.id,
                format_type=job.format_type,
                title=job.title,
                status="failed",
                scene_count=_scene_count(job),
                duration_seconds=0,
                render_output_path="",
                thumbnail_output_path="",
                report_output_path=str(report_path),
                warnings=[],
                error_message=str(exc),
            )
            job.status = "failed"
            job.error_message = str(exc)
            db.add(job)
            db.commit()
            return result


def render_preview(job_id: int) -> RenderResult:
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        if job is None:
            raise ValueError("Video job not found.")
        if job.status not in {"ready_for_render", "rendered"}:
            raise ValueError(f"Video job must be ready_for_render or rendered for preview, current status is {job.status}.")
        try:
            return _render(job, preview=True)
        except Exception as exc:
            report_path = _report_path(job, preview=True)
            return save_render_report(
                job_id=job.id,
                format_type=job.format_type,
                title=job.title,
                status="failed",
                scene_count=_scene_count(job),
                duration_seconds=0,
                preview=True,
                render_output_path="",
                thumbnail_output_path="",
                report_output_path=str(report_path),
                warnings=[],
                error_message=str(exc),
            )


def render_ready_jobs(limit: int = 1) -> list[RenderResult]:
    with SessionLocal() as db:
        jobs = db.execute(select(VideoJob).where(VideoJob.status == "ready_for_render").order_by(VideoJob.created_at).limit(limit)).scalars().all()
        ids = [job.id for job in jobs]
    return [render_job(job_id) for job_id in ids]


def render_batch(limit: int = 5, format_type: str | None = None, include_failed: bool = False, force: bool = False) -> dict[str, object]:
    started = datetime.now(UTC)
    with SessionLocal() as db:
        query = select(VideoJob)
        statuses = ["ready_for_render"]
        if include_failed:
            statuses.append("failed")
        if not force:
            query = query.where(VideoJob.status.in_(statuses))
        if format_type:
            query = query.where(VideoJob.format_type == format_type)
        jobs = db.execute(query.order_by(VideoJob.created_at).limit(limit)).scalars().all()
        ids = [job.id for job in jobs]
    results = []
    rendered_count = 0
    failed_count = 0
    skipped_count = 0
    for job_id in ids:
        try:
            if force:
                with SessionLocal() as db:
                    job = db.get(VideoJob, job_id)
                    if job and job.status == "rendered":
                        job.status = "ready_for_render"
                        db.add(job)
                        db.commit()
            result = render_job(job_id)
            validation = validate_render_result(result)
            if result.status == "rendered" and validation["passed"]:
                rendered_count += 1
            else:
                failed_count += 1
                _mark_render_failed(job_id, "; ".join(validation["warnings"]) or result.error_message)
            results.append({**result.__dict__, "validation": validation})
        except Exception as exc:
            failed_count += 1
            _mark_render_failed(job_id, str(exc))
            results.append({"job_id": job_id, "status": "failed", "error": str(exc)})
    skipped_count = max(0, limit - len(ids))
    report = {
        "started_at": started.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "total_requested": limit,
        "total_processed": len(ids),
        "rendered_count": rendered_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "job_results": results,
        "warnings": [],
    }
    path = Path(BASE_DIR) / "renders" / "reports" / f"batch_{started.strftime('%Y%m%d_%H%M%S')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["report_path"] = str(path)
    return report


def reset_failed_renders(db: Session) -> int:
    rows = db.execute(select(VideoJob).where(VideoJob.status == "failed")).scalars().all()
    for row in rows:
        row.status = "ready_for_render"
        row.error_message = ""
        db.add(row)
    db.commit()
    return len(rows)


def validate_render_result(result: RenderResult) -> dict[str, object]:
    warnings: list[str] = []
    path = Path(result.render_output_path)
    if not path.exists() or path.stat().st_size == 0:
        warnings.append("render_file_missing_or_empty")
    metadata = inspect_media(str(path)) if path.exists() else {}
    expected = (1080, 1920) if result.format_type == "short" else (1920, 1080)
    if int(metadata.get("width") or result.width or 0) != expected[0] or int(metadata.get("height") or result.height or 0) != expected[1]:
        warnings.append("resolution_mismatch")
    if float(metadata.get("fps") or result.fps or 0) < 24:
        warnings.append("fps_below_expected")
    min_duration = 2.0 if _test_mode() else (40.0 if result.format_type == "short" and not result.preview else 10.0)
    if float(metadata.get("duration_seconds") or result.duration_seconds or 0) < min_duration:
        warnings.append("duration_below_minimum")
    if not bool(metadata.get("has_audio", result.has_audio)):
        warnings.append("audio_stream_missing")
    if not Path(result.thumbnail_output_path).exists():
        warnings.append("thumbnail_missing")
    if not Path(result.report_output_path).exists():
        warnings.append("report_missing")
    return {"passed": not warnings, "warnings": warnings, "metadata": metadata}


def _mark_render_failed(job_id: int, error: str) -> None:
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        if job:
            job.status = "failed"
            job.error_message = error
            db.add(job)
            db.commit()


def _render(job: VideoJob, *, preview: bool = False) -> RenderResult:
    scene_plan = json.loads(job.scene_plan_json)
    scenes = scene_plan.get("scenes", [])
    if preview:
        scenes = _preview_scenes(scenes, job.format_type)
    else:
        scenes = _full_render_scenes(scenes, job.format_type)
    settings = _render_settings(job, preview=preview)
    assets = select_assets_for_job(job, scenes)
    if _test_mode():
        return _render_fast_test_video(job, scenes, settings, preview=preview, assets=assets)
    try:
        from moviepy import AudioFileClip, concatenate_videoclips
    except Exception as exc:
        raise RuntimeError("MoviePy/FFmpeg is required. Install dependencies with pip install -e \".[test]\" and ensure FFmpeg is available.") from exc
    clips = []
    for index, scene in enumerate(scenes):
        duration = _scene_duration(scene, job.format_type)
        asset = assets[index].to_dict() if index < len(assets) else None
        if job.format_type == "short":
            clips.append(create_short_scene_clip(scene, settings["size"], duration, asset=asset))
        else:
            clips.append(create_long_scene_clip(scene, settings["size"], duration, asset=asset))
    if not clips:
        raise RuntimeError("Cannot render job with empty scene plan.")
    video = concatenate_videoclips(clips, method="compose")
    duration = float(video.duration)
    paths = _paths(job, preview=preview)
    voice_result = generate_voice_for_job(job, scenes, preview=preview)
    audio_path = Path(voice_result.combined_audio_path)
    audio = None
    try:
        audio = AudioFileClip(str(audio_path)).subclipped(0, duration)
        video = video.with_audio(audio)
    except Exception as exc:
        raise RuntimeError(f"Could not attach narration or silent audio track: {exc}") from exc
    video.write_videofile(
        str(paths["video"]),
        fps=settings["fps"],
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast" if _test_mode() else "medium",
        temp_audiofile=str(paths["temp_audio"]),
        remove_temp=True,
        logger=None,
    )
    if audio:
        audio.close()
    video.close()
    for clip in clips:
        clip.close()
    thumbnail = generate_thumbnail(job, str(paths["thumbnail"]))
    ai_thumbnail_assets = [asset.to_dict() for asset in generate_ai_thumbnail_concepts(job)]
    thumbnail_variants = generate_thumbnail_variants(job, assets=ai_thumbnail_assets or [asset.to_dict() for asset in assets])
    warnings = render_quality_warnings(scenes, thumbnail_text=job.thumbnail_text or job.title, short=job.format_type == "short")
    warnings.extend(voice_result.warnings)
    if voice_result.fallback_used:
        warnings.append("silent_audio_fallback_used")
    metadata = inspect_media(str(paths["video"]))
    warnings.extend(str(warning) for warning in metadata.get("warnings", []))
    return save_render_report(
        job_id=job.id,
        format_type=job.format_type,
        title=job.title,
        status="preview" if preview else "rendered",
        scene_count=len(scenes),
        duration_seconds=float(metadata.get("duration_seconds") or duration),
        width=int(metadata.get("width") or settings["size"][0]),
        height=int(metadata.get("height") or settings["size"][1]),
        fps=float(metadata.get("fps") or settings["fps"]),
        has_audio=bool(metadata.get("has_audio")),
        preview=preview,
        render_output_path=str(paths["video"]),
        thumbnail_output_path=thumbnail,
        report_output_path=str(paths["report"]),
        assets_used=[asset.to_dict() for asset in assets],
        thumbnail_variants=thumbnail_variants,
        voice_metadata=voice_result.to_dict(),
        **_ai_report_fields(assets, ai_thumbnail_assets),
        warnings=warnings,
        error_message="",
    )


def _render_fast_test_video(job: VideoJob, scenes: list[dict[str, object]], settings: dict[str, object], *, preview: bool, assets) -> RenderResult:
    if not scenes:
        raise RuntimeError("Cannot render job with empty scene plan.")
    paths = _paths(job, preview=preview)
    duration = sum(_scene_duration(scene, job.format_type) for scene in scenes)
    voice_result = generate_voice_for_job(job, scenes, preview=preview)
    width, height = settings["size"]
    fps = int(settings["fps"])
    _write_ffmpeg_test_video(paths["video"], Path(voice_result.combined_audio_path), width, height, fps, duration)
    thumbnail = generate_thumbnail(job, str(paths["thumbnail"]))
    ai_thumbnail_assets = [asset.to_dict() for asset in generate_ai_thumbnail_concepts(job)]
    thumbnail_variants = generate_thumbnail_variants(job, assets=ai_thumbnail_assets or [asset.to_dict() for asset in assets])
    warnings = render_quality_warnings(scenes, thumbnail_text=job.thumbnail_text or job.title, short=job.format_type == "short")
    warnings.append("silent_audio_fallback_used")
    metadata = inspect_media(str(paths["video"]))
    warnings.extend(str(warning) for warning in metadata.get("warnings", []))
    return save_render_report(
        job_id=job.id,
        format_type=job.format_type,
        title=job.title,
        status="preview" if preview else "rendered",
        scene_count=len(scenes),
        duration_seconds=float(metadata.get("duration_seconds") or duration),
        width=int(metadata.get("width") or width),
        height=int(metadata.get("height") or height),
        fps=float(metadata.get("fps") or fps),
        has_audio=bool(metadata.get("has_audio")),
        preview=preview,
        render_output_path=str(paths["video"]),
        thumbnail_output_path=thumbnail,
        report_output_path=str(paths["report"]),
        assets_used=[asset.to_dict() for asset in assets],
        thumbnail_variants=thumbnail_variants,
        voice_metadata=voice_result.to_dict(),
        **_ai_report_fields(assets, ai_thumbnail_assets),
        warnings=warnings,
        error_message="",
    )


def _write_ffmpeg_test_video(video_path: Path, audio_path: Path, width: int, height: int, fps: int, duration: float) -> None:
    try:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("FFmpeg is required for test-mode render encoding.") from exc
    video_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x050b18:s={width}x{height}:r={fps}:d={duration}",
        "-i",
        str(audio_path),
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        str(video_path),
    ]
    subprocess.run(command, text=True, capture_output=True, check=True)


def _ai_report_fields(assets, thumbnail_assets: list[dict[str, object]]) -> dict[str, object]:
    scene_ai_assets = [asset.to_dict() for asset in assets if str(asset.provider).startswith("ai_")]
    all_ai_assets = [*scene_ai_assets, *thumbnail_assets]
    status = ai_visual_status()
    return {
        "ai_visual_assets": all_ai_assets,
        "ai_visual_provider": status.provider,
        "ai_visual_model": status.image_model,
        "ai_disclosure_recommended": bool(all_ai_assets),
        "visual_priority_used": "ai_visual" if all_ai_assets else "stock_or_generated",
    }


def _paths(job: VideoJob, *, preview: bool = False) -> dict[str, Path]:
    root = Path(BASE_DIR)
    video_dir = root / "renders" / ("shorts" if job.format_type == "short" else "long")
    thumb_dir = root / "renders" / "thumbnails"
    report_dir = root / "renders" / "reports"
    audio_dir = root / "renders" / "audio"
    for path in [video_dir, thumb_dir, report_dir, audio_dir]:
        path.mkdir(parents=True, exist_ok=True)
    suffix = "_preview" if preview else ""
    return {
        "video": video_dir / f"{job.id}{suffix}.mp4",
        "thumbnail": thumb_dir / f"{job.id}{suffix}.png",
        "report": report_dir / f"{job.id}{suffix}.json",
        "tts_audio": audio_dir / f"{job.id}{suffix}.mp3",
        "silent_audio": audio_dir / f"{job.id}{suffix}.wav",
        "temp_audio": audio_dir / f"{job.id}{suffix}_temp_audio.m4a",
    }


def _report_path(job: VideoJob, *, preview: bool = False) -> Path:
    suffix = "_preview" if preview else ""
    path = Path(BASE_DIR) / "renders" / "reports" / f"{job.id}{suffix}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _scene_count(job: VideoJob) -> int:
    try:
        return len(json.loads(job.scene_plan_json).get("scenes", []))
    except Exception:
        return 0


def _scene_duration(scene: dict[str, object], format_type: str) -> float:
    key = "duration_seconds" if format_type == "short" else "estimated_duration_seconds"
    return float(scene.get(key) or 5)


def _render_settings(job: VideoJob, *, preview: bool) -> dict[str, object]:
    if job.format_type == "short":
        return {"size": (1080, 1920), "fps": 30, "preview_target": 12.0, "full_target": 54.0}
    return {"size": (1920, 1080), "fps": 30, "preview_target": 20.0, "full_target": 90.0}


def _preview_scenes(scenes: list[dict[str, object]], format_type: str) -> list[dict[str, object]]:
    if not scenes:
        return []
    minimum = 3
    count = max(minimum, min(len(scenes), 4 if format_type == "short" else 5))
    selected = [dict(scenes[index % len(scenes)]) for index in range(count)]
    target = 12.0 if format_type == "short" else 20.0
    return _with_scaled_durations(selected, format_type, target)


def _full_render_scenes(scenes: list[dict[str, object]], format_type: str) -> list[dict[str, object]]:
    if not scenes:
        return []
    selected = [dict(scene) for scene in scenes]
    if _test_mode():
        target = 3.0 if format_type == "short" else 4.0
        return _with_scaled_durations(selected, format_type, target)
    target = 54.0 if format_type == "short" else min(120.0, max(45.0, sum(_scene_duration(scene, format_type) for scene in selected)))
    if format_type == "short":
        target = min(60.0, max(45.0, target))
    return _with_scaled_durations(selected, format_type, target)


def _with_scaled_durations(scenes: list[dict[str, object]], format_type: str, target: float) -> list[dict[str, object]]:
    key = "duration_seconds" if format_type == "short" else "estimated_duration_seconds"
    current = sum(max(0.25, _scene_duration(scene, format_type)) for scene in scenes)
    scale = target / current if current else 1.0
    adjusted: list[dict[str, object]] = []
    for scene in scenes:
        clone = dict(scene)
        clone[key] = round(max(1.0, _scene_duration(scene, format_type) * scale), 3)
        adjusted.append(clone)
    return adjusted


def _test_mode() -> bool:
    import os

    return os.getenv("RENDER_TEST_MODE", "").lower() in {"1", "true", "yes"}
