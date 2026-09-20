from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JobPosting
from app.schemas.board import BoardFeedOut, JobPostingOut
from app.schemas.jd import JdSource
from app.services import board_policy, jd_fetch

router = APIRouter(prefix="/board", tags=["board"])

@router.get("", response_model=BoardFeedOut)
def get_board_feed(
    # Unbounded before: ?limit=100000 returned all 1925 rows in one response, and
    # page=0 produced a negative offset.
    page: int = Query(1, ge=1, le=2**31 - 1),  # also keep SQL OFFSET in integer range
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * limit
    eligible = board_policy.eligible_postings()

    total_count = db.execute(
        select(func.count()).select_from(JobPosting).where(*eligible)
    ).scalar()

    jobs = db.execute(
        select(JobPosting)
        .where(*eligible)
        .order_by(JobPosting.created_at.desc(), JobPosting.url.asc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    has_more = (offset + limit) < total_count
    total_pages = (total_count + limit - 1) // limit

    return BoardFeedOut(
        jobs=[JobPostingOut.model_validate(j) for j in jobs],
        has_more=has_more,
        total_pages=total_pages
    )


class ResolvePostingIn(BaseModel):
    url: str


def _available_posting(db: Session, url: str) -> JobPosting:
    # Bypass the session identity cache: harvest/retention may have committed
    # another version while this request was waiting for a remote description.
    posting = db.get(JobPosting, url, populate_existing=True)
    if posting is None:
        raise HTTPException(404, "This listing is no longer on the Board.")
    if not board_policy.is_recent(posting.created_at):
        raise HTTPException(410, "This listing is outside the Board's 14-day window.")
    if posting.status != "open":
        raise HTTPException(410, "This job is no longer available.")
    return posting


@router.post("/resolve", response_model=JdSource)
def resolve_posting(body: ResolvePostingIn, db: Session = Depends(get_db)):
    posting = _available_posting(db, body.url)
    try:
        source = jd_fetch.fetch_jd_from_url(posting.url)
    except jd_fetch.JdUnavailable as e:
        # Retention may delete the row while the network request is in flight.
        db.execute(update(JobPosting).where(JobPosting.url == body.url).values(status="closed"))
        db.commit()
        raise HTTPException(410, str(e)) from e
    except (jd_fetch.JdFetchError, ValueError) as e:
        raise HTTPException(502, "Couldn't check this posting right now. Please retry.") from e
    if len(source.text.strip()) < jd_fetch.config.JD_MIN_CHARS:
        # A 200 containing an empty careers shell is not proof of closure.
        raise HTTPException(502, "Couldn't read a full job description. Retry or paste it below.")
    # Recheck both elapsed age and concurrent changes before handing off the JD.
    _available_posting(db, body.url)
    return source
