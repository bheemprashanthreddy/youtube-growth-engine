import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.db.session import get_db, init_db
from app.jobs.daily import run_daily_job
from app.jobs.trend_scan import run_trend_scan
from app.models.content import ContentOutput, Topic
from app.services.outputs import get_latest_json_file, get_latest_output
from app.services.rendering.engines import build_moneyprinterturbo_payload, render_engine_status, resolve_render_engine
from app.services.rendering.engines.moneyprinterturbo_engine import MoneyPrinterTurboEngine
from app.services.rendering.renderer import render_batch, render_job, render_preview
from app.services.rendering.thumbnails import generate_thumbnail_variants
from app.services.review import (
    get_review_item,
    list_review_items,
    regenerate_metadata,
    regenerate_script,
    serialize_review_item,
    set_approval_status,
    update_notes,
)
from app.services.visual_assets.asset_selector import visual_provider_status
from app.services.youtube.upload_checks import run_upload_checks
from app.services.youtube.upload_service import list_uploads, upload_video, youtube_status
from app.services.youtube.upload_review import build_upload_checklist, mark_upload_reviewed, select_thumbnail_variant
from app.services.video_job_service import (
    create_both_jobs,
    create_long_job,
    create_short_job,
    jobs_summary,
    list_video_jobs,
    mark_job_ready_for_render,
    regenerate_scene_plan,
    require_video_job,
    serialize_video_job,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(BASE_DIR) / "app" / "templates"))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "youtube-growth-engine"}


@router.post("/run/daily")
def run_daily() -> dict[str, object]:
    init_db()
    result = run_daily_job()
    return result.model_dump()


@router.post("/run/trend-scan")
def run_scan() -> dict[str, object]:
    result = run_trend_scan()
    return result.model_dump()


@router.get("/topics")
def list_topics(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    rows = db.execute(select(Topic).order_by(Topic.score.desc(), Topic.created_at.desc())).scalars().all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "pillar": row.pillar,
            "score": row.score,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/scripts")
def list_scripts(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    rows = db.execute(select(ContentOutput).order_by(ContentOutput.created_at.desc())).scalars().all()
    return [
        {
            "id": row.id,
            "topic": row.topic_name,
            "quality_gate_status": row.quality_gate_status,
            "output_path": row.output_path,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/outputs/latest")
def latest_output() -> dict[str, object]:
    return get_latest_output()


@router.get("/trends/raw")
def trends_raw() -> dict[str, object] | list[dict[str, object]]:
    return get_latest_json_file("trends_raw.json")


@router.get("/trends/scored")
def trends_scored() -> dict[str, object] | list[dict[str, object]]:
    return get_latest_json_file("trends_scored.json")


@router.get("/topics/top")
def topics_top() -> list[dict[str, object]] | dict[str, object]:
    scored = get_latest_json_file("trends_scored.json")
    if isinstance(scored, dict) and scored.get("status") == "empty":
        return scored
    return [item for item in scored if item.get("status") != "rejected"][:10]


@router.get("/review/items")
def review_items(status: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [serialize_review_item(item) for item in list_review_items(db, status=status)]


@router.get("/jobs")
def jobs(request: Request, db: Session = Depends(get_db)):
    job_items = [serialize_video_job(job) for job in list_video_jobs(db)]
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(request, "jobs_dashboard.html", {"jobs": job_items})
    return job_items


@router.get("/jobs/{job_id}")
def job_detail(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return serialize_video_job(_require_video_job(db, job_id))


@router.get("/review/items/{item_id}")
def review_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    item = _require_review_item(db, item_id)
    return serialize_review_item(item)


@router.post("/review/items/{item_id}/approve")
def approve_review_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    item = _set_status_or_400(db, _require_review_item(db, item_id), "approved")
    return serialize_review_item(item)


@router.post("/review/items/{item_id}/reject")
def reject_review_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    item = _set_status_or_400(db, _require_review_item(db, item_id), "rejected")
    return serialize_review_item(item)


@router.post("/review/items/{item_id}/mark-ready-for-render")
def mark_ready_for_render(item_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    item = _set_status_or_400(db, _require_review_item(db, item_id), "ready_for_render")
    return serialize_review_item(item)


@router.post("/review/items/{item_id}/notes")
def notes_review_item(item_id: int, notes: str = Form(""), db: Session = Depends(get_db)) -> dict[str, object]:
    item = update_notes(db, _require_review_item(db, item_id), notes)
    return serialize_review_item(item)


@router.post("/review/items/{item_id}/regenerate-script")
def regenerate_review_script(item_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    item = regenerate_script(db, _require_review_item(db, item_id))
    return serialize_review_item(item)


@router.post("/review/items/{item_id}/regenerate-metadata")
def regenerate_review_metadata(item_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    item = regenerate_metadata(db, _require_review_item(db, item_id))
    return serialize_review_item(item)


@router.post("/review/items/{item_id}/create-short-job")
def create_short_job_route(item_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return serialize_video_job(_job_or_400(lambda: create_short_job(db, item_id)))


@router.post("/review/items/{item_id}/create-long-job")
def create_long_job_route(item_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return serialize_video_job(_job_or_400(lambda: create_long_job(db, item_id)))


@router.post("/review/items/{item_id}/create-both-jobs")
def create_both_jobs_route(item_id: int, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [serialize_video_job(job) for job in _job_or_400(lambda: create_both_jobs(db, item_id))]


@router.post("/jobs/{job_id}/regenerate-scene-plan")
def regenerate_scene_plan_route(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return serialize_video_job(_job_or_400(lambda: regenerate_scene_plan(db, job_id)))


@router.post("/jobs/{job_id}/mark-ready-for-render")
def mark_job_ready_route(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return serialize_video_job(_job_or_400(lambda: mark_job_ready_for_render(db, job_id)))


@router.post("/jobs/{job_id}/render")
def render_job_route(job_id: int) -> dict[str, object]:
    return render_job(job_id).__dict__


@router.post("/jobs/{job_id}/render/{engine}")
def render_job_with_engine_route(job_id: int, engine: str) -> dict[str, object]:
    return resolve_render_engine(engine).render_job(job_id).__dict__


@router.post("/jobs/{job_id}/render-preview")
def render_preview_route(job_id: int) -> dict[str, object]:
    return render_preview(job_id).__dict__


@router.post("/jobs/render-batch")
def render_batch_route(limit: int = 5, format_type: str | None = None) -> dict[str, object]:
    return render_batch(limit=limit, format_type=format_type)


@router.get("/render/summary")
def render_summary_route(db: Session = Depends(get_db)) -> dict[str, object]:
    return jobs_summary(db)


@router.get("/render-engine/status")
def render_engine_status_route() -> dict[str, object]:
    return render_engine_status()


@router.get("/moneyprinterturbo/status")
def moneyprinterturbo_status_route() -> dict[str, object]:
    return MoneyPrinterTurboEngine().get_status()


@router.get("/jobs/{job_id}/moneyprinterturbo-request-preview")
def moneyprinterturbo_request_preview_route(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return build_moneyprinterturbo_payload(_require_video_job(db, job_id))


@router.get("/jobs/{job_id}/render-report")
def render_report_route(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    job = _require_video_job(db, job_id)
    report_path = Path("renders") / "reports" / f"{job.id}.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Render report not found.")
    return json.loads(report_path.read_text(encoding="utf-8"))


@router.get("/visual-provider/status")
def visual_provider_status_route() -> dict[str, object]:
    return visual_provider_status().__dict__


@router.get("/youtube/status")
def youtube_status_route(db: Session = Depends(get_db)) -> dict[str, object]:
    return youtube_status(db)


@router.post("/jobs/{job_id}/upload-private")
def upload_private_route(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return upload_video(db, job_id)


@router.get("/jobs/{job_id}/upload-checklist")
def upload_checklist_route(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return build_upload_checklist(db, _require_video_job(db, job_id))


@router.post("/jobs/{job_id}/mark-upload-reviewed")
def mark_upload_reviewed_route(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return serialize_video_job(_job_or_400(lambda: mark_upload_reviewed(db, job_id)))


@router.post("/jobs/{job_id}/select-thumbnail")
def select_thumbnail_route(job_id: int, variant: str = Form(...), db: Session = Depends(get_db)) -> dict[str, object]:
    return serialize_video_job(_job_or_400(lambda: select_thumbnail_variant(db, job_id, variant)))


@router.get("/uploads")
def uploads_route(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [_serialize_upload(upload) for upload in list_uploads(db)]


@router.get("/uploads/{upload_id}")
def upload_detail_route(upload_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    uploads = [upload for upload in list_uploads(db) if upload.id == upload_id]
    if not uploads:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return _serialize_upload(uploads[0])


@router.post("/jobs/{job_id}/thumbnail-variants")
def thumbnail_variants_route(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    job = _require_video_job(db, job_id)
    paths = generate_thumbnail_variants(job)
    return {"job_id": job.id, "thumbnail_variants": paths}


@router.get("/review", response_class=HTMLResponse)
def review_dashboard(request: Request, status: str | None = None, db: Session = Depends(get_db)) -> HTMLResponse:
    items = [serialize_review_item(item) for item in list_review_items(db, status=status)]
    return templates.TemplateResponse(request, "review_dashboard.html", {"items": items, "status": status or ""})


@router.get("/review/{item_id}", response_class=HTMLResponse)
def review_detail(request: Request, item_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    item = serialize_review_item(_require_review_item(db, item_id))
    return templates.TemplateResponse(request, "review_detail.html", {"item": item})


@router.get("/jobs-ui", response_class=HTMLResponse)
def jobs_dashboard_alias(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    job_items = [serialize_video_job(job) for job in list_video_jobs(db)]
    return templates.TemplateResponse(request, "jobs_dashboard.html", {"jobs": job_items})


@router.get("/jobs/{job_id}/view", response_class=HTMLResponse)
def job_detail_page(request: Request, job_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    job = serialize_video_job(_require_video_job(db, job_id))
    job_model = _require_video_job(db, job_id)
    report = {}
    report_path = Path("renders") / "reports" / f"{job_id}.json"
    preview_report_path = Path("renders") / "reports" / f"{job_id}_preview.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    elif preview_report_path.exists():
        report = json.loads(preview_report_path.read_text(encoding="utf-8"))
    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {
            "job": job,
            "visual_provider": visual_provider_status().__dict__,
            "render_engine_status": render_engine_status(),
            "moneyprinterturbo_status": MoneyPrinterTurboEngine().get_status(),
            "moneyprinterturbo_request": build_moneyprinterturbo_payload(job_model),
            "render_report": report,
            "youtube_status": youtube_status(db),
            "upload_checks": run_upload_checks(db, job_model),
            "upload_checklist": build_upload_checklist(db, job_model),
        },
    )


@router.post("/review/{item_id}/action")
def review_ui_action(
    item_id: int,
    action: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    item = _require_review_item(db, item_id)
    if action == "approve":
        _set_status_or_400(db, item, "approved")
    elif action == "reject":
        _set_status_or_400(db, item, "rejected")
    elif action == "ready":
        _set_status_or_400(db, item, "ready_for_render")
    elif action == "notes":
        update_notes(db, item, notes)
    elif action == "regenerate_script":
        regenerate_script(db, item)
    elif action == "regenerate_metadata":
        regenerate_metadata(db, item)
    elif action == "create_short_job":
        _job_or_400(lambda: create_short_job(db, item_id))
    elif action == "create_long_job":
        _job_or_400(lambda: create_long_job(db, item_id))
    elif action == "create_both_jobs":
        _job_or_400(lambda: create_both_jobs(db, item_id))
    else:
        raise HTTPException(status_code=400, detail="Unknown review action.")
    return RedirectResponse(url=f"/review/{item_id}", status_code=303)


@router.post("/jobs/{job_id}/action")
def job_ui_action(job_id: int, action: str = Form(...), db: Session = Depends(get_db)) -> RedirectResponse:
    if action == "render":
        render_job(job_id)
    elif action == "render_moneyprinterturbo":
        resolve_render_engine("moneyprinterturbo").render_job(job_id)
    elif action == "render_preview":
        render_preview(job_id)
    elif action == "thumbnail_variants":
        job = _require_video_job(db, job_id)
        generate_thumbnail_variants(job)
    elif action in {"select_thumbnail_a", "select_thumbnail_b", "select_thumbnail_c"}:
        select_thumbnail_variant(db, job_id, action.rsplit("_", 1)[1])
    elif action == "mark_upload_reviewed":
        mark_upload_reviewed(db, job_id)
    elif action == "upload_private":
        upload_video(db, job_id)
    else:
        raise HTTPException(status_code=400, detail="Unknown job action.")
    return RedirectResponse(url=f"/jobs/{job_id}/view", status_code=303)


def _require_review_item(db: Session, item_id: int):
    item = get_review_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found.")
    return item


def _set_status_or_400(db: Session, item, status: str):
    try:
        return set_approval_status(db, item, status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _require_video_job(db: Session, job_id: int):
    try:
        return require_video_job(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _job_or_400(factory):
    try:
        return factory()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _serialize_upload(upload) -> dict[str, object]:
    return {
        "id": upload.id,
        "job_id": upload.job_id,
        "status": upload.youtube_upload_status,
        "privacy": upload.youtube_privacy_status,
        "video_id": upload.youtube_video_id,
        "url": upload.youtube_upload_url,
        "uploaded_at": upload.youtube_uploaded_at.isoformat() if upload.youtube_uploaded_at else "",
        "error": upload.youtube_upload_error,
        "report_path": upload.youtube_upload_report_path,
    }
