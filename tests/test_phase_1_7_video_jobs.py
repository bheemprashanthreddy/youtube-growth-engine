import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.services.review import clear_dev_data, list_review_items, review_summary, set_approval_status
from app.services.scene_planner import create_long_scene_plan, create_short_scene_plan
from app.services.video_job_service import (
    create_both_jobs,
    create_jobs_for_approved,
    create_long_job,
    create_short_job,
    jobs_summary,
    list_video_jobs,
)


def test_cannot_create_job_from_unapproved_review_item() -> None:
    item_id = _fresh_review_item_id()
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            create_short_job(db, item_id)


def test_can_create_short_job_from_approved_item() -> None:
    item_id = _approved_review_item_id()
    with SessionLocal() as db:
        job = create_short_job(db, item_id)
        assert job.format_type == "short"
        assert job.status == "ready_for_render"
        assert Path(job.package_path).exists()


def test_can_create_long_job_from_ready_item() -> None:
    item_id = _approved_review_item_id(mark_ready=True)
    with SessionLocal() as db:
        job = create_long_job(db, item_id)
        assert job.format_type == "long"
        assert job.aspect_ratio == "16:9"
        assert Path(job.package_path).exists()


def test_can_create_both_jobs_from_approved_item() -> None:
    item_id = _approved_review_item_id()
    with SessionLocal() as db:
        jobs = create_both_jobs(db, item_id)
        assert {job.format_type for job in jobs} == {"short", "long"}


def test_duplicate_jobs_not_created_on_repeated_calls() -> None:
    item_id = _approved_review_item_id()
    with SessionLocal() as db:
        first = create_short_job(db, item_id)
        second = create_short_job(db, item_id)
        assert first.id == second.id
        assert len(list_video_jobs(db)) == 1


def test_scene_planner_returns_valid_short_scene_plan() -> None:
    item_id = _fresh_review_item_id()
    with SessionLocal() as db:
        item = next(row for row in list_review_items(db) if row.id == item_id)
        plan = create_short_scene_plan(item)
        assert plan["aspect_ratio"] == "9:16"
        assert 6 <= len(plan["scenes"]) <= 10
        assert {"scene_number", "duration_seconds", "voiceover", "visual_prompt"} <= set(plan["scenes"][0])


def test_scene_planner_returns_valid_long_scene_plan() -> None:
    item_id = _fresh_review_item_id()
    with SessionLocal() as db:
        item = next(row for row in list_review_items(db) if row.id == item_id)
        plan = create_long_scene_plan(item)
        assert plan["aspect_ratio"] == "16:9"
        assert 8 <= len(plan["scenes"]) <= 15
        assert {"scene_number", "section_title", "estimated_duration_seconds", "narration_goal"} <= set(plan["scenes"][0])


def test_jobs_summary_works() -> None:
    item_id = _approved_review_item_id()
    with SessionLocal() as db:
        create_both_jobs(db, item_id)
        summary = jobs_summary(db)
        assert summary["total_jobs"] == 2
        assert summary["short_jobs"] == 1
        assert summary["long_jobs"] == 1


def test_job_json_package_is_created() -> None:
    item_id = _approved_review_item_id()
    with SessionLocal() as db:
        job = create_short_job(db, item_id)
        package = json.loads(Path(job.package_path).read_text(encoding="utf-8"))
        assert package["job"]["id"] == job.id
        assert package["renderer_note"].startswith("Phase 2 renderer")


def test_review_summary_approved_without_jobs_count() -> None:
    item_id = _approved_review_item_id()
    with SessionLocal() as db:
        summary = review_summary(db)
        assert summary["approved_without_jobs"] >= 1
        create_short_job(db, item_id)
        updated = review_summary(db)
        assert updated["approved_without_jobs"] <= summary["approved_without_jobs"]


def test_create_jobs_cli_and_jobs_summary_cli_work() -> None:
    _approved_review_item_id()
    create = subprocess.run(
        [sys.executable, "-m", "app.cli", "create-jobs", "--approved", "--format", "short"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "created or found jobs:" in create.stdout
    summary = subprocess.run(
        [sys.executable, "-m", "app.cli", "jobs-summary"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "total jobs:" in summary.stdout


def _fresh_review_item_id() -> int:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        return list_review_items(db)[0].id


def _approved_review_item_id(mark_ready: bool = False) -> int:
    item_id = _fresh_review_item_id()
    with SessionLocal() as db:
        item = next(row for row in list_review_items(db) if row.id == item_id)
        set_approval_status(db, item, "approved")
        if mark_ready:
            set_approval_status(db, item, "ready_for_render")
    return item_id
