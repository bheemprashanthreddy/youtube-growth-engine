import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.models.content import VideoJob
from app.services.ai_visuals.prompt_builder import build_scene_image_prompt
from app.services.ai_visuals.visual_service import ai_visual_status, generate_ai_thumbnail_concepts, generate_scene_images
from app.services.rendering.renderer import render_preview
from app.services.review import clear_dev_data, list_review_items, set_approval_status
from app.services.video_job_service import create_short_job
from app.services.youtube.upload_checks import run_upload_checks


@pytest.fixture(autouse=True)
def clear_settings_cache_after_test():
    yield
    get_settings.cache_clear()


def test_ai_visual_status_works_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AI_VISUALS_ENABLED", "false")
    get_settings.cache_clear()
    try:
        status = ai_visual_status()
        assert status.enabled is False
        assert status.fallback_mode is True
    finally:
        get_settings.cache_clear()


def test_prompt_builder_sanitizes_unsafe_people_political_violent_terms() -> None:
    job = _fake_job("AI search replacing links")
    prompt = build_scene_image_prompt(
        {"visual_prompt": "real person politician with weapon in breaking news scene", "broll_keywords": ["ai"]},
        job,
    )
    lower = prompt.lower()
    assert "no real people" in lower
    assert "no public figures" in lower
    assert "no weapons" in lower


def test_scene_image_generation_writes_mocked_files(monkeypatch) -> None:
    _enable_fallback_ai(monkeypatch)
    job_id = _ready_job_id()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        scenes = json.loads(job.scene_plan_json)["scenes"][:2]
        assets = generate_scene_images(job, scenes)
    assert len(assets) == 2
    assert all(Path(asset.local_path).exists() for asset in assets)


def test_ai_thumbnail_generation_writes_mocked_files(monkeypatch) -> None:
    _enable_fallback_ai(monkeypatch)
    job_id = _ready_job_id()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        assets = generate_ai_thumbnail_concepts(job)
    assert len(assets) == 3
    assert all(Path(asset.local_path).exists() for asset in assets)


def test_renderer_uses_ai_visual_path_when_available(monkeypatch) -> None:
    _enable_fallback_ai(monkeypatch)
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _ready_job_id()
    result = render_preview(job_id)
    report = json.loads(Path(result.report_output_path).read_text(encoding="utf-8"))
    assert report["ai_visuals_used"] is True
    assert report["visual_priority_used"] == "ai_visual"
    assert report["ai_visual_assets"]


def test_upload_check_includes_ai_disclosure_review(monkeypatch) -> None:
    _enable_fallback_ai(monkeypatch)
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_PRIVACY_STATUS", "private")
    job_id = _ready_job_id()
    result = render_preview(job_id)
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        job.status = "rendered"
        job.render_output_path = result.render_output_path
        job.thumbnail_output_path = result.thumbnail_output_path
        db.add(job)
        db.commit()
        checks = run_upload_checks(db, job)
    assert "AI disclosure review required for generated visual assets." in checks["warnings"]


def test_ai_visual_status_cli_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "ai-visual-status"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "enabled:" in result.stdout
    assert "fallback mode:" in result.stdout


def _enable_fallback_ai(monkeypatch) -> None:
    monkeypatch.setenv("AI_VISUALS_ENABLED", "true")
    monkeypatch.setenv("AI_SCENE_IMAGES_ENABLED", "true")
    monkeypatch.setenv("AI_THUMBNAILS_ENABLED", "true")
    monkeypatch.setenv("AI_VISUAL_PROVIDER", "fallback")
    monkeypatch.setenv("AI_IMAGE_MODEL", "fallback-image")
    monkeypatch.setenv("VOICE_PROVIDER", "silent")
    get_settings.cache_clear()


def _ready_job_id() -> int:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        item = list_review_items(db)[0]
        set_approval_status(db, item, "approved")
        job = create_short_job(db, item.id)
        job.status = "ready_for_render"
        db.add(job)
        db.commit()
        return job.id


def _fake_job(title: str):
    class Job:
        def __init__(self, value: str) -> None:
            self.title = value

    return Job(title)
