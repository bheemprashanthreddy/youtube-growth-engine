import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import reset_settings_cache
from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.services.rendering.renderer import render_preview
from app.services.review import clear_dev_data, list_review_items, set_approval_status
from app.services.video_job_service import create_long_job, create_short_job
from app.services.voice.voice_cache import voice_cache_path
from app.services.voice.voice_service import _write_silent_wav, generate_voice_for_job, voice_provider_status


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_voice_provider_status_works_without_keys(monkeypatch) -> None:
    monkeypatch.setenv("VOICE_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    reset_settings_cache()
    status = voice_provider_status()
    assert status.selected_provider == "openai"
    assert status.fallback_mode is True


def test_silent_provider_creates_audio_file(monkeypatch) -> None:
    monkeypatch.setenv("VOICE_PROVIDER", "silent")

    reset_settings_cache()
    job_id = _ready_job_id()
    with SessionLocal() as db:
        job = db.get(__import__("app.models.content", fromlist=["VideoJob"]).VideoJob, job_id)
        scenes = json.loads(job.scene_plan_json)["scenes"][:2]
        result = generate_voice_for_job(job, scenes, preview=True)
    assert Path(result.combined_audio_path).exists()
    assert result.fallback_used is True


def test_voice_cache_path_is_safe() -> None:
    path = voice_cache_path(1, 1, "hello/../world", "edge", "curious_signal_default")
    assert ".." not in path.name
    assert path.suffix == ".wav"


def test_render_report_includes_voice_metadata(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    monkeypatch.setenv("VOICE_PROVIDER", "silent")
    reset_settings_cache()
    job_id = _ready_job_id()
    result = render_preview(job_id)
    report = json.loads(Path(result.report_output_path).read_text(encoding="utf-8"))
    assert report["voice"]["provider"] == "silent"
    assert report["voice"]["voice_files"]
    assert report["has_audio"] is True


def test_voice_provider_cache_reset_respects_env_change(monkeypatch) -> None:
    monkeypatch.setenv("VOICE_PROVIDER", "openai")
    reset_settings_cache()
    assert voice_provider_status().selected_provider == "openai"
    monkeypatch.setenv("VOICE_PROVIDER", "silent")
    reset_settings_cache()
    assert voice_provider_status().selected_provider == "silent"


def test_voice_provider_status_cli_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "voice-provider-status"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "selected voice provider:" in result.stdout


def test_long_form_voice_generation_duration_is_capped(monkeypatch) -> None:
    monkeypatch.setenv("VOICE_PROVIDER", "silent")
    monkeypatch.setenv("VOICE_MAX_LONG_SECONDS", "3")

    reset_settings_cache()
    job_id = _ready_long_job_id()
    with SessionLocal() as db:
        job = db.get(__import__("app.models.content", fromlist=["VideoJob"]).VideoJob, job_id)
        scenes = json.loads(job.scene_plan_json)["scenes"]
        for scene in scenes:
            scene["estimated_duration_seconds"] = 120
        result = generate_voice_for_job(job, scenes, preview=False)
    assert result.capped is True
    assert result.total_audio_duration <= 3.1
    assert "long_form_voice_capped_for_mvp" in result.warnings


def test_silence_writer_cleans_partial_failed_audio_file(monkeypatch) -> None:
    output = Path("storage") / "test_partial_voice_failure.wav"
    output.unlink(missing_ok=True)

    def fail_after_partial_write(wav, frame_count, channels, sample_width, sample_rate):
        wav.writeframes(b"\x00\x00")
        raise RuntimeError("forced write failure")

    monkeypatch.setattr("app.services.voice.voice_service._write_silence_frames", fail_after_partial_write)
    with pytest.raises(RuntimeError):
        _write_silent_wav(output, 2)
    assert not output.exists()


def test_generate_voice_cli_for_long_job_does_not_crash(monkeypatch) -> None:
    monkeypatch.setenv("VOICE_PROVIDER", "silent")
    monkeypatch.setenv("VOICE_MAX_LONG_SECONDS", "3")

    reset_settings_cache()
    job_id = _ready_long_job_id()
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "generate-voice", "--id", str(job_id)],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "job id:" in result.stdout
    assert "format: long" in result.stdout
    assert "capped:" in result.stdout


def test_generate_voice_cli_missing_job_lists_existing_jobs(monkeypatch) -> None:
    monkeypatch.setenv("VOICE_PROVIDER", "silent")
    reset_settings_cache()
    _ready_job_id()
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "generate-voice", "--id", "99999"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "Video job #99999 not found." in result.stderr
    assert "Existing ready/renderable jobs:" in result.stderr


def test_short_voice_generation_still_works(monkeypatch) -> None:
    monkeypatch.setenv("VOICE_PROVIDER", "silent")

    reset_settings_cache()
    job_id = _ready_job_id()
    with SessionLocal() as db:
        job = db.get(__import__("app.models.content", fromlist=["VideoJob"]).VideoJob, job_id)
        scenes = json.loads(job.scene_plan_json)["scenes"][:2]
        result = generate_voice_for_job(job, scenes, preview=False)
    assert Path(result.combined_audio_path).exists()
    assert result.total_audio_duration > 0


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


def _ready_long_job_id() -> int:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        item = list_review_items(db)[0]
        set_approval_status(db, item, "approved")
        job = create_long_job(db, item.id)
        job.status = "ready_for_render"
        db.add(job)
        db.commit()
        return job.id
