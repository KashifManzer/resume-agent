"""JD-from-URL (T10). Separate from /jobs so the user reviews/edits the fetched
JD before running the pipeline (human in the loop)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.jd import JdSource
from app.services import board_sync, jd_adapters, jd_fetch

router = APIRouter()


class FromUrlIn(BaseModel):
    url: str


@router.post("/jd/from-url")
def jd_from_url(body: FromUrlIn, db: Session = Depends(get_db)) -> JdSource:
    try:
        source = jd_fetch.fetch_jd_from_url(body.url)
    except jd_fetch.JdFetchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # T28: a pasted link's company joins the Board. Only when the ATS API itself
    # answered (not the generic fallback), which proves the board exists, and
    # only for ATSes the harvester can list (not Workday).
    adapter = next((a for a in jd_adapters.ADAPTERS if a.name == source.adapter), None)
    if hasattr(adapter, "board_slug"):
        try:
            added = board_sync.track_company(db, source.adapter, adapter.board_slug(source.source_url), "pasted")
        except ValueError:  # suspicious slug: still hand back the JD, just don't track it
            return source
        db.commit()
        source.board = "added" if added else "tracked"
    return source
