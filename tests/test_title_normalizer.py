import subprocess
import sys

from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.services.review import clear_dev_data, list_review_items, set_approval_status
from app.services.video_job_service import create_short_job
from app.utils.title_normalizer import choose_video_job_title, normalize_title


def test_complete_why_title_stays_clean() -> None:
    title = "Why AI search engines are changing how people find information online"
    assert normalize_title(title) == title


def test_duplicate_why_prefix_is_removed() -> None:
    assert (
        normalize_title("Why Why AI search engines are changing how people find information online")
        == "Why AI search engines are changing how people find information online"
    )


def test_video_title_does_not_wrap_complete_question() -> None:
    fallback = "Why AI search engines are changing how people find information online"
    option = "Why Why AI search engines are changing how people find information online Is Suddenly Everywhere"
    assert choose_video_job_title([option], fallback) == fallback


def test_video_job_creation_uses_clean_title() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        item = list_review_items(db)[0]
        set_approval_status(db, item, "approved")
        job = create_short_job(db, item.id)
        assert "Why Why" not in job.title
        assert not job.title.endswith("Is Suddenly Everywhere")


def test_normalize_job_titles_cli_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "normalize-job-titles"],
        cwd="C:/MVP/youtube-growth-engine",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "normalized video job titles:" in result.stdout
