import json
import shutil
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR, get_settings
from app.db.session import SessionLocal
from app.models.content import VideoJob
from app.services.rendering.inspect import inspect_media
from app.services.rendering.reports import RenderResult, save_render_report
from app.services.rendering.thumbnails import generate_thumbnail
from app.services.rendering.engines.base import RenderEngine


class MoneyPrinterTurboEngine(RenderEngine):
    name = "moneyprinterturbo"

    def render_job(self, job_id: int, preview: bool = False) -> RenderResult:
        settings = get_settings()
        with SessionLocal() as db:
            job = db.get(VideoJob, job_id)
            if job is None:
                raise ValueError("Video job not found.")
            if job.status != "ready_for_render":
                raise ValueError(f"Video job must be ready_for_render, current status is {job.status}.")
            if preview:
                return self._failed(job, "MoneyPrinterTurbo preview rendering is not supported by the adapter yet.", preview=True)
            if not settings.moneyprinterturbo_enabled:
                return self._failed(job, "MoneyPrinterTurbo rendering is disabled. Set MONEYPRINTERTURBO_ENABLED=true.", preview=False)
            status = self.get_status()
            if not status.get("reachable"):
                warnings = [str(warning) for warning in status.get("warnings", [])]
                return self._failed(
                    job,
                    "MoneyPrinterTurbo is enabled but unreachable. Start the external API and verify /docs or /redoc before retrying.",
                    preview=False,
                    warnings=warnings,
                )

            job.status = "rendering"
            job.error_message = ""
            db.add(job)
            db.commit()

            payload = build_moneyprinterturbo_payload(job)
            request_path = _integration_path(job.id, "request")
            response_path = _integration_path(job.id, "response")
            request_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            warnings = _music_warnings()
            try:
                response = self._create_video(payload)
                response_path.write_text(json.dumps(response, indent=2, default=str), encoding="utf-8")
                task_id = str(response.get("task_id") or response.get("id") or "")
                final_response = response
                if task_id and not _response_has_output(response):
                    final_response = self._poll_status(task_id)
                    response_path.write_text(json.dumps(final_response, indent=2, default=str), encoding="utf-8")
                paths = self._import_outputs(job, final_response, task_id=task_id)
                metadata = inspect_media(str(paths["video"])) if paths["video"].exists() else {}
                result = save_render_report(
                    job_id=job.id,
                    format_type=job.format_type,
                    title=job.title,
                    status="rendered",
                    scene_count=_scene_count(job),
                    duration_seconds=float(metadata.get("duration_seconds") or 0),
                    width=int(metadata.get("width") or (1080 if job.format_type == "short" else 1920)),
                    height=int(metadata.get("height") or (1920 if job.format_type == "short" else 1080)),
                    fps=float(metadata.get("fps") or 0),
                    has_audio=bool(metadata.get("has_audio")),
                    render_output_path=str(paths["video"]),
                    thumbnail_output_path=str(paths["thumbnail"]),
                    report_output_path=str(_standard_report_path(job.id)),
                    render_engine=self.name,
                    external_service_used=True,
                    request_payload_path=str(request_path),
                    response_payload_path=str(response_path),
                    imported_video_path=str(paths["video"]),
                    imported_thumbnail_path=str(paths["thumbnail"]),
                    copyright_music_flags={"background_music_enabled": settings.moneyprinterturbo_use_background_music},
                    warnings=warnings + list(metadata.get("warnings", [])),
                )
                job.status = "rendered"
                job.render_output_path = result.render_output_path
                job.thumbnail_output_path = result.thumbnail_output_path
                job.error_message = ""
                db.add(job)
                db.commit()
                return result
            except Exception as exc:
                response_path.write_text(json.dumps({"error": str(exc)}, indent=2), encoding="utf-8")
                result = self._failed(job, str(exc), request_path=str(request_path), response_path=str(response_path), warnings=warnings)
                job.status = "failed"
                job.error_message = str(exc)
                db.add(job)
                db.commit()
                return result

    def get_status(self) -> dict[str, object]:
        settings = get_settings()
        warnings = _music_warnings()
        create_endpoint = settings.moneyprinterturbo_create_endpoint
        status_endpoint = settings.moneyprinterturbo_status_endpoint
        if not settings.moneyprinterturbo_enabled:
            return {
                "engine": self.name,
                "enabled": False,
                "base_url": settings.moneyprinterturbo_base_url,
                "reachable": False,
                "configured": False,
                "create_endpoint": create_endpoint,
                "status_endpoint": status_endpoint,
                "setup_guidance": "Clone MoneyPrinterTurbo separately, start its API service, set MONEYPRINTERTURBO_ENABLED=true, and verify /docs.",
                "warnings": warnings,
                "detail": "MoneyPrinterTurbo disabled; native renderer remains available.",
            }
        try:
            request = urllib.request.Request(settings.moneyprinterturbo_base_url, method="GET")
            with urllib.request.urlopen(request, timeout=3) as response:
                reachable = 200 <= response.status < 500
            return {
                "engine": self.name,
                "enabled": True,
                "base_url": settings.moneyprinterturbo_base_url,
                "reachable": reachable,
                "configured": True,
                "create_endpoint": create_endpoint,
                "status_endpoint": status_endpoint,
                "setup_guidance": "Confirm request schema in the running service at /docs or /redoc before production use.",
                "warnings": warnings,
                "detail": "MoneyPrinterTurbo base URL responded.",
            }
        except Exception as exc:
            return {
                "engine": self.name,
                "enabled": True,
                "base_url": settings.moneyprinterturbo_base_url,
                "reachable": False,
                "configured": True,
                "create_endpoint": create_endpoint,
                "status_endpoint": status_endpoint,
                "setup_guidance": "Start the external MoneyPrinterTurbo API or update MONEYPRINTERTURBO_BASE_URL.",
                "warnings": [*warnings, f"MoneyPrinterTurbo unreachable: {exc}"],
                "detail": "MoneyPrinterTurbo is enabled but not reachable.",
            }

    def _create_video(self, payload: dict[str, object]) -> dict[str, object]:
        settings = get_settings()
        url = _join_url(settings.moneyprinterturbo_base_url, settings.moneyprinterturbo_create_endpoint)
        return _post_json(url, payload, timeout=settings.moneyprinterturbo_timeout_seconds)

    def _poll_status(self, task_id: str) -> dict[str, object]:
        settings = get_settings()
        endpoint = settings.moneyprinterturbo_status_endpoint.format(task_id=task_id)
        url = _join_url(settings.moneyprinterturbo_base_url, endpoint)
        return _get_json(url, timeout=settings.moneyprinterturbo_timeout_seconds)

    def _import_outputs(self, job: VideoJob, response: dict[str, object], *, task_id: str = "") -> dict[str, Path]:
        video_path = _standard_video_path(job)
        thumbnail_path = _standard_thumbnail_path(job)
        video_path.parent.mkdir(parents=True, exist_ok=True)
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        source_video = _first_response_value(response, ["video_path", "output_path", "render_output_path", "file_path", "url", "download_url"])
        source_thumbnail = _first_response_value(response, ["thumbnail_path", "cover_path", "thumbnail_url"])
        if source_video:
            _copy_or_download(source_video, video_path)
        elif task_id:
            settings = get_settings()
            endpoint = settings.moneyprinterturbo_download_endpoint.format(task_id=task_id)
            _download(_join_url(settings.moneyprinterturbo_base_url, endpoint), video_path, timeout=settings.moneyprinterturbo_timeout_seconds)
        else:
            raise RuntimeError("MoneyPrinterTurbo response did not include a video path, URL, or task id.")
        if source_thumbnail:
            _copy_or_download(source_thumbnail, thumbnail_path)
        else:
            generate_thumbnail(job, str(thumbnail_path))
        return {"video": video_path, "thumbnail": thumbnail_path}

    def _failed(
        self,
        job: VideoJob,
        error: str,
        *,
        preview: bool = False,
        request_path: str = "",
        response_path: str = "",
        warnings: list[str] | None = None,
    ) -> RenderResult:
        return save_render_report(
            job_id=job.id,
            format_type=job.format_type,
            title=job.title,
            status="failed",
            scene_count=_scene_count(job),
            duration_seconds=0,
            preview=preview,
            render_output_path="",
            thumbnail_output_path="",
            report_output_path=str(_standard_report_path(job.id, preview=preview)),
            render_engine=self.name,
            external_service_used=True,
            request_payload_path=request_path,
            response_payload_path=response_path,
            copyright_music_flags={"background_music_enabled": get_settings().moneyprinterturbo_use_background_music},
            warnings=warnings or _music_warnings(),
            error_message=error,
        )


def build_moneyprinterturbo_payload(job: VideoJob) -> dict[str, object]:
    scenes = _scenes(job)
    narration = _script_text(job, scenes)
    keywords = _material_keywords(job, scenes)
    # TODO: Verify MoneyPrinterTurbo's exact request schema against the running API.
    # This adapter keeps our canonical job data explicit so field mapping is easy to adjust.
    return {
        "subject": job.title,
        "title": job.title,
        "script": narration,
        "video_terms": keywords,
        "aspect_ratio": "9:16" if job.format_type == "short" else "16:9",
        "resolution": "1080x1920" if job.format_type == "short" else "1920x1080",
        "format_type": job.format_type,
        "language": "en",
        "voice_profile": job.voice_profile,
        "subtitle_enabled": True,
        "background_music_enabled": bool(get_settings().moneyprinterturbo_use_background_music),
        "upload_public": False,
        "private_upload_only": True,
        "source": {
            "system": "youtube-growth-engine",
            "video_job_id": job.id,
            "review_item_id": job.review_item_id,
        },
        "metadata": {
            "description": job.description,
            "hashtags": job.hashtags,
            "thumbnail_text": job.thumbnail_text,
            "ai_disclosure_recommendation": job.ai_disclosure_recommendation,
        },
    }


def _script_text(job: VideoJob, scenes: list[dict[str, Any]]) -> str:
    if job.format_type == "short" and job.script.strip():
        return job.script.strip()
    lines = [str(scene.get("voiceover") or scene.get("narration_goal") or scene.get("on_screen_text") or scene.get("section_title") or "").strip() for scene in scenes]
    text = "\n".join(line for line in lines if line)
    return text or job.script or "\n".join(job.outline)


def _material_keywords(job: VideoJob, scenes: list[dict[str, Any]]) -> list[str]:
    terms: list[str] = []
    for scene in scenes:
        for value in scene.get("broll_keywords") or []:
            if value:
                terms.append(str(value))
        prompt = str(scene.get("visual_prompt") or "").strip()
        if prompt:
            terms.append(prompt)
    if not terms:
        terms.extend([job.title, job.thumbnail_text])
    return sorted({term for term in terms if term})[:12]


def _post_json(url: str, payload: dict[str, object], *, timeout: int) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def _get_json(url: str, *, timeout: int) -> dict[str, object]:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def _copy_or_download(source: str, destination: Path) -> None:
    if source.startswith(("http://", "https://")):
        _download(source, destination, timeout=get_settings().moneyprinterturbo_timeout_seconds)
        return
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"MoneyPrinterTurbo output not found: {source}")
    shutil.copyfile(source_path, destination)


def _download(url: str, destination: Path, *, timeout: int) -> None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            destination.write_bytes(response.read())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not download MoneyPrinterTurbo output: {exc}") from exc


def _first_response_value(response: dict[str, object], keys: list[str]) -> str:
    for key in keys:
        value = response.get(key)
        if value:
            return str(value)
    data = response.get("data")
    if isinstance(data, dict):
        return _first_response_value(data, keys)
    return ""


def _response_has_output(response: dict[str, object]) -> bool:
    return bool(_first_response_value(response, ["video_path", "output_path", "render_output_path", "file_path", "url", "download_url"]))


def _scenes(job: VideoJob) -> list[dict[str, Any]]:
    try:
        return list(json.loads(job.scene_plan_json).get("scenes", []))
    except Exception:
        return []


def _scene_count(job: VideoJob) -> int:
    return len(_scenes(job))


def _integration_path(job_id: int, kind: str) -> Path:
    root = get_settings().moneyprinterturbo_output_dir / "reports"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{job_id}_{kind}.json"


def _standard_video_path(job: VideoJob) -> Path:
    folder = "shorts" if job.format_type == "short" else "long"
    return Path(BASE_DIR) / "renders" / folder / f"{job.id}.mp4"


def _standard_thumbnail_path(job: VideoJob) -> Path:
    return Path(BASE_DIR) / "renders" / "thumbnails" / f"{job.id}.png"


def _standard_report_path(job_id: int, *, preview: bool = False) -> Path:
    suffix = "_preview" if preview else ""
    path = Path(BASE_DIR) / "renders" / "reports" / f"{job_id}{suffix}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _join_url(base_url: str, endpoint: str) -> str:
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"


def _music_warnings() -> list[str]:
    if get_settings().moneyprinterturbo_use_background_music:
        return ["moneyprinterturbo_background_music_enabled_confirm_license_before_publish"]
    return ["moneyprinterturbo_background_music_disabled_by_default"]
