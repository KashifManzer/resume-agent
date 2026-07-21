from pydantic import BaseModel


class ImproveResult(BaseModel):
    tex: str
    changed: bool
    changes: list[str] = []  # human-readable "what changed"
    added: list[str] = []  # skills/projects/claims newly added — the user's review list
    compiled: bool
    single_page: bool
    warnings: list[str] = []
