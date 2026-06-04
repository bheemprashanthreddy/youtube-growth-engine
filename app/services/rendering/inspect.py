import json
import shutil
import subprocess
from pathlib import Path


def inspect_media(path: str) -> dict[str, object]:
    media_path = Path(path)
    result: dict[str, object] = {
        "path": str(media_path),
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "duration_seconds": 0.0,
        "has_audio": False,
        "file_size": media_path.stat().st_size if media_path.exists() else 0,
        "warnings": [],
    }
    if not media_path.exists():
        result["warnings"] = ["file_missing"]
        return result
    if shutil.which("ffprobe"):
        return _inspect_with_ffprobe(media_path, result)
    return _inspect_with_moviepy(media_path, result)


def _inspect_with_ffprobe(media_path: Path, result: dict[str, object]) -> dict[str, object]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(media_path),
    ]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=True)
        payload = json.loads(completed.stdout)
    except Exception as exc:
        result["warnings"] = [f"ffprobe_failed:{exc}"]
        return _inspect_with_moviepy(media_path, result)
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    result["width"] = int(video.get("width") or 0)
    result["height"] = int(video.get("height") or 0)
    result["fps"] = _parse_fps(str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"))
    duration = payload.get("format", {}).get("duration") or video.get("duration") or 0
    result["duration_seconds"] = round(float(duration or 0), 3)
    result["has_audio"] = audio is not None
    result["warnings"] = _metadata_warnings(result)
    return result


def _inspect_with_moviepy(media_path: Path, result: dict[str, object]) -> dict[str, object]:
    try:
        from moviepy import VideoFileClip

        clip = VideoFileClip(str(media_path))
        result["width"], result["height"] = clip.size
        result["fps"] = float(clip.fps or 0)
        result["duration_seconds"] = round(float(clip.duration or 0), 3)
        result["has_audio"] = clip.audio is not None
        clip.close()
    except Exception as exc:
        result["warnings"] = [f"metadata_inspection_failed:{exc}"]
        return result
    result["warnings"] = _metadata_warnings(result)
    return result


def _parse_fps(value: str) -> float:
    try:
        numerator, denominator = value.split("/")
        return round(float(numerator) / max(1.0, float(denominator)), 3)
    except Exception:
        return 0.0


def _metadata_warnings(result: dict[str, object]) -> list[str]:
    warnings: list[str] = []
    if not result["width"] or not result["height"]:
        warnings.append("resolution_unavailable")
    if float(result["fps"] or 0) < 24:
        warnings.append("fps_below_24")
    if float(result["duration_seconds"] or 0) <= 0:
        warnings.append("duration_unavailable")
    if not result["has_audio"]:
        warnings.append("audio_stream_missing")
    return warnings
