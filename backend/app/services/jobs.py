"""In-memory job store + runner. The job API is the seam (design §10): swap this
for Redis/Celery later without touching the routers. ponytail: single-process,
in-memory, threads/GIL — fine for the MVP."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import OUTER_LOOP_MAX
from app.schemas.job import Job, JobSummary
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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _title(jd_text: str) -> str:
    """First non-empty JD line (trimmed) so the user recognizes the run."""
    for line in jd_text.splitlines():
        if line.strip():
            return line.strip()[:80]
    return "Untitled run"


class JobStore:
    def __init__(self) -> None:
        self._recs: dict[str, _Record] = {}

    def create(
        self, jd_text: str, resumes: list[ResumeInput], apply_url: str | None = None
    ) -> Job:
        job = Job(id=uuid4().hex, apply_url=apply_url)  # apply_url survives on the Job (T16)
        self._recs[job.id] = _Record(job=job, jd_text=jd_text, resumes=resumes)
        return job

    def get(self, job_id: str) -> Job:
        rec = self._recs.get(job_id)
        if rec is None:
            raise JobNotFound(job_id)
        return rec.job

    def list(self) -> list[JobSummary]:
        """Recent runs, newest first — the extension's run picker (T12)."""
        return [
            JobSummary(
                id=rec.job.id,
                title=_title(rec.jd_text),
                status=rec.job.status,
                created_at=rec.created_at,
                has_pdf=rec.job.result is not None,
            )
            for rec in reversed(self._recs.values())
        ]

    def grounding(self, job_id: str) -> tuple[str, str]:
        """(jd_text, tailored_tex) for the screening answerer (T13). Empty
        strings when the job is missing or not finished — the caller degrades
        gracefully rather than raising."""
        rec = self._recs.get(job_id)
        if rec is None or rec.job.result is None:
            return "", ""
        return rec.jd_text, rec.job.result.tex

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
