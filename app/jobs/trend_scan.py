from datetime import date

from app.schemas.content import DailyRunResult
from app.services.outputs import output_dir_for, save_json_output
from app.services.scoring import pick_top_scored_trends, score_trends
from app.services.trend_ingestion import collect_trends, deduplicate_trends
from app.services.topic_expander import expand_trend_items


def run_trend_scan() -> DailyRunResult:
    run_date = date.today()
    output_dir = output_dir_for(run_date)
    raw = collect_trends()
    cleaned, rejected = expand_trend_items(raw)
    merged = deduplicate_trends(cleaned)
    scored = score_trends(merged)
    top = pick_top_scored_trends(scored)

    raw_path = save_json_output("trends_raw.json", [item.model_dump() for item in raw], output_dir)
    rejected_path = save_json_output("trends_rejected.json", [item.model_dump() for item in rejected], output_dir)
    cleaned_path = save_json_output("trends_cleaned.json", [item.model_dump() for item in cleaned], output_dir)
    scored_path = save_json_output("trends_scored.json", scored, output_dir)
    daily_path = save_json_output(
        "daily_run.json",
        {
            "run_date": run_date.isoformat(),
            "phase": "phase_1_5_real_trend_intelligence",
            "raw_count": len(raw),
            "rejected_count": len(rejected),
            "accepted_transformed_count": len(cleaned),
            "deduped_count": len(merged),
            "top_count": len(top),
            "top_topics": top,
        },
        output_dir,
    )
    return DailyRunResult(
        run_date=run_date.isoformat(),
        output_dir=str(output_dir),
        selected_count=len(top),
        outputs=[str(raw_path), str(rejected_path), str(cleaned_path), str(scored_path), str(daily_path)],
    )
