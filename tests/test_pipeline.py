from app.db.session import init_db
from app.jobs.daily import run_daily_job
from app.jobs.trend_scan import run_trend_scan
from app.services.outputs import get_latest_output
from app.services.trends import load_source_topics, normalize_topics


def test_normalize_topics_removes_duplicates() -> None:
    topics = load_source_topics()
    normalized = normalize_topics([topics[0], topics[0], topics[1]])
    assert len(normalized) == 2


def test_daily_pipeline_creates_outputs() -> None:
    init_db()
    result = run_daily_job()
    assert result.selected_count > 0
    assert any(path.endswith("manifest.json") for path in result.outputs)
    latest = get_latest_output()
    assert latest["channel"] == "CuriousSignal"
    assert latest["items"][0]["quality_gate"]["final_status"] in {"approved", "needs_review", "rejected"}


def test_trend_scan_creates_phase_1_5_outputs() -> None:
    result = run_trend_scan()
    assert result.selected_count > 0
    assert any(path.endswith("trends_raw.json") for path in result.outputs)
    assert any(path.endswith("trends_scored.json") for path in result.outputs)
    assert any(path.endswith("daily_run.json") for path in result.outputs)
