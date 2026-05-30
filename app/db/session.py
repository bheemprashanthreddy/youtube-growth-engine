from pathlib import Path
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()

if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.replace("sqlite:///", "", 1)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app.models import content  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_review_items()
    _migrate_sqlite_video_jobs()


def _migrate_sqlite_review_items() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    columns = {
        "content_key": "VARCHAR(128) DEFAULT ''",
        "format_family": "VARCHAR(60) DEFAULT 'shorts_longform'",
        "raw_phrase": "TEXT DEFAULT ''",
        "expanded_topic": "TEXT DEFAULT ''",
        "quality_score": "FLOAT DEFAULT 0",
        "quality_status": "VARCHAR(30) DEFAULT 'accepted'",
        "quality_reasons": "TEXT DEFAULT '[]'",
        "risk_flags": "TEXT DEFAULT '[]'",
        "approved_at": "DATETIME",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(review_items)"))}
        for column, ddl in columns.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE review_items ADD COLUMN {column} {ddl}"))
        conn.execute(
            text(
                """
                UPDATE review_items
                SET format_family = 'shorts_longform'
                WHERE format_family IS NULL OR format_family = ''
                """
            )
        )
        rows = conn.execute(
            text(
                """
                SELECT id, COALESCE(expanded_topic, topic, ''), COALESCE(pillar, '')
                FROM review_items
                WHERE content_key IS NULL OR content_key = ''
                """
            )
        ).all()
        for row_id, topic, pillar in rows:
            key_source = f"{topic} {pillar} shorts_longform".lower()
            key = " ".join("".join(char if char.isalnum() else " " for char in key_source).split())
            conn.execute(text("UPDATE review_items SET content_key = :key WHERE id = :id"), {"key": key, "id": row_id})


def _migrate_sqlite_video_jobs() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    columns = {
        "package_path": "TEXT DEFAULT ''",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(video_jobs)"))}
        for column, ddl in columns.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE video_jobs ADD COLUMN {column} {ddl}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
