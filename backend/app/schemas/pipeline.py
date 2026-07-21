from pathlib import Path

from pydantic import BaseModel

from app.schemas.ats import AtsScore


class HiringAgentReport(BaseModel):
    overall: float  # Σ min(score,max) + bonus − deductions (0-120)
    categories: dict[str, float]  # capped per-category scores
    advice: list[str] = []  # areas_for_improvement
    note: str = ""  # the "GitHub-driven, won't move via edits" explanation, set when below gate


class Report(BaseModel):
    selection_warning: str | None = None
    ats_before: AtsScore
    ats_after: AtsScore
    changes: list[str] = []
    added: list[str] = []  # skills/projects/claims added by the aggressive rewrite — review list
    hiring_agent: HiringAgentReport | None = None  # None if the gate couldn't run
    warnings: list[str] = []


class PipelineResult(BaseModel):
    pdf_path: Path
    tex: str
    report: Report
