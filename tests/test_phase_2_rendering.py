import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.models.content import VideoJob
from app.services.rendering.renderer import render_job, render_ready_jobs
from app.services.rendering.thumbnails import generate_thumbnail
from app.services.review import clear_dev_data, list_review_items, set_approval_status
from app.services.video_job_service import create_both_jobs, create_short_job, list_video_jobs


def test_cannot_render_non_ready_job(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _job_id(status="queued")
    with pytest.raises(ValueError):
        render_job(job_id)


def test_render_service_creates_expected_output_paths(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _job_id(status="ready_for_render")
    result = render_job(job_id)
    assert result.status == "rendered"
    assert Path(result.render_output_path).exists()
    assert Path(result.thumbnail_output_path).exists()
    assert Path(result.report_output_path).exists()


def test_thumbnail_generation_creates_png(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _job_id(status="ready_for_render")
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        path = generate_thumbnail(job, f"renders/thumbnails/test-{job_id}.png")
    assert Path(path).exists()
    assert Path(path).suffix == ".png"


def test_failed_render_stores_error_message(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _job_id(status="ready_for_render")

    def fail_render(job):
        raise RuntimeError("forced render failure")

    monkeypatch.setattr("app.services.rendering.renderer._render", fail_render)
    result = render_job(job_id)
    assert result.status == "failed"
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        assert "forced render failure" in job.error_message


def test_render_report_json_is_created(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _job_id(status="ready_for_render")
    result = render_job(job_id)
    report = json.loads(Path(result.report_output_path).read_text(encoding="utf-8"))
    assert report["job_id"] == job_id
    assert report["status"] == "rendered"


def test_render_summary_cli_works(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    _job_id(status="ready_for_render")
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "render-summary"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "total jobs:" in result.stdout


def test_render_ready_respects_limit(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        item = list_review_items(db)[0]
        set_approval_status(db, item, "approved")
        create_both_jobs(db, item.id)
    results = render_ready_jobs(limit=1)
    assert len(results) == 1
    with SessionLocal() as db:
        rendered = [job for job in list_video_jobs(db) if job.status == "rendered"]
        ready = [job for job in list_video_jobs(db) if job.status == "ready_for_render"]
    assert len(rendered) == 1
    assert len(ready) == 1


def _job_id(status: str) -> int:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        item = list_review_items(db)[0]
        set_approval_status(db, item, "approved")
        job = create_short_job(db, item.id)
        job.status = status
        db.add(job)
        db.commit()
        return job.id
