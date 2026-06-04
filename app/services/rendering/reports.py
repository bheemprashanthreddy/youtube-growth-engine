import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class RenderResult:
    job_id: int
    format_type: str
    status: str
    render_output_path: str
    thumbnail_output_path: str
    report_output_path: str
    duration_seconds: float
    width: int = 0
    height: int = 0
    fps: float = 0
    has_audio: bool = False
    preview: bool = False
    error_message: str = ""


def save_render_report(
    *,
    job_id: int,
    format_type: str,
    title: str,
    status: str,
    scene_count: int,
    duration_seconds: float,
    width: int = 0,
    height: int = 0,
    fps: float = 0,
    has_audio: bool = False,
    preview: bool = False,
    render_output_path: str,
    thumbnail_output_path: str,
    report_output_path: str,
    assets_used: list[dict[str, object]] | None = None,
    thumbnail_variants: list[str] | None = None,
    voice_metadata: dict[str, object] | None = None,
    ai_visual_assets: list[dict[str, object]] | None = None,
    ai_visual_provider: str = "",
    ai_visual_model: str = "",
    ai_disclosure_recommended: bool = False,
    visual_priority_used: str = "stock_or_generated",
    render_engine: str = "native",
    external_service_used: bool = False,
    request_payload_path: str = "",
    response_payload_path: str = "",
    imported_video_path: str = "",
    imported_thumbnail_path: str = "",
    copyright_music_flags: dict[str, object] | None = None,
    warnings: list[str] | None = None,
    error_message: str = "",
) -> RenderResult:
    result = RenderResult(
        job_id=job_id,
        format_type=format_type,
        status=status,
        render_output_path=render_output_path,
        thumbnail_output_path=thumbnail_output_path,
        report_output_path=report_output_path,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        fps=fps,
        has_audio=has_audio,
        preview=preview,
        error_message=error_message,
    )
    payload = {
        **asdict(result),
        "title": title,
        "scene_count": scene_count,
        "created_at": datetime.now(UTC).isoformat(),
        "warnings": warnings or [],
        "assets_used": assets_used or [],
        "thumbnail_variants": thumbnail_variants or [],
        "voice": voice_metadata or {},
        "ai_visuals_used": bool(ai_visual_assets),
        "ai_visual_assets": ai_visual_assets or [],
        "ai_visual_provider": ai_visual_provider,
        "ai_visual_model": ai_visual_model,
        "ai_disclosure_recommended": ai_disclosure_recommended,
        "visual_priority_used": visual_priority_used,
        "render_engine": render_engine,
        "external_service_used": external_service_used,
        "request_payload_path": request_payload_path,
        "response_payload_path": response_payload_path,
        "imported_video_path": imported_video_path,
        "imported_thumbnail_path": imported_thumbnail_path,
        "copyright_music_flags": copyright_music_flags or {"background_music_enabled": False},
        "fallback_used": any(str(asset.get("asset_type")) == "generated" for asset in (assets_used or [])),
    }
    Path(report_output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return result
