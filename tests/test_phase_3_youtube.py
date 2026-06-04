import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.main import app
from app.models.content import VideoJob, YouTubeUpload
from app.services.review import clear_dev_data, list_review_items, set_approval_status
from app.services.video_job_service import create_short_job
from app.services.youtube.upload_checks import run_upload_checks
from app.services.youtube.upload_review import build_upload_checklist, mark_upload_reviewed, select_thumbnail_variant
from app.services.youtube.upload_service import upload_video, youtube_status
from app.services.youtube.uploader import FakeYouTubeUploader


def test_youtube_status_with_missing_credentials(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with SessionLocal() as db:
            status = youtube_status(db)
        assert status["upload_enabled"] is False
        assert status["privacy_status"] == "private"
    finally:
        get_settings.cache_clear()


def test_upload_blocked_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "false")
    job_id = _rendered_job(monkeypatch)
    _approve_upload_review(job_id)
    with SessionLocal() as db:
        report = upload_video(db, job_id, uploader=FakeYouTubeUploader())
    assert report["upload_status"] == "failed"
    assert "YouTube upload disabled." in report["errors"]


def test_upload_blocked_when_privacy_not_private(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_PRIVACY_STATUS", "public")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        job_id = _rendered_job(monkeypatch)
        _approve_upload_review(job_id)
        with SessionLocal() as db:
            report = upload_video(db, job_id, uploader=FakeYouTubeUploader())
        assert report["upload_status"] == "failed"
        assert "Privacy status must be private." in report["errors"]
    finally:
        get_settings.cache_clear()


def test_upload_checks_pass_for_rendered_job(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_PRIVACY_STATUS", "private")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        job_id = _rendered_job(monkeypatch)
        _approve_upload_review(job_id)
        with SessionLocal() as db:
            job = db.get(VideoJob, job_id)
            checks = run_upload_checks(db, job)
        assert checks["passed"] is True
    finally:
        get_settings.cache_clear()


def test_mocked_private_upload_stores_video_id(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_PRIVACY_STATUS", "private")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        job_id = _rendered_job(monkeypatch)
        _approve_upload_review(job_id)
        with SessionLocal() as db:
            report = upload_video(db, job_id, uploader=FakeYouTubeUploader())
            upload = db.query(YouTubeUpload).filter(YouTubeUpload.job_id == job_id).one()
        assert report["upload_status"] == "uploaded_private"
        assert upload.youtube_video_id.startswith("private_mock_")
        assert Path(report["report_path"]).exists()
    finally:
        get_settings.cache_clear()


def test_upload_blocked_if_already_uploaded(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_PRIVACY_STATUS", "private")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        job_id = _rendered_job(monkeypatch)
        _approve_upload_review(job_id)
        with SessionLocal() as db:
            upload_video(db, job_id, uploader=FakeYouTubeUploader())
            second = upload_video(db, job_id, uploader=FakeYouTubeUploader())
        assert second["upload_status"] == "failed"
        assert "Job is already uploaded." in second["errors"]
    finally:
        get_settings.cache_clear()


def test_upload_blocked_if_job_not_rendered(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_PRIVACY_STATUS", "private")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        init_db()
        with SessionLocal() as db:
            clear_dev_data(db)
        run_daily_job()
        with SessionLocal() as db:
            item = list_review_items(db)[0]
            set_approval_status(db, item, "approved")
            job = create_short_job(db, item.id)
            report = upload_video(db, job.id, uploader=FakeYouTubeUploader())
        assert "Job must be rendered before upload." in report["errors"]
    finally:
        get_settings.cache_clear()


def test_upload_blocked_if_file_missing(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_PRIVACY_STATUS", "private")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        job_id = _rendered_job(monkeypatch)
        _approve_upload_review(job_id)
        with SessionLocal() as db:
            job = db.get(VideoJob, job_id)
            job.render_output_path = "renders/shorts/missing.mp4"
            db.add(job)
            db.commit()
            report = upload_video(db, job_id, uploader=FakeYouTubeUploader())
        assert "Rendered video file missing." in report["errors"]
    finally:
        get_settings.cache_clear()


def test_daily_upload_limit_enforced(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_PRIVACY_STATUS", "private")
    monkeypatch.setenv("YOUTUBE_DAILY_UPLOAD_LIMIT", "0")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        job_id = _rendered_job(monkeypatch)
        _approve_upload_review(job_id)
        with SessionLocal() as db:
            report = upload_video(db, job_id, uploader=FakeYouTubeUploader())
        assert "Daily upload limit reached." in report["errors"]
    finally:
        get_settings.cache_clear()


def test_youtube_api_routes_exist() -> None:
    client = TestClient(app)
    assert client.get("/youtube/status").status_code == 200
    assert client.get("/uploads").status_code == 200


def test_upload_blocked_when_checklist_not_reviewed(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_PRIVACY_STATUS", "private")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        job_id = _rendered_job(monkeypatch)
        with SessionLocal() as db:
            report = upload_video(db, job_id, uploader=FakeYouTubeUploader())
        assert "Final upload review is not approved." in report["errors"]
    finally:
        get_settings.cache_clear()


def test_mark_upload_reviewed_sets_final_gate(monkeypatch) -> None:
    job_id = _rendered_job(monkeypatch)
    with SessionLocal() as db:
        job = mark_upload_reviewed(db, job_id)
        checklist = build_upload_checklist(db, job)
    assert job.upload_review_approved is True
    assert checklist["final_review_approved"] is True


def test_select_thumbnail_variant(monkeypatch) -> None:
    job_id = _rendered_job(monkeypatch)
    variant_path = Path("renders/thumbnails") / f"{job_id}_a.png"
    variant_path.parent.mkdir(parents=True, exist_ok=True)
    variant_path.write_bytes(b"fake png")
    with SessionLocal() as db:
        job = select_thumbnail_variant(db, job_id, "a")
    assert job.selected_thumbnail_path.endswith(f"{job_id}_a.png")


def _rendered_job(monkeypatch) -> int:
    monkeypatch.setenv("RENDER_TEST_MODE", "1")
    monkeypatch.setenv("VOICE_PROVIDER", "silent")
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    os.environ["MODEL_PROVIDER"] = "mock"
    from app.core.config import get_settings

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
        job_id = job.id
    video_path = Path("renders/shorts") / f"{job_id}_preview.mp4"
    thumbnail_path = Path("renders/thumbnails") / f"{job_id}_preview.png"
    report_path = Path("renders/reports") / f"{job_id}_preview.json"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"0" * 4096)
    thumbnail_path.write_bytes(b"fake png")
    report_path.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "width": 1080,
                "height": 1920,
                "has_audio": True,
                "voice": {"provider": "silent", "fallback_used": True},
                "assets_used": [{"provider": "generated", "license_note": "Generated fallback asset."}],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        job.status = "rendered"
        job.render_output_path = str(video_path)
        job.thumbnail_output_path = str(thumbnail_path)
        db.add(job)
        db.commit()
    return job_id


def _approve_upload_review(job_id: int) -> None:
    token_path = Path("storage/youtube/token.json")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text("{}", encoding="utf-8")
    with SessionLocal() as db:
        job = mark_upload_reviewed(db, job_id)
        db.add(job)
        db.commit()
