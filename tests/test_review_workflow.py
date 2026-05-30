from app.db.session import SessionLocal, init_db
from app.jobs.daily import run_daily_job
from app.services.review import clear_dev_data, get_review_item, list_review_items, set_approval_status, update_notes


def test_review_items_created_by_daily_run() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    result = run_daily_job()
    with SessionLocal() as db:
        items = list_review_items(db)
        assert len(items) >= result.selected_count
        assert items[0].approval_status in {"generated", "needs_review"}
        assert items[0].short_script
        assert items[0].title_options


def test_approval_status_transitions_and_notes() -> None:
    init_db()
    with SessionLocal() as db:
        clear_dev_data(db)
    run_daily_job()
    with SessionLocal() as db:
        item = list_review_items(db)[0]
        set_approval_status(db, item, "approved")
        approved = get_review_item(db, item.id)
        assert approved is not None
        assert approved.approval_status == "approved"

        set_approval_status(db, approved, "ready_for_render")
        ready = get_review_item(db, item.id)
        assert ready is not None
        assert ready.approval_status == "ready_for_render"

        update_notes(db, ready, "Needs a tighter source check before render.")
        noted = get_review_item(db, item.id)
        assert noted is not None
        assert "source check" in noted.reviewer_notes
