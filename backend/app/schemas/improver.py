from pydantic import BaseModel


class ImproveResult(BaseModel):
    tex: str
    changed: bool
    changes: list[str] = []  # transparency: what changed + why
    could_not_add: list[str] = []  # JD keywords not honestly supportable — surfaced, not invented
    fabrication_flags: list[str] = []  # unsupported new claims caught by the verifier
    compiled: bool
    single_page: bool
    warnings: list[str] = []
