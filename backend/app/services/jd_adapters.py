"""Per-ATS adapters (T10). When a URL's host matches a known ATS, hit its public
JSON API directly (deterministic, no LLM, structured title/location) instead of
scraping. Registry — append new boards over time (this ticket is semi-open).

Each adapter: match(url) -> bool, api_url(url) -> str (pure), parse(data, url) -> JdSource.
The network GET (SSRF-guarded) lives in jd_fetch, so adapters stay pure + testable."""

import html
import re
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
        )


class Greenhouse:
    name = "greenhouse"

    def match(self, url: str) -> bool:
        return "greenhouse.io/" in url and ("/jobs/" in url or "gh_jid=" in url)

    def api_url(self, url: str) -> str:
        p = urlparse(url)
        token = p.path.strip("/").split("/")[0]
        m = re.search(r"/jobs/(\d+)", p.path)
        jid = m.group(1) if m else parse_qs(p.query).get("gh_jid", [""])[0]
        return f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{jid}"

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
        )


class Lever:
    name = "lever"

    def match(self, url: str) -> bool:
        return "jobs.lever.co/" in url

    def api_url(self, url: str) -> str:
        company, jid = urlparse(url).path.strip("/").split("/")[:2]
        return f"https://api.lever.co/v0/postings/{company}/{jid}"

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
        )


ADAPTERS = [Workday(), Greenhouse(), Lever(), Ashby()]


def by_name(name: str):
    """A bare next() raises StopIteration, which inside a coroutine surfaces as an
    opaque "RuntimeError: coroutine raised StopIteration"."""
    try:
        return next(a for a in ADAPTERS if a.name == name)
    except StopIteration:
        raise LookupError(f"no ATS adapter named {name!r}") from None
