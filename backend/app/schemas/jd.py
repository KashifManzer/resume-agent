from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class JdSource(BaseModel):
    """A job description fetched from a URL (T10). `text` drops into the
    editable JD field; the rest is context shown to the user before running."""

    text: str
    title: str | None = None
    location: str | None = None
    company: str | None = None
    source_url: str
    # The ATS *apply form* URL (T16) — Ashby `applyUrl` / Greenhouse `absolute_url`
    # / Lever `hostedUrl` / Workday = the posting URL. NOT source_url (a listing
    # page). None for the generic path. Threaded → job → the Result "Apply" button.
    apply_url: str | None = None
    adapter: str  # "workday" | "greenhouse" | "lever" | "ashby" | "generic"
    warnings: list[str] = []
    # T28 freshness, naive UTC like the Board; a bare date when that is all the
    # source has (Workday). None when there is no date (updated_at: Greenhouse only).
    posted_at: datetime | date | None = None
    updated_at: datetime | None = None
    # T28: a pasted Greenhouse/Lever/Ashby link adds its company to the Board.
    # None = not a harvestable ATS (Workday, generic) or not a pasted link.
    board: Literal["added", "tracked"] | None = None
