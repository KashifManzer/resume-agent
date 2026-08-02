"""Screening-question answerer (T13). Mirrors T12's field_map: a question
resolves via cache → heuristic → LLM classify → cache, then branches on the
matched answer-bank entry:

    verbatim  → fill the bank value as-is, NO LLM
    adaptable → LLM tailors the stored template to this JD + tailored résumé
    fresh     → LLM drafts from the tailored résumé + profile (no bank match)

The classification is cached (stable); the prose is regenerated every call
(per-JD, never cached across jobs). Honesty guardrails are the trust boundary —
see the never-invent / never-auto handling below; do NOT simplify them away."""

import hashlib
import re

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.canonical import ANSWER_CANONICAL, ANSWER_CLASSIFY, NEVER_AUTO
from app.models import Answer, AnswerResolution
from app.schemas.answer import AnswerResult
from app.services import llm

PID = "default"

# Deterministic classifier. Never-auto categories first so a demographic /
# background question can never be shadowed by a benign match. Ordered
# most-specific → most-general within each group.
_Q_RULES: list[tuple[str, re.Pattern]] = [
    ("eeo_demographic", re.compile(r"\b(race|ethnicit|gender|\bsex\b|veteran|disab|sexual orientation|pronoun)")),
    ("criminal_background", re.compile(r"crimin|convict|felon|background check|been arrested")),
    ("requires_sponsorship", re.compile(r"sponsor|require.*visa|visa.*require")),
    ("work_authorization", re.compile(r"authoriz(ed|ation)\s*to\s*work|right\s*to\s*work|work permit|legally.*work|eligible to work")),
    ("salary_expectation", re.compile(r"salary|compensation|desired pay|expected (pay|salary|comp)|pay expectation")),
    ("notice_period", re.compile(r"notice period")),
    ("earliest_start_date", re.compile(r"start date|when can you start|available.*start|earliest.*start")),
    ("willing_to_relocate", re.compile(r"relocat")),
    ("preferred_location_remote", re.compile(r"\bremote\b|on-?site|hybrid|location preference")),
    ("years_experience", re.compile(r"years?\s*of\s*experience|years?\s*experience|how many years")),
    ("how_heard_about_us", re.compile(r"how did you hear|where did you hear|hear about (us|this|the)|referr")),
    ("why_leaving", re.compile(r"why.*leav|reason for leaving|leaving your (current|present|last)")),
    ("why_company", re.compile(r"why.*(work (here|for us|at)|join|interested in (us|this|our|working))|this (company|role|position)|our (company|mission|team|product)")),
    ("tell_me_about_yourself", re.compile(r"tell (us|me) about yourself|about yourself|introduce yourself|your background")),
]


def _norm(q: str) -> str:
    """Lowercase, strip required-markers, collapse whitespace — so trivial
    punctuation/spacing churn doesn't thrash the cache or miss a custom match."""
    return " ".join(re.sub(r"[*✱?:]", " ", q.lower()).split())


def question_sig(question: str) -> str:
    return hashlib.sha256(_norm(question).encode()).hexdigest()[:16]


def _heuristic(question: str) -> str | None:
    hay = _norm(question)
    for canon, rx in _Q_RULES:
        if rx.search(hay):
            return canon
    return None


class _ClassifyOut(BaseModel):
    canonical: str


def _llm_classify(question: str) -> str | None:
    """One LLM call to classify a question into the answer vocab. Returns a
    canonical key, or None for no-match (fresh). Coerces anything off-vocab to
    None. Raises on transport failure — the caller decides whether to cache."""
    vocab = ", ".join(sorted(ANSWER_CLASSIFY))
    messages = [
        {
            "role": "system",
            "content": (
                "You classify a job-application screening QUESTION into a fixed vocabulary. "
                "You only say what the question ASKS — you never answer it. Reply JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Vocabulary: {vocab}\n\nQuestion: {question!r}\n\n"
                'Return {"canonical":"<key>"}. Use "none" if nothing fits.'
            ),
        },
    ]
    resp = llm.chat(messages, format=_ClassifyOut.model_json_schema())
    canon = resp.get("canonical") if isinstance(resp, dict) else None
    if canon in NEVER_AUTO or canon in ANSWER_CANONICAL:
        return canon
    return None  # "none" or anything off-vocab


def resolve(host: str, question: str, session: Session) -> str | None:
    """cache → heuristic → LLM classify → cache. Returns a canonical key or None
    (no match → fresh). An LLM outage is transient: fall back to the heuristic
    result and DON'T cache, so the cache is never poisoned with a wrong 'none'."""
    sig = question_sig(question)
    cached = session.scalar(
        select(AnswerResolution).where(AnswerResolution.host == host, AnswerResolution.question_sig == sig)
    )
    if cached is not None:
        return cached.canonical or None

    canon = _heuristic(question)
    if canon is None:
        try:
            canon = _llm_classify(question)
        except Exception:
            return None  # transient — resolve again next time, cache nothing

    session.add(AnswerResolution(host=host, question_sig=sig, canonical=canon or ""))
    session.commit()
    return canon


# --- answer bank lookups ----------------------------------------------------


def _bank(session: Session, canonical: str) -> Answer | None:
    return session.scalar(
        select(Answer).where(Answer.profile_id == PID, Answer.canonical == canonical)
    )


def _custom_match(session: Session, question: str) -> Answer | None:
    """A user's custom Q&A whose stored question matches this one (normalized).
    Exact-normalized match only — no embeddings (YAGNI); it grows if real forms
    need fuzzier matching. ponytail: O(n) scan, n = a user's custom entries."""
    want = _norm(question)
    for a in session.scalars(select(Answer).where(Answer.profile_id == PID, Answer.canonical.is_(None))):
        if a.question and _norm(a.question) == want:
            return a
    return None


# --- result builders --------------------------------------------------------


def _verbatim(text: str, canonical: str | None) -> AnswerResult:
    return AnswerResult(answer=text, source="bank_verbatim", needs_review=False, canonical=canonical)


def _blank(reason: str, canonical: str | None) -> AnswerResult:
    # needs_review so a blanked high-stakes / ungroundable field is surfaced, not silently dropped.
    return AnswerResult(answer="", source="blank", needs_review=True, canonical=canonical, reason=reason)


def _draft(question: str, template: str, job_id: str | None, canonical: str | None,
           source: str, session: Session) -> AnswerResult:
    """adaptable/fresh LLM path. Grounds on the tailored résumé; every result is
    needs_review (the human-review backstop). LLM down → blank + flag, no crash."""
    jd, tex = _grounding(job_id, session)
    try:
        text = _llm_answer(question, template, jd, tex)
    except Exception:
        return _blank("couldn't draft — LLM unavailable", canonical)
    if not text.strip():
        # LLM found no grounded fact to assert → blank, never invent one.
        return _blank("couldn't ground an answer — fill this yourself", canonical)
    return AnswerResult(answer=text.strip(), source=source, needs_review=True, canonical=canonical)


class _AnswerOut(BaseModel):
    answer: str


def _llm_answer(question: str, template: str, jd: str, tex: str) -> str:
    """Draft or tailor one answer. Honesty is baked into the prompt: assert only
    facts present in the résumé/profile; unknown factual question → empty."""
    task = (
        f"Tailor the applicant's template to this company/role. Preserve every fact in the "
        f"template; do not invent new credentials.\nTemplate: {template!r}"
        if template.strip()
        else "Draft an answer grounded ONLY on the résumé below."
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You draft an applicant's answer to a job screening question. Assert ONLY facts "
                "present in the résumé/job description provided — never invent experience, numbers, "
                "employers or credentials. If the question asks for a fact not in the résumé, return "
                'an empty answer. First person, concise, no preamble. Reply JSON only.'
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {question!r}\n\n{task}\n\n"
                f"--- Job description ---\n{jd[:6000]}\n\n--- Tailored résumé ---\n{tex[:6000]}\n\n"
                'Return {"answer":"<text or empty>"}'
            ),
        },
    ]
    resp = llm.chat(messages, format=_AnswerOut.model_json_schema())
    return resp.get("answer", "") if isinstance(resp, dict) else ""


def _grounding(job_id: str | None, session: Session) -> tuple[str, str]:
    """(jd_text, résumé_tex) to draft from. Prefer the selected run's tailored
    résumé; with no run (or a gone one), fall back to the default library résumé
    so free-text questions still draft from the user's real experience."""
    if job_id:
        from app.services.jobs import store  # local import avoids a router import cycle
        jd, tex = store.grounding(job_id)
        if tex:
            return jd, tex
    return "", _default_resume_tex(session)


def _default_resume_tex(session: Session) -> str:
    from app.models import Resume
    from app.services import storage

    r = session.scalar(select(Resume).where(Resume.profile_id == PID, Resume.is_default.is_(True))) \
        or session.scalar(select(Resume).where(Resume.profile_id == PID))
    if r is None:
        return ""
    try:
        return storage.open_resume_file(PID, r.id, "source.tex").decode("utf-8", "replace")
    except Exception:
        return ""


# --- the resolver's public entrypoint ---------------------------------------


def answer(question: str, job_id: str | None, host: str, session: Session) -> AnswerResult:
    """Resolve one screening question to a fillable answer + provenance."""
    # A user's explicit custom entry is the strongest signal — honor it first.
    custom = _custom_match(session, question)
    if custom is not None:
        if custom.mode == "verbatim":
            return _verbatim(custom.answer, None) if custom.answer.strip() \
                else _blank("no stored value — add it to your answer bank", None)
        return _draft(question, custom.answer, job_id, None, source="bank_adapted", session=session)

    canonical = resolve(host, question, session)

    # Hard rule: never-auto categories are NEVER LLM-answered.
    if canonical in NEVER_AUTO:
        a = _bank(session, canonical)
        if a is not None and a.answer.strip():
            return _verbatim(a.answer, canonical)
        return _blank("high-stakes — leave this to yourself", canonical)

    if canonical in ANSWER_CANONICAL:
        a = _bank(session, canonical)
        mode = a.mode if a is not None else ANSWER_CANONICAL[canonical]
        template = a.answer.strip() if a is not None else ""
        if mode == "verbatim":
            # salary (and any verbatim) with no stored value → blank, never guess.
            return _verbatim(template, canonical) if template \
                else _blank("no stored value — add it to your answer bank", canonical)
        # adaptable: tailor the template, or draft fresh when the template is empty.
        return _draft(question, template, job_id, canonical,
                      source="bank_adapted" if template else "llm_fresh", session=session)

    # No match → fresh draft grounded on the tailored résumé.
    return _draft(question, "", job_id, None, source="llm_fresh", session=session)
