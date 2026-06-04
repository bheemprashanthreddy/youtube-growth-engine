from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.content import YouTubeUpload


def quota_status(db: Session) -> dict[str, object]:
    today = date.today()
    rows = db.execute(select(YouTubeUpload)).scalars().all()
    uploaded_today = [
        row for row in rows if row.youtube_uploaded_at and row.youtube_uploaded_at.date() == today and row.youtube_upload_status == "uploaded_private"
    ]
    limit = get_settings().youtube_daily_upload_limit
    return {"date": today.isoformat(), "uploaded_today": len(uploaded_today), "daily_limit": limit, "remaining": max(0, limit - len(uploaded_today))}


def enforce_quota(db: Session) -> tuple[bool, str]:
    status = quota_status(db)
    if int(status["remaining"]) <= 0:
        return False, "Daily upload limit reached."
    return True, ""
