"""Job API — the stable seam the frontend (T7) drives. POST a JD + résumé .tex
files, poll status/result, request feedback rounds, download the final PDF."""

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import db
from app.models import Resume
from app.routers.profile import PID
from app.schemas.job import Job
from app.schemas.selector import ResumeInput
from app.services import jobs, storage

router = APIRouter()


class FeedbackIn(BaseModel):
    feedback: str


def _resumes_from_library(resume_ids: list[str]) -> list[ResumeInput]:
    """Resolve library résumé ids → ResumeInput(id, tex); the pipeline still
    receives exactly what an ad-hoc upload gives it."""
    out = []
    with db.SessionLocal() as session:
        for rid in resume_ids:
            r = session.get(Resume, rid)
            if r is None or r.profile_id != PID:
                raise HTTPException(status_code=404, detail=f"résumé not found: {rid}")
            tex = storage.open_resume_file(PID, rid, "source.tex").decode("utf-8", "replace")
            out.append(ResumeInput(id=r.label or r.filename or r.id, tex=tex))
    return out


@router.post("/jobs")
async def create_job(
    background: BackgroundTasks,
    jd: str = Form(...),
    resume_ids: list[str] = Form(default=[]),
    files: list[UploadFile] = File(default=[]),
) -> dict[str, str]:
    # ad-hoc upload (as today) OR pick from the library — mirrors JD paste-or-link
    if files:
        resumes = [
            ResumeInput(id=f.filename or f"resume{i}", tex=(await f.read()).decode("utf-8", "replace"))
            for i, f in enumerate(files)
        ]
    elif resume_ids:
        resumes = _resumes_from_library(resume_ids)
    else:
        raise HTTPException(status_code=400, detail="provide resume_ids or files")
    job = jobs.store.create(jd, resumes)
    background.add_task(jobs.store.run, job.id)
    return {"job_id": job.id}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> Job:
    try:
        return jobs.store.get(job_id)
    except jobs.JobNotFound:
        raise HTTPException(status_code=404, detail="job not found")


@router.post("/jobs/{job_id}/feedback")
def post_feedback(job_id: str, body: FeedbackIn, background: BackgroundTasks) -> dict:
    try:
        job = jobs.store.request_feedback(job_id, body.feedback)
    except jobs.JobNotFound:
        raise HTTPException(status_code=404, detail="job not found")
    except jobs.JobNotDone:
        raise HTTPException(status_code=409, detail="job is not finished yet")
    except jobs.FeedbackLimitReached:
        raise HTTPException(status_code=429, detail="feedback limit reached")
    background.add_task(jobs.store.run, job_id)
    return {"job_id": job.id, "round": job.round}


@router.get("/jobs/{job_id}/pdf")
def get_pdf(job_id: str):
    try:
        job = jobs.store.get(job_id)
    except jobs.JobNotFound:
        raise HTTPException(status_code=404, detail="job not found")
    if job.result is None:
        raise HTTPException(status_code=404, detail="no PDF yet")
    # inline so the UI can render it in an <iframe>; the download button's
    # `download` attribute still forces a save client-side.
    return FileResponse(
        job.result.pdf_path,
        media_type="application/pdf",
        filename="resume.pdf",
        content_disposition_type="inline",
    )
