"""SQLAlchemy engine/session/Base (T11). SQLite now; DATABASE_URL flips it to
Postgres later with no code change. Sync — SQLite serializes writes, so async
buys nothing at this scale (ponytail)."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core import config

_connect_args = {"check_same_thread": False} if config.DB_URL.startswith("sqlite") else {}
engine = create_engine(config.DB_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    with SessionLocal() as s:
        yield s


def init_db() -> None:
    """Create tables and seed the single profile_id='default' row. Idempotent."""
    from app import models  # noqa: F401 — register mappers before create_all

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if s.get(models.Profile, "default") is None:
            s.add(models.Profile(id="default"))
            s.commit()
