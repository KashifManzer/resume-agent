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
