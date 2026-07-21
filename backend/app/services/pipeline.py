"""Orchestrator: JD + N résumé .tex → best tailored, ATS-scored, quality-gated,
1-page PDF + .tex + report. Wires T4 selector → T2 render → T3 score ↔ T5
improve (inner loop, the only optimization loop) → T1 hiring-agent gate (once).

Services are called module-qualified so tests can mock each one."""

from typing import Callable

from app.core.config import HIRING_AGENT_GATE, INNER_LOOP_MAX, TARGET_ATS
from app.schemas.pipeline import PipelineResult, Report
from app.schemas.selector import ResumeInput
from app.services import ats, hiring_agent, improver, render, selector

_GITHUB_NOTE = (
    "This general-quality score is largely GitHub/experience-driven (T1: ~90% comes from "
    "open-source and production history), so résumé edits can't move it much. It's a gate, "
    "not a dial — see the advice below for the honest levers."
)


def _tex_for(resume_id: str, resumes: list[ResumeInput]) -> str:
    return next(r.tex for r in resumes if r.id == resume_id)


def run_pipeline(
    jd_text: str,
    resumes: list[ResumeInput],
    *,
    feedback: str | None = None,
    prior: PipelineResult | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> PipelineResult:
    progress = on_progress or (lambda _s: None)
    warnings: list[str] = []

    # 1. Start point: select (first pass) or the prior round's résumé (feedback).
    if prior is not None:
        picked_tex = prior.tex
        selection_warning = prior.report.selection_warning
        base = render.render_tex(picked_tex)
        ats_before = prior.report.ats_after  # reuse; avoids a redundant LLM re-score
    else:
        progress("selecting the closest résumé")
        selection = selector.select_resume(jd_text, resumes)
        picked_tex = _tex_for(selection.picked_id, resumes)
        selection_warning = selection.warning
        progress("scoring the baseline")
        base = render.render_tex(picked_tex)
        ats_before = ats.score_ats(jd_text, base.text)

    best_tex, best_ats, best_pdf = picked_tex, ats_before, base.pdf_path
    changes: list[str] = []
    could_not_add: list[str] = []

    # 2. Inner loop — the only optimization loop. Keep a candidate only if it
    #    compiles, is ≤1 page, and improves `overall`; stop early on plateau/target.
    jd_for_edit = jd_text if not feedback else f"{jd_text}\n\nUSER FEEDBACK (address this): {feedback}"
    for i in range(INNER_LOOP_MAX):
        progress(f"improving (round {i + 1})")
        imp = improver.improve(best_tex, jd_for_edit, best_ats)
        if not imp.changed:
            break
        cand = render.render_tex(imp.tex)
        if not (cand.guards.compiles and cand.guards.single_page):
            break  # improver validates already; never trust — stop rather than ship junk
        cand_ats = ats.score_ats(jd_text, cand.text)
        if cand_ats.overall <= best_ats.overall:
            break  # plateau / regression — discard this round, keep the best so far
        # accepted: record only what we actually keep, so the report matches the final résumé
        best_tex, best_ats, best_pdf = imp.tex, cand_ats, cand.pdf_path
        changes += imp.changes
        could_not_add += imp.could_not_add
        if best_ats.overall >= TARGET_ATS:
            break

    # 3. Quality gate — run ONCE, never looped. Gate + advice, not an optimization target.
    progress("running the quality gate")
    hiring = None
    try:
        hiring = hiring_agent.score_resume(best_pdf)
        if hiring.overall < HIRING_AGENT_GATE:
            hiring = hiring.model_copy(update={"note": _GITHUB_NOTE})
    except Exception as e:
        warnings.append(f"quality gate unavailable: {e}")

    # 4. Package.
    progress("packaging the result")
    report = Report(
        selection_warning=selection_warning,
        ats_before=ats_before,
        ats_after=best_ats,
        changes=changes,
        could_not_add=list(dict.fromkeys(could_not_add)),  # dedup, preserve order
        hiring_agent=hiring,
        warnings=warnings,
    )
    return PipelineResult(pdf_path=best_pdf, tex=best_tex, report=report)
