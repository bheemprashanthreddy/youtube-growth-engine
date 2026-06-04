import json
from pathlib import Path

from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.models.content import VideoJob
from app.services.rendering.renderer import render_batch, reset_failed_renders, validate_render_result
from app.services.review import clear_dev_data, list_review_items, set_approval_status
from app.services.video_job_service import create_both_jobs, create_short_job, jobs_summary


def test_batch_renders_only_ready_jobs(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    _two_jobs()
    report = render_batch(limit=1, format_type="short")
    assert report["total_processed"] == 1
    assert report["rendered_count"] == 1


def test_batch_skips_rendered_jobs(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    job_id = _ready_job()
    render_batch(limit=1)
    report = render_batch(limit=1)
    assert report["total_processed"] == 0


def test_batch_report_is_written(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    _ready_job()
    report = render_batch(limit=1)
    assert Path(report["report_path"]).exists()


def test_reset_failed_renders_works() -> None:
    job_id = _ready_job()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        job.status = "failed"
        db.add(job)
        db.commit()
        count = reset_failed_renders(db)
    assert count == 1


def test_render_validation_passes_for_mocked_output(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    _ready_job()
    report = render_batch(limit=1)
    validation = report["job_results"][0]["validation"]
    assert validation["passed"] is True


def test_render_summary_counts() -> None:
    _ready_job()
    with SessionLocal() as db:
        summary = jobs_summary(db)
    assert "ready_for_render" in summary


def _ready_job() -> int:
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


def _two_jobs() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        item = list_review_items(db)[0]
        set_approval_status(db, item, "approved")
        create_both_jobs(db, item.id)
