import argparse

from app.db.session import SessionLocal
from app.db.session import init_db
from app.jobs.daily import run_daily_job
from app.jobs.trend_scan import run_trend_scan
from app.services.outputs import get_latest_json_file
from app.services.review import clear_dev_data, dedupe_review_items, reset_invalid_ready_for_render, review_summary
from app.services.video_job_service import create_jobs_for_approved, jobs_summary, normalize_existing_job_titles


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


def main() -> None:
    parser = argparse.ArgumentParser(description="CuriousSignal content intelligence CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run-daily", help="Run the daily trend-to-script planning pipeline.")
    subparsers.add_parser("scan-trends", help="Run trend ingestion, deduplication, and opportunity scoring.")
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
    args = parser.parse_args()

    if args.command == "run-daily":
        run_daily()
    elif args.command == "scan-trends":
        scan_trends()
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


if __name__ == "__main__":
    main()
