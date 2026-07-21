"""Improver: one content-only improvement pass over a résumé's LaTeX.

Integrity is enforced *structurally*, not by trusting the prompt:
- format-respect: the LLM only sees/edits the BODY; the original preamble and
  closing are reattached byte-for-byte, so it cannot alter class/packages/macros.
- no-fabrication: prompt constraint PLUS an independent `fabrication_check`; any
  flag reverts the entire edit (keep the honest original over a padded fake).
- compiles / ≤1 page / clean text: every candidate is validated via T2
  `render_tex`; failures are fed back and retried.
The improver↔score loop lives in T6, not here — this is a single self-validating pass.
"""

import re

from pydantic import BaseModel

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
    "You improve a résumé's LaTeX body to better fit a job description, WITHOUT "
    "fabricating. Rules:\n"
    "- Edit ONLY the body given. Preserve the LaTeX structure, commands, and "
    "environments; keep it compilable and to ONE page (trade weak content out for "
    "strong rather than adding length).\n"
    "- Weave in missing JD keywords ONLY where the résumé already demonstrates that "
    "skill/experience. Rephrase, reorder, and re-emphasize REAL content to surface "
    "JD-relevant experience.\n"
    "- NEVER invent employers, titles, dates, numbers/metrics, certifications, "
    "degrees, or skills the résumé does not support. Any JD keyword you cannot "
    "honestly support goes in could_not_add — do NOT add it to the résumé.\n"
    "Output EXACTLY this and nothing else:\n"
    "===TEX===\n<the full edited LaTeX body>\n===END===\n"
    "===CHANGES===\n"
    '{"changes": ["short note per change"], "could_not_add": ["unaddable jd keyword"]}\n'
    "===ENDCHANGES==="
)

_FAB_SYS = (
    "You are a strict résumé fact-checker. Compare an ORIGINAL résumé body to an "
    "EDITED one and list every factual claim in EDITED that is NOT supported by "
    "ORIGINAL — any new employer, job title, date, number/metric, certification, "
    "degree, or skill. Rephrasing or reordering existing facts is NOT a fabrication. "
    "Return ONLY JSON of exactly this shape, no prose: "
    '{"flags": ["the unsupported claim"]}. Empty list if nothing was fabricated.'
)


class _Flags(BaseModel):
    flags: list[str] = []


def _parse_edit(resp: str) -> tuple[str, list[str], list[str]]:
    m = re.search(r"===TEX===\s*(.*?)\s*===END===", resp, re.S)
    if not m:
        raise ValueError("no ===TEX=== block in edit response")
    new_body = m.group(1)
    changes: list[str] = []
    could_not_add: list[str] = []
    cm = re.search(r"===CHANGES===\s*(.*?)\s*(?:===ENDCHANGES===|$)", resp, re.S)
    if cm:
        try:
            data = llm._loads(cm.group(1))
            changes = data.get("changes") or []
            could_not_add = data.get("could_not_add") or []
        except Exception:
            pass  # sentinels parsed; a malformed changes block just yields empty lists
    return new_body, changes, could_not_add


def _edit_body(body: str, jd_text: str, ats: AtsScore, error: str | None = None):
    user = (
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        f"MISSING JD KEYWORDS (close honestly where evidenced; list the rest in "
        f"could_not_add): {ats.missing}\n\n"
        f"RÉSUMÉ BODY (LaTeX — edit ONLY this):\n{body}"
    )
    if error:
        user += f"\n\nYOUR PREVIOUS ATTEMPT FAILED: {error}\nReturn a corrected version."
    resp = llm.chat([{"role": "system", "content": _EDIT_SYS}, {"role": "user", "content": user}])
    return _parse_edit(resp)


def fabrication_check(old_body: str, new_body: str) -> list[str]:
    """Independent verifier: flags claims in the edit not supported by the original."""
    out = llm.chat(
        [
            {"role": "system", "content": _FAB_SYS},
            {"role": "user", "content": f"ORIGINAL:\n{old_body}\n\nEDITED:\n{new_body}"},
        ],
        format=_Flags.model_json_schema(),
    )
    return _Flags.model_validate(out).flags


def _baseline(tex: str, **over) -> ImproveResult:
    """Never-worse fallback: return the original, its real compile/page status."""
    r = render_tex(tex)
    return ImproveResult(
        tex=tex,
        changed=False,
        compiled=r.guards.compiles,
        single_page=r.guards.single_page,
        **over,
    )


def improve(tex: str, jd_text: str, ats: AtsScore) -> ImproveResult:
    """One improvement pass. Returns an improved, compile-validated, ≤1-page,
    non-fabricated `.tex` + change-log — or the untouched original if no valid,
    honest improvement is found (never a broken/2-page/fabricated résumé)."""
    preamble, body, closing = split_tex(tex)
    anchors = [t for t in ats.matched if t in body][:5]  # real facts that must survive
    error: str | None = None
    last_flags: list[str] = []  # fabrication from the final attempt, if it never came clean

    for _ in range(1 + IMPROVER_COMPILE_RETRIES):
        try:
            new_body, changes, could_not_add = _edit_body(body, jd_text, ats, error)
        except Exception as e:
            error = f"could not parse the edit ({e})"
            continue

        new_tex = reassemble(preamble, new_body, closing)
        r = render_tex(new_tex, expect=anchors)
        if not (r.guards.compiles and r.guards.single_page and r.guards.extraction_clean):
            error = "; ".join(r.errors) or "edit did not compile to one clean page"
            continue

        last_flags = fabrication_check(body, new_body)
        if last_flags:  # feed the fabrication back so the next attempt drops it
            error = (
                "You fabricated unsupported claims: "
                + "; ".join(last_flags)
                + ". Remove them and use ONLY facts stated in the original résumé."
            )
            continue

        return ImproveResult(
            tex=new_tex,
            changed=True,
            changes=changes,
            could_not_add=could_not_add,
            compiled=True,
            single_page=True,
        )

    # exhausted: never ship a broken/fabricated résumé — keep the honest original.
    if last_flags:
        return _baseline(
            tex,
            fabrication_flags=last_flags,
            warnings=["could not produce a non-fabricated improvement; kept the original"],
        )
    return _baseline(tex, warnings=["no valid ≤1-page improvement found; kept the original"])
