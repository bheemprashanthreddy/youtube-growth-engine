import json
from datetime import date

from app.agents.planner import ContentPlanner
from app.db.session import SessionLocal
from app.models.content import ContentOutput, DailyRun, Topic
from app.providers.factory import get_llm_provider
from app.schemas.content import DailyRunResult
from app.services.outputs import output_dir_for, save_content_plan, save_json_output, save_manifest
from app.services.review import create_review_item
from app.services.scoring import pick_top_scored_trends, score_trends
from app.services.trend_ingestion import collect_trends, deduplicate_trends
from app.services.topic_expander import expand_trend_items


def run_daily_job() -> DailyRunResult:
    run_date = date.today()
    output_dir = output_dir_for(run_date)
    raw = collect_trends()
    cleaned, rejected = expand_trend_items(raw)
    merged = deduplicate_trends(cleaned)
    scored = score_trends(merged)
    selected = pick_top_scored_trends(scored)

    save_json_output("trends_raw.json", [item.model_dump() for item in raw], output_dir)
    save_json_output("trends_rejected.json", [item.model_dump() for item in rejected], output_dir)
    save_json_output("trends_cleaned.json", [item.model_dump() for item in cleaned], output_dir)
    save_json_output("trends_scored.json", scored, output_dir)

    planner = ContentPlanner(get_llm_provider())
    plans = [planner.build_plan(_content_topic_from_scored(item), _score_from_scored(item)) for item in selected]
    output_paths = [str(save_content_plan(plan, output_dir)) for plan in plans]
    manifest = save_manifest(run_date, plans, output_dir)
    daily_path = save_json_output(
        "daily_run.json",
        {
            "run_date": run_date.isoformat(),
            "phase": "phase_1_5_real_trend_intelligence_with_content_planning",
            "raw_count": len(raw),
            "rejected_count": len(rejected),
            "accepted_transformed_count": len(cleaned),
            "deduped_count": len(merged),
            "selected_count": len(selected),
            "selected_topics": selected,
            "content_manifest": str(manifest),
        },
        output_dir,
    )

    with SessionLocal() as db:
        daily_run = DailyRun(run_date=run_date.isoformat(), output_dir=str(output_dir), status="completed")
        db.add(daily_run)
        db.flush()
        for item in selected:
            trend = item["trend"]
            score = item["score"]
            db.add(
                Topic(
                    name=str(trend["display_topic"]),
                    pillar=str(trend["category_guess"]),
                    trend_reason=str(score["explanation"]),
                    score=float(score["final_score"]),
                    status="selected",
                )
            )
        for plan, path, item in zip(plans, output_paths, selected, strict=True):
            db.add(
                ContentOutput(
                    daily_run_id=daily_run.id,
                    topic_name=plan.topic,
                    quality_gate_status=plan.quality_gate.final_status,
                    output_path=path,
                    payload_json=json.dumps(plan.model_dump()),
                )
            )
            create_review_item(
                db,
                plan=plan,
                daily_run_id=daily_run.id,
                source_names=list(item["trend"].get("source_names", [])),
                quality_metadata=item["trend"],
            )
        db.commit()

    return DailyRunResult(
        run_date=run_date.isoformat(),
        output_dir=str(output_dir),
        selected_count=len(plans),
        outputs=[*output_paths, str(manifest), str(daily_path)],
    )


def _content_topic_from_scored(item: dict[str, object]) -> dict[str, object]:
    trend = item["trend"]
    score = item["score"]
    return {
        "topic": trend["display_topic"],
        "pillar": trend.get("content_pillar") or trend["category_guess"],
        "trend_reason": score["explanation"],
        "curiosity_trigger": trend.get("curiosity_angle") or _curiosity_trigger(str(trend["display_topic"])),
        "target_viewer": "CuriousSignal viewers who want trend-backed explainers instead of surface-level hype",
    }


def _score_from_scored(item: dict[str, object]):
    from app.schemas.content import OpportunityScore

    return OpportunityScore(**item["score"])


def _curiosity_trigger(topic: str) -> str:
    return f"why {topic.lower()} is gaining attention now and what most viewers are missing"
