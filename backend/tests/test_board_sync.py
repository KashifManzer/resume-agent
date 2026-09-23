import pytest
from datetime import datetime, timezone
from app.services import board_policy
from app.services.board_sync import is_target_role


@pytest.fixture(autouse=True)
def posting_clock(monkeypatch):
    # Existing sync fixtures were published Jan 2; keep age tests deterministic.
    monkeypatch.setattr(board_policy, "utcnow", lambda: datetime(2026, 1, 3, 12))


def test_admits_the_generalist_and_in_band_engineering_roles():
    for t in [
        "Software Engineer", "sOfTwArE EnGiNeEr", "Software Engineer, Compute Foundations",
        "Software Development Engineer", "SDE I", "New Grad SWE", "Software Developer",
        "Member of Technical Staff",          # bare "staff" used to reject this
        "Frontend Engineer, Payments & Risk",  # "frontend" was missing entirely
        "Backend Developer", "Full Stack Web Developer", "Forward Deployed Engineer",
        "AI Engineer", "Data Engineer", "Platform Engineer", "Infrastructure Engineer",
        "Site Reliability Engineer", "Cloud Security Engineer", "Software Engineer II, Fullstack",
        "Software Engineer, Sales Platform",   # team name must not poison the role
    ]:
        assert is_target_role(t) is True, t


def test_rejects_non_engineering_roles_that_merely_mention_ai():
    """A bare \\bai\\b used to admit anything AI-adjacent, engineering or not."""
    for t in [
        "AI Recruiter", "Director, Applied AI", "Account Executive, AI Sales",
        "Business Systems Analyst, Sales AI & Automation", "Applied AI Architect",
        "Product Marketing Manager", "Sales Development Rep", "HR Coordinator", "IT Support",
        "Machine Learning Specialist",  # a specialist role, not an engineering one
        "Copywriter, Developer",                  # role is Copywriter; "developer" is the team
        "Data Scientist, Developer Productivity",  # role is Data Scientist
    ]:
        assert is_target_role(t) is False, t


def test_rejects_above_band_seniority_including_the_sr_abbreviation():
    for t in [
        "Senior Software Engineer", "SENIOR swe", "Senior SWE",
        "Sr. Software Engineer - Ingestion Core team",  # "sr." was never excluded
        "Sr Software Engineer (Backend)",               # nor bare "sr"
        "Staff Machine Learning Engineer", "Lead AI Researcher", "Principal Full Stack",
        "Manager, Software Engineering", "Lead backend engineer",
    ]:
        assert is_target_role(t) is False, t


def test_rejects_unwanted_domains_and_non_software_engineering():
    for t in [
        "Software Engineer in Test, LUS", "Software Quality Assurance Engineer", "SDET II",
        "Software Engineer, iOS", "Android Engineer, Terminal", "Mobile Engineer, Treasury",
        "Data Center Electrical Engineer", "Manufacturing Quality Engineer",
    ]:
        assert is_target_role(t) is False, t


def test_rejects_customer_facing_and_internal_it_engineering():
    """Real engineering titles, but not the software-building kind. Found by
    auditing what the four gates actually admitted across 3585 live postings."""
    for t in [
        "AV Engineer", "Silicon Engineer", "Network Engineer II",
        "IT Support Engineer", "Product Support Engineer III", "Technical Support Engineer, Metronome",
        "Customer Engineer, Korea", "Presales Customer Engineer, Enterprise (Sydney)",
        "Solutions Engineer", "Solutions Integration Engineer IV", "Technical Solutions Engineer",
        "Partner Engineer, Spain", "Recruiting Solutions Engineer", "Salesforce Developer",
        "Developer Relations", "Technical Documentation and Content Engineer, Claude Docs",
    ]:
        assert is_target_role(t) is False, t


def test_security_engineering_is_kept():
    """The user wants security; only QA/test and mobile are excluded domains."""
    for t in ["Cloud Security Engineer", "Red Team Engineer, Safeguards",
              "Threat Intelligence Engineer", "Vulnerability Management Engineer", "GRC Engineer"]:
        assert is_target_role(t) is True, t


def test_a_team_name_never_triggers_the_non_software_gate():
    """Those words are only disqualifying in the ROLE, not the team it sits on."""
    for t in ["Software Engineer, Network Firewall", "Software Engineer, Enterprise Integrations",
              "Software Engineer, Business Technology", "Software Engineer, Payments and Risk"]:
        assert is_target_role(t) is True, t


def test_search_quality_is_relevance_work_not_qa():
    """A bare "quality"/"test" exclusion would wrongly drop real SWE roles."""
    assert is_target_role("Software Engineer, Search Quality") is True
    assert is_target_role("Software Engineer, Data Quality and Governance") is True


def test_deliberately_kept_edge_categories():
    """User reviewed these three on 2026-09-18 and chose to keep them. They sit
    just outside the stated band, so pin them: a future tightening that drops
    them must be a decision, not an accident."""
    for t in [
        "Software Engineer, Intern",                        # below new grad
        "Software Engineering Internship - San Francisco",
        "Software Engineering Intern (2027 Start) - Winter",
        "Firmware Engineer",                                # embedded, not backend/infra
        "Integration Engineer, Metronome",                  # customer-integration work
    ]:
        assert is_target_role(t) is True, t


# --- T29: software must be positively identified ------------------------------
# A bare "engineer" let aerospace/defense boards flood the feed: 144 of 450 kept
# titles in the 2026-09-23 audit were hardware, facilities or supply-chain roles.
# Every title below is real, taken from that audit.

def test_hardware_and_facilities_engineering_is_rejected():
    for t in [
        "Propulsion Engineer (Raptor Test)", "Avionics Systems Engineer (Starship)",
        "Systems Engineer II, Avionics", "Fluids Engineer - Propulsion Valves, Ducts, Lines",
        "Structural Engineer (Starship Infrastructure)", "Wiring Harness Engineer",
        "Winter 2027 EWIS Harness Engineer Co-op", "PCB Layout Engineer", "RF Electronics Engineer",
        "Powerpack Engineer Level II", "Battery Engineer (Falcon & Dragon)",
        "Supplier Development Engineer, SMT (Starlink)", "Physical Design Engineer, Timing",
        "Midcore Design Verification Engineer", "Controls Engineer, Manufacturing Automation",
        "Robotics Engineer, Manufacturing Automation", "Product Quality Engineer",
        "Construction Project Engineer (MEP)", "Environmental Engineer, Compliance/Air Programs",
        "HVAC Programmer", "CMM Programmer (Valves) - 2nd Shift", "Launch Vehicle Engineer",
        "Engineer II, Propulsion - Engine Performance (R5907)",
        "Engineering Technician, Vacuum & Cryogenic Systems",
    ]:
        assert is_target_role(t) is False, t


def test_non_software_engineer_titles_without_hardware_words_are_rejected():
    """No hardware word, but nothing says software either."""
    for t in ["Operations Engineer (Starshield)", "Deployment Engineer", "Account Engineer",
              "GTM Engineer", "Technical Success Engineer", "Test & Evaluation Engineer",
              "Deployed Engineer, Professional Services", "Software Asset Coordinator"]:
        assert is_target_role(t) is False, t


def test_software_work_is_kept_even_when_the_team_names_hardware():
    """The ROLE decides. A hardware word in the team must not reject a SWE."""
    for t in [
        "Backend Engineer, Control Plane", "Full Stack Engineer, Launch Software",
        "Software Engineer, Manufacturing Infrastructure", "Software Supply Chain Security Engineer",
        "Software Engineer (Controls Software)", "Firmware Engineer, Manufacturing Test",
        "Data Engineer, Ground Network Engineering (Gateway)", "Robotics Software Engineer - Grasping",
        "Engineer- Data Visualization Platform", "Systems Engineer, Email Service",
        "Performance Engineer, Inference Engine", "Engine Programmer Intern",
    ]:
        assert is_target_role(t) is True, t


def test_seniority_anywhere_in_the_title_is_rejected():
    """The head-only check let the level hide in the tail."""
    for t in [
        "BESS Project Engineer, Senior or Staff", "Software Engineer, Full Stack (Senior, Staff+)",
        "Site Reliability Engineer (SRE) Manager", "Member of Technical Staff - Lead, Machines",
        "Backend Engineer - Senior", "Chief Engineer, Navy Airpower",
    ]:
        assert is_target_role(t) is False, t
    for t in ["Member of Technical Staff - Storage", "Software Engineer (Staffing Platform)",
              "Software Engineer, Leadership Tools"]:
        assert is_target_role(t) is True, t


def test_the_role_is_found_after_a_marker_or_program_prefix():
    """Real titles the head-only read dropped."""
    for t in [
        "Intern, Software Engineering, 2027", "Flight Software Intern (Summer 2027)",
        "Flight Software Associate (Winter 2027)", "CONTRACT - Web Development Engineer",
        "AI Inference Core - Infrastructure SW Engineer",
        "Binance Accelerator Programm - Software Engineer (Convert)",
    ]:
        assert is_target_role(t) is True, t


def test_a_person_role_before_a_dash_is_not_rescued():
    for t in ["Technical Recruiter - Software Engineering", "Recruiting Coordinator - Engineering",
              "Sales - Software Engineer", "Intern, Marketing", "Contract - Account Executive"]:
        assert is_target_role(t) is False, t


# --- location: US + Canada, any state or city (T26 item 3) -------------------
# The old EXCLUDE_LOCATIONS was a ~25-string denylist: it never asked "is this
# US/Canada?", only "is this one of 25 places I know?". It has no tests at all,
# which is how a refactor silently deleted it (NameError on every posting,
# swallowed by sync_company_jobs' broad except - the board would just go empty).

from app.services.board_sync import is_target_location


def test_keeps_us_and_canada_in_any_form():
    for l in [
        "San Francisco, CA", "Austin", "Atlanta", "Raleigh, NC", "Washington, DC",
        "Remote - United States", "US-San Francisco; US-NYC; US-Remote",
        "NYC, SF, Seattle, US", "US-SF, US-SEA", "CHI and DUB",
        "Toronto, ON, Canada", "Montreal, Canada", "Vancouver, British Columbia",
        "London, Ontario",          # the Canadian London must beat the UK one
        "AMER", "USCA",             # US/Canada region codes
        "Remote - LA; Remote - OK; Remote - TX",  # LA here is Louisiana
    ]:
        assert is_target_location(l) is True, l


def test_every_us_state_and_canadian_province_is_recognised_by_name():
    """A gap here is a silent false drop: "Fargo, North Dakota; Bangalore, India"
    would lose its US half and be rejected outright."""
    from app.services.board_sync import _DOMESTIC
    states = ["alabama","alaska","arizona","arkansas","california","colorado",
        "connecticut","delaware","florida","georgia","hawaii","idaho","illinois",
        "indiana","iowa","kansas","kentucky","louisiana","maine","maryland",
        "massachusetts","michigan","minnesota","mississippi","missouri","montana",
        "nebraska","nevada","new hampshire","new jersey","new mexico","new york",
        "north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania",
        "rhode island","south carolina","south dakota","tennessee","texas","utah",
        "vermont","virginia","washington","west virginia","wisconsin","wyoming"]
    provinces = ["ontario","british columbia","quebec","alberta","manitoba",
        "saskatchewan","nova scotia","new brunswick","newfoundland",
        "prince edward island","yukon","northwest territories","nunavut"]
    assert len(states) == 50
    for name in states + provinces:
        assert _DOMESTIC.search(name), name
    assert is_target_location("Fargo, North Dakota; Bangalore, India") is True


def test_drops_foreign_only_postings():
    for l in [
        "Bengaluru", "Bengaluru, India", "Dublin", "London, UK", "Berlin",
        "Tel Aviv, Israel", "Zurich, Switzerland", "Seoul, South Korea", "Ukraine",
        "Bangkok", "Auckland", "CDMX", "Mexico City, MX", "Luxembourg",
        "Riyadh, Saudi Arabia", "Singapore", "EMEA", "APAC",
        "Bengaluru, India; Delhi, India; Mumbai, India",
    ]:
        assert is_target_location(l) is False, l


def test_any_valid_wins_on_multi_location_postings():
    """A US role also offered abroad is still a US role. The old denylist dropped
    these outright because a foreign name appeared anywhere in the string."""
    for l in [
        "New York, NY | London, UK", "San Francisco, CA; Bengaluru",
        "Raleigh, NC; Bangalore, India", "Austin, TX | Dublin",
        "Dublin, IE; London, UK; New York City, NY",
    ]:
        assert is_target_location(l) is True, l


def test_two_letter_country_codes_are_not_mistaken_for_us_states():
    """NL is Newfoundland *and* the Netherlands; DE Delaware and Germany; IL
    Illinois and Israel. A foreign city in the same unit must win."""
    for l in [
        "Amsterdam, NL", "Berlin, DE", "Tel Aviv, IL", "Bogota, CO",
        "Buenos Aires, AR", "Jakarta, ID", "Panama City, PA", "Bratislava, SK",
        "Valletta, MT", "Casablanca, MA", "Vientiane, LA", "Lima, PE", "Mumbai, IN",
    ]:
        assert is_target_location(l) is False, l


def test_accented_and_local_spellings_are_recognised_as_foreign():
    """Greenhouse sends "Zurich, CH" with an umlaut, and the foreign list holds
    the English exonym. Found live: "Zurich, CH" was being kept as a US job."""
    for l in ["Z\u00fcrich, CH", "M\u00fcnchen, DE", "Krak\u00f3w, PL", "S\u00e3o Paulo, BR",
              "Bogot\u00e1, CO", "Malm\u00f6, SE", "D\u00fcsseldorf", "Gen\u00e8ve", "Wien, AT",
              "Praha", "Lisboa", "Milano", "K\u00f8benhavn", "\u0141\u00f3d\u017a, PL", "G\u00f6teborg"]:
        assert is_target_location(l) is False, l


def test_accent_folding_never_breaks_a_domestic_match():
    """Transliteration must preserve case: _DOMESTIC_CODE matches UPPERCASE
    codes, so lowercasing here stops "Raleigh, NC" counting and silently
    breaks any-valid-wins. That regression happened; this pins it."""
    for l in ["Montr\u00e9al, Canada", "Raleigh, NC", "Raleigh, NC; Bangalore, India",
              "Wilmington, DE", "Indianapolis, IN", "Chicago, IL", "Denver, CO",
              "Boston, MA", "New Orleans, LA", "Philadelphia, PA", "Atlanta, GA"]:
        assert is_target_location(l) is True, l


def test_unambiguous_foreign_country_codes_are_rejected():
    """CH/SE/AT are not US states, so they read as foreign safely. Codes that
    ARE also US states (DE, NL, IL, IN, CO...) are deliberately excluded."""
    assert is_target_location("Basel, CH") is False
    assert is_target_location("Lund, SE") is False
    assert is_target_location("Graz, AT") is False
    assert is_target_location("Wilmington, DE") is True   # Delaware, not Germany


def test_unrecognised_or_missing_locations_are_kept():
    """Losing a real job is worse than showing one the user can skip."""
    for l in [None, "", "N/A", "Hybrid", "In-Office", "Distributed", "LOCATION"]:
        assert is_target_location(l) is True, repr(l)


def test_lowercase_words_never_match_a_state_code():
    """"OR" is Oregon, "or" is not. Codes match uppercase + comma/dash-preceded."""
    assert is_target_location("Poland - Remote OR Romania - Remote") is False
    assert is_target_location("Remote in Germany") is False


def test_world_regions_are_foreign():
    """T29 audit: all six were on the Board as "unknown, so kept"."""
    for l in ["Asia", "Europe", "Remote (Europe)", "Middle East", "Middle East & North Africa",
              "Ljubljana, Slovenia"]:
        assert is_target_location(l) is False, l


def test_a_region_never_hides_a_us_option():
    """Bare "US" must count as domestic, or a region beside it drops the job."""
    for l in ["Remote - US or Europe", "US | Europe", "Remote (US, Europe)", "US Remote"]:
        assert is_target_location(l) is True, l


# --- posting date (T26 finding A) -------------------------------------------
# Greenhouse bulk-rewrites `updated_at`, collapsing whole boards onto a handful
# of timestamps, which clumps the feed by company and buries new roles. The true
# posting date is `first_published`.

import asyncio
import json
from pathlib import Path


import httpx

from app.services import board_sync
from app.services.board_sync import UNDATED, fetch_greenhouse, parse_ats_date


def _fake_board(payload, status=200, headers=None):
    """Stand in for httpx.AsyncClient. Mirrors the streaming API board_sync uses
    (client.stream -> aiter_bytes), not .get(), so the fake cannot drift into
    testing a code path the real fetcher does not take."""
    body = json.dumps(payload).encode()

    class Resp:
        status_code = status

        def __init__(self):
            # httpx.Headers, not a dict: real header lookup is case-insensitive
            # and a plain dict would make "Retry-After" invisible to .get("retry-after").
            self.headers = httpx.Headers(headers or {})

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"HTTP {self.status_code}", request=httpx.Request("GET", "https://x"),
                    response=httpx.Response(self.status_code))

        async def aiter_bytes(self):
            yield body

    class Stream:
        async def __aenter__(self): return Resp()
        async def __aexit__(self, *a): return False

    class Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def stream(self, method, url, **kw): return Stream()

    return Client


def test_greenhouse_prefers_first_published_over_updated_at(monkeypatch):
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": [{
        "title": "Software Engineer",
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
        "location": {"name": "San Francisco"},
        "first_published": "2026-01-02T00:00:00-05:00",
        "updated_at": "2026-09-17T00:00:00-04:00",  # bulk-rewritten, must lose
    }]}))
    [job] = asyncio.run(fetch_greenhouse("acme"))
    assert job["published_at"] == "2026-01-02T00:00:00-05:00"


def test_greenhouse_does_not_use_edit_time_when_unpublished(monkeypatch):
    """An edit timestamp is not evidence of publication."""
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": [{
        "title": "Software Engineer",
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
        "location": {"name": "Remote"},
        "updated_at": "2026-09-17T00:00:00-04:00",
    }]}))
    [job] = asyncio.run(fetch_greenhouse("acme"))
    assert job["published_at"] is None


def test_undated_job_sorts_last_instead_of_floating_to_the_top():
    """now() would re-stamp undated jobs every sync, pinning them to the top."""
    assert parse_ats_date(None) == UNDATED
    assert parse_ats_date("not-a-date") == UNDATED
    assert parse_ats_date("2026-05-01T00:00:00Z") > UNDATED


def test_real_posting_dates_still_parse_per_provider():
    ashby = parse_ats_date("2026-03-12T16:38:15.322+00:00")
    lever = parse_ats_date("1711403416463")  # epoch ms
    greenhouse = parse_ats_date("2026-09-17T13:05:33-04:00")
    assert ashby.year == 2026 and lever.year == 2024 and greenhouse.year == 2026
    assert all(d.tzinfo is None for d in (ashby, lever, greenhouse))  # naive UTC


# --- canonical Greenhouse URL (T26 item 4) ----------------------------------
# Greenhouse's absolute_url points at the company's own careers site for ~44% of
# the postings that reach the board, which jd_adapters.Greenhouse cannot match,
# so tailoring silently used the generic scraper and got 26-44% of the JD.

from app.services import jd_adapters
from app.services.board_sync import greenhouse_url


def test_builds_the_canonical_board_url_not_the_branded_one():
    job = {"id": 8172487, "absolute_url": "https://stripe.com/jobs/search?gh_jid=8172487"}
    assert greenhouse_url("stripe", job) == "https://job-boards.greenhouse.io/stripe/jobs/8172487"


def test_the_url_we_store_is_one_the_greenhouse_adapter_can_actually_use():
    """The contract between board_sync and jd_adapters, pinned in one place.

    This is the T18 lesson: the two modules know about the same ATS and drifted
    apart silently. If either side changes its URL shape, this fails.
    """
    gh = jd_adapters.by_name("greenhouse")
    url = greenhouse_url("stripe", {"id": 8172487, "absolute_url": "https://stripe.com/x"})
    assert gh.match(url) is True
    assert gh.api_url(url) == "https://boards-api.greenhouse.io/v1/boards/stripe/jobs/8172487"


def test_the_branded_url_is_exactly_what_the_adapter_cannot_match():
    """Pins WHY this fix exists, so nobody 'simplifies' it back to absolute_url."""
    gh = jd_adapters.by_name("greenhouse")
    for branded in [
        "https://stripe.com/jobs/search?gh_jid=8172487",
        "https://www.pinterestcareers.com/jobs/?gh_jid=6922682",
        "https://www.brex.com/careers?gh_jid=123",
        "https://careers.airbnb.com/positions/456",
    ]:
        assert gh.match(branded) is False, branded


def test_falls_back_to_absolute_url_when_there_is_no_id():
    job = {"absolute_url": "https://boards.greenhouse.io/acme/jobs/9"}
    assert greenhouse_url("acme", job) == "https://boards.greenhouse.io/acme/jobs/9"
    assert greenhouse_url("acme", {}) is None


def test_a_zero_id_is_still_an_id():
    """`if not jid` would wrongly treat 0 as missing; the check must be `is None`."""
    assert greenhouse_url("acme", {"id": 0, "absolute_url": "https://x.com/y"}) == \
        "https://job-boards.greenhouse.io/acme/jobs/0"


def test_location_fanout_rows_keep_distinct_urls():
    """One role posted in N locations has N distinct Greenhouse ids, so
    canonicalising must not collapse them into a single primary key."""
    jobs = [{"id": i, "absolute_url": "https://databricks.com/x"} for i in (101, 102, 103)]
    urls = {greenhouse_url("databricks", j) for j in jobs}
    assert len(urls) == 3


def test_fetch_greenhouse_stores_the_canonical_url(monkeypatch):
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": [{
        "id": 555, "title": "Software Engineer",
        "absolute_url": "https://stripe.com/jobs/search?gh_jid=555",
        "location": {"name": "San Francisco, CA"},
        "first_published": "2026-01-02T00:00:00-05:00",
    }]}))
    [job] = asyncio.run(board_sync.fetch_greenhouse("stripe"))
    assert job["url"] == "https://job-boards.greenhouse.io/stripe/jobs/555"
    assert jd_adapters.by_name("greenhouse").match(job["url"]) is True


def test_ashby_and_lever_urls_are_already_canonical_and_untouched(monkeypatch):
    """Only Greenhouse had the branded-host problem; do not 'fix' the others."""
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": [{
        "title": "Software Engineer", "location": "Remote, US",
        "jobUrl": "https://jobs.ashbyhq.com/openai/abc-123", "publishedAt": "2026-03-12T16:38:15Z",
    }]}))
    [job] = asyncio.run(board_sync.fetch_ashby("openai"))
    assert job["url"] == "https://jobs.ashbyhq.com/openai/abc-123"
    assert jd_adapters.by_name("ashby").match(job["url"]) is True


# --- the write path (T26): sync_company_jobs has never been tested ----------
# Its `except Exception: print(...)` turns any bug into a silently empty board.
# That is exactly how a NameError in is_target_location survived a green suite.
# These assert on real rows, so a swallowed exception shows up as zero rows.

from app import db as _db          # resolve SessionLocal at CALL time: conftest's
from app.models import JobPosting, TrackedCompany  # temp-db fixture rebinds it, and a
                                   # module-level `from app.db import SessionLocal`
                                   # would capture the real database instead.


def _sync(monkeypatch, jobs, slug="stripe", provider="greenhouse"):
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": jobs}))
    with _db.SessionLocal() as db:
        company = db.get(TrackedCompany, slug) or TrackedCompany(slug=slug, provider=provider)
        db.add(company)
        db.commit()
        asyncio.run(board_sync.sync_company_jobs(db, company))
    with _db.SessionLocal() as db:
        return {r.url: r for r in db.query(JobPosting).all()}


def _gh(jid, title, location, published="2026-01-02T00:00:00-05:00"):
    return {"id": jid, "title": title, "location": {"name": location},
            "absolute_url": f"https://stripe.com/jobs/search?gh_jid={jid}",
            "first_published": published}


def test_sync_writes_only_matching_jobs_with_the_canonical_url(monkeypatch):
    rows = _sync(monkeypatch, [
        _gh(1, "Software Engineer, Payments", "San Francisco, CA"),   # keep
        _gh(2, "Senior Software Engineer", "San Francisco, CA"),      # too senior
        _gh(3, "Software Engineer, iOS", "San Francisco, CA"),        # mobile
        _gh(4, "Account Executive, AI Sales", "San Francisco, CA"),   # not engineering
        _gh(5, "Software Engineer, Core", "Bengaluru, India"),        # foreign
    ])
    assert list(rows) == ["https://job-boards.greenhouse.io/stripe/jobs/1"], list(rows)
    row = rows["https://job-boards.greenhouse.io/stripe/jobs/1"]
    assert row.status == "open"
    assert row.company_slug == "stripe"
    assert row.created_at.year == 2026 and row.created_at.month == 1  # first_published


def test_sync_keeps_a_us_job_that_is_also_offered_abroad(monkeypatch):
    rows = _sync(monkeypatch, [_gh(7, "Backend Engineer", "New York, NY | London, UK")])
    assert len(rows) == 1


def test_a_posting_that_disappears_is_closed_not_deleted(monkeypatch):
    first = _sync(monkeypatch, [_gh(1, "Software Engineer", "San Francisco, CA"),
                                _gh(2, "Backend Engineer", "Austin, TX")])
    assert len(first) == 2 and all(r.status == "open" for r in first.values())
    second = _sync(monkeypatch, [_gh(1, "Software Engineer", "San Francisco, CA")])
    assert second["https://job-boards.greenhouse.io/stripe/jobs/1"].status == "open"
    assert second["https://job-boards.greenhouse.io/stripe/jobs/2"].status == "closed"


def test_an_empty_board_closes_everything_without_losing_rows(monkeypatch):
    _sync(monkeypatch, [_gh(1, "Software Engineer", "Austin, TX")])
    rows = _sync(monkeypatch, [])
    assert len(rows) == 1
    assert all(r.status == "closed" for r in rows.values())


def test_resync_is_idempotent(monkeypatch):
    jobs = [_gh(1, "Software Engineer", "Austin, TX")]
    _sync(monkeypatch, jobs)
    rows = _sync(monkeypatch, jobs)
    assert len(rows) == 1 and rows["https://job-boards.greenhouse.io/stripe/jobs/1"].status == "open"


def test_a_job_with_no_title_or_url_is_skipped_not_crashed(monkeypatch):
    rows = _sync(monkeypatch, [
        {"id": 9, "title": None, "location": {"name": "Austin, TX"}, "first_published": None},
        _gh(1, "Software Engineer", "Austin, TX"),
    ])
    assert list(rows) == ["https://job-boards.greenhouse.io/stripe/jobs/1"]


# --- item 6: architecture ---------------------------------------------------

def test_ats_endpoints_live_in_one_module():
    """T18's lesson: board_sync and jd_adapters both know these hosts, and two
    copies of the same knowledge drift silently. board_sync must not build ATS
    URLs of its own - it asks the adapter."""
    src = Path(board_sync.__file__).read_text()
    for host in ("api.ashbyhq.com", "boards-api.greenhouse.io", "api.lever.co"):
        assert host not in src, f"{host} is hardcoded in board_sync; use jd_adapters.list_url"
    for name, expected in [
        ("ashby", "https://api.ashbyhq.com/posting-api/job-board/acme"),
        ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/acme/jobs"),
        ("lever", "https://api.lever.co/v0/postings/acme?mode=json"),
    ]:
        assert jd_adapters.by_name(name).list_url("acme") == expected


def test_ashby_list_and_single_job_urls_are_the_same_endpoint():
    """Ashby has no per-job endpoint; if these ever diverge one of them is wrong."""
    a = jd_adapters.by_name("ashby")
    assert a.api_url("https://jobs.ashbyhq.com/acme/1234") == a.list_url("acme")


def test_we_identify_ourselves_honestly():
    assert "resume-agent" in board_sync.USER_AGENT
    assert "Chrome" not in board_sync.USER_AGENT


def test_traversal_shaped_slugs_are_refused():
    for slug in ("../evil", "a/b", "foo bar", "", "..", "a\\\\b", "x..", "figma\n"):  # $ alone admits a trailing newline
        with pytest.raises(ValueError):
            asyncio.run(board_sync._get_board("greenhouse", slug))


def test_retry_after_accepts_seconds_and_http_dates():
    from email.utils import format_datetime
    from datetime import timedelta as _td

    def resp(value):
        return httpx.Response(429, headers={"Retry-After": value} if value else {})

    assert board_sync._retry_after_seconds(resp("120")) == 120
    assert board_sync._retry_after_seconds(resp(""), default=7) == 7
    assert board_sync._retry_after_seconds(resp("not-a-date"), default=9) == 9
    future = datetime.now(timezone.utc) + _td(seconds=90)
    assert 60 <= board_sync._retry_after_seconds(resp(format_datetime(future))) <= 95
    past = datetime.now(timezone.utc) - _td(seconds=90)
    assert board_sync._retry_after_seconds(resp(format_datetime(past))) == 0  # never negative


def test_rate_limiting_raises_instead_of_sleeping_inside_the_company_call():
    """A fixed sleep inside sync_company_jobs stalled every remaining company
    behind one unhappy vendor. It must surface to the loop instead."""
    for status in (403, 429):
        with pytest.raises(board_sync.RateLimited) as got:
            asyncio.run(_get_with(status, {"Retry-After": "42"}))
        assert got.value.retry_after == 42


async def _get_with(status, headers):
    import unittest.mock as m
    with m.patch.object(board_sync.httpx, "AsyncClient", _fake_board({}, status=status, headers=headers)):
        return await board_sync._get_board("greenhouse", "acme")


def test_a_missing_board_is_not_an_error(monkeypatch):
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({}, status=404))
    assert asyncio.run(board_sync._get_board("greenhouse", "gone")) is None
    # None, not [] - "we could not see the board" must stay distinguishable from
    # "the board is empty", because only the latter justifies closing postings.
    assert asyncio.run(board_sync.fetch_greenhouse("gone")) is None
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": []}))
    assert asyncio.run(board_sync.fetch_greenhouse("empty")) == []


def test_a_transient_404_does_not_close_a_companys_whole_feed(monkeypatch):
    """A 404 means we did not observe the board. Closing everything on it would
    wipe a company's feed on one bad request, then reopen it next cycle."""
    _company("acme")
    with _db.SessionLocal() as db:
        company = db.get(TrackedCompany, "acme")
        monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": [
            {"id": 1, "title": "Software Engineer", "location": {"name": "Austin, TX"},
             "first_published": "2026-01-02T00:00:00-05:00"}]}))
        assert asyncio.run(board_sync.sync_company_jobs(db, company)) == 1

        monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({}, status=404))
        assert asyncio.run(board_sync.sync_company_jobs(db, company)) == 0
    with _db.SessionLocal() as db:
        assert [r.status for r in db.query(JobPosting).all()] == ["open"]


def test_an_observed_empty_board_still_closes_its_postings(monkeypatch):
    """The other half: a 200 with no jobs IS evidence the postings are gone."""
    _company("acme")
    with _db.SessionLocal() as db:
        company = db.get(TrackedCompany, "acme")
        monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": [
            {"id": 1, "title": "Software Engineer", "location": {"name": "Austin, TX"},
             "first_published": "2026-01-02T00:00:00-05:00"}]}))
        asyncio.run(board_sync.sync_company_jobs(db, company))
        monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": []}))
        asyncio.run(board_sync.sync_company_jobs(db, company))
    with _db.SessionLocal() as db:
        assert [r.status for r in db.query(JobPosting).all()] == ["closed"]


def test_an_oversized_board_is_refused_rather_than_buffered(monkeypatch):
    monkeypatch.setattr(board_sync, "BOARD_MAX_BYTES", 10)
    monkeypatch.setattr(board_sync.httpx, "AsyncClient",
                        _fake_board({"jobs": [{"title": "x" * 500}]}))
    with pytest.raises(ValueError, match="exceeds"):
        asyncio.run(board_sync._get_board("greenhouse", "acme"))


def test_vendor_failure_and_our_own_bug_are_told_apart(monkeypatch):
    """The whole point of 13b. A vendor problem is expected noise; a NameError in
    our filters must never be swallowed into a silently empty board."""
    with _db.SessionLocal() as db:
        company = TrackedCompany(slug="acme", provider="greenhouse")
        db.add(company); db.commit()

        monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({}, status=500))
        with pytest.raises(board_sync.BoardVendorError):
            asyncio.run(board_sync.sync_company_jobs(db, company))

        monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": [{"title": "Software Engineer", "id": 1, "location": {"name": "Austin, TX"}}]}))
        monkeypatch.setattr(board_sync, "is_target_role", lambda t: (_ for _ in ()).throw(NameError("boom")))
        with pytest.raises(NameError):
            asyncio.run(board_sync.sync_company_jobs(db, company))


def _company(slug="acme", provider="greenhouse", last_synced=None):
    with _db.SessionLocal() as db:
        c = TrackedCompany(slug=slug, provider=provider, last_synced_at=last_synced)
        db.add(c); db.commit()


def test_a_restart_does_not_re_harvest_boards_synced_within_the_interval(monkeypatch):
    """A full ~1000-request cycle used to fire on every uvicorn restart."""
    fresh = board_policy.utcnow()  # the harvester's clock, pinned by posting_clock
    _company("fresh", last_synced=fresh)
    _company("stale", last_synced=fresh - board_sync.HARVEST_INTERVAL * 2)
    _company("never", last_synced=None)
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": []}))
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["skipped_fresh"] == 1
    assert stats["companies"] == 2


def test_one_rate_limited_vendor_does_not_stall_the_rest(monkeypatch):
    _company("a"); _company("b")
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    monkeypatch.setattr(board_sync, "MAX_BACKOFF", 0.01)
    monkeypatch.setattr(board_sync.httpx, "AsyncClient",
                        _fake_board({}, status=429, headers={"Retry-After": "99999"}))
    slept = []
    real_sleep = asyncio.sleep
    async def spy(sec, *a, **k):
        slept.append(sec); return await real_sleep(0)
    monkeypatch.setattr(board_sync.asyncio, "sleep", spy)
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["companies"] == 2               # both attempted, not abandoned
    assert max(slept) <= board_sync.MAX_BACKOFF  # Retry-After honoured but capped


def test_a_vendor_error_is_counted_not_crashed(monkeypatch):
    _company("a")
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({}, status=503))
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["vendor_errors"] == 1 and stats["bugs"] == 0


def test_our_own_bug_is_counted_separately_and_reported(monkeypatch, capsys):
    _company("a")
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    monkeypatch.setattr(board_sync.httpx, "AsyncClient",
                        _fake_board({"jobs": [{"id": 1, "title": "Software Engineer",
                                               "location": {"name": "Austin, TX"}}]}))
    monkeypatch.setattr(board_sync, "is_target_role",
                        lambda t: (_ for _ in ()).throw(NameError("EXCLUDE_LOCATIONS")))
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["bugs"] == 1 and stats["vendor_errors"] == 0
    captured = capsys.readouterr()
    assert "OUR code" in captured.out          # the summary line
    assert "NameError" in captured.err         # the traceback, correctly on stderr


def test_a_cycle_that_writes_nothing_says_so(monkeypatch, capsys):
    """The silent-empty-board failure mode, made audible."""
    _company("a")
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _fake_board({"jobs": []}))
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["kept"] == 0
    assert "no eligible postings" in capsys.readouterr().out


def test_a_normal_cycle_reports_what_it_kept(monkeypatch, capsys):
    _company("a")
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    monkeypatch.setattr(board_sync.httpx, "AsyncClient",
                        _fake_board({"jobs": [{"id": 1, "title": "Software Engineer",
                                               "location": {"name": "Austin, TX"},
                                               "first_published": "2026-01-02T00:00:00-05:00"}]}))
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["kept"] == 1 and stats["bugs"] == 0 and stats["vendor_errors"] == 0
    assert "no eligible postings" not in capsys.readouterr().out


def test_prefix_style_exclusions_match_their_longer_forms():
    """The alternation is wrapped in \\b(...)\\b, so a stem like "facilit" never
    matched "Facilities". Found by auditing what a live harvest actually wrote."""
    for t in ["Facilities Engineer", "Facility Engineer",
              "Datacenter Engineer", "Data Centre Engineer", "Data Center Engineer"]:
        assert is_target_role(t) is False, t


def test_recruiter_titles_are_rejected_by_the_engineering_gate_alone():
    """Deliberately NOT handled by the non-software list: a "recruit" stem would
    also reject "Recruiting Analytics Data Engineer", which is a real data role."""
    for t in ["AI Recruiter", "Technical Recruiter", "Recruiting Coordinator",
              "Recruiter, Technical", "Recruiting Manager"]:
        assert is_target_role(t) is False, t
    assert is_target_role("Recruiting Analytics Data Engineer") is True
    assert is_target_role("Analytics Engineer") is True


def test_an_unknown_or_listless_provider_fails_clearly():
    """A bare next() in by_name surfaced as "RuntimeError: coroutine raised
    StopIteration" - useless when a scout inserts an unexpected provider.
    Workday is a real adapter with no board-listing endpoint."""
    with pytest.raises(LookupError):
        jd_adapters.by_name("nope")
    for provider in ("nosuchprovider", "workday"):
        with pytest.raises(ValueError, match="cannot list a board"):
            asyncio.run(board_sync._get_board(provider, "acme"))


def test_the_scout_identifies_itself_too():
    """It fetches GitHub and Serper; it was sending no User-Agent at all."""
    src = Path(board_sync.__file__).read_text()
    scout = src[src.index("async def scout_loop"):]
    assert "AsyncClient(timeout=15.0)" not in scout, "scout client sends no User-Agent"
    assert "USER_AGENT" in scout


def test_one_failing_company_does_not_lose_another_companys_work(monkeypatch):
    """Each failure path rolls the session back. Prove that rollback does not
    discard a sibling company's committed postings."""
    _company("good"); _company("bad")
    calls = {"n": 0}
    good_board = {"jobs": [{"id": 1, "title": "Software Engineer",
                            "location": {"name": "Austin, TX"},
                            "first_published": "2026-01-02T00:00:00-05:00"}]}

    def client_factory(**kw):
        calls["n"] += 1
        maker = _fake_board(good_board) if calls["n"] == 1 else _fake_board({}, status=500)
        return maker(**kw)

    monkeypatch.setattr(board_sync.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["kept"] == 1 and stats["vendor_errors"] == 1 and stats["bugs"] == 0
    with _db.SessionLocal() as db:
        assert db.query(JobPosting).count() == 1


def test_only_one_traceback_is_printed_however_many_companies_break(monkeypatch, capsys):
    """900 identical tracebacks is noise; one is a signal. The count carries the rest."""
    for i in range(4):
        _company(f"c{i}")
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    monkeypatch.setattr(board_sync.httpx, "AsyncClient",
                        _fake_board({"jobs": [{"id": 1, "title": "Software Engineer",
                                               "location": {"name": "Austin, TX"}}]}))
    monkeypatch.setattr(board_sync, "is_target_role",
                        lambda t: (_ for _ in ()).throw(NameError("boom")))
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["bugs"] == 4
    # count tracebacks, not the exception name: one traceback mentions NameError
    # several times across its frames.
    assert capsys.readouterr().err.count("Traceback (most recent call last)") == 1


# --- scout (had zero coverage) ---------------------------------------------

def test_discover_slugs_finds_all_three_providers():
    text = ("boards.greenhouse.io/acme jobs.ashbyhq.com/Beta "
            "jobs.lever.co/gamma and some prose")
    assert sorted(board_sync.discover_slugs(text)) == [
        ("ashby", "beta"), ("greenhouse", "acme"), ("lever", "gamma")]


def test_discover_slugs_rejects_traversal_shaped_slugs():
    """The capture class permits dots, so "boards.greenhouse.io/../x" yields "..".
    Stored unfiltered it fails EVERY harvest cycle forever as a vendor error."""
    found = board_sync.discover_slugs("boards.greenhouse.io/.. and jobs.lever.co/ok")
    assert found == [("lever", "ok")]


def test_discover_slugs_is_deduplicated_and_lowercased():
    text = "jobs.lever.co/Acme jobs.lever.co/acme jobs.lever.co/ACME"
    assert board_sync.discover_slugs(text) == [("lever", "acme")]


def _listings(*items, status=200):
    """Stand in for the scout's client: GET returns SimplifyJobs listings.json."""
    class Resp:
        status_code = status
        def json(self):
            if isinstance(items[0] if items else None, Exception):
                raise items[0]
            return list(items) if not (items and items[0] == "NOT-A-LIST") else {"x": 1}
    class Client:
        async def get(self, url, **kw):
            assert url == board_sync.SIMPLIFY_LISTINGS
            return Resp()
    return Client()


def test_scout_tracks_new_companies(monkeypatch):
    client = _listings({"active": True, "url": "https://job-boards.greenhouse.io/newco/jobs/1"},
                       {"active": True, "url": "https://jobs.lever.co/otherco/abc?lever-source=Simplify"})
    with _db.SessionLocal() as db:
        added = asyncio.run(board_sync._scout_github(client, db))
        assert added == 2
        slugs = {c.slug: c for c in db.query(TrackedCompany).all()}
    assert slugs["newco"].provider == "greenhouse"
    assert slugs["newco"].discovery_source == "simplify"
    assert slugs["otherco"].provider == "lever"


def test_scout_counts_only_companies_that_are_new(monkeypatch):
    """It used to print every sighting as if it were a discovery."""
    client = _listings({"active": True, "url": "https://jobs.ashbyhq.com/acme/1"},
                       {"active": True, "url": "https://jobs.ashbyhq.com/acme/2"})
    with _db.SessionLocal() as db:
        assert asyncio.run(board_sync._scout_github(client, db)) == 1
        assert asyncio.run(board_sync._scout_github(client, db)) == 0


def test_scout_ignores_closed_and_malformed_listings(monkeypatch):
    client = _listings({"active": False, "url": "https://jobs.ashbyhq.com/closedco/1"},
                       {"active": "yes", "url": "https://jobs.ashbyhq.com/truthyco/1"},
                       {"active": True, "url": None}, {"active": True}, "a string", 7,
                       {"active": True, "url": "https://boards.greenhouse.io/embed/job_app?token=1"},
                       {"active": True, "url": "https://jobs.ashbyhq.com/embedding-vc/1"})
    with _db.SessionLocal() as db:
        assert asyncio.run(board_sync._scout_github(client, db)) == 1
        assert [c.slug for c in db.query(TrackedCompany)] == ["embedding-vc"]


@pytest.mark.parametrize("body", [ValueError("not json"), "NOT-A-LIST"])
def test_a_broken_listings_file_is_vendor_noise_not_a_crash(monkeypatch, body, capsys):
    with _db.SessionLocal() as db:
        assert asyncio.run(board_sync._scout_github(_listings(body), db)) == 0
    assert "[scout] listings.json" in capsys.readouterr().out


def test_scout_does_not_flip_an_existing_companys_provider(monkeypatch):
    """Overwriting provider orphans the postings harvested under the old one."""
    _company("acme", provider="greenhouse")
    with _db.SessionLocal() as db:
        asyncio.run(board_sync._scout_github(_listings({"active": True, "url": "https://jobs.lever.co/acme/1"}), db))
        assert db.get(TrackedCompany, "acme").provider == "greenhouse"


def test_scout_skips_a_source_that_does_not_return_200(monkeypatch):
    client = _listings({"active": True, "url": "https://jobs.ashbyhq.com/shouldnotappear/1"}, status=404)
    with _db.SessionLocal() as db:
        assert asyncio.run(board_sync._scout_github(client, db)) == 0
        assert db.query(TrackedCompany).count() == 0


def test_scout_skips_serper_without_a_key(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    with _db.SessionLocal() as db:
        assert asyncio.run(board_sync._scout_serper(object(), db)) == 0


# --- T29: dead and moved boards, conditional GET, rolling cadence ------------

from datetime import timedelta


@pytest.fixture(autouse=True)
def fresh_etags():
    board_sync._ETAGS.clear(); board_sync._UNCOMMITTED_ETAGS.clear()
    yield
    board_sync._ETAGS.clear(); board_sync._UNCOMMITTED_ETAGS.clear()


def _routed(routes, seen=None):
    """Like _fake_board, but answers per vendor host and records each request.
    routes: {host fragment: (payload, status, headers) or a callable(headers)
    returning one}. Any host not routed answers 404, like a vendor without
    that slug."""
    def answer(url, headers):
        for fragment, route in routes.items():
            if fragment in url:
                return route(headers) if callable(route) else route
        return ({}, 404, {})

    class Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def stream(self, method, url, headers=None, **kw):
            if seen is not None:
                seen.append((url, dict(headers or {})))
            payload, status, hdrs = answer(url, headers or {})
            return _fake_board(payload, status=status, headers=hdrs)().stream(method, url)
    return Client


GH, ASHBY, LEVER = "boards-api.greenhouse.io", "api.ashbyhq.com", "api.lever.co"
_ASHBY_JOB = {"id": "a1", "title": "Software Engineer", "location": "Austin, TX",
              "jobUrl": "https://jobs.ashbyhq.com/acme/a1", "publishedAt": "2026-01-02T00:00:00Z"}
_GH_JOB = {"id": 1, "title": "Software Engineer", "location": {"name": "Austin, TX"},
           "first_published": "2026-01-02T00:00:00-05:00"}


def _sync_acme(monkeypatch, client):
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", client)
    with _db.SessionLocal() as db:
        company = db.get(TrackedCompany, "acme")
        result = asyncio.run(board_sync.sync_company_jobs(db, company))
    with _db.SessionLocal() as db:
        return result, db.get(TrackedCompany, "acme"), {r.url: r for r in db.query(JobPosting)}


def test_a_board_that_moved_ats_is_followed(monkeypatch):
    """Notion, Sentry, Zapier... 404'd on their recorded ATS for hours on end."""
    _company("acme", provider="greenhouse")
    kept, company, rows = _sync_acme(monkeypatch, _routed({ASHBY: ({"jobs": [_ASHBY_JOB]}, 200, {})}))
    assert kept == 1 and company.provider == "ashby" and company.gone_at is None
    assert list(rows) == ["https://jobs.ashbyhq.com/acme/a1"]


def test_the_old_ats_postings_close_once_the_move_is_seen(monkeypatch):
    _company("acme", provider="greenhouse")
    _sync_acme(monkeypatch, _routed({GH: ({"jobs": [_GH_JOB]}, 200, {})}))
    _, _, rows = _sync_acme(monkeypatch, _routed({ASHBY: ({"jobs": [_ASHBY_JOB]}, 200, {})}))
    assert rows["https://job-boards.greenhouse.io/acme/jobs/1"].status == "closed"
    assert rows["https://jobs.ashbyhq.com/acme/a1"].status == "open"


def test_a_board_on_no_ats_is_parked_and_keeps_its_postings(monkeypatch):
    _company("acme", provider="greenhouse")
    _sync_acme(monkeypatch, _routed({GH: ({"jobs": [_GH_JOB]}, 200, {})}))
    seen = []
    kept, company, rows = _sync_acme(monkeypatch, _routed({}, seen))
    assert kept == 0 and company.gone_at is not None and company.provider == "greenhouse"
    assert sorted(u.split("/")[2] for u, _ in seen) == sorted([GH, LEVER, ASHBY])  # all three asked
    assert [r.status for r in rows.values()] == ["open"]  # a 404 is not proof of closure


def test_a_parked_board_is_skipped_until_its_weekly_recheck(monkeypatch):
    now = board_policy.utcnow()
    long_ago = now - board_sync.HARVEST_INTERVAL * 3
    with _db.SessionLocal() as db:
        db.add(TrackedCompany(slug="dead", provider="greenhouse", last_synced_at=long_ago,
                              gone_at=now - timedelta(days=1)))
        db.add(TrackedCompany(slug="due", provider="greenhouse", last_synced_at=long_ago,
                              gone_at=now - board_sync.PARK_FOR - timedelta(hours=1)))
        db.commit()
    seen = []
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _routed({}, seen))
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["parked"] == 1 and stats["companies"] == 1
    assert seen and all("/due" in u for u, _ in seen)  # only the due one was asked


def test_a_board_that_comes_back_is_unparked(monkeypatch):
    with _db.SessionLocal() as db:
        db.add(TrackedCompany(slug="acme", provider="greenhouse", gone_at=datetime(2025, 1, 1)))
        db.commit()
    kept, company, _ = _sync_acme(monkeypatch, _routed({GH: ({"jobs": [_GH_JOB]}, 200, {})}))
    assert kept == 1 and company.gone_at is None


def test_a_stale_etag_on_the_other_ats_cannot_hide_a_moved_board(monkeypatch):
    """A 304 carries no jobs, so re-resolve must ask unconditionally."""
    _company("acme", provider="greenhouse")
    board_sync._ETAGS[("ashby", "acme")] = '"old"'
    ashby = lambda h: ({}, 304, {}) if "If-None-Match" in h else ({"jobs": [_ASHBY_JOB]}, 200, {})
    kept, company, _ = _sync_acme(monkeypatch, _routed({ASHBY: ashby}))
    assert kept == 1 and company.provider == "ashby"


def test_an_unchanged_board_is_not_reprocessed(monkeypatch):
    _company("acme", provider="greenhouse")
    seen = []
    etagged = _routed({GH: ({"jobs": [_GH_JOB]}, 200, {"ETag": 'W/"v1"'})}, seen)
    assert _sync_acme(monkeypatch, etagged)[0] == 1
    first_update = _sync_acme(monkeypatch, _routed({}))[2]  # sanity: rows exist
    not_modified = lambda h: ({}, 304, {}) if h.get("If-None-Match") == 'W/"v1"' else ({"jobs": []}, 200, {})
    kept, company, rows = _sync_acme(monkeypatch, _routed({GH: not_modified}, seen))
    assert kept is None                                    # "unchanged", not "0 kept"
    assert seen[-1][1]["If-None-Match"] == 'W/"v1"'
    assert [r.status for r in rows.values()] == ["open"]   # an empty 200 would have closed it
    assert company.gone_at is None and company.last_synced_at is not None
    assert first_update


def test_an_etag_is_trusted_only_after_its_rows_commit(monkeypatch):
    """If processing crashes, the next request must refetch, not get a 304 that
    pins whatever half-state the crash left."""
    _company("acme", provider="greenhouse")
    real_filter = board_sync.is_target_role
    monkeypatch.setattr(board_sync, "is_target_role", lambda t: (_ for _ in ()).throw(NameError("bug")))
    with pytest.raises(NameError):
        _sync_acme(monkeypatch, _routed({GH: ({"jobs": [_GH_JOB]}, 200, {"ETag": '"v1"'})}))
    assert board_sync._ETAGS == {}
    # NOT monkeypatch.undo(): it would also undo conftest's temp-DB patch.
    monkeypatch.setattr(board_sync, "is_target_role", real_filter)
    seen = []
    _sync_acme(monkeypatch, _routed({GH: ({"jobs": [_GH_JOB]}, 200, {"ETag": '"v2"'})}, seen))
    assert "If-None-Match" not in seen[0][1]
    assert board_sync._ETAGS == {("greenhouse", "acme"): '"v2"'}


def test_an_etag_dropped_by_the_vendor_is_forgotten(monkeypatch):
    _company("acme", provider="greenhouse")
    _sync_acme(monkeypatch, _routed({GH: ({"jobs": [_GH_JOB]}, 200, {"ETag": '"v1"'})}))
    _sync_acme(monkeypatch, _routed({GH: ({"jobs": [_GH_JOB]}, 200, {})}))
    assert board_sync._ETAGS == {}


def test_an_all_unchanged_pass_does_not_cry_empty_board(monkeypatch, capsys):
    _company("a")
    board_sync._ETAGS[("greenhouse", "a")] = '"v1"'
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", _routed({GH: ({}, 304, {})}))
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["unchanged"] == 1 and stats["kept"] == 0
    assert "no eligible postings" not in capsys.readouterr().out


@pytest.mark.parametrize("status", [503, 429])
def test_a_failing_board_waits_the_interval_instead_of_every_pass(monkeypatch, status):
    """With a 60s poll, an unstamped failure would be refetched ~60 times an hour."""
    _company("a")
    seen = []
    monkeypatch.setattr(board_sync.httpx, "AsyncClient",
                        _routed({GH: ({}, status, {"Retry-After": "0"})}, seen))
    monkeypatch.setattr(board_sync, "JITTER", (0, 0))
    asyncio.run(board_sync._harvest_cycle())
    second = asyncio.run(board_sync._harvest_cycle())
    assert len(seen) == 1 and second["skipped_fresh"] == 1


def test_a_quiet_pass_prints_nothing(monkeypatch, capsys):
    _company("a", last_synced=board_policy.utcnow())
    stats = asyncio.run(board_sync._harvest_cycle())
    assert stats["skipped_fresh"] == 1 and capsys.readouterr().out == ""


def test_the_harvester_polls_every_minute(monkeypatch):
    slept = []
    async def cycle(): return {}
    async def sleep(seconds):
        slept.append(seconds)
        raise asyncio.CancelledError
    monkeypatch.setattr(board_sync, "_harvest_cycle", cycle)
    monkeypatch.setattr(board_sync.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(board_sync.harvester_loop())
    assert slept == [board_sync.HARVEST_POLL] == [60]


def test_an_existing_db_file_gains_the_gone_at_column(tmp_path, monkeypatch):
    """create_all never ALTERs; without the migration every harvest would crash."""
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE tracked_companies (slug VARCHAR PRIMARY KEY, "
                          "provider VARCHAR, discovery_source VARCHAR, last_synced_at DATETIME)"))
        conn.execute(text("INSERT INTO tracked_companies VALUES ('acme', 'lever', 'github', NULL)"))
    monkeypatch.setattr(_db, "engine", engine)
    monkeypatch.setattr(_db, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    _db.init_db()
    assert "gone_at" in {c["name"] for c in inspect(engine).get_columns("tracked_companies")}
    with _db.SessionLocal() as db:
        assert db.get(TrackedCompany, "acme").gone_at is None


def test_discover_slugs_never_yields_the_greenhouse_embed_path():
    text = "https://boards.greenhouse.io/embed/job_app?token=7669159003 jobs.ashbyhq.com/embedding-vc/x"
    assert board_sync.discover_slugs(text) == [("ashby", "embedding-vc")]


def test_serper_rotates_the_phrase_across_all_four_sites(monkeypatch, capsys):
    monkeypatch.setenv("SERPER_API_KEY", "k")
    asked = []
    class Resp:
        status_code = 200
        def __init__(self, q): self.q = q
        def json(self):
            if "jobs.ashbyhq.com" in self.q:
                return {"organic": [{"link": "https://jobs.ashbyhq.com/newco/1"},
                                    {"link": "https://jobs.ashbyhq.com/newco/2"}]}
            return {"organic": [{"link": "https://www.youtube.com/watch?v=x"}]}  # site: fell back
    class Client:
        async def post(self, url, json=None, **kw):
            asked.append(json); return Resp(json["q"])
    with _db.SessionLocal() as db:
        assert asyncio.run(board_sync._scout_serper(Client(), db)) == 1
    assert [q["q"].split('"')[0].strip() for q in asked] == [f"site:{s}" for s in board_sync.SERPER_SITES]
    assert len({q["q"].split('"')[1] for q in asked}) == 1          # one phrase per day
    assert all(set(q) == {"q"} for q in asked)                        # no page/tbs: both break site:
    out = capsys.readouterr().out
    assert "0 boards in 1 results" in out                              # a fallback is visible


def test_every_serper_phrase_is_used_within_a_week():
    import datetime as dt
    days = [dt.date(2026, 9, 23) + dt.timedelta(d) for d in range(7)]
    used = {board_sync.SERPER_PHRASES[d.toordinal() % len(board_sync.SERPER_PHRASES)] for d in days}
    assert used == set(board_sync.SERPER_PHRASES)


def test_the_scout_runs_daily_across_restarts(tmp_path, monkeypatch):
    """A --reload restart used to rerun the whole scout, spending Serper credits."""
    import os, time
    monkeypatch.setattr(board_sync.config, "DATA_DIR", tmp_path)
    assert board_sync._scout_due() is True                       # fresh install: run now
    marker = tmp_path / "scout_last_run"
    marker.touch()
    assert board_sync._scout_due() is False                      # a restart an hour later
    old = time.time() - board_sync.SCOUT_INTERVAL.total_seconds() - 1
    os.utime(marker, (old, old))
    assert board_sync._scout_due() is True                       # a day later


@pytest.mark.parametrize("fails", [False, True])
def test_the_marker_is_touched_only_after_a_successful_scout(tmp_path, monkeypatch, fails):
    monkeypatch.setattr(board_sync.config, "DATA_DIR", tmp_path)
    async def github(client, db):
        if fails:
            raise RuntimeError("boom")
        return 0
    async def serper(client, db): return 0
    async def stop(_): raise asyncio.CancelledError
    monkeypatch.setattr(board_sync, "_scout_github", github)
    monkeypatch.setattr(board_sync, "_scout_serper", serper)
    monkeypatch.setattr(board_sync.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(board_sync.scout_loop())
    assert (tmp_path / "scout_last_run").exists() is (not fails)


def test_a_scout_that_is_not_due_does_no_network_io(tmp_path, monkeypatch):
    monkeypatch.setattr(board_sync.config, "DATA_DIR", tmp_path)
    (tmp_path / "scout_last_run").touch()
    def no_client(**kw): raise AssertionError("scout touched the network while not due")
    async def stop(_): raise asyncio.CancelledError
    monkeypatch.setattr(board_sync.httpx, "AsyncClient", no_client)
    monkeypatch.setattr(board_sync.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(board_sync.scout_loop())
