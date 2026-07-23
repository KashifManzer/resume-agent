"""One file, two tables (T11). `profile_id` is the tenant key on every résumé
row (hardcoded 'default' now) — multi-user later resolves the real id with zero
schema change. Résumé bytes live on disk (see storage.py), never in the DB."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    name: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)
    phone: Mapped[str | None] = mapped_column(default=None)
    location: Mapped[str | None] = mapped_column(default=None)
    work_auth: Mapped[str | None] = mapped_column(default=None)
    links: Mapped[dict] = mapped_column(JSON, default=dict)  # {github, linkedin, portfolio}


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid4().hex)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"), default="default", index=True)
    label: Mapped[str | None] = mapped_column(default=None)
    format: Mapped[str] = mapped_column(String, default="tex")  # tex|pdf|docx (docx later)
    filename: Mapped[str | None] = mapped_column(default=None)  # original upload name (display/download)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
