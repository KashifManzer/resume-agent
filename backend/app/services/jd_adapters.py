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


def _strip_html(s: str) -> str:
    """HTML fragment → readable text: block tags become line breaks, other tags
    drop, entities unescape, blank lines collapse."""
    s = _BLOCK.sub("\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return "\n".join(ln.strip() for ln in s.splitlines() if ln.strip()).strip()


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
        info = data.get("jobPostingInfo", {})
        return JdSource(
            text=_strip_html(info.get("jobDescription", "")),
            title=info.get("title"),
            location=info.get("location"),
            source_url=url,
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

    def parse(self, data: dict, url: str) -> JdSource:
        return JdSource(
            text=_strip_html(html.unescape(data.get("content", ""))),  # content is entity-escaped HTML
            title=data.get("title"),
            location=(data.get("location") or {}).get("name"),
            company=data.get("company_name"),
            source_url=url,
            adapter=self.name,
        )


class Lever:
    name = "lever"

    def match(self, url: str) -> bool:
        return "jobs.lever.co/" in url

    def api_url(self, url: str) -> str:
        company, jid = urlparse(url).path.strip("/").split("/")[:2]
        return f"https://api.lever.co/v0/postings/{company}/{jid}"

    def parse(self, data: dict, url: str) -> JdSource:
        return JdSource(
            text=data.get("descriptionPlain", ""),  # already clean text
            title=data.get("text"),
            location=(data.get("categories") or {}).get("location"),
            source_url=url,
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
        return f"https://api.ashbyhq.com/posting-api/job-board/{org}"

    def parse(self, data: dict, url: str) -> JdSource:
        from app.services.jd_fetch import JdFetchError  # local: avoid import cycle

        _, jid = self._org_jid(url)
        job = next((j for j in data.get("jobs", []) if j.get("id") == jid), None)
        if job is None:
            raise JdFetchError("job not found in Ashby board")
        return JdSource(
            text=job.get("descriptionPlain", ""),  # already clean text
            title=job.get("title"),
            location=job.get("location"),
            source_url=url,
            adapter=self.name,
        )


ADAPTERS = [Workday(), Greenhouse(), Lever(), Ashby()]


def by_name(name: str):
    return next(a for a in ADAPTERS if a.name == name)
