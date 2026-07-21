import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ats import AtsScore
from app.schemas.pipeline import PipelineResult, Report
from app.services import jobs


@pytest.fixture
def client(monkeypatch, tmp_path):
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake pdf bytes")
    a = AtsScore(
        overall=80, keyword_coverage=1.0, llm_fit=80,
        required_keywords=[], matched=[], missing=[], rationale="r",
    )
    result = PipelineResult(pdf_path=pdf, tex="TEX", report=Report(ats_before=a, ats_after=a))
    # BackgroundTasks run before TestClient returns, so the pipeline "completes" instantly.
    monkeypatch.setattr(jobs, "run_pipeline", lambda jd, rs, **k: result)
    jobs.store._recs.clear()
    return TestClient(app)


def _post_job(client):
    return client.post(
        "/jobs",
        data={"jd": "some job description"},
        files={"files": ("good.tex", b"\\documentclass{article}", "text/plain")},
    )


def test_post_get_pdf_flow(client):
    r = _post_job(client)
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    g = client.get(f"/jobs/{job_id}")
    assert g.status_code == 200
    body = g.json()
    assert body["status"] == "done"
    assert body["result"]["tex"] == "TEX"

    p = client.get(f"/jobs/{job_id}/pdf")
    assert p.status_code == 200
    assert p.headers["content-type"] == "application/pdf"
    assert p.content.startswith(b"%PDF")


def test_get_missing_job_404(client):
    assert client.get("/jobs/nope").status_code == 404


def test_feedback_new_round_then_cap(client):
    job_id = _post_job(client).json()["job_id"]
    for _ in range(jobs.OUTER_LOOP_MAX):
        resp = client.post(f"/jobs/{job_id}/feedback", json={"feedback": "more"})
        assert resp.status_code == 200
    over = client.post(f"/jobs/{job_id}/feedback", json={"feedback": "more"})
    assert over.status_code == 429
