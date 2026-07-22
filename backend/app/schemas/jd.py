from pydantic import BaseModel


class JdSource(BaseModel):
    """A job description fetched from a URL (T10). `text` drops into the
    editable JD field; the rest is context shown to the user before running."""

    text: str
    title: str | None = None
    location: str | None = None
    company: str | None = None
    source_url: str
    adapter: str  # "workday" | "greenhouse" | "lever" | "ashby" | "generic"
    warnings: list[str] = []
