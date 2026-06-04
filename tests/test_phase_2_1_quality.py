import json
import subprocess
import sys
from pathlib import Path

from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.models.content import VideoJob
from app.providers.factory import get_llm_provider, get_provider_status
from app.services.rendering.captions import caption_from_scene
from app.services.rendering.audio import generate_silent_audio
from app.services.rendering.quality import render_quality_warnings
from app.services.rendering.renderer import render_preview
from app.services.rendering.thumbnails import generate_thumbnail
from app.services.rendering.visual_templates import create_short_scene_clip, create_short_scene_image
from app.services.review import clear_dev_data, list_review_items, set_approval_status
from app.services.video_job_service import create_short_job


def test_provider_status_command_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "provider-status"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "selected provider:" in result.stdout
    assert "using mock fallback:" in result.stdout


def test_mock_fallback_works_when_configured_key_missing(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        status = get_provider_status()
        provider = get_llm_provider()
        assert status.selected_provider == "openai"
        assert status.using_mock_fallback is True
        assert provider.name == "mock"
    finally:
        get_settings.cache_clear()


def test_scene_text_generic_warning() -> None:
    warnings = render_quality_warnings(
        [{"scene_number": 1, "on_screen_text": "WHY NOW?", "voiceover": "Why now matters"}],
        thumbnail_text="SEARCH JUST SHIFTED",
        short=True,
    )
    assert "scene_1_generic_main_text" in warnings


def test_caption_is_shortened() -> None:
    caption = caption_from_scene(
        {"voiceover": "0-3 sec hook: Search is moving from links to answers much faster than most people expected"},
        short=True,
    )
    assert len(caption.split()) <= 8
    assert "0-3" not in caption


def test_premium_template_returns_image_and_clip() -> None:
    scene = {
        "scene_number": 1,
        "layout": "hook",
        "on_screen_text": "Search is moving\nfrom links to answers",
        "voiceover": "Search is moving from links to answers.",
    }
    image = create_short_scene_image(scene, (270, 480))
    assert image.size == (270, 480)
    clip = create_short_scene_clip(scene, (270, 480), 0.25)
    assert clip.duration == 0.25
    clip.close()


def test_thumbnail_output_exists(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _ready_job_id()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        path = generate_thumbnail(job, f"renders/thumbnails/phase-2-1-{job_id}.png")
    assert Path(path).exists()
    assert Path(path).suffix == ".png"


def test_render_preview_creates_short_preview(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _ready_job_id()
    result = render_preview(job_id)
    assert result.status == "preview"
    assert result.duration_seconds >= 10
    assert result.width == 1080
    assert result.height == 1920
    assert result.fps == 30
    assert result.has_audio is True
    assert Path(result.render_output_path).name.endswith("_preview.mp4")
    assert Path(result.render_output_path).exists()
    assert Path(result.thumbnail_output_path).exists()


def test_render_report_includes_quality_warnings(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _ready_job_id()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        plan = json.loads(job.scene_plan_json)
        plan["scenes"][0]["on_screen_text"] = "WHY NOW?"
        job.scene_plan_json = json.dumps(plan)
        db.add(job)
        db.commit()
    result = render_preview(job_id)
    report = json.loads(Path(result.report_output_path).read_text(encoding="utf-8"))
    assert "scene_1_generic_main_text" in report["warnings"]
    assert report["width"] == 1080
    assert report["height"] == 1920
    assert report["fps"] == 30
    assert report["duration_seconds"] >= 10
    assert report["has_audio"] is True
    assert report["preview"] is True
    assert report["scene_count"] >= 3


def test_silent_audio_fallback_creates_audio_file() -> None:
    output = Path("storage") / "test_silent_audio.wav"
    output.unlink(missing_ok=True)
    path = generate_silent_audio(1.0, str(output))
    assert Path(path).exists()
    assert Path(path).stat().st_size > 1000


def test_inspect_render_command_works(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _ready_job_id()
    result = render_preview(job_id)
    completed = subprocess.run(
        [sys.executable, "-m", "app.cli", "inspect-render", "--path", result.render_output_path],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "resolution: 1080x1920" in completed.stdout
    assert "has_audio: True" in completed.stdout


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
