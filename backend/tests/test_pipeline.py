import os
from pathlib import Path

import pytest

from app.schemas.ats import AtsScore
from app.schemas.improver import ImproveResult
from app.schemas.pipeline import HiringAgentReport
from app.schemas.render import Guards, RenderResult
from app.schemas.selector import ResumeInput, Selection
from app.services import pipeline

RESUMES = [ResumeInput(id="r1", tex="TEX1"), ResumeInput(id="r2", tex="TEX2")]


def _ats(overall):
    return AtsScore(
        overall=overall,
        keyword_coverage=0.5,
        llm_fit=overall,
        required_keywords=["Python"],
        matched=["Python"],
        missing=["Rust"],
        rationale="r",
    )


def _render(text="resume text"):
    return RenderResult(
        ok=True,
        pdf_path=Path("/tmp/fake.pdf"),
        page_count=1,
        text=text,
        guards=Guards(compiles=True, extraction_clean=True, single_page=True),
        errors=[],
    )


def _mock(monkeypatch, scores, *, warning=None, hiring=None):
    calls = []
    monkeypatch.setattr(
        pipeline.selector,
        "select_resume",
        lambda jd, rs: Selection(
            picked_id=rs[0].id,
            picked_score=_ats(scores[0]),
            ranked=[{"id": rs[0].id, "score": scores[0]}],
            close=warning is None,
            warning=warning,
        ),
    )
    monkeypatch.setattr(pipeline.render, "render_tex", lambda tex, **k: _render())
    it = iter(scores)
    monkeypatch.setattr(pipeline.ats, "score_ats", lambda jd, text: _ats(next(it)))
    monkeypatch.setattr(
        pipeline.improver,
        "improve",
        lambda tex, jd, ats: ImproveResult(
            tex=tex + "+", changed=True, changes=["change"], could_not_add=["Rust"],
            compiled=True, single_page=True,
        ),
    )

    def fake_hiring(pdf):
        calls.append(pdf)
        return hiring if hiring is not None else HiringAgentReport(
            overall=85, categories={"production": 25}, advice=["do x"]
        )

    monkeypatch.setattr(pipeline.hiring_agent, "score_resume", fake_hiring)
    return calls


def test_inner_loop_keeps_best_stops_on_plateau_gate_once(monkeypatch):
    # baseline 70; rounds score 80, 85, 85 (3rd is a plateau → discard, stop)
    calls = _mock(monkeypatch, [70, 80, 85, 85])
    r = pipeline.run_pipeline("jd", RESUMES)
    assert r.report.ats_before.overall == 70
    assert r.report.ats_after.overall == 85
    assert len(calls) == 1  # hiring-agent called exactly once
    assert r.report.changes == ["change", "change"]  # only the 2 kept rounds
    assert r.report.could_not_add == ["Rust"]  # deduped
    assert r.report.hiring_agent is not None
    assert r.report.selection_warning is None


def test_inner_loop_capped_at_max(monkeypatch):
    # every round improves → would run forever, but caps at INNER_LOOP_MAX
    calls = _mock(monkeypatch, [10, 20, 30, 40, 50, 60])
    r = pipeline.run_pipeline("jd", RESUMES)
    assert len(r.report.changes) == pipeline.INNER_LOOP_MAX


def test_below_gate_adds_github_note(monkeypatch):
    calls = _mock(
        monkeypatch, [70, 70],
        hiring=HiringAgentReport(overall=50, categories={"production": 25}, advice=["add OSS"]),
    )
    r = pipeline.run_pipeline("jd", RESUMES)
    assert r.report.hiring_agent.overall == 50
    assert r.report.hiring_agent.note  # GitHub-driven explanation attached
    assert "add OSS" in r.report.hiring_agent.advice


def test_gate_failure_is_warned_not_fatal(monkeypatch):
    _mock(monkeypatch, [70, 80, 85, 85])
    monkeypatch.setattr(
        pipeline.hiring_agent, "score_resume",
        lambda pdf: (_ for _ in ()).throw(RuntimeError("no venv")),
    )
    r = pipeline.run_pipeline("jd", RESUMES)
    assert r.report.hiring_agent is None
    assert any("quality gate unavailable" in w for w in r.report.warnings)


def test_selection_warning_propagates(monkeypatch):
    _mock(monkeypatch, [30, 30], warning="no résumé is a strong match")
    r = pipeline.run_pipeline("jd", RESUMES)
    assert r.report.selection_warning == "no résumé is a strong match"


# --- live end-to-end (real select→render→score↔improve→gate; slow) ----------

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.skipif(not os.getenv("OLLAMA_API_KEY"), reason="OLLAMA_API_KEY not set")
def test_live_e2e_completes():
    good = ResumeInput(id="good", tex=(FIXTURES / "good.tex").read_text())
    jd = (FIXTURES / "jd_sample.txt").read_text()
    result = pipeline.run_pipeline(jd, [good])
    assert result.pdf_path.exists()  # a real PDF was produced
    assert result.tex.strip()
    # the optimization loop never makes the score worse
    assert result.report.ats_after.overall >= result.report.ats_before.overall
    # report is populated (hiring_agent may be None if the gate can't run)
    assert result.report.ats_before and result.report.ats_after
