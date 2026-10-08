from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

_engine_url = settings.DATABASE_URL

# Fallback to local SQLite when DATABASE_URL is not configured
if not _engine_url:
    _db_path = settings.STORAGE_DIR / "database.db"
    _engine_url = f"sqlite:///{_db_path.as_posix()}"
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

connect_args = {}
if _engine_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(_engine_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
