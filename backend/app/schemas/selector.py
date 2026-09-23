from pydantic import BaseModel

from app.schemas.ats import AtsScore, JdKeyword


class ResumeInput(BaseModel):
    id: str
    tex: str


class Selection(BaseModel):
    picked_id: str
    picked_score: AtsScore | None = None
    ranked: list[dict]  # [{id, score}], highest first
    close: bool
    warning: str | None = None  # set when the best pick is below CLOSE_THRESHOLD
    keywords: list[JdKeyword] = []  # the JD extraction every later score reuses
