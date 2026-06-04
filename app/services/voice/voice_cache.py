import hashlib
import re
from pathlib import Path

from app.core.config import get_settings


def voice_cache_dir() -> Path:
    root = get_settings().voice_cache_dir
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def voice_cache_path(job_id: int, scene_number: int, text: str, provider: str, voice_profile: str, suffix: str = ".wav") -> Path:
    safe_provider = re.sub(r"[^a-zA-Z0-9_-]+", "-", provider).strip("-").lower() or "voice"
    digest = hashlib.sha256(f"{job_id}|{scene_number}|{text}|{provider}|{voice_profile}".encode("utf-8")).hexdigest()[:24]
    extension = suffix if suffix.startswith(".") else f".{suffix}"
    path = voice_cache_dir() / safe_provider / f"{digest}{extension}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def combined_voice_path(job_id: int, provider: str, voice_profile: str, preview: bool = False) -> Path:
    suffix = "_preview" if preview else ""
    safe_provider = re.sub(r"[^a-zA-Z0-9_-]+", "-", provider).strip("-").lower() or "voice"
    path = voice_cache_dir() / safe_provider / f"job_{job_id}_{voice_profile}{suffix}.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
