"""Job API — the stable seam the frontend (T7) drives. POST a JD + résumé .tex
files, poll status/result, request feedback rounds, download the final PDF."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import db
from app.db import get_db
from app.models import Profile, Resume
from app.routers.profile import PID
from app.schemas.job import Job, JobAnswer, JobSummary
from app.schemas.selector import ResumeInput
from app.services import answerer, jobs, local_save, storage

router = APIRouter()


class FeedbackIn(BaseModel):
    feedback: str


class QuestionIn(BaseModel):
    question: str


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
    apply_url: str | None = Form(default=None),  # T16: adapter's apply URL (link JDs only)
    title: str | None = Form(default=None),  # T32: adapter's posting title (link JDs only)
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
    job = jobs.store.create(jd, resumes, apply_url=apply_url or None, title=title or None)
    background.add_task(jobs.store.run, job.id)
    return {"job_id": job.id}


@router.get("/jobs")
def list_jobs() -> list[JobSummary]:
    """Recent tailored runs for the extension's picker (T12)."""
    return jobs.store.list()


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


@router.post("/jobs/{job_id}/answer")
def post_answer(job_id: str, body: QuestionIn, session: Session = Depends(get_db)) -> JobAnswer:
    """Draft an answer to an application question (T24), grounded on THIS run's
    tailored résumé, and append it to the run's answers log. Deliberately never
    touches `round` — answering and revising are separate concerns."""
    try:
        job = jobs.store.get(job_id)
    except jobs.JobNotFound:
        raise HTTPException(status_code=404, detail="job not found")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="ask a question")
    res = answerer.answer(question, job_id, host=answerer.WEBAPP_HOST, session=session)
    entry = JobAnswer(**res.model_dump(), question=question, save_mode=answerer.save_mode(res.canonical))
    job.answers.append(entry)
    return entry


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


@router.post("/jobs/{job_id}/save-local")
def save_local(job_id: str):
    """Copy the tailored PDF into tailored-resume/ + upsert the tracker CSV
    (LOCAL-DEV ONLY). Company/position are extracted from the JD."""
    try:
        job = jobs.store.get(job_id)
    except jobs.JobNotFound:
        raise HTTPException(status_code=404, detail="job not found")
    if job.result is None:
        raise HTTPException(status_code=409, detail="run isn't finished yet")
    jd_text, _ = jobs.store.grounding(job_id)
    with db.SessionLocal() as session:
        p = session.get(Profile, PID)
        name = p.name if p else None
    try:
        return local_save.save_local(job, jd_text, name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
