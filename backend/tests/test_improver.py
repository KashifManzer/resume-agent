import os
from pathlib import Path

import pytest

from app.schemas.ats import AtsScore
from app.services import improver
from app.services.render import render_tex

FIXTURES = Path(__file__).parent / "fixtures"
GOOD = (FIXTURES / "good.tex").read_text()


def _ats(missing=("Rust",), matched=("Python", "Kubernetes")):
    return AtsScore(
        overall=60,
        keyword_coverage=0.6,
        llm_fit=60,
        required_keywords=list(matched) + list(missing),
        matched=list(matched),
        missing=list(missing),
        rationale="x",
    )


# --- split_tex / reassemble: pure, byte-exact ------------------------------


def test_reassemble_roundtrips_byte_identical():
    preamble, body, closing = improver.split_tex(GOOD)
    assert improver.reassemble(preamble, body, closing) == GOOD


def test_split_boundaries():
    preamble, body, closing = improver.split_tex(GOOD)
    assert preamble.endswith(r"\begin{document}")
    assert closing.startswith(r"\end{document}")
    assert r"\begin{document}" not in body and r"\end{document}" not in body


# --- never-worse: no valid candidate → original, changed=False -------------


def test_never_worse_returns_original(monkeypatch):
    monkeypatch.setattr(
        improver,
        "_edit_body",
        lambda b, jd, ats, err=None: (r"\undefinedcmd breaks compile", ["x"], ["y"]),
    )
    result = improver.improve(GOOD, "jd", _ats())
    assert result.changed is False
    assert result.tex == GOOD
    assert result.compiled is True  # the original does compile
    assert result.single_page is True
    assert result.warnings


# --- live: aggressive rewrite closes gaps and stays valid ------------------


@pytest.mark.skipif(not os.getenv("OLLAMA_API_KEY"), reason="OLLAMA_API_KEY not set")
def test_live_aggressive_rewrite_closes_gaps():
    from app.services.ats import score_ats

    jd = (FIXTURES / "jd_missingskill.txt").read_text()  # demands Rust / Elixir (absent)
    ats = score_ats(jd, render_tex(GOOD).text)
    result = improver.improve(GOOD, jd, ats)

    assert result.compiled is True
    assert result.single_page is True
    assert result.changed is True
    assert result.changes  # a change-log rode along
    assert result.added  # it reports what it newly claimed
    # preamble byte-identical (structural format-respect held)
    assert improver.split_tex(result.tex)[0] == improver.split_tex(GOOD)[0]
    # a previously-missing keyword now appears in the résumé
    tex_lower = result.tex.lower()
    assert any(m.lower() in tex_lower for m in ats.missing)
