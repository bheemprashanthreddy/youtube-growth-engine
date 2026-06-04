import json
import subprocess
import sys
from pathlib import Path

from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.models.content import VideoJob
from app.services.rendering.renderer import render_preview
from app.services.rendering.thumbnails import generate_thumbnail_variants
from app.services.review import clear_dev_data, list_review_items, set_approval_status
from app.services.video_job_service import create_short_job
from app.services.visual_assets.asset_cache import safe_cache_path
from app.services.visual_assets.asset_selector import build_asset_query, select_assets_for_job, visual_provider_status
from app.services.visual_assets.safety import is_safe_asset_query


def test_visual_provider_status_works_without_keys(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_ASSET_PROVIDER", "pexels")
    monkeypatch.setenv("PEXELS_API_KEY", "")
    monkeypatch.setenv("ALLOW_STOCK_ASSETS", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        status = visual_provider_status()
        assert status.selected_provider == "pexels"
        assert status.active is False
        assert status.fallback_mode is True
    finally:
        get_settings.cache_clear()


def test_asset_selector_creates_relevant_search_query() -> None:
    job = _fake_job("Why AI search engines are changing how people find information online")
    query = build_asset_query({"visual_prompt": "AI search answer box", "broll_keywords": ["search", "answers"]}, job)
    assert "AI search interface" in query


def test_cache_path_is_generated_safely() -> None:
    path = safe_cache_path("../pexels?", "AI search interface / unsafe?", ".jpg")
    assert ".." not in path.name
    assert path.suffix == ".jpg"
    assert "storage" in str(path)


def test_safety_filter_rejects_unsafe_terms() -> None:
    assert is_safe_asset_query("politician with weapon") is False
    assert is_safe_asset_query("technology data network abstract") is True


def test_renderer_falls_back_when_provider_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    monkeypatch.setenv("VISUAL_ASSET_PROVIDER", "none")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        job_id = _ready_job_id()
        result = render_preview(job_id)
        report = json.loads(Path(result.report_output_path).read_text(encoding="utf-8"))
        assert report["assets_used"]
        assert report["fallback_used"] is True
        assert report["assets_used"][0]["asset_type"] == "generated"
    finally:
        get_settings.cache_clear()


def test_thumbnail_variants_are_created(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _ready_job_id()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        assets = [asset.to_dict() for asset in select_assets_for_job(job, json.loads(job.scene_plan_json)["scenes"][:1])]
        paths = generate_thumbnail_variants(job, assets=assets)
    assert len(paths) == 3
    assert all(Path(path).exists() for path in paths)


def test_visual_provider_status_cli_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "visual-provider-status"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "selected visual provider:" in result.stdout
    assert "fallback mode:" in result.stdout


def test_generate_thumbnail_variants_cli_works(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _ready_job_id()
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "generate-thumbnail-variants", "--id", str(job_id)],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "thumbnail variants:" in result.stdout


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
            self.scene_plan_json = "{}"

    return Job(title)
