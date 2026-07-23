"""Profile + résumé library (T11). Single profile, hardcoded profile_id — the
tenant seam that makes multi-user a later bolt-on. One router covers both."""

from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Profile, Resume
from app.schemas.profile import ProfileIn, ProfileOut, ResumeMeta
from app.services import storage

router = APIRouter()

PID = "default"  # the only profile for now; auth resolves the real id later


def _resumes(db: Session) -> list[Resume]:
    return list(db.scalars(select(Resume).where(Resume.profile_id == PID).order_by(Resume.created_at)))


def _get_resume(db: Session, rid: str) -> Resume:
    r = db.get(Resume, rid)
    if r is None or r.profile_id != PID:
        raise HTTPException(status_code=404, detail="résumé not found")
    return r


@router.get("/profile")
def get_profile(db: Session = Depends(get_db)) -> ProfileOut:
    p = db.get(Profile, PID)
    return ProfileOut(id=p.id, links=p.links or {}, **{k: getattr(p, k) for k in
                      ("name", "email", "phone", "location", "work_auth")})


@router.put("/profile")
def update_profile(body: ProfileIn, db: Session = Depends(get_db)) -> ProfileOut:
    p = db.get(Profile, PID)
    p.name, p.email, p.phone = body.name, body.email, body.phone
    p.location, p.work_auth = body.location, body.work_auth
    p.links = body.links.model_dump()
    db.commit()
    return get_profile(db)


@router.get("/resumes")
def list_resumes(db: Session = Depends(get_db)) -> list[ResumeMeta]:
    return [ResumeMeta.model_validate(r) for r in _resumes(db)]


@router.post("/resumes")
async def upload_resume(
    file: UploadFile = File(...),
    label: str | None = Form(None),
    db: Session = Depends(get_db),
) -> ResumeMeta:
    rid = uuid4().hex
    storage.save_resume_file(PID, rid, "source.tex", await file.read())
    r = Resume(
        id=rid, profile_id=PID, label=label, format="tex", filename=file.filename,
        is_default=not _resumes(db),  # first upload becomes the default
    )
    db.add(r)
    db.commit()
    return ResumeMeta.model_validate(r)


@router.put("/resumes/{rid}/default")
def set_default(rid: str, db: Session = Depends(get_db)) -> ResumeMeta:
    target = _get_resume(db, rid)
    for r in _resumes(db):
        r.is_default = r.id == rid
    db.commit()
    return ResumeMeta.model_validate(target)


@router.delete("/resumes/{rid}")
def delete_resume(rid: str, db: Session = Depends(get_db)) -> dict:
    r = _get_resume(db, rid)
    was_default = r.is_default
    db.delete(r)
    db.commit()
    storage.delete_resume_dir(PID, rid)
    # keep exactly-one-default invariant: promote the newest survivor
    if was_default and (rest := _resumes(db)):
        rest[-1].is_default = True
        db.commit()
    return {"ok": True}
