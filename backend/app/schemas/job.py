from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.pipeline import PipelineResult

JobStatus = Literal["queued", "running", "done", "error"]


class Job(BaseModel):
    id: str
    status: JobStatus = "queued"
    progress: list[str] = []
    result: PipelineResult | None = None
    error: str | None = None
    round: int = 0  # completed improve rounds (0 = first pass), capped at OUTER_LOOP_MAX
    apply_url: str | None = None  # T16: the ATS apply form, when the JD came from a link (not a paste)


class JobSummary(BaseModel):
    """Lightweight row for the extension's run picker (T12) — no result payload."""

    id: str
    title: str  # first non-empty JD line, for the human to recognize the run
    status: JobStatus
    created_at: datetime
    has_pdf: bool  # only done runs have a tailored PDF to attach
