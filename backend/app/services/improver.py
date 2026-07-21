"""Improver: one AGGRESSIVE tailoring pass over a résumé's LaTeX.

Product decision: maximize ATS/JD match (target 95%+) — inject every required JD
keyword (including current gaps), rewrite the summary tight, and swap the first
project for a JD-specific one. This is the user's own résumé; they review and own
every claim, so the pass reports an `added` list (what was newly claimed) for
transparency instead of refusing to add it.

Still enforced structurally: edits touch the BODY only (preamble/closing reattached
byte-for-byte), and every candidate must compile to ONE page (T2 render_tex),
retried on failure. The improver↔score loop lives in T6, not here.
"""

import re

from app.core.config import IMPROVER_COMPILE_RETRIES
from app.schemas.ats import AtsScore
from app.schemas.improver import ImproveResult
from app.services import llm
from app.services.render import render_tex

_BEGIN = r"\begin{document}"
_END = r"\end{document}"


def split_tex(tex: str) -> tuple[str, str, str]:
    """(preamble, body, closing). Preamble includes `\\begin{document}`; closing
    is `\\end{document}`→end; body is between. Pure: preamble+body+closing == tex."""
    bi = tex.find(_BEGIN)
    if bi == -1:
        return "", tex, ""
    b = bi + len(_BEGIN)
    ei = tex.find(_END, b)
    if ei == -1:
        return tex[:b], tex[b:], ""
    return tex[:b], tex[b:ei], tex[ei:]


def reassemble(preamble: str, body: str, closing: str) -> str:
    return preamble + body + closing


_EDIT_SYS = (
    "You are an elite résumé writer optimizing a résumé to score 95%+ on ATS / "
    "JD-match for a specific job. Rewrite the LaTeX body to match the job as closely "
    "as possible. Rules:\n"
    "- Incorporate EVERY required JD keyword, tool, and skill into the résumé — "
    "including ones not currently present. Weave them into the skills list, the "
    "experience bullets, and the summary so they read naturally.\n"
    "- PROFESSIONAL SUMMARY: rewrite it to a tight 2–3 lines, 30–40 words MAX, "
    "laser-targeted to this job.\n"
    "- Replace the FIRST project with a new JD-specific project that showcases the "
    "job's core technologies and responsibilities.\n"
    "- Give each work-experience entry 3–4 bullet points, and each project 2–3 "
    "bullet points.\n"
    "- In the Technical Skills section, also include the soft skills the JD asks for "
    "(e.g. communication, collaboration, ownership) if they aren't already there.\n"
    "- Keep it to ONE page. Preserve the LaTeX structure, commands, and environments "
    "so it compiles. Do NOT touch anything outside the body you are given.\n"
    "- This is the user's own résumé; they will review and own every claim.\n"
    "Output EXACTLY this and nothing else:\n"
    "===TEX===\n<the full rewritten LaTeX body>\n===END===\n"
    "===CHANGES===\n"
    '{"changes": ["what you changed, one per item"], '
    '"added": ["each skill / project / claim you ADDED that was not in the original"]}\n'
    "===ENDCHANGES==="
)


def _parse_edit(resp: str) -> tuple[str, list[str], list[str]]:
    m = re.search(r"===TEX===\s*(.*?)\s*===END===", resp, re.S)
    if not m:
        raise ValueError("no ===TEX=== block in edit response")
    new_body = m.group(1)
    changes: list[str] = []
    added: list[str] = []
    cm = re.search(r"===CHANGES===\s*(.*?)\s*(?:===ENDCHANGES===|$)", resp, re.S)
    if cm:
        try:
            data = llm._loads(cm.group(1))
            changes = data.get("changes") or []
            added = data.get("added") or []
        except Exception:
            pass  # sentinels parsed; a malformed changes block just yields empty lists
    return new_body, changes, added


def _edit_body(body: str, jd_text: str, ats: AtsScore, error: str | None = None):
    user = (
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        f"REQUIRED JD KEYWORDS TO COVER: {ats.required_keywords}\n"
        f"CURRENTLY MISSING — make sure these now appear in the résumé: {ats.missing}\n\n"
        f"RÉSUMÉ BODY (LaTeX — rewrite ONLY this):\n{body}"
    )
    if error:
        user += f"\n\nYOUR PREVIOUS ATTEMPT FAILED: {error}\nReturn a corrected version."
    resp = llm.chat([{"role": "system", "content": _EDIT_SYS}, {"role": "user", "content": user}])
    return _parse_edit(resp)


def _baseline(tex: str, **over) -> ImproveResult:
    """Compile-failure fallback: return the original with its real compile/page status."""
    r = render_tex(tex)
    return ImproveResult(
        tex=tex,
        changed=False,
        compiled=r.guards.compiles,
        single_page=r.guards.single_page,
        **over,
    )


def improve(tex: str, jd_text: str, ats: AtsScore) -> ImproveResult:
    """One aggressive tailoring pass. Returns a compile-validated, ≤1-page rewrite
    that maximizes JD match + an `added` review list — or the untouched original if
    no candidate compiles to one page (never ship a broken/2-page résumé)."""
    preamble, body, closing = split_tex(tex)
    error: str | None = None

    for _ in range(1 + IMPROVER_COMPILE_RETRIES):
        try:
            new_body, changes, added = _edit_body(body, jd_text, ats, error)
        except Exception as e:
            error = f"could not parse the edit ({e})"
            continue

        new_tex = reassemble(preamble, new_body, closing)
        r = render_tex(new_tex)
        if not (r.guards.compiles and r.guards.single_page and r.guards.extraction_clean):
            error = "; ".join(r.errors) or "the rewrite did not compile to one clean page"
            continue

        return ImproveResult(
            tex=new_tex,
            changed=True,
            changes=changes,
            added=added,
            compiled=True,
            single_page=True,
        )

    return _baseline(tex, warnings=["could not produce a valid ≤1-page rewrite; kept the original"])
