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
