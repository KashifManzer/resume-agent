from datetime import datetime

from pydantic import BaseModel


class Links(BaseModel):
    github: str | None = None
    linkedin: str | None = None
    portfolio: str | None = None


class ProfileIn(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    work_auth: str | None = None
    links: Links = Links()


class ProfileOut(ProfileIn):
    id: str


class ResumeMeta(BaseModel):
    id: str
    label: str | None
    format: str
    filename: str | None
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}
