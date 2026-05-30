from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_daily_run_and_read_routes() -> None:
    client = TestClient(app)
    scan_response = client.post("/run/trend-scan")
    assert scan_response.status_code == 200

    run_response = client.post("/run/daily")
    assert run_response.status_code == 200
    assert run_response.json()["selected_count"] > 0

    topics_response = client.get("/topics")
    assert topics_response.status_code == 200
    assert len(topics_response.json()) > 0

    scripts_response = client.get("/scripts")
    assert scripts_response.status_code == 200
    assert len(scripts_response.json()) > 0

    latest_response = client.get("/outputs/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["channel"] == "CuriousSignal"

    raw_response = client.get("/trends/raw")
    assert raw_response.status_code == 200
    assert len(raw_response.json()) > 0

    scored_response = client.get("/trends/scored")
    assert scored_response.status_code == 200
    assert len(scored_response.json()) > 0

    top_response = client.get("/topics/top")
    assert top_response.status_code == 200
    assert len(top_response.json()) > 0

    review_response = client.get("/review/items")
    assert review_response.status_code == 200
    review_items = review_response.json()
    assert len(review_items) > 0

    item_id = review_items[0]["id"]
    approve_response = client.post(f"/review/items/{item_id}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["approval_status"] == "approved"

    notes_response = client.post(f"/review/items/{item_id}/notes", data={"notes": "API test note"})
    assert notes_response.status_code == 200
    assert notes_response.json()["reviewer_notes"] == "API test note"

    ready_response = client.post(f"/review/items/{item_id}/mark-ready-for-render")
    assert ready_response.status_code == 200
    assert ready_response.json()["approval_status"] == "ready_for_render"

    dashboard_response = client.get("/review")
    assert dashboard_response.status_code == 200
    assert "CuriousSignal Review Dashboard" in dashboard_response.text
