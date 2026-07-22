"""JD-from-URL (T10). Separate from /jobs so the user reviews/edits the fetched
JD before running the pipeline (human in the loop)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.jd import JdSource
from app.services import jd_fetch

router = APIRouter()


class FromUrlIn(BaseModel):
    url: str


@router.post("/jd/from-url")
def jd_from_url(body: FromUrlIn) -> JdSource:
    try:
        return jd_fetch.fetch_jd_from_url(body.url)
    except jd_fetch.JdFetchError as e:
        raise HTTPException(status_code=400, detail=str(e))
