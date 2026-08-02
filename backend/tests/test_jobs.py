import pytest

from app.schemas.ats import AtsScore
from app.schemas.pipeline import PipelineResult, Report
from app.schemas.selector import ResumeInput
from app.services import jobs


def _result():
    a = AtsScore(
        overall=80, keyword_coverage=1.0, llm_fit=80,
        required_keywords=[], matched=[], missing=[], rationale="r",
    )
    return PipelineResult(pdf_path="/tmp/x.pdf", tex="TEX", report=Report(ats_before=a, ats_after=a))


def _store(monkeypatch, run=None):
    monkeypatch.setattr(jobs, "run_pipeline", run or (lambda jd, rs, **k: _result()))
    return jobs.JobStore()


def test_lifecycle_queued_running_done(monkeypatch):
    store = _store(monkeypatch)
    job = store.create("jd", [ResumeInput(id="r", tex="T")])
    assert job.status == "queued"
    store.run(job.id)
    done = store.get(job.id)
    assert done.status == "done"
    assert done.result.tex == "TEX"


def test_exception_sets_error_status(monkeypatch):
    def boom(jd, rs, **k):
        raise ValueError("kaboom")

    store = _store(monkeypatch, boom)
    job = store.create("jd", [])
    store.run(job.id)
    j = store.get(job.id)
    assert j.status == "error"
    assert "kaboom" in j.error


def test_feedback_increments_and_caps(monkeypatch):
    store = _store(monkeypatch)
    job = store.create("jd", [ResumeInput(id="r", tex="T")])
    store.run(job.id)  # done, round 0
    for n in range(1, jobs.OUTER_LOOP_MAX + 1):
        j = store.request_feedback(job.id, "more please")
        assert j.round == n
        store.run(job.id)  # complete the round → done again
    with pytest.raises(jobs.FeedbackLimitReached):
        store.request_feedback(job.id, "more please")


def test_feedback_requires_done_job(monkeypatch):
    store = _store(monkeypatch)
    job = store.create("jd", [])
    with pytest.raises(jobs.JobNotDone):  # still queued
        store.request_feedback(job.id, "x")


def test_get_missing_raises(monkeypatch):
    store = _store(monkeypatch)
    with pytest.raises(jobs.JobNotFound):
        store.get("does-not-exist")


def test_list_returns_summaries_newest_first(monkeypatch):
    store = _store(monkeypatch)
    j1 = store.create("Senior Backend Engineer\nAcme Corp", [ResumeInput(id="r", tex="T")])
    j2 = store.create("  \nFrontend Role at Gizmo", [])  # leading blank line
    summaries = store.list()
    assert [s.id for s in summaries] == [j2.id, j1.id]  # newest first
    assert summaries[1].title == "Senior Backend Engineer"  # first non-empty JD line
    assert summaries[0].title == "Frontend Role at Gizmo"
    assert summaries[1].status == "queued"


def test_list_summary_has_pdf_flag_and_title_fallback(monkeypatch):
    store = _store(monkeypatch)
    job = store.create("", [ResumeInput(id="r", tex="T")])  # empty JD → fallback title
    assert store.list()[0].has_pdf is False
    store.run(job.id)  # produces a result with a pdf_path
    s = store.list()[0]
    assert s.has_pdf is True
    assert s.title == "Untitled run"
