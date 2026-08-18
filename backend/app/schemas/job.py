from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.pipeline import PipelineResult

JobStatus = Literal["queued", "running", "done", "error"]


class RoundEntry(BaseModel):
    """One proof round on the timeline (T22). Informational: the PDF is always the
    latest round - viewing/reverting an old one is a future ticket."""

    index: int  # 0 = the initial tailoring
    kind: Literal["initial", "revision"]
    feedback: str | None = None  # the user's prompt, echoed back on revision rounds
    summary: str = ""  # the improver's 2-3 line brief of what this round did
    ats_overall: int
    ats_delta: int | None = None  # vs the previous round; None for round 0
    changes: list[str] = []
    added: list[str] = []


class Job(BaseModel):
    id: str
    status: JobStatus = "queued"
    progress: list[str] = []
    result: PipelineResult | None = None
    error: str | None = None
    round: int = 0  # completed improve rounds (0 = first pass), capped at OUTER_LOOP_MAX
    rounds: list[RoundEntry] = []  # T22: the full round history, oldest first
    apply_url: str | None = None  # T16: the ATS apply form, when the JD came from a link (not a paste)


class JobSummary(BaseModel):
    """Lightweight row for the extension's run picker (T12) — no result payload."""

    id: str
    title: str  # first non-empty JD line, for the human to recognize the run
    status: JobStatus
    created_at: datetime
    has_pdf: bool  # only done runs have a tailored PDF to attach
