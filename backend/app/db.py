"""Synchronous SQLAlchemy sessions. Schema changes belong to Alembic."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings


def build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    options: dict = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False, "timeout": 10}
        if url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        else:
            options["poolclass"] = StaticPool
    engine = create_engine(database_url, **options)
    if url.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

    return engine


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
