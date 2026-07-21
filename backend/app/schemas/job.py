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
