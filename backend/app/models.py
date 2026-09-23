"""One file, two tables (T11). `profile_id` is the tenant key on every résumé
row (hardcoded 'default' now) — multi-user later resolves the real id with zero
schema change. Résumé bytes live on disk (see storage.py), never in the DB."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
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
    # T17 — assisted screening: work eligibility + voluntary EEO self-ID, so the
    # extension can answer those Yes/No/demographic questions from the user's own
    # stated facts (all nullable; "yes"/"no" for the boolean ones).
    work_eligible: Mapped[str | None] = mapped_column(default=None)  # eligible to work? yes/no
    needs_sponsorship: Mapped[str | None] = mapped_column(default=None)  # require visa sponsorship? yes/no
    gender: Mapped[str | None] = mapped_column(default=None)
    race: Mapped[str | None] = mapped_column(default=None)
    disability: Mapped[str | None] = mapped_column(default=None)  # yes/no/decline
    veteran: Mapped[str | None] = mapped_column(default=None)  # yes/no/decline
    links: Mapped[dict] = mapped_column(JSON, default=dict)  # {github, linkedin, portfolio}


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid4().hex)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"), default="default", index=True)
    label: Mapped[str | None] = mapped_column(default=None)
    format: Mapped[str] = mapped_column(String, default="tex")  # tex|pdf|docx (docx later)
    filename: Mapped[str | None] = mapped_column(default=None)  # original upload name (display/download)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class FieldMapping(Base):
    """Self-building autofill registry (T12): a resolved label→canonical map for
    one form, keyed by host + form_sig. The LLM discovers a mapping once; the
    cache promotes it so every later hit on that form is instant, free and
    deterministic. No hand-maintained per-ATS field maps."""

    __tablename__ = "field_mappings"
    __table_args__ = (UniqueConstraint("host", "form_sig", name="uq_field_mapping_host_sig"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid4().hex)
    host: Mapped[str] = mapped_column(String, index=True)
    form_sig: Mapped[str] = mapped_column(String, index=True)  # order-independent hash of the field set
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)  # {field_ref: {canonical, confidence}}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Answer(Base):
    """Answer bank (T13). Seeded canonical-core rows (canonical set, question
    None) hold reusable facts/templates; custom rows (canonical None, question
    set) cover the long tail. `mode` = verbatim (fill as-is) | adaptable (LLM
    tailors it to the JD). One row per (profile, canonical) keeps the core
    stable and seeding idempotent — custom rows carry canonical=None (NULLs are
    distinct under the unique constraint, so many custom rows coexist)."""

    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("profile_id", "canonical", name="uq_answer_profile_canonical"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid4().hex)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"), default="default", index=True)
    canonical: Mapped[str | None] = mapped_column(String, default=None)  # None for custom Q&A
    question: Mapped[str | None] = mapped_column(String, default=None)  # custom entries carry their own text
    answer: Mapped[str] = mapped_column(String, default="")
    mode: Mapped[str] = mapped_column(String, default="verbatim")  # verbatim | adaptable
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AnswerResolution(Base):
    """Mirrors FieldMapping (T13): cache a question→canonical *classification*,
    keyed by host + question_sig. The classification is stable so it's cached;
    the prose it drives is regenerated per-JD, never cached across jobs."""

    __tablename__ = "answer_resolutions"
    __table_args__ = (UniqueConstraint("host", "question_sig", name="uq_answer_res_host_sig"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid4().hex)
    host: Mapped[str] = mapped_column(String, index=True)
    question_sig: Mapped[str] = mapped_column(String, index=True)
    canonical: Mapped[str] = mapped_column(String)  # canonical key, or "" for no-match (fresh)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class TrackedCompany(Base):
    __tablename__ = "tracked_companies"

    slug: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String)  # ashby | greenhouse | lever
    discovery_source: Mapped[str] = mapped_column(String, default="manual")
    # Last harvest ATTEMPT, success or not (T29): a failing board waits the
    # interval too. Only the harvester's staleness check reads it.
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    # Set when the board 404s on every ATS we list; rechecked weekly (T29).
    gone_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class JobPosting(Base):
    """Harvested ATS postings (T26).

    Deliberately NOT scoped by profile_id, unlike every other table here. A job
    opening is public reference data, identical for every user, so tenanting it
    would duplicate the same rows per profile and multiply the harvest cost for
    no benefit. When multi-user lands (T8), per-user state belongs in a separate
    join table (saved/dismissed/applied), not in this one.
    """

    __tablename__ = "job_postings"

    url: Mapped[str] = mapped_column(String, primary_key=True)
    company_slug: Mapped[str] = mapped_column(String, ForeignKey("tracked_companies.slug"), index=True)
    title: Mapped[str] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="open")  # open | closed
    # ATS publication time, not discovery time. Indexed for feed order/retention.
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
