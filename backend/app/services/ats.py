"""Grounded JD-fit / ATS scorer: deterministic keyword coverage + an
independent LLM fit judge. The scorer NEVER edits or grades against the
improver (T5) — the writer must not grade its own homework (design §4)."""

import re

from pydantic import BaseModel

from app.core.config import ATS_COVERAGE_WEIGHT
from app.schemas.ats import AtsScore, JdKeyword
from app.services import llm


def _mentions(text: str, needle: str) -> bool:
    """Case-insensitive, boundary-aware match: 'Go' matches 'write Go' but not
    'Google'; 'k8s' and 'ci/cd' match literally. Boundaries guard only the
    outer edges so terms with symbols (C++, CI/CD) still match."""
    n = needle.strip().lower()
    if not n:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", text.lower()) is not None


def keyword_coverage(
    keywords: list[JdKeyword], resume_text: str
) -> tuple[float, list[str], list[str]]:
    """Pure/deterministic. Coverage over REQUIRED keywords only; a keyword is
    matched if its term or any alias appears in the résumé."""
    required = [k for k in keywords if k.required]
    matched, missing = [], []
    for k in required:
        if any(_mentions(resume_text, t) for t in [k.term, *k.aliases]):
            matched.append(k.term)
        else:
            missing.append(k.term)
    pct = len(matched) / len(required) if required else 1.0
    return pct, matched, missing


class _JdKeywords(BaseModel):
    keywords: list[JdKeyword]


class _Fit(BaseModel):
    score: int
    rationale: str


def extract_jd_keywords(jd_text: str) -> list[JdKeyword]:
    """LLM, structured output. Pulls the JD's skills/tools/keywords, splits
    required vs nice-to-have, and includes common aliases (k8s, cicd, …)."""
    out = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "Extract the concrete skills, tools, and technologies from a job "
                    "description (not soft skills or generic phrases). For each: the canonical "
                    "term, common aliases/synonyms (Kubernetes->[k8s], CI/CD->[cicd, ci cd]), "
                    "and required=true if the JD lists it as a requirement/must-have, false if "
                    "nice-to-have. Return ONLY a JSON object of exactly this shape, no markdown "
                    'or prose: {"keywords": [{"term": "Kubernetes", "aliases": ["k8s"], '
                    '"required": true}]}'
                ),
            },
            {"role": "user", "content": jd_text},
        ],
        format=_JdKeywords.model_json_schema(),
    )
    return _JdKeywords.model_validate(out).keywords


def llm_fit(jd_text: str, resume_text: str) -> tuple[int, str]:
    """Independent LLM judge with a fixed rubric. Returns (0-100, rationale)."""
    out = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "You are an impartial technical recruiter. Score 0-100 how well the "
                    "résumé fits the job description on three axes, weighted equally: "
                    "skills match, seniority match, and domain match. 0 = no fit, "
                    "100 = ideal fit. Judge only what the résumé states; do not assume "
                    "unstated experience. Return ONLY a JSON object of exactly this shape, no "
                    'markdown or prose: {"score": 87, "rationale": "one paragraph citing '
                    'specifics"}'
                ),
            },
            {"role": "user", "content": f"JOB DESCRIPTION:\n{jd_text}\n\nRÉSUMÉ:\n{resume_text}"},
        ],
        format=_Fit.model_json_schema(),
    )
    fit = _Fit.model_validate(out)
    return max(0, min(100, fit.score)), fit.rationale


def score_with_keywords(
    keywords: list[JdKeyword], jd_text: str, resume_text: str
) -> AtsScore:
    """Blend grounded coverage + independent fit against pre-extracted JD
    keywords. Lets callers (T4 selector) extract the JD once and score N
    résumés against it. `missing` is the gap list that drives T5 and the report."""
    pct, matched, missing = keyword_coverage(keywords, resume_text)
    fit, rationale = llm_fit(jd_text, resume_text)

    w = ATS_COVERAGE_WEIGHT
    overall = round(w * (pct * 100) + (1 - w) * fit)
    return AtsScore(
        overall=max(0, min(100, overall)),
        keyword_coverage=pct,
        llm_fit=fit,
        required_keywords=[k.term for k in keywords if k.required],
        matched=matched,
        missing=missing,
        rationale=rationale,
    )


def score_ats(jd_text: str, resume_text: str) -> AtsScore:
    """Orchestrate: extract JD keywords -> score. The single-résumé entry point."""
    return score_with_keywords(extract_jd_keywords(jd_text), jd_text, resume_text)
