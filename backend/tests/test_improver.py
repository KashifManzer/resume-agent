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


# --- fabrication: any flag reverts the whole edit --------------------------


def test_fabrication_flag_reverts_to_original(monkeypatch):
    _, body, _ = improver.split_tex(GOOD)
    monkeypatch.setattr(
        improver, "_edit_body", lambda b, jd, ats, err=None: (body + "\n% test-edit\n", ["tweaked"], [])
    )
    monkeypatch.setattr(
        improver, "fabrication_check", lambda old, new: ["invented: Staff Engineer at Google"]
    )
    result = improver.improve(GOOD, "jd", _ats())
    assert result.changed is False
    assert result.tex == GOOD  # reverted, byte-identical
    assert result.fabrication_flags == ["invented: Staff Engineer at Google"]
    assert result.warnings


# --- never-worse: no valid candidate → original, changed=False -------------


def test_never_worse_returns_original(monkeypatch):
    monkeypatch.setattr(
        improver, "_edit_body", lambda b, jd, ats, err=None: (r"\undefinedcmd breaks compile", ["x"], [])
    )
    monkeypatch.setattr(improver, "fabrication_check", lambda old, new: [])
    result = improver.improve(GOOD, "jd", _ats())
    assert result.changed is False
    assert result.tex == GOOD
    assert result.compiled is True  # reflects the original, which does compile
    assert result.single_page is True
    assert result.warnings


# --- live: real edit respects the integrity boundaries ---------------------


@pytest.mark.skipif(not os.getenv("OLLAMA_API_KEY"), reason="OLLAMA_API_KEY not set")
def test_live_improve_is_valid_and_faithful():
    from app.services.ats import score_ats

    jd = (FIXTURES / "jd_sample.txt").read_text()
    ats = score_ats(jd, render_tex(GOOD).text)
    result = improver.improve(GOOD, jd, ats)
    assert result.compiled is True
    assert result.single_page is True
    assert result.fabrication_flags == []
    # preamble byte-identical (structural format-respect)
    assert improver.split_tex(result.tex)[0] == improver.split_tex(GOOD)[0]


@pytest.mark.skipif(not os.getenv("OLLAMA_API_KEY"), reason="OLLAMA_API_KEY not set")
def test_live_honesty_absent_skill_not_invented():
    from app.services.ats import score_ats

    jd = (FIXTURES / "jd_missingskill.txt").read_text()
    ats = score_ats(jd, render_tex(GOOD).text)
    result = improver.improve(GOOD, jd, ats)
    assert result.fabrication_flags == []  # did not invent the absent skill
    blob = " ".join(result.could_not_add).lower()
    assert "rust" in blob or "elixir" in blob  # surfaced as unaddable, not faked
