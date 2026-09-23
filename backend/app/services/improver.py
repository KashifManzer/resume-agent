"""Improver: one tailoring pass over a résumé's LaTeX - AGGRESSIVE by default,
DIRECTED when the caller passes the user's `feedback` (T22).

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

from app.core.config import IMPROVER_COMPILE_RETRIES, OLLAMA_MODEL, OLLAMA_WRITER_MODEL
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


_OUTPUT_FMT = (
    "Output EXACTLY this and nothing else:\n"
    "===TEX===\n<the full rewritten LaTeX body>\n===END===\n"
    "===CHANGES===\n"
    '{"summary": "2-3 short sentences, plain English: what THIS pass did and why", '
    '"changes": ["what you changed, one per item"], '
    '"added": ["each skill / project / claim you ADDED that was not in the original"]}\n'
    "===ENDCHANGES==="
)

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
) + _OUTPUT_FMT

# T22: a human-directed revision is NOT an optimization pass. The person read the
# résumé and said what to change, so their request outranks keyword coverage - and
# the pass must not quietly undo it by re-stuffing what they asked to tone down.
_REVISE_SYS = (
    "You are an elite résumé writer applying a HUMAN'S DIRECTED REVISION to a résumé's "
    "LaTeX body. The user has read this exact résumé and told you what to change. Rules:\n"
    "- The user's request is AUTHORITATIVE. Apply it faithfully and visibly. It takes "
    "precedence over JD-keyword coverage and over any match score - losing keyword "
    "coverage is an acceptable price for doing what they asked.\n"
    "- NEVER re-add, restore, or re-emphasize anything they asked you to remove or tone "
    "down, no matter how strongly the job description calls for it.\n"
    "- This is a revision, not a fresh rewrite: change what the request implies and leave "
    "the rest of the résumé alone.\n"
    "- Do NOT stuff in new keywords. Keep the coverage already there only where it does "
    "not conflict with the request.\n"
    "- Keep it to ONE page. Preserve the LaTeX structure, commands, and environments "
    "so it compiles. Do NOT touch anything outside the body you are given.\n"
    "- This is the user's own résumé; they will review and own every claim.\n"
) + _OUTPUT_FMT


def _parse_edit(resp: str) -> tuple[str, list[str], list[str], str]:
    m = re.search(r"===TEX===\s*(.*?)\s*===END===", resp, re.S)
    if not m:
        raise ValueError("no ===TEX=== block in edit response")
    new_body = m.group(1)
    changes: list[str] = []
    added: list[str] = []
    summary = ""
    cm = re.search(r"===CHANGES===\s*(.*?)\s*(?:===ENDCHANGES===|$)", resp, re.S)
    if cm:
        try:
            data = llm._loads(cm.group(1))
            changes = data.get("changes") or []
            added = data.get("added") or []
            summary = data.get("summary") or ""
        except Exception:
            pass  # sentinels parsed; a malformed changes block just yields empty lists
    return new_body, changes, added, summary


def _edit_body(
    body: str, jd_text: str, ats: AtsScore, error: str | None = None, feedback: str | None = None,
    model: str | None = None,
):
    if feedback:
        user = (
            f"THE USER'S REVISION REQUEST - do exactly this:\n{feedback}\n\n"
            f"JOB DESCRIPTION (context only - it does NOT override the request):\n{jd_text}\n\n"
            f"RÉSUMÉ BODY (LaTeX - revise ONLY this):\n{body}"
        )
    else:
        user = (
            f"JOB DESCRIPTION:\n{jd_text}\n\n"
            f"REQUIRED JD KEYWORDS TO COVER: {ats.required_keywords}\n"
            f"CURRENTLY MISSING — make sure these now appear in the résumé: {ats.missing}\n\n"
            f"RÉSUMÉ BODY (LaTeX — rewrite ONLY this):\n{body}\n\n"
            # Page overflow was the #1 failure: this budget took one-page success from 58%
            # to 92% (gpt-oss) and 79% to 92% (gemma), 24 rewrites each, in fewer calls.
            f"LENGTH BUDGET: the body above is {len(body)} characters and fills exactly one "
            f"page. Your rewritten body must be no longer than {len(body)} characters - "
            "replace content, do not add to it."
        )
    if error:
        user += f"\n\nYOUR PREVIOUS ATTEMPT FAILED: {error}\nReturn a corrected version."
    system = _REVISE_SYS if feedback else _EDIT_SYS
    resp = llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model or OLLAMA_WRITER_MODEL,
    )
    return _parse_edit(resp)


_BARE_AMP = re.compile(r"(?<!\\)&")


def _sanitize(new_body: str, original_body: str) -> str:
    """Fix LaTeX the writer gets wrong, all seen in real rewrites:
    - bare `&` in prose ("Infrastructure & DevOps") and U+202F (narrow no-break
      space) fail to compile, and gpt-oss repeats them on retry. `&` is escaped only
      when the original body had no bare `&`, so a body that tabulates is left alone.
    - `~1 hour` and `40%` compile but silently corrupt the page ("from  1 hour",
      or the rest of the line dropped), so no retry would ever catch them. A `%`
      comment line never follows a digit, so comments are untouched.
    ponytail: only the observed cases; anything else still falls to the retry loop."""
    if not _BARE_AMP.search(original_body):
        new_body = _BARE_AMP.sub(r"\\&", new_body)
    new_body = re.sub(r"(?<!\\)~(?=\d)", r"$\\sim$", new_body)  # ~1 → ∼1
    new_body = re.sub(r"(?<=\d)%", r"\\%", new_body)  # 40% → 40\%
    return new_body.replace("\u202f", " ")


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


def improve(
    tex: str, jd_text: str, ats: AtsScore, feedback: str | None = None
) -> ImproveResult:
    """One tailoring pass. Without `feedback`: the aggressive JD-match rewrite.
    With `feedback`: a directed revision that honors the user's instruction over
    keyword coverage (T22). Either way returns a compile-validated, ≤1-page rewrite
    + an `added` review list - or the untouched original if no candidate compiles
    to one page (never ship a broken/2-page résumé)."""
    preamble, body, closing = split_tex(tex)
    # A page that is already ~96% full fits or overflows on how lines wrap, which no
    # prompt rule controlled: on a real run gpt-oss fit 4/10 while gemma's own retry
    # loop fit 6/6. So the default model gets a fresh loop before we keep the original.
    for model in dict.fromkeys((OLLAMA_WRITER_MODEL, OLLAMA_MODEL)):  # dedup: same model runs once
        error: str | None = None  # retry feedback is about THIS model's own attempt
        for _ in range(1 + IMPROVER_COMPILE_RETRIES):
            try:
                new_body, changes, added, summary = _edit_body(body, jd_text, ats, error, feedback, model)
            except Exception as e:
                error = f"could not parse the edit ({e})"
                continue

            new_tex = reassemble(preamble, _sanitize(new_body, body), closing)
            r = render_tex(new_tex)
            if not (r.guards.compiles and r.guards.single_page and r.guards.extraction_clean):
                error = "; ".join(r.errors) or "the rewrite did not compile to one clean page"
                continue

            return ImproveResult(
                tex=new_tex,
                changed=True,
                changes=changes,
                added=added,
                summary=summary,
                compiled=True,
                single_page=True,
            )

    return _baseline(tex, warnings=["could not produce a valid ≤1-page rewrite; kept the original"])
