import hashlib
from pathlib import Path

from app.core.config import get_settings


def ai_visual_cache_dir() -> Path:
    root = get_settings().ai_visual_cache_dir
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:24]


def scene_image_path(job_id: int, scene_number: int, prompt: str) -> Path:
    path = ai_visual_cache_dir() / "scenes" / f"{job_id}_{scene_number}_{prompt_hash(prompt)}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def thumbnail_concept_path(job_id: int, variant: str, prompt: str) -> Path:
    path = ai_visual_cache_dir() / "thumbnails" / f"{job_id}_concept_{variant}_{prompt_hash(prompt)}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
