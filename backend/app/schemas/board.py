from datetime import datetime
from pydantic import BaseModel, ConfigDict

class JobPostingOut(BaseModel):
    url: str
    company_slug: str
    title: str
    location: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BoardFeedOut(BaseModel):
    jobs: list[JobPostingOut]
    has_more: bool
    total_pages: int
