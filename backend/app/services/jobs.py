"""In-memory job store + runner. The job API is the seam (design §10): swap this
for Redis/Celery later without touching the routers. ponytail: single-process,
in-memory, threads/GIL — fine for the MVP."""

from dataclasses import dataclass
from uuid import uuid4

from app.core.config import OUTER_LOOP_MAX
from app.schemas.job import Job
from app.schemas.pipeline import PipelineResult
from app.schemas.selector import ResumeInput
from app.services.pipeline import run_pipeline


class JobError(Exception):
    """Base for job-store errors the router maps to HTTP codes."""


class JobNotFound(JobError):
    pass


class JobNotDone(JobError):
    pass


class FeedbackLimitReached(JobError):
    pass


@dataclass
class _Record:
    job: Job
    jd_text: str
    resumes: list[ResumeInput]
    pending_feedback: str | None = None
    prior: PipelineResult | None = None


class JobStore:
    def __init__(self) -> None:
        self._recs: dict[str, _Record] = {}

    def create(self, jd_text: str, resumes: list[ResumeInput]) -> Job:
        job = Job(id=uuid4().hex)
        self._recs[job.id] = _Record(job=job, jd_text=jd_text, resumes=resumes)
        return job

    def get(self, job_id: str) -> Job:
        rec = self._recs.get(job_id)
        if rec is None:
            raise JobNotFound(job_id)
        return rec.job

    def request_feedback(self, job_id: str, feedback: str) -> Job:
        """Queue another improve round on a finished job (capped at OUTER_LOOP_MAX)."""
        rec = self._recs.get(job_id)
        if rec is None:
            raise JobNotFound(job_id)
        if rec.job.status != "done":
            raise JobNotDone(job_id)
        if rec.job.round >= OUTER_LOOP_MAX:
            raise FeedbackLimitReached(job_id)
        rec.pending_feedback = feedback
        rec.prior = rec.job.result
        rec.job.round += 1
        rec.job.status = "queued"
        return rec.job

    def run(self, job_id: str) -> None:
        """Execute the pipeline for a queued job. Called from a background task."""
        rec = self._recs[job_id]
        rec.job.status = "running"
        rec.job.progress = []
        try:
            result = run_pipeline(
                rec.jd_text,
                rec.resumes,
                feedback=rec.pending_feedback,
                prior=rec.prior,
                on_progress=rec.job.progress.append,
            )
            rec.job.result = result
            rec.job.status = "done"
            rec.prior = result
            rec.pending_feedback = None
        except Exception as e:  # never let a worker thread die silently
            rec.job.status = "error"
            rec.job.error = str(e)


store = JobStore()  # module-level singleton the routers share
