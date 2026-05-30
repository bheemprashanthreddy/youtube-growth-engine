import json
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.schemas.content import ContentPlan


def output_dir_for(run_date: date) -> Path:
    path = get_settings().output_root / run_date.isoformat()
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_content_plan(plan: ContentPlan, output_dir: Path) -> Path:
    slug = _slugify(plan.topic)
    path = output_dir / f"{slug}.json"
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return path


def save_manifest(run_date: date, plans: list[ContentPlan], output_dir: Path) -> Path:
    path = output_dir / "manifest.json"
    payload = {
        "run_date": run_date.isoformat(),
        "channel": "CuriousSignal",
        "publishing_mode": "private_upload_first_manual_publish_after_review",
        "phase": "phase_1_trend_to_script_planning",
        "items": [plan.model_dump() for plan in plans],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def save_json_output(filename: str, payload: object, output_dir: Path) -> Path:
    path = output_dir / filename
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def get_latest_output() -> dict[str, object]:
    root = get_settings().output_root
    if not root.exists():
        return {"status": "empty", "message": "No outputs have been generated."}
    dated_dirs = sorted([path for path in root.iterdir() if path.is_dir()], reverse=True)
    if not dated_dirs:
        return {"status": "empty", "message": "No outputs have been generated."}
    manifest = dated_dirs[0] / "manifest.json"
    if not manifest.exists():
        return {"status": "missing_manifest", "output_dir": str(dated_dirs[0])}
    return json.loads(manifest.read_text(encoding="utf-8"))


def get_latest_json_file(filename: str) -> dict[str, object]:
    root = get_settings().output_root
    if not root.exists():
        return {"status": "empty", "message": "No outputs have been generated."}
    for dated_dir in sorted([path for path in root.iterdir() if path.is_dir()], reverse=True):
        path = dated_dir / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {"status": "empty", "message": f"No {filename} output has been generated."}


def _slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in cleaned.split("-") if part)
