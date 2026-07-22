"""T10 — JD from URL: adapters (URL→API transform + fixture parse), the SSRF
guard, the generic extraction path, dispatch, and the /jd/from-url route."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import jd_adapters as A
from app.services import jd_fetch

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name):
    return (FIXTURES / name).read_text()


# --- adapter URL → API transforms (pure) -----------------------------------


def test_workday_api_url():
    a = A.by_name("workday")
    url = "https://acme.wd5.myworkdayjobs.com/en-US/careers/job/San-Francisco/Senior-Backend-Engineer_R-123"
    assert a.match(url)
    assert a.api_url(url) == (
        "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/careers/job/San-Francisco/Senior-Backend-Engineer_R-123"
    )


def test_greenhouse_api_url_path_and_query_forms():
    a = A.by_name("greenhouse")
    path_url = "https://job-boards.greenhouse.io/acme/jobs/456"
    assert a.match(path_url)
    assert a.api_url(path_url) == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/456"
    q_url = "https://boards.greenhouse.io/acme?gh_jid=456"
    assert a.match(q_url)
    assert a.api_url(q_url) == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/456"


def test_lever_api_url():
    a = A.by_name("lever")
    url = "https://jobs.lever.co/acme/789"
    assert a.match(url)
    assert a.api_url(url) == "https://api.lever.co/v0/postings/acme/789"


def test_ashby_api_url_uses_org_slug():
    a = A.by_name("ashby")
    url = "https://jobs.ashbyhq.com/acme/aaa-111"
    assert a.match(url)
    assert a.api_url(url) == "https://api.ashbyhq.com/posting-api/job-board/acme"


def test_ashby_embedded_form_not_matched():
    # ?ashby_jid= form carries no slug in the URL → don't match → generic/paste.
    a = A.by_name("ashby")
    assert not a.match("https://www.ashbyhq.com/careers?ashby_jid=aaa-111")


# --- adapter parse (saved JSON fixtures) -----------------------------------


def test_workday_parse_strips_html():
    a = A.by_name("workday")
    src = a.parse(json.loads(_fixture("workday.json")), "https://acme.wd5.myworkdayjobs.com/x")
    assert src.title == "Senior Backend Engineer"
    assert src.location == "San Francisco, CA"
    assert "<" not in src.text and "Python & Go" in src.text and "Kubernetes" in src.text
    assert src.adapter == "workday"


def test_greenhouse_parse_unescapes_and_strips():
    a = A.by_name("greenhouse")
    src = a.parse(json.loads(_fixture("greenhouse.json")), "https://job-boards.greenhouse.io/acme/jobs/456")
    assert src.title == "Data Engineer"
    assert src.location == "Remote - US"
    assert src.company == "Acme"
    assert "<" not in src.text and "Spark" in src.text and "Airflow" in src.text
    assert src.adapter == "greenhouse"


def test_lever_parse_uses_plain_description():
    a = A.by_name("lever")
    src = a.parse(json.loads(_fixture("lever.json")), "https://jobs.lever.co/acme/789")
    assert src.title == "Staff Frontend Engineer"
    assert src.location == "New York"
    assert "Build React apps at scale." in src.text
    assert src.adapter == "lever"


def test_ashby_parse_filters_board_by_jid():
    a = A.by_name("ashby")
    src = a.parse(json.loads(_fixture("ashby.json")), "https://jobs.ashbyhq.com/acme/aaa-111")
    assert src.title == "ML Engineer"  # not the "other-000" recruiter job
    assert "PyTorch" in src.text
    assert src.adapter == "ashby"


def test_ashby_parse_missing_jid_raises():
    a = A.by_name("ashby")
    with pytest.raises(jd_fetch.JdFetchError):
        a.parse(json.loads(_fixture("ashby.json")), "https://jobs.ashbyhq.com/acme/zzz-999")


# --- SSRF guard ------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/internal",
    "http://[::1]/x",
    "ftp://example.com/x",
    "file:///etc/passwd",
])
def test_ssrf_blocks_bad_urls(url):
    with pytest.raises(jd_fetch.JdFetchError):
        jd_fetch._check_url(url)


def test_ssrf_validates_resolved_ip(monkeypatch):
    # A public-looking hostname that resolves to a private IP must be blocked.
    monkeypatch.setattr(jd_fetch, "_resolve_ips", lambda host: {"10.0.0.5"})
    with pytest.raises(jd_fetch.JdFetchError):
        jd_fetch._check_url("http://evil.example.com/")


def test_ssrf_allows_public_host(monkeypatch):
    monkeypatch.setattr(jd_fetch, "_resolve_ips", lambda host: {"93.184.216.34"})
    jd_fetch._check_url("https://example.com/jobs/1")  # no raise


def test_ssrf_blocks_redirect_to_private_ip(monkeypatch):
    monkeypatch.setattr(
        jd_fetch, "_resolve_ips",
        lambda host: {"93.184.216.34"} if host == "public.example.com" else {"10.0.0.5"},
    )
    transport = httpx.MockTransport(
        lambda req: httpx.Response(302, headers={"location": "http://internal.evil/"})
    )
    with pytest.raises(jd_fetch.JdFetchError):
        jd_fetch._guarded_get("http://public.example.com/job", transport=transport)


def test_guarded_get_enforces_size_cap(monkeypatch):
    monkeypatch.setattr(jd_fetch, "_resolve_ips", lambda host: {"93.184.216.34"})
    monkeypatch.setattr(jd_fetch.config, "JD_FETCH_MAX_BYTES", 100)
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=b"x" * 500))
    with pytest.raises(jd_fetch.JdFetchError):
        jd_fetch._guarded_get("http://public.example.com/big", transport=transport)


# --- generic extraction path ----------------------------------------------


def test_generic_extracts_and_strips_chrome(monkeypatch):
    monkeypatch.setattr(jd_fetch, "_guarded_get", lambda url, **kw: _fixture("generic_job.html").encode())
    monkeypatch.setattr(jd_fetch.config, "OLLAMA_API_KEY", None)  # skip LLM cleanup
    src = jd_fetch.fetch_jd_from_url("https://careers.example.com/platform-engineer")
    assert src.adapter == "generic"
    assert "Kubernetes" in src.text
    assert "About Us" not in src.text  # nav stripped
    assert "Privacy Policy" not in src.text  # footer stripped
    assert src.warnings == []


def test_generic_short_page_warns(monkeypatch):
    monkeypatch.setattr(jd_fetch, "_guarded_get", lambda url, **kw: b"<html><body><p>hi</p></body></html>")
    monkeypatch.setattr(jd_fetch.config, "OLLAMA_API_KEY", None)
    src = jd_fetch.fetch_jd_from_url("https://careers.example.com/thin")
    assert src.warnings  # too short → warned, no crash
    assert src.adapter == "generic"


# --- dispatch --------------------------------------------------------------


def test_dispatch_routes_to_matching_adapter(monkeypatch):
    monkeypatch.setattr(jd_fetch, "_guarded_get", lambda url, **kw: _fixture("lever.json").encode())
    src = jd_fetch.fetch_jd_from_url("https://jobs.lever.co/acme/789")
    assert src.adapter == "lever"
    assert src.title == "Staff Frontend Engineer"


def test_dispatch_unknown_host_falls_to_generic(monkeypatch):
    monkeypatch.setattr(jd_fetch, "_guarded_get", lambda url, **kw: _fixture("generic_job.html").encode())
    monkeypatch.setattr(jd_fetch.config, "OLLAMA_API_KEY", None)
    src = jd_fetch.fetch_jd_from_url("https://some-random-company.com/careers/1")
    assert src.adapter == "generic"


# --- /jd/from-url route ----------------------------------------------------


def test_route_returns_jdsource(monkeypatch):
    from app.schemas.jd import JdSource
    monkeypatch.setattr(
        jd_fetch, "fetch_jd_from_url",
        lambda url: JdSource(text="Do the job.", title="Engineer", source_url=url, adapter="lever"),
    )
    r = TestClient(app).post("/jd/from-url", json={"url": "https://jobs.lever.co/acme/789"})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "Do the job." and body["adapter"] == "lever"


def test_route_blocked_url_is_4xx(monkeypatch):
    def boom(url):
        raise jd_fetch.JdFetchError("blocked non-public address")
    monkeypatch.setattr(jd_fetch, "fetch_jd_from_url", boom)
    r = TestClient(app).post("/jd/from-url", json={"url": "http://169.254.169.254/"})
    assert r.status_code == 400
