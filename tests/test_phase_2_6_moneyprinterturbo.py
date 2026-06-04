import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

from app.core.config import get_settings
from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.models.content import VideoJob
from app.services.rendering.engines import build_moneyprinterturbo_payload, render_engine_status, resolve_render_engine
from app.services.rendering.engines.moneyprinterturbo_engine import MoneyPrinterTurboEngine
from app.services.rendering.renderer import render_job
from app.services.review import clear_dev_data, list_review_items, set_approval_status
from app.services.video_job_service import create_short_job
from app.services.youtube.upload_checks import run_upload_checks


def test_render_engine_status_works_when_moneyprinterturbo_disabled(monkeypatch) -> None:
    monkeypatch.setenv("MONEYPRINTERTURBO_ENABLED", "false")
    get_settings.cache_clear()
    try:
        status = render_engine_status()
        assert status["selected_engine"] == "native"
        assert status["native_available"] is True
        assert status["moneyprinterturbo_enabled"] is False
        assert status["moneyprinterturbo_reachable"] is False
    finally:
        get_settings.cache_clear()


def test_moneyprinterturbo_request_preview_payload_maps_job(monkeypatch) -> None:
    monkeypatch.setenv("MONEYPRINTERTURBO_USE_BACKGROUND_MUSIC", "false")
    get_settings.cache_clear()
    try:
        job_id = _ready_job_id()
        with SessionLocal() as db:
            job = db.get(VideoJob, job_id)
            payload = build_moneyprinterturbo_payload(job)
        assert payload["subject"] == job.title
        assert payload["format_type"] == "short"
        assert payload["aspect_ratio"] == "9:16"
        assert payload["resolution"] == "1080x1920"
        assert payload["subtitle_enabled"] is True
        assert payload["background_music_enabled"] is False
        assert payload["upload_public"] is False
        assert payload["script"]
        assert payload["video_terms"]
    finally:
        get_settings.cache_clear()


def test_moneyprinterturbo_adapter_fails_gracefully_when_service_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("MONEYPRINTERTURBO_ENABLED", "true")
    get_settings.cache_clear()
    try:
        job_id = _ready_job_id()

        result = MoneyPrinterTurboEngine().render_job(job_id)
        assert result.status == "failed"
        assert "unreachable" in result.error_message
        assert Path(result.report_output_path).exists()
        with SessionLocal() as db:
            job = db.get(VideoJob, job_id)
            assert job.status == "ready_for_render"
    finally:
        get_settings.cache_clear()


def test_mocked_moneyprinterturbo_success_imports_output_paths(monkeypatch) -> None:
    monkeypatch.setenv("MONEYPRINTERTURBO_ENABLED", "true")
    monkeypatch.setenv("MONEYPRINTERTURBO_USE_BACKGROUND_MUSIC", "false")
    get_settings.cache_clear()
    try:
        job_id = _ready_job_id()
        source_video, source_thumbnail = _fake_external_outputs(job_id)

        def fake_post(url, payload, *, timeout):
            return {"task_id": "task-1", "video_path": str(source_video), "thumbnail_path": str(source_thumbnail)}

        monkeypatch.setattr(MoneyPrinterTurboEngine, "get_status", lambda self: {"reachable": True, "warnings": []})
        monkeypatch.setattr("app.services.rendering.engines.moneyprinterturbo_engine._post_json", fake_post)
        result = MoneyPrinterTurboEngine().render_job(job_id)
        assert result.status == "rendered"
        assert Path(result.render_output_path).exists()
        assert Path(result.thumbnail_output_path).exists()
        report = json.loads(Path(result.report_output_path).read_text(encoding="utf-8"))
        assert report["render_engine"] == "moneyprinterturbo"
        assert report["external_service_used"] is True
        assert Path(report["request_payload_path"]).exists()
        assert Path(report["response_payload_path"]).exists()
        assert report["copyright_music_flags"]["background_music_enabled"] is False
    finally:
        get_settings.cache_clear()


def test_native_engine_still_works(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    monkeypatch.setenv("VOICE_PROVIDER", "silent")
    get_settings.cache_clear()
    try:
        job_id = _ready_job_id()
        result = resolve_render_engine("native").render_job(job_id)
        assert result.status == "rendered"
        assert Path(result.render_output_path).exists()
    finally:
        get_settings.cache_clear()


def test_upload_workflow_still_requires_rendered_job(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()
    try:
        job_id = _ready_job_id()
        with SessionLocal() as db:
            job = db.get(VideoJob, job_id)
            checks = run_upload_checks(db, job)
        assert "Job must be rendered before upload." in checks["blockers"]
    finally:
        get_settings.cache_clear()


def test_render_engine_status_cli_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "render-engine-status"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "selected engine:" in result.stdout
    assert "MoneyPrinterTurbo enabled:" in result.stdout


def test_moneyprinterturbo_request_preview_cli_works() -> None:
    job_id = _ready_job_id()
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "moneyprinterturbo-request-preview", "--id", str(job_id)],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["source"]["video_job_id"] == job_id
    assert payload["background_music_enabled"] is False


def _ready_job_id() -> int:
    os.environ["MODEL_PROVIDER"] = "mock"
    os.environ["VOICE_PROVIDER"] = "silent"
    os.environ["RENDER_TEST_MODE"] = "1"
    get_settings.cache_clear()
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


def _fake_external_outputs(job_id: int) -> tuple[Path, Path]:
    root = Path("storage") / "test_moneyprinterturbo"
    root.mkdir(parents=True, exist_ok=True)
    video = root / f"{job_id}.mp4"
    video.write_bytes(b"0" * 4096)
    thumbnail = root / f"{job_id}.png"
    Image.new("RGB", (1280, 720), "#0b1020").save(thumbnail)
    return video, thumbnail
