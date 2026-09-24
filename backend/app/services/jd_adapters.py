"""Per-ATS adapters (T10). When a URL's host matches a known ATS, hit its public
JSON API directly (deterministic, no LLM, structured title/location) instead of
scraping. Registry — append new boards over time (this ticket is semi-open).

Each adapter: match(url) -> bool, api_url(url) -> str (pure), parse(data, url) -> JdSource.
The network GET (SSRF-guarded) lives in jd_fetch, so adapters stay pure + testable."""

import html
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from app.schemas.jd import JdSource

_BLOCK = re.compile(r"</(?:p|div|li|h[1-6]|tr|ul|ol)>|<br\s*/?>|<li[^>]*>", re.I)


def board_jobs(data, provider: str) -> list[dict]:
    """A missing/malformed list is not evidence that every posting has closed."""
    jobs = data if provider == "lever" else data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs):
        raise ValueError(f"invalid {provider} board: expected a jobs list")
    url_key = {"greenhouse": "absolute_url", "lever": "hostedUrl", "ashby": "jobUrl"}[provider]
    for job in jobs:
        if not any(isinstance(job.get(key), (str, int)) and str(job[key]).strip()
                   for key in ("id", url_key)):
            raise ValueError(f"invalid {provider} board: missing posting identifier")
    return jobs


def _strip_html(s: str) -> str:
    """HTML fragment → readable text: block tags become line breaks, other tags
    drop, entities unescape, blank lines collapse."""
    if not isinstance(s, str):
        raise ValueError("invalid ATS description: expected text")
    s = _BLOCK.sub("\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return "\n".join(ln.strip() for ln in s.splitlines() if ln.strip()).strip()


def parse_ats_date(value) -> datetime | None:
    """ATS date -> naive UTC, or None when missing/unparseable. Handles ISO strings
    (with or without offset, or date-only as Workday sends) and Lever's epoch ms."""
    if not value:
        return None
    try:
        if str(value).isdigit():
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).replace(tzinfo=None)
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        # Naive is assumed to be UTC already; aware is converted and stripped.
        return dt if dt.tzinfo is None else dt.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        return None


def object_field(data: dict, key: str) -> dict:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"invalid ATS {key}: expected an object")
    return value


class Workday:
    name = "workday"

    def match(self, url: str) -> bool:
        return bool(re.search(r"\.wd\d+\.myworkdayjobs\.com/", url)) and "/job/" in url

    def api_url(self, url: str) -> str:
        p = urlparse(url)
        tenant = p.hostname.split(".")[0]
        left, job_path = p.path.split("/job/", 1)
        site = left.rstrip("/").split("/")[-1]  # last segment before /job/ (skips a locale like en-US)
        return f"https://{p.hostname}/wday/cxs/{tenant}/{site}/job/{job_path}"

    def parse(self, data: dict, url: str) -> JdSource:
        info = object_field(data, "jobPostingInfo")
        return JdSource(
            text=_strip_html(info.get("jobDescription", "")),
            title=info.get("title"),
            location=info.get("location"),
            source_url=url,
            apply_url=url,  # Workday's posting URL is itself the apply page
            adapter=self.name,
            # A bare calendar date (verified: "Posted Today" -> today's date). Kept
            # as a date, not UTC midnight, which reads as "yesterday" west of UTC.
            posted_at=(d := parse_ats_date(info.get("startDate"))) and d.date(),
        )


class Greenhouse:
    name = "greenhouse"

    def match(self, url: str) -> bool:
        if "greenhouse.io/" not in url:
            return False
        p = urlparse(url)
        if p.path.startswith("/embed/"):
            # the iframe a careers site embeds: embed/job_app?for={board}&token={job id}
            q = parse_qs(p.query)
            return p.path.startswith("/embed/job_app") and "for" in q and "token" in q
        return "/jobs/" in url or "gh_jid=" in url

    def api_url(self, url: str) -> str:
        p = urlparse(url)
        m = re.search(r"/jobs/(\d+)", p.path)
        q = parse_qs(p.query)
        jid = m.group(1) if m else (q.get("gh_jid") or q.get("token") or [""])[0]
        return f"https://boards-api.greenhouse.io/v1/boards/{self._token(url)}/jobs/{jid}"

    def _token(self, url: str) -> str:
        p = urlparse(url)
        if p.path.startswith("/embed/"):
            return parse_qs(p.query)["for"][0]
        return p.path.strip("/").split("/")[0]

    def board_slug(self, url: str) -> str:
        """The slug list_url takes. Lowercase, like every tracked company (T28)."""
        return self._token(url).lower()

    def list_url(self, slug: str) -> str:
        """Every posting on a board (T26). Same API family as api_url - kept here
        so ATS endpoint knowledge lives in ONE module (the T18 drift lesson)."""
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"

    def parse(self, data: dict, url: str) -> JdSource:
        content = data.get("content", "")
        if not isinstance(content, str):
            raise ValueError("invalid Greenhouse content: expected text")
        return JdSource(
            text=_strip_html(html.unescape(content)),  # content is entity-escaped HTML
            title=data.get("title"),
            location=object_field(data, "location").get("name"),
            company=data.get("company_name"),
            source_url=url,
            apply_url=data.get("absolute_url"),
            adapter=self.name,
            posted_at=parse_ats_date(data.get("first_published")),
            # Greenhouse bulk-rewrites this on board-wide edits (T26), so it is
            # "last touched", not proof the posting itself changed.
            updated_at=parse_ats_date(data.get("updated_at")),
        )


class Lever:
    name = "lever"

    def match(self, url: str) -> bool:
        return "jobs.lever.co/" in url

    def api_url(self, url: str) -> str:
        company, jid = urlparse(url).path.strip("/").split("/")[:2]
        return f"https://api.lever.co/v0/postings/{company}/{jid}"

    def board_slug(self, url: str) -> str:
        # ponytail: lowercased like the scout; Lever slugs ARE case-sensitive
        # (Palantir 404s), but 0 of 51 stored and 0 of 1219 sampled live Lever
        # URLs used uppercase (2026-09-22). Keep the URL's case if one ever does.
        return urlparse(url).path.strip("/").split("/")[0].lower()

    def list_url(self, slug: str) -> str:
        return f"https://api.lever.co/v0/postings/{slug}?mode=json"

    def parse(self, data: dict, url: str) -> JdSource:
        # descriptionPlain combines opening/body, but excludes the requirements
        # lists and closing text. Some live postings put their entire JD in lists.
        sections = [data.get("descriptionPlain") or _strip_html(data.get("description") or "")]
        lists = data.get("lists")
        if lists is None:
            lists = []
        if not isinstance(lists, list) or any(not isinstance(item, dict) for item in lists):
            raise ValueError("invalid Lever lists: expected a list of sections")
        for item in lists:
            sections.extend([item.get("text") or "", _strip_html(item.get("content") or "")])
        sections.append(data.get("additionalPlain") or _strip_html(data.get("additional") or ""))
        if any(not isinstance(section, str) for section in sections):
            raise ValueError("invalid Lever section: expected text")
        return JdSource(
            text="\n\n".join(section.strip() for section in sections if section.strip()),
            title=data.get("text"),
            location=object_field(data, "categories").get("location"),
            source_url=url,
            apply_url=data.get("hostedUrl"),
            adapter=self.name,
            posted_at=parse_ats_date(data.get("createdAt")),  # Lever exposes no update time
        )


class Ashby:
    name = "ashby"

    def match(self, url: str) -> bool:
        # only the jobs.ashbyhq.com/{org}/{id} form carries a slug; the embedded
        # ?ashby_jid= form has none → let it fall through to generic/paste.
        p = urlparse(url)
        return p.hostname == "jobs.ashbyhq.com" and len(p.path.strip("/").split("/")) >= 2

    def _org_jid(self, url: str) -> tuple[str, str]:
        org, jid = urlparse(url).path.strip("/").split("/")[:2]
        return org, jid

    def api_url(self, url: str) -> str:
        org, _ = self._org_jid(url)
        return self.list_url(org)

    def board_slug(self, url: str) -> str:
        return self._org_jid(url)[0].lower()

    def list_url(self, slug: str) -> str:
        """Ashby has no per-job endpoint - api_url fetches the whole board and
        parse() filters it, so the two are literally the same URL."""
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"

    def parse(self, data: dict, url: str) -> JdSource:
        from app.services.jd_fetch import JdFetchError  # local: avoid import cycle

        _, jid = self._org_jid(url)
        jobs = board_jobs(data, self.name)
        # Missing identifiers make absence ambiguous, not a confirmed removal.
        if any(not isinstance(j.get("id"), str) or not j["id"].strip() for j in jobs):
            raise ValueError("invalid Ashby board: missing posting identifier")
        job = next((j for j in jobs if j.get("id") == jid), None)
        if job is None:
            raise JdFetchError("job not found in Ashby board", status_code=404)
        return JdSource(
            text=job.get("descriptionPlain", ""),  # already clean text
            title=job.get("title"),
            location=job.get("location"),
            source_url=url,
            apply_url=job.get("applyUrl") or job.get("jobUrl"),
            adapter=self.name,
            posted_at=parse_ats_date(job.get("publishedAt")),  # Ashby exposes no update time
        )


ADAPTERS = [Workday(), Greenhouse(), Lever(), Ashby()]


def by_name(name: str):
    """A bare next() raises StopIteration, which inside a coroutine surfaces as an
    opaque "RuntimeError: coroutine raised StopIteration"."""
    try:
        return next(a for a in ADAPTERS if a.name == name)
    except StopIteration:
        raise LookupError(f"no ATS adapter named {name!r}") from None
