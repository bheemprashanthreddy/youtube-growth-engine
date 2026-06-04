import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.db.session import init_db
from app.jobs.daily import run_daily_job
from app.jobs.trend_scan import run_trend_scan
from app.providers.factory import get_provider_status
from app.services.outputs import get_latest_json_file
from app.services.rendering.engines import build_moneyprinterturbo_payload, render_engine_status, resolve_render_engine
from app.services.rendering.engines.moneyprinterturbo_engine import MoneyPrinterTurboEngine
from app.services.rendering.inspect import inspect_media
from app.services.rendering.renderer import render_batch, render_job, render_preview, render_ready_jobs, reset_failed_renders
from app.services.rendering.thumbnails import generate_thumbnail_variants
from app.services.review import clear_dev_data, dedupe_review_items, reset_invalid_ready_for_render, review_summary
from app.services.visual_assets.asset_selector import select_assets_for_job, visual_provider_status
from app.services.voice.voice_cache import voice_cache_dir
from app.services.voice.voice_service import generate_voice_for_job, voice_provider_status
from app.services.video_job_service import create_jobs_for_approved, jobs_summary, normalize_existing_job_titles
from app.models.content import VideoJob
from app.services.youtube.auth import run_youtube_auth
from app.services.youtube.upload_service import list_uploads, upload_ready, upload_video, youtube_status
from app.services.youtube.upload_review import build_upload_checklist, mark_upload_reviewed, select_thumbnail_variant
from app.services.ai_visuals.cache import ai_visual_cache_dir
from app.services.ai_visuals.visual_service import ai_visual_status, generate_ai_thumbnail_concepts, generate_scene_images


def run_daily() -> None:
    init_db()
    result = run_daily_job()
    print(f"Daily run complete: {result.output_dir}")


def scan_trends() -> None:
    result = run_trend_scan()
    print(f"Trend scan complete: {result.output_dir}")
    daily = get_latest_json_file("daily_run.json")
    if isinstance(daily, dict):
        print(f"raw trends count: {daily.get('raw_count', 0)}")
        print(f"rejected trends count: {daily.get('rejected_count', 0)}")
        print(f"accepted/transformed trends count: {daily.get('accepted_transformed_count', 0)}")
        print(f"top scored count: {daily.get('top_count', daily.get('selected_count', 0))}")


def print_provider_status() -> None:
    status = get_provider_status()
    print(f"selected provider: {status.selected_provider}")
    print(f"configured: {status.configured}")
    print(f"active: {status.active}")
    print(f"using mock fallback: {status.using_mock_fallback}")
    print(f"detail: {status.detail}")


def print_visual_provider_status() -> None:
    status = visual_provider_status()
    print(f"selected visual provider: {status.selected_provider}")
    print(f"configured: {status.configured}")
    print(f"active: {status.active}")
    print(f"cache directory: {status.cache_directory}")
    print(f"fallback mode: {status.fallback_mode}")
    print(f"detail: {status.detail}")


def print_ai_visual_status() -> None:
    status = ai_visual_status()
    print(f"enabled: {status.enabled}")
    print(f"provider: {status.provider}")
    print(f"image model: {status.image_model}")
    print(f"video model: {status.video_model}")
    print(f"scene images enabled: {status.scene_images_enabled}")
    print(f"thumbnails enabled: {status.thumbnails_enabled}")
    print(f"cache dir: {status.cache_dir}")
    print(f"fallback mode: {status.fallback_mode}")
    print(f"detail: {status.detail}")


def print_voice_provider_status() -> None:
    status = voice_provider_status()
    print(f"selected voice provider: {status.selected_provider}")
    print(f"configured: {status.configured}")
    print(f"active: {status.active}")
    print(f"fallback mode: {status.fallback_mode}")
    print(f"cache dir: {status.cache_dir}")
    print(f"voice profile: {status.voice_profile}")
    print(f"selected voice: {status.selected_voice}")
    print(f"detail: {status.detail}")


def print_review_summary() -> None:
    init_db()
    with SessionLocal() as db:
        summary = review_summary(db)
    print(f"total generated: {summary['total_generated']}")
    print(f"duplicates detected: {summary['duplicates_detected']}")
    print(f"invalid lifecycle count: {summary['invalid_lifecycle_count']}")
    print(f"approved: {summary['approved']}")
    print(f"rejected: {summary['rejected']}")
    print(f"ready_for_render: {summary['ready_for_render']}")
    print(f"approved without jobs: {summary['approved_without_jobs']}")
    print("top 5 by score:")
    for row in summary["top_5"]:
        print(f"- #{row['id']} {row['score']:.1f} {row['status']} :: {row['topic']}")


def reset_review_statuses() -> None:
    init_db()
    with SessionLocal() as db:
        corrected = reset_invalid_ready_for_render(db)
    print(f"corrected invalid ready_for_render rows: {corrected}")


def clear_local_dev_data(confirm: bool) -> None:
    if not confirm:
        raise SystemExit("Refusing to clear dev data without --confirm.")
    init_db()
    with SessionLocal() as db:
        counts = clear_dev_data(db)
    print("cleared local SQLite dev data:")
    for name, count in counts.items():
        print(f"- {name}: {count}")


def dedupe_review_data() -> None:
    init_db()
    with SessionLocal() as db:
        result = dedupe_review_items(db)
    print(f"duplicate groups: {result['groups']}")
    print(f"removed duplicate rows: {result['removed']}")
    for detail in result["details"]:
        print(f"- {detail['key']} kept #{detail['kept_id']} removed {detail['removed_ids']}")


def print_quality_report() -> None:
    raw = get_latest_json_file("trends_raw.json")
    rejected = get_latest_json_file("trends_rejected.json")
    cleaned = get_latest_json_file("trends_cleaned.json")
    scored = get_latest_json_file("trends_scored.json")
    raw_items = raw if isinstance(raw, list) else []
    rejected_items = rejected if isinstance(rejected, list) else []
    cleaned_items = cleaned if isinstance(cleaned, list) else []
    scored_items = scored if isinstance(scored, list) else []
    transformed = [item for item in cleaned_items if item.get("quality_status") == "transformed"]
    accepted = [item for item in cleaned_items if item.get("quality_status") == "accepted"]
    reasons: dict[str, int] = {}
    for item in rejected_items:
        for reason in item.get("quality_reasons", []):
            reasons[reason] = reasons.get(reason, 0) + 1

    print(f"total raw phrases: {len(raw_items)}")
    print(f"rejected count: {len(rejected_items)}")
    print(f"accepted count: {len(accepted)}")
    print(f"transformed count: {len(transformed)}")
    print("top rejection reasons:")
    for reason, count in sorted(reasons.items(), key=lambda row: row[1], reverse=True)[:5]:
        print(f"- {reason}: {count}")
    print("top 10 expanded topics:")
    for item in scored_items[:10]:
        trend = item["trend"]
        print(f"- {item['score']['final_score']:.1f} :: {trend.get('expanded_topic') or trend['display_topic']}")


def create_jobs(approved: bool, format_type: str | None) -> None:
    if not approved:
        raise SystemExit("Use --approved to explicitly create jobs from approved/ready review items.")
    init_db()
    with SessionLocal() as db:
        jobs = create_jobs_for_approved(db, format_type=format_type)
        rows = [(job.id, job.format_type, job.status, job.title) for job in jobs]
    print(f"created or found jobs: {len(rows)}")
    for job_id, job_format, status, title in rows:
        print(f"- #{job_id} {job_format} {status} :: {title}")


def print_jobs_summary() -> None:
    init_db()
    with SessionLocal() as db:
        summary = jobs_summary(db)
    print(f"total jobs: {summary['total_jobs']}")
    print(f"short jobs: {summary['short_jobs']}")
    print(f"long jobs: {summary['long_jobs']}")
    print(f"ready_for_render: {summary['ready_for_render']}")
    print(f"rendered: {summary['rendered']}")
    print(f"failed: {summary['failed']}")
    print(f"duplicate job count: {summary['duplicate_job_count']}")
    print("top ready jobs:")
    for job in summary["top_ready_jobs"]:
        print(f"- #{job['id']} {job['format_type']} review #{job['review_item_id']} :: {job['title']}")


def normalize_job_titles() -> None:
    init_db()
    with SessionLocal() as db:
        changed = normalize_existing_job_titles(db)
    print(f"normalized video job titles: {changed}")


def print_render_engine_status() -> None:
    status = render_engine_status()
    print(f"selected engine: {status['selected_engine']}")
    print(f"native available: {status['native_available']}")
    print(f"MoneyPrinterTurbo enabled: {status['moneyprinterturbo_enabled']}")
    print(f"MoneyPrinterTurbo base URL: {status['moneyprinterturbo_base_url']}")
    print(f"MoneyPrinterTurbo reachable: {status['moneyprinterturbo_reachable']}")
    print("warnings:")
    for warning in status["warnings"]:
        print(f"- {warning}")


def print_moneyprinterturbo_status() -> None:
    status = MoneyPrinterTurboEngine().get_status()
    for key, value in status.items():
        if key == "warnings":
            print("warnings:")
            for warning in value:
                print(f"- {warning}")
        else:
            print(f"{key}: {value}")
    if not status.get("enabled"):
        print("likely reason: MONEYPRINTERTURBO_ENABLED is false.")
    elif not status.get("reachable"):
        print("likely reason: external MoneyPrinterTurbo API is not running or base URL is wrong.")
    print("next setup: clone MoneyPrinterTurbo outside this repo, start its API, then confirm /docs or /redoc.")
    print("note: MoneyPrinterTurbo is an external service; this repo only stores request/response packages.")


def moneyprinterturbo_request_preview(job_id: int) -> None:
    init_db()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        if job is None:
            raise SystemExit(_missing_video_job_message(db, job_id))
        import json

        print(json.dumps(build_moneyprinterturbo_payload(job), indent=2))


def render_one_job(job_id: int, engine: str | None = None) -> None:
    init_db()
    try:
        active_engine = resolve_render_engine(engine)
        result = active_engine.render_job(job_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"engine: {active_engine.name}")
    print(f"render status: {result.status}")
    print(f"mp4: {result.render_output_path}")
    print(f"thumbnail: {result.thumbnail_output_path}")
    print(f"report: {result.report_output_path}")
    if result.error_message:
        print(f"error: {result.error_message}")


def render_ready(limit: int) -> None:
    init_db()
    results = render_ready_jobs(limit=limit)
    if not results:
        print("No ready_for_render jobs found.")
        return
    print(f"rendered jobs attempted: {len(results)}")
    for result in results:
        print(f"- #{result.job_id} {result.format_type} {result.status} :: {result.render_output_path}")


def render_preview_job(job_id: int, engine: str | None = None) -> None:
    init_db()
    try:
        active_engine = resolve_render_engine(engine)
        result = active_engine.render_job(job_id, preview=True)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"engine: {active_engine.name}")
    print(f"preview status: {result.status}")
    print(f"mp4: {result.render_output_path}")
    print(f"thumbnail: {result.thumbnail_output_path}")
    print(f"report: {result.report_output_path}")
    if result.error_message:
        print(f"error: {result.error_message}")


def print_render_summary() -> None:
    init_db()
    with SessionLocal() as db:
        summary = jobs_summary(db)
        from app.services.video_job_service import list_video_jobs

        latest = [
            (job.id, job.format_type, job.render_output_path, job.thumbnail_output_path)
            for job in list_video_jobs(db)
            if job.status == "rendered"
        ][:5]
    print(f"total jobs: {summary['total_jobs']}")
    print(f"ready_for_render: {summary['ready_for_render']}")
    print(f"rendering: {summary.get('rendering', 0)}")
    print(f"rendered: {summary['rendered']}")
    print(f"failed: {summary['failed']}")
    print("latest rendered outputs:")
    for job_id, format_type, video, thumb in latest:
        print(f"- #{job_id} {format_type} video={video} thumbnail={thumb}")


def render_batch_cli(limit: int, format_type: str | None, include_failed: bool, force: bool) -> None:
    init_db()
    report = render_batch(limit=limit, format_type=format_type, include_failed=include_failed, force=force)
    print(f"batch report: {report['report_path']}")
    print(f"processed: {report['total_processed']}")
    print(f"rendered: {report['rendered_count']}")
    print(f"failed: {report['failed_count']}")
    print(f"skipped: {report['skipped_count']}")
    for row in report["job_results"]:
        print(f"- #{row.get('job_id')} {row.get('format_type', '')} {row.get('status')}")


def render_report_cli(job_id: int) -> None:
    path = Path("renders") / "reports" / f"{job_id}.json"
    if not path.exists():
        raise SystemExit("Render report not found.")
    print(path.read_text(encoding="utf-8"))


def reset_failed_renders_cli(confirm: bool) -> None:
    if not confirm:
        raise SystemExit("Refusing to reset failed renders without --confirm.")
    init_db()
    with SessionLocal() as db:
        count = reset_failed_renders(db)
    print(f"reset failed renders: {count}")


def inspect_render(path: str) -> None:
    metadata = inspect_media(path)
    print(f"resolution: {metadata['width']}x{metadata['height']}")
    print(f"fps: {metadata['fps']}")
    print(f"duration: {metadata['duration_seconds']}")
    print(f"has_audio: {metadata['has_audio']}")
    print(f"file size: {metadata['file_size']}")
    print("warnings:")
    for warning in metadata["warnings"]:
        print(f"- {warning}")


def generate_thumbnail_variants_cli(job_id: int) -> None:
    init_db()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        if job is None:
            raise SystemExit(_missing_video_job_message(db, job_id))
        import json

        scenes = json.loads(job.scene_plan_json).get("scenes", [])
        assets = [asset.to_dict() for asset in select_assets_for_job(job, scenes[:3])]
        paths = generate_thumbnail_variants(job, assets=assets)
    print("thumbnail variants:")
    for path in paths:
        print(f"- {path}")


def generate_scene_images_cli(job_id: int) -> None:
    init_db()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        if job is None:
            raise SystemExit("Video job not found.")
        import json

        scenes = json.loads(job.scene_plan_json).get("scenes", [])
        assets = generate_scene_images(job, scenes, force=False)
    print("scene images:")
    for asset in assets:
        print(f"- {asset.local_path}")


def generate_ai_thumbnails_cli(job_id: int) -> None:
    init_db()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        if job is None:
            raise SystemExit("Video job not found.")
        concepts = generate_ai_thumbnail_concepts(job, force=False)
        paths = generate_thumbnail_variants(job, assets=[asset.to_dict() for asset in concepts])
    print("ai thumbnail concepts:")
    for asset in concepts:
        print(f"- {asset.local_path}")
    print("final thumbnail variants:")
    for path in paths:
        print(f"- {path}")


def clear_ai_visual_cache(confirm: bool) -> None:
    if not confirm:
        raise SystemExit("Refusing to clear AI visual cache without --confirm.")
    root = ai_visual_cache_dir()
    count = 0
    for path in root.rglob("*"):
        if path.is_file():
            path.unlink()
            count += 1
    print(f"cleared AI visual cache files: {count}")


def generate_voice_cli(job_id: int) -> None:
    init_db()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        if job is None:
            raise SystemExit(_missing_video_job_message(db, job_id))
        import json

        scenes = json.loads(job.scene_plan_json).get("scenes", [])
        result = generate_voice_for_job(job, scenes, preview=False)
        format_type = job.format_type
    print(f"job id: {job_id}")
    print(f"format: {format_type}")
    print(f"voice provider: {result.provider}")
    print(f"voice profile: {result.voice_profile}")
    print(f"combined audio: {result.combined_audio_path}")
    print(f"total duration: {result.total_audio_duration}")
    print(f"capped: {result.capped}")
    print(f"fallback used: {result.fallback_used}")
    print("warnings:")
    for warning in result.warnings:
        print(f"- {warning}")
    print("voice files:")
    for path in result.voice_files:
        print(f"- {path}")


def _missing_video_job_message(db, job_id: int) -> str:
    jobs = db.query(VideoJob).filter(VideoJob.status.in_(["ready_for_render", "rendered"])).order_by(VideoJob.id).limit(10).all()
    if not jobs:
        return (
            f"Video job #{job_id} not found. No ready_for_render or rendered jobs exist. "
            "Run python -m app.cli run-daily, approve items in /review, then run python -m app.cli create-jobs --approved."
        )
    lines = [f"Video job #{job_id} not found. Existing ready/renderable jobs:"]
    for job in jobs:
        lines.append(f"- #{job.id} {job.format_type} {job.status} :: {job.title}")
    return "\n".join(lines)


def clear_voice_cache(confirm: bool) -> None:
    if not confirm:
        raise SystemExit("Refusing to clear voice cache without --confirm.")
    root = voice_cache_dir()
    count = 0
    for path in root.rglob("*"):
        if path.is_file():
            path.unlink()
            count += 1
    print(f"cleared voice cache files: {count}")


def youtube_auth_cli() -> None:
    result = run_youtube_auth()
    for key, value in result.items():
        print(f"{key}: {value}")


def youtube_status_cli() -> None:
    init_db()
    with SessionLocal() as db:
        status = youtube_status(db)
    for key, value in status.items():
        print(f"{key}: {value}")


def upload_checklist_cli(job_id: int) -> None:
    init_db()
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        if job is None:
            raise SystemExit(_missing_video_job_message(db, job_id))
        checklist = build_upload_checklist(db, job)
    print(f"job id: {job_id}")
    print(f"passed: {checklist['passed']}")
    print(f"thumbnail: {checklist['thumbnail_path']}")
    print(f"privacy: {checklist['privacy_status']}")
    print("checks:")
    for check in checklist["checks"]:
        marker = "PASS" if check["passed"] else "BLOCK"
        print(f"- {marker}: {check['label']}")
    if checklist["warnings"]:
        print("warnings:")
        for warning in checklist["warnings"]:
            print(f"- {warning}")
    if checklist["blockers"]:
        print("blockers:")
        for blocker in checklist["blockers"]:
            print(f"- {blocker}")


def mark_upload_reviewed_cli(job_id: int) -> None:
    init_db()
    with SessionLocal() as db:
        try:
            job = mark_upload_reviewed(db, job_id)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    print(f"upload review approved for job #{job.id}")
    print(f"selected thumbnail: {job.selected_thumbnail_path}")


def select_thumbnail_cli(job_id: int, variant: str) -> None:
    init_db()
    with SessionLocal() as db:
        try:
            job = select_thumbnail_variant(db, job_id, variant)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    print(f"selected thumbnail variant {variant.lower()} for job #{job.id}: {job.selected_thumbnail_path}")


def upload_video_cli(job_id: int, bypass_review: bool) -> None:
    init_db()
    with SessionLocal() as db:
        report = upload_video(db, job_id, bypass_review=bypass_review)
    print(f"upload status: {report['upload_status']}")
    print(f"privacy: {report['privacy_status']}")
    print(f"youtube video id: {report['youtube_video_id']}")
    print(f"report: {report['report_path']}")
    for error in report["errors"]:
        print(f"error: {error}")


def upload_ready_cli(limit: int) -> None:
    init_db()
    with SessionLocal() as db:
        report = upload_ready(db, limit=limit)
    print(f"processed uploads: {report['processed']}")
    for row in report["results"]:
        print(f"- job #{row['job_id']} {row['upload_status']} {row['youtube_video_id']}")


def upload_summary_cli() -> None:
    init_db()
    with SessionLocal() as db:
        uploads = list_uploads(db)
    print(f"total uploads: {len(uploads)}")
    for upload in uploads[:10]:
        print(f"- job #{upload.job_id} {upload.youtube_upload_status} privacy={upload.youtube_privacy_status} video_id={upload.youtube_video_id} error={upload.youtube_upload_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CuriousSignal content intelligence CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run-daily", help="Run the daily trend-to-script planning pipeline.")
    subparsers.add_parser("scan-trends", help="Run trend ingestion, deduplication, and opportunity scoring.")
    subparsers.add_parser("provider-status", help="Show configured AI provider status and fallback behavior.")
    subparsers.add_parser("visual-provider-status", help="Show configured visual asset provider status.")
    subparsers.add_parser("ai-visual-status", help="Show configured AI visual provider status.")
    subparsers.add_parser("voice-provider-status", help="Show configured voice provider status.")
    subparsers.add_parser("render-engine-status", help="Show selected render engine and adapter status.")
    subparsers.add_parser("moneyprinterturbo-status", help="Show MoneyPrinterTurbo adapter status.")
    mpt_preview_parser = subparsers.add_parser("moneyprinterturbo-request-preview", help="Print the MoneyPrinterTurbo request payload without sending it.")
    mpt_preview_parser.add_argument("--id", type=int, required=True, help="VideoJob id.")
    subparsers.add_parser("review-summary", help="Print review workflow counts and top topics.")
    subparsers.add_parser("quality-report", help="Print topic quality filtering and expansion summary.")
    subparsers.add_parser("reset-review-statuses", help="Reset invalid ready_for_render rows to needs_review.")
    clear_parser = subparsers.add_parser("clear-dev-data", help="Clear local generated SQLite dev data.")
    clear_parser.add_argument("--confirm", action="store_true", help="Required confirmation flag.")
    subparsers.add_parser("dedupe-review-items", help="Remove duplicate review items, keeping highest score.")
    create_jobs_parser = subparsers.add_parser("create-jobs", help="Create VideoJob packages from approved review items.")
    create_jobs_parser.add_argument("--approved", action="store_true", help="Required explicit approval scope.")
    create_jobs_parser.add_argument("--format", choices=["short", "long"], default=None, help="Optional job format.")
    subparsers.add_parser("jobs-summary", help="Print video job queue summary.")
    subparsers.add_parser("normalize-job-titles", help="Normalize existing VideoJob titles and refresh job packages.")
    render_job_parser = subparsers.add_parser("render-job", help="Render a single ready_for_render job.")
    render_job_parser.add_argument("--id", type=int, required=True, help="VideoJob id.")
    render_job_parser.add_argument("--engine", choices=["native", "moneyprinterturbo"], default=None, help="Optional render engine override.")
    render_ready_parser = subparsers.add_parser("render-ready", help="Render ready_for_render jobs.")
    render_ready_parser.add_argument("--limit", type=int, default=1, help="Max jobs to render.")
    render_batch_parser = subparsers.add_parser("render-batch", help="Render ready jobs one by one and write a batch report.")
    render_batch_parser.add_argument("--limit", type=int, default=5, help="Max jobs to process.")
    render_batch_parser.add_argument("--format", choices=["short", "long"], default=None, help="Optional format filter.")
    render_batch_parser.add_argument("--include-failed", action="store_true", help="Also retry failed jobs.")
    render_batch_parser.add_argument("--force", action="store_true", help="Allow rerendering rendered jobs.")
    render_preview_parser = subparsers.add_parser("render-preview", help="Render a 10-15 second preview for a job.")
    render_preview_parser.add_argument("--id", type=int, required=True, help="VideoJob id.")
    render_preview_parser.add_argument("--engine", choices=["native", "moneyprinterturbo"], default=None, help="Optional render engine override.")
    inspect_render_parser = subparsers.add_parser("inspect-render", help="Inspect a rendered MP4 file.")
    inspect_render_parser.add_argument("--path", required=True, help="Rendered MP4 path.")
    render_report_parser = subparsers.add_parser("render-report", help="Print a job render report JSON.")
    render_report_parser.add_argument("--id", type=int, required=True, help="VideoJob id.")
    reset_failed_parser = subparsers.add_parser("reset-failed-renders", help="Reset failed render jobs to ready_for_render.")
    reset_failed_parser.add_argument("--confirm", action="store_true", help="Required confirmation flag.")
    thumbnail_variants_parser = subparsers.add_parser("generate-thumbnail-variants", help="Generate three thumbnail variants for a job.")
    thumbnail_variants_parser.add_argument("--id", type=int, required=True, help="VideoJob id.")
    scene_images_parser = subparsers.add_parser("generate-scene-images", help="Generate AI scene images for a job.")
    scene_images_parser.add_argument("--id", type=int, required=True, help="VideoJob id.")
    ai_thumbs_parser = subparsers.add_parser("generate-ai-thumbnails", help="Generate AI thumbnail concepts and final variants for a job.")
    ai_thumbs_parser.add_argument("--id", type=int, required=True, help="VideoJob id.")
    clear_ai_parser = subparsers.add_parser("clear-ai-visual-cache", help="Clear AI visual cache files.")
    clear_ai_parser.add_argument("--confirm", action="store_true", help="Required confirmation flag.")
    generate_voice_parser = subparsers.add_parser("generate-voice", help="Generate cached voice files for a job.")
    generate_voice_parser.add_argument("--id", type=int, required=True, help="VideoJob id.")
    clear_voice_parser = subparsers.add_parser("clear-voice-cache", help="Clear generated voice cache files.")
    clear_voice_parser.add_argument("--confirm", action="store_true", help="Required confirmation flag.")
    subparsers.add_parser("youtube-auth", help="Run YouTube OAuth installed app flow.")
    subparsers.add_parser("youtube-status", help="Show private YouTube upload status.")
    upload_video_parser = subparsers.add_parser("upload-video", help="Upload one rendered job privately to YouTube.")
    upload_video_parser.add_argument("--job-id", type=int, required=True, help="VideoJob id.")
    upload_video_parser.add_argument("--bypass-review", action="store_true", help="Bypass final upload review gate; private-only enforcement remains active.")
    upload_ready_parser = subparsers.add_parser("upload-ready", help="Upload rendered jobs privately to YouTube.")
    upload_ready_parser.add_argument("--limit", type=int, default=1, help="Max rendered jobs to upload.")
    checklist_parser = subparsers.add_parser("upload-checklist", help="Print the private upload review checklist for a job.")
    checklist_parser.add_argument("--job-id", type=int, required=True, help="VideoJob id.")
    mark_review_parser = subparsers.add_parser("mark-upload-reviewed", help="Approve final human upload review for a job.")
    mark_review_parser.add_argument("--job-id", type=int, required=True, help="VideoJob id.")
    select_thumb_parser = subparsers.add_parser("select-thumbnail", help="Select thumbnail variant a, b, or c for upload.")
    select_thumb_parser.add_argument("--job-id", type=int, required=True, help="VideoJob id.")
    select_thumb_parser.add_argument("--variant", choices=["a", "b", "c"], required=True, help="Thumbnail variant.")
    subparsers.add_parser("upload-summary", help="Print YouTube upload summary.")
    subparsers.add_parser("render-summary", help="Print render status summary.")
    args = parser.parse_args()

    if args.command == "run-daily":
        run_daily()
    elif args.command == "scan-trends":
        scan_trends()
    elif args.command == "provider-status":
        print_provider_status()
    elif args.command == "visual-provider-status":
        print_visual_provider_status()
    elif args.command == "ai-visual-status":
        print_ai_visual_status()
    elif args.command == "voice-provider-status":
        print_voice_provider_status()
    elif args.command == "render-engine-status":
        print_render_engine_status()
    elif args.command == "moneyprinterturbo-status":
        print_moneyprinterturbo_status()
    elif args.command == "moneyprinterturbo-request-preview":
        moneyprinterturbo_request_preview(args.id)
    elif args.command == "review-summary":
        print_review_summary()
    elif args.command == "quality-report":
        print_quality_report()
    elif args.command == "reset-review-statuses":
        reset_review_statuses()
    elif args.command == "clear-dev-data":
        clear_local_dev_data(confirm=args.confirm)
    elif args.command == "dedupe-review-items":
        dedupe_review_data()
    elif args.command == "create-jobs":
        create_jobs(approved=args.approved, format_type=args.format)
    elif args.command == "jobs-summary":
        print_jobs_summary()
    elif args.command == "normalize-job-titles":
        normalize_job_titles()
    elif args.command == "render-job":
        render_one_job(args.id, engine=args.engine)
    elif args.command == "render-ready":
        render_ready(args.limit)
    elif args.command == "render-batch":
        render_batch_cli(args.limit, args.format, args.include_failed, args.force)
    elif args.command == "render-preview":
        render_preview_job(args.id, engine=args.engine)
    elif args.command == "inspect-render":
        inspect_render(args.path)
    elif args.command == "render-report":
        render_report_cli(args.id)
    elif args.command == "reset-failed-renders":
        reset_failed_renders_cli(args.confirm)
    elif args.command == "generate-thumbnail-variants":
        generate_thumbnail_variants_cli(args.id)
    elif args.command == "generate-scene-images":
        generate_scene_images_cli(args.id)
    elif args.command == "generate-ai-thumbnails":
        generate_ai_thumbnails_cli(args.id)
    elif args.command == "clear-ai-visual-cache":
        clear_ai_visual_cache(args.confirm)
    elif args.command == "generate-voice":
        generate_voice_cli(args.id)
    elif args.command == "clear-voice-cache":
        clear_voice_cache(confirm=args.confirm)
    elif args.command == "youtube-auth":
        youtube_auth_cli()
    elif args.command == "youtube-status":
        youtube_status_cli()
    elif args.command == "upload-video":
        upload_video_cli(args.job_id, bypass_review=args.bypass_review)
    elif args.command == "upload-ready":
        upload_ready_cli(args.limit)
    elif args.command == "upload-checklist":
        upload_checklist_cli(args.job_id)
    elif args.command == "mark-upload-reviewed":
        mark_upload_reviewed_cli(args.job_id)
    elif args.command == "select-thumbnail":
        select_thumbnail_cli(args.job_id, args.variant)
    elif args.command == "upload-summary":
        upload_summary_cli()
    elif args.command == "render-summary":
        print_render_summary()


if __name__ == "__main__":
    main()
