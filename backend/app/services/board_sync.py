import asyncio
import json
import os
import random
import time
import traceback
import re
import unicodedata
from datetime import datetime, timezone, timedelta

import httpx
from email.utils import parsedate_to_datetime
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.sqlite import insert

# Import the module, not the name: tests rebind db.SessionLocal to a temp
# database, and `from app.db import SessionLocal` would capture the real one.
from app import db as _db
from app.core import config  # module, not names: tests rebind config.DATA_DIR
from app.models import TrackedCompany, JobPosting
from app.services import board_policy, jd_adapters

# Identify honestly. These are public, unauthenticated board APIs and the project's
# stated ethic is assisted-never-autonomous, so pretending to be Chrome is both
# unnecessary and off-brand. Mirrors jd_fetch._UA.
USER_AGENT = "Mozilla/5.0 (compatible; resume-agent/1.0; +job-board)"

BOARD_TIMEOUT = 10.0          # unchanged: worst real board (lever/palantir, 6MB) takes ~1.8s
BOARD_MAX_BYTES = 64 * 1024 * 1024   # largest real board is Ashby/bjakcareer at 33.6MB (2026-09-23)

# Slugs come from untrusted sources (SimplifyJobs listings, Serper results,
# pasted links) and are interpolated into a vendor URL path. The host is always a
# literal, so this is not an SSRF vector, but a traversal-shaped slug has no
# business being fetched.
_SLUG_OK = re.compile(r"(?!.*\.\.)[A-Za-z0-9_.-]+")  # fullmatch; no ".." anywhere

HARVEST_INTERVAL = timedelta(hours=1)   # per company: how stale a board may get
# T30: 91% of weekday postings (715 of 783) land 13:00-01:00 UTC, US business
# hours, so boards are refreshed 3x as often then and hourly overnight.
PEAK_INTERVAL = timedelta(minutes=20)
HARVEST_POLL = 60               # seconds between passes; each pass takes only stale boards
PARK_FOR = timedelta(days=7)    # a board on no ATS we list is rechecked weekly
SCOUT_INTERVAL = timedelta(hours=24)
RETENTION_INTERVAL = 15 * 60    # independent of the potentially long harvest cycle
JITTER = (1.0, 3.0)             # polite gap between requests to ONE vendor
MAX_BACKOFF = 300.0              # cap on an honoured Retry-After
MAX_SLOWDOWN = 10.0              # a strained vendor's gap grows to at most 10x (30s)

SEED_COMPANIES = {  # vendors verified live 2026-09-23 (figma is Greenhouse, plaid moved to Ashby)
    "ashby": ["vercel", "notion", "ramp", "plaid", "linear"],
    "greenhouse": ["airbnb", "stripe", "figma", "discord", "anthropic"]
}

# A title names the ROLE first and the TEAM second: "Software Engineer, Sales
# Platform" is a SWE role, "Account Executive, AI Sales" is not. So the role and
# discipline gates read the ROLE SEGMENT, while seniority and unwanted domains
# are checked against the WHOLE title ("Software Engineer, iOS" is a mobile role
# even though its head is generic; "Engineer, Senior or Staff" is senior).
_HEAD = re.compile(r"[,–—(]| - ")

# Gate 1: the role segment must actually name an engineering role. "software"
# alone is not a role ("Software Asset Coordinator"), but "Flight Software
# Intern" is one.
_ENG_ROLE = re.compile(
    r"\b(software engineer|engineer|engineering|developer|programmer|swe|sde"
    r"|member of technical staff|software (intern(ship)?|associate|co-?op))\b", re.I)

# Some heads name no role at all: an early-career marker ("Intern, Software
# Engineering, 2027") or a program prefix before a dash ("Accelerator Program -
# Software Engineer"). Then the role is the next segment - unless the head is a
# person's job ("Technical Recruiter - Software Engineering").
_MARKER_HEAD = re.compile(r"\s*(intern(ship)?|co-?op|new grad(uate)?|contract(or)?)\s*", re.I)
_PEOPLE_ROLE = re.compile(
    r"\b(recruit\w*|sourc\w*|coordinator|designer|technician|counsel|accountant"
    r"|representative|consultant|officer|administrator)\b", re.I)

# Gate 2: above the target band (new grad through mid). "staff" is excluded
# EXCEPT after "technical", so "Staff Machine Learning Engineer" is rejected
# while "Member of Technical Staff" survives.
_TOO_SENIOR = re.compile(
    r"\b(senior|sr\.?|principal|distinguished|lead|manager|director|vp|head of"
    r"|architect|chief)\b|(?<!technical )\bstaff\b", re.I)

# Gate 3: engineering, but not software.
_NOT_SOFTWARE = re.compile(
    r"\b(electrical|mechanical|civil|chemical|industrial|hardware|optical|thermal"
    r"|manufacturing|silicon|data ?cent(er|re)\w*|facilit\w*|audio|video|\bav\b"
    # customer-facing and internal-IT engineering: real jobs, not the ones we want
    # NB: no "recruit" here. Gate 1 already rejects "AI Recruiter"/"Technical
    # Recruiter" (no engineering noun), and a prefix match would wrongly reject
    # "Recruiting Analytics Data Engineer", which IS a data-engineering role.
    r"|sales|presales|pre-sales|marketing|account executive|customer"
    r"|solutions?|support|\bit\b|partner|field|salesforce|developer relations|devrel"
    r"|documentation|technical writer|network"
    r"|copywriter|scientist|analyst|specialist)\b", re.I)

# Gate 4: software, but a domain we do not want (QA/test and mobile). Deliberately
# targeted: a bare "quality" or "test" would reject "Software Engineer, Search
# Quality", which is relevance work, not QA.
_UNWANTED_DOMAIN = re.compile(
    r"\b(qa|sdet|ios|android|mobile)\b|quality assurance"
    r"|\b(engineer|engineering) in test\b|\btest(ing)? engineer\b", re.I)

# Gate 5: positive identification of SOFTWARE work, like the location filter
# below. Gate 3 was a denylist, and on aerospace/defense boards a bare
# "engineer" let Propulsion, Avionics, Wiring Harness and PCB Layout roles
# through (T29 audit: 144 of 450 kept titles). A role noun that says software
# passes outright; a software field passes unless it names hardware; a bare
# "engineer" needs software evidence somewhere and no hardware anywhere.
_SOFTWARE_ROLE = re.compile(r"\b(software|developer|swe|sde|member of technical staff)\b", re.I)
_SOFTWARE_FIELD = re.compile(
    r"\b(programmer|back.?end|front.?end|full.?stack|web|data|analytics|ml|machine learning"
    r"|ai|llm|agent\w*|infra\w*|platform|devops|site reliability|sre|cloud|security|devsecops"
    r"|forward deployed|founding|research|applied|distributed|kernel|operating systems"
    r"|compiler|database|firmware|embedded|hpc|perception|robotics software|simulation"
    r"|growth|red team|threat|vulnerability|grc|abuse|detection"
    r"|incident response|identity|iam|build|performance|integration|design engineer)\b", re.I)
# Weaker hints, trusted only when no hardware word appears in the whole title.
# "systems" stays ambiguous-but-kept: Cloudflare's SWEs are "Systems Engineers".
_SOFTWARE_HINT = re.compile(
    r"\b(product|reliability|robotics|autonomy|motion planning|tools|api|systems"
    r"|new grad|intern|internship|co-op)\b", re.I)
_HARDWARE = re.compile(
    r"\b(propulsion|avionics|structur\w*|mechanic\w*|mechanism\w*|fluids?|materials?|metals?"
    r"|environmental|pcb|harness|wiring|ewis|rf|battery|powerpack|welding|hvac|construction"
    r"|ordnance|warhead|cmm|edm|supplier|supply chain|sourcing|npi|equipment|machine maintenance"
    r"|physical design|design verification|fpga|asic|dfx|dynamics|thermal|power generation"
    r"|bess|solar|launch|recovery|test stand|vacuum|cryogenic|scada|controls?|automation"
    r"|failure analysis|product quality|quality systems|liaison|material flow|technician"
    r"|body|chassis|manufacturing|electronics|hardware)\b", re.I)


def _role_segment(title: str) -> str:
    sep = _HEAD.search(title)
    if not sep:
        return title
    head = title[:sep.start()]
    if _ENG_ROLE.search(head):
        return head
    following = _HEAD.split(title[sep.end():], 1)[0]
    if _ENG_ROLE.search(following) and (
            _MARKER_HEAD.fullmatch(head)
            or (sep.group() == " - " and not _PEOPLE_ROLE.search(head)
                and not _NOT_SOFTWARE.search(head))):
        return following
    return head


def is_target_role(title: str) -> bool:
    """Backend/infra/devops/full-stack/AI-ML and generalist SWE, new grad to mid.

    Gates rather than a keyword soup. The old "match any target word, reject
    any exclude word" design fought itself: bare "staff" rejected "Member of
    Technical Staff", and a bare "ai" admitted "AI Recruiter" while no rule
    required the posting to be an engineering role at all.
    """
    role = _role_segment(title)
    if not _ENG_ROLE.search(role) or _NOT_SOFTWARE.search(role):
        return False
    if _TOO_SENIOR.search(title) or _UNWANTED_DOMAIN.search(title):
        return False
    if _SOFTWARE_ROLE.search(role):
        return True
    if _SOFTWARE_FIELD.search(role) and not _HARDWARE.search(role):
        return True
    return bool(_SOFTWARE_FIELD.search(title) or _SOFTWARE_HINT.search(title)) \
        and not _HARDWARE.search(title)


# US + Canada, any state or city. Positive identification, not a denylist: the
# old EXCLUDE_LOCATIONS blocked ~25 named places and let everything else through,
# so Israel/Switzerland/Korea/Ukraine all passed by omission.

# Splits a multi-location posting into units. NOT on comma, which separates
# "city, state" inside a single unit.
_LOC_UNITS = re.compile(r"[|;•\n]|\s+or\s+|\s/\s")

# Unambiguous US/Canada evidence: country words, full state/province names, and
# city names that appear with no state or country attached.
_DOMESTIC = re.compile(
    r"\b(united states|u\.s\.a?|usa|canada|north america|amer|usca"
    r"|alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware"
    r"|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana"
    r"|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska"
    r"|nevada|new hampshire|new jersey|new mexico|new york|north carolina"
    r"|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina"
    r"|south dakota|tennessee|texas"
    r"|utah|vermont|virginia|washington|wisconsin|wyoming"
    r"|ontario|british columbia|quebec|alberta|manitoba|saskatchewan|nova scotia"
    r"|new brunswick|newfoundland|labrador|prince edward island|yukon|nunavut"
    r"|northwest territories"
    r"|san francisco|new york city|nyc|seattle|austin|boston|chicago|denver|atlanta"
    r"|miami|portland|los angeles|san diego|san jose|palo alto|mountain view|dallas"
    r"|houston|philadelphia|phoenix|detroit|pittsburgh|san mateo|sunnyvale|redmond"
    r"|bellevue|toronto|vancouver|montreal|ottawa|calgary|waterloo)\b", re.I)
# Uppercase only, and only abbreviations confirmed present in real board data.
# "LA" is deliberately absent: both real occurrences are "Remote - LA" meaning
# Louisiana (alongside "Remote - OK"/"Remote - TX"), which the code rule covers.
# "US" ("US Remote", "Remote - US") must count once regions are foreign, or
# "Remote - US or Europe" would read as unknown + foreign and be dropped.
_DOMESTIC_ABBR = re.compile(r"\b(SF|NYC|DC|CHI|SEA|US)\b")

# Two-letter state/province codes. Checked only AFTER the foreign list, because
# many collide with ISO country codes: NL is Newfoundland *and* the Netherlands,
# DE Delaware and Germany, IL Illinois and Israel, IN Indiana and India.
_DOMESTIC_CODE = re.compile(
    r"[,\-]\s*(A[LKZR]|C[AOT]|DE|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]"
    r"|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY]|DC"
    r"|ON|BC|QC|AB|MB|SK|NS|NB|NL|PE|YT|NT|NU)\b")

_FOREIGN = re.compile(
    r"\b(united kingdom|\buk\b|england|scotland|wales|ireland|dublin|london"
    r"|manchester|edinburgh|belfast|luxembourg|iceland|reykjavik"
    r"|india|bengaluru|bangalore|mumbai|delhi|hyderabad|pune|chennai|gurugram|noida"
    r"|germany|berlin|munich|munchen|hamburg|frankfurt|koln|cologne|dusseldorf"
    r"|france|paris|lyon|spain|madrid|sevilla|seville"
    r"|barcelona|portugal|lisbon|lisboa|porto|italy|milan|milano|rome|roma|torino"
    r"|firenze|netherlands|amsterdam|den haag|the hague"
    r"|belgium|brussels|switzerland|zurich|geneva|geneve|basel|austria|vienna|wien"
    r"|poland|warsaw|warszawa"
    r"|krakow|czech|prague|praha|slovakia|bratislava|romania|bucharest|bucuresti"
    r"|bulgaria|sofia"
    r"|hungary|budapest|greece|athens|serbia|belgrade|croatia|zagreb|malta|valletta"
    r"|sweden|stockholm|malmo|goteborg|gothenburg|norway|oslo|denmark|copenhagen"
    r"|kobenhavn|aarhus|finland|helsinki"
    r"|estonia|latvia|lithuania|ukraine|kyiv|russia|moscow|israel|tel aviv"
    r"|turkey|istanbul|\buae\b|dubai|abu dhabi|saudi|riyadh|jeddah|qatar|doha"
    r"|singapore|japan|tokyo|osaka|china|beijing|shanghai|shenzhen|hong kong"
    r"|taiwan|taipei|korea|seoul|philippines|manila|indonesia|jakarta|vietnam"
    r"|hanoi|ho chi minh|thailand|bangkok|malaysia|kuala lumpur|australia|sydney"
    r"|melbourne|brisbane|perth|new zealand|auckland|wellington|south africa"
    r"|cape town|johannesburg|nigeria|lagos|kenya|nairobi|egypt|cairo|morocco"
    r"|casablanca|brazil|sao paulo|rio de janeiro|mexico|cdmx|guadalajara"
    r"|argentina|buenos aires|colombia|bogota|chile|santiago|peru|lima"
    r"|costa rica|panama|uruguay|montevideo|laos|vientiane|emea|apac|latam|anz"
    r"|europe|asia|middle east|africa|slovenia|ljubljana)\b", re.I)


# Two-letter country codes that are NOT also a US state or Canadian province, so
# they can be read as foreign with no ambiguity. DE, NL, IL, IN, CO, AR, ID, PA,
# SK, MA, MT, LA, PE and GA are all deliberately absent - each is a US state or
# province code too, and the collision is what this module already guards against.
_FOREIGN_CODE = re.compile(
    r"[,\-]\s*(CH|SE|NO|DK|FI|IE|MX|BR|JP|CN|SG|AU|NZ|ZA|AE|PT|ES|FR|IT|GR|TR"
    r"|KR|TW|PH|TH|VN|MY|PL|CZ|RO|HU|BG|HR|RS|UA|RU|EG|KE|NG|CL|GB|AT|BE|LU|IS"
    r"|EE|LV|LT|SI|HK|SA|QA|KW|CR|UY|EC)\b")


# NFKD decomposes accents (Zurich, Krakow, Sao Paulo) but NOT letters that are
# distinct characters rather than base+mark: Kobenhavn, Malmo, Lodz, Duesseldorf.
# Case is preserved on purpose: _DOMESTIC_CODE and _FOREIGN_CODE match UPPERCASE
# two-letter codes, so lowercasing here would silently stop "Raleigh, NC" from
# counting as domestic and break any-valid-wins.
_TRANSLIT = str.maketrans({
    "\u00f8": "o", "\u00d8": "O", "\u00e6": "ae", "\u00c6": "AE", "\u00e5": "a", "\u00c5": "A",
    "\u00df": "ss", "\u0142": "l", "\u0141": "L", "\u0111": "d", "\u0110": "D",
    "\u0131": "i", "\u00fe": "th", "\u00de": "TH", "\u00f0": "d", "\u00d0": "D",
})


def _translit(text: str) -> str:
    return text.translate(_TRANSLIT)


def _classify_unit(unit: str) -> str:
    """Order matters: a foreign city outranks a two-letter code that merely looks
    like a US state. "Amsterdam, NL" is the Netherlands, not Newfoundland."""
    if _DOMESTIC.search(unit) or _DOMESTIC_ABBR.search(unit):
        return "domestic"
    if _FOREIGN.search(unit) or _FOREIGN_CODE.search(unit):
        return "foreign"
    if _DOMESTIC_CODE.search(unit):
        return "domestic"
    return "unknown"


def is_target_location(location: str | None) -> bool:
    """US + Canada, any state or city. Any-valid-wins on multi-location postings.

    "New York, NY | London, UK" is a US job also offered in London, so it is KEPT;
    the old denylist dropped it because London appeared anywhere in the string.
    Unrecognised text is KEPT: silently deleting a real job is worse than showing
    one the user can skip past.
    """
    if not location:
        return True
    # Strip accents first: "Zurich" is in the foreign list but "Zürich" is what
    # Greenhouse actually sends, and the two never matched. Same for Munchen,
    # Krakow, Sao Paulo, Bogota, Malmo. It also lets "Montreal" match directly
    # instead of relying on the word "Canada" happening to be present.
    folded = "".join(c for c in unicodedata.normalize("NFKD", _translit(location))
                     if not unicodedata.combining(c))
    kinds = {_classify_unit(u) for u in _LOC_UNITS.split(folded) if u.strip()}
    if "domestic" in kinds:
        return True
    return "foreign" not in kinds


# Missing/invalid dates must never become now(). The stable sentinel makes them
# ineligible under the publication-age policy instead of falsely fresh.
UNDATED = datetime(1970, 1, 1)


def parse_ats_date(date_str: str | None) -> datetime:
    return jd_adapters.parse_ats_date(date_str) or UNDATED


def seed_db_if_empty(db):
    if not db.execute(select(TrackedCompany.slug).limit(1)).scalar():
        for provider, slugs in SEED_COMPANIES.items():
            for slug in slugs:
                stmt = insert(TrackedCompany).values(
                    slug=slug, provider=provider, discovery_source="seed"
                ).on_conflict_do_nothing()
                db.execute(stmt)
        db.commit()


class RateLimited(Exception):
    """A vendor asked us to slow down. Raised out of the per-company call so the
    harvester backs off ONCE at the loop level, instead of a fixed sleep inside
    sync_company_jobs stalling every remaining company behind it."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after:.0f}s")
        self.retry_after = retry_after


def _retry_after_seconds(resp: httpx.Response, default: float = 300.0) -> float:
    """RFC 9110 allows either a delay in seconds or an HTTP date."""
    raw = (resp.headers.get("retry-after") or "").strip()
    if not raw:
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(raw)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return default


# Conditional GET (T29). Measured 2026-09-23: after an hour, 643 of 668 live
# boards answered 304, so most passes download almost nothing. In memory on
# purpose: a restart (every code change under --reload) refetches every board
# once, so a filter change always re-applies to all of them. An ETag is only
# trusted once its board's rows are committed (_commit_etag); until then it
# waits in _UNCOMMITTED_ETAGS, so a crash mid-sync can never pin stale rows.
NOT_MODIFIED = object()
_ETAGS: dict[tuple[str, str], str] = {}
_UNCOMMITTED_ETAGS: dict[tuple[str, str], str | None] = {}


def _commit_etag(provider: str, slug: str) -> None:
    etag = _UNCOMMITTED_ETAGS.pop((provider, slug), None)
    if etag:
        _ETAGS[(provider, slug)] = etag
    else:
        _ETAGS.pop((provider, slug), None)


async def _get_board(provider: str, slug: str, client=None) -> list | dict | object | None:
    """The single network path for every board. Returns parsed JSON, None when
    the board is gone (404), or NOT_MODIFIED (304). Raises RateLimited on 429/403
    and HTTPStatusError on anything else, so the caller can tell "this vendor is
    unhappy" from "our code is broken". Endpoint URLs come from jd_adapters so
    they live in one module.
    """
    if not _SLUG_OK.fullmatch(slug):
        raise ValueError(f"refusing suspicious board slug: {slug!r}")
    try:
        adapter = jd_adapters.by_name(provider)
        url = adapter.list_url(slug)
    except (LookupError, AttributeError) as e:  # unknown ATS, or one with no board endpoint
        raise ValueError(f"cannot list a board for provider {provider!r}") from e
    if client is None:  # a lane passes its own, reused connection (T30)
        async with httpx.AsyncClient(timeout=BOARD_TIMEOUT) as own:
            return await _get_board(provider, slug, own)
    headers = {"User-Agent": USER_AGENT}
    if (provider, slug) in _ETAGS:
        headers["If-None-Match"] = _ETAGS[(provider, slug)]
    async with client.stream("GET", url, headers=headers) as resp:
        if resp.status_code == 404:
            return None
        if resp.status_code == 304:  # before raise_for_status: httpx raises on 3xx
            return NOT_MODIFIED
        if resp.status_code in (403, 429):
            raise RateLimited(_retry_after_seconds(resp))
        resp.raise_for_status()
        total, chunks = 0, []
        async for chunk in resp.aiter_bytes():
            total += len(chunk)
            if total > BOARD_MAX_BYTES:
                raise ValueError(f"{provider}/{slug}: board exceeds {BOARD_MAX_BYTES} bytes")
            chunks.append(chunk)
        _UNCOMMITTED_ETAGS[(provider, slug)] = resp.headers.get("etag")
    return json.loads(b"".join(chunks))


async def fetch_ashby(slug: str, client=None) -> list[dict] | object | None:
    """None means the board could not be observed (404); [] means it is empty;
    NOT_MODIFIED means it is unchanged since the last committed sync."""
    data = await _get_board("ashby", slug, client)
    if data is None or data is NOT_MODIFIED:
        return data
    return [
        {
            "title": job.get("title"),
            "location": job.get("location"),
            "url": job.get("jobUrl"),
            "published_at": job.get("publishedAt"),
        }
        for job in jd_adapters.board_jobs(data, "ashby")
    ]


def greenhouse_url(slug: str, job: dict) -> str | None:
    """Use the canonical URL to select the ATS adapter; keep absolute_url for apply.
    Fall back to absolute_url when the posting has no id.
    """
    jid = job.get("id")
    if jid is None:
        return job.get("absolute_url")
    return f"https://job-boards.greenhouse.io/{slug}/jobs/{jid}"


async def fetch_greenhouse(slug: str, client=None) -> list[dict] | object | None:
    data = await _get_board("greenhouse", slug, client)
    if data is None or data is NOT_MODIFIED:
        return data
    return [
        {
            "title": job.get("title"),
            "location": job.get("location", {}).get("name") if isinstance(job.get("location"), dict) else job.get("location"),
            "url": greenhouse_url(slug, job),
            # A recent edit is not proof of a recent posting. Undated jobs are
            # excluded by the shared freshness policy, never stamped as new.
            "published_at": job.get("first_published"),
        }
        for job in jd_adapters.board_jobs(data, "greenhouse")
    ]


async def fetch_lever(slug: str, client=None) -> list[dict] | object | None:
    data = await _get_board("lever", slug, client)
    if data is None or data is NOT_MODIFIED:
        return data
    return [
        {
            "title": job.get("text"),
            "location": jd_adapters.object_field(job, "categories").get("location"),
            "url": job.get("hostedUrl"),
            "published_at": str(job["createdAt"]) if job.get("createdAt") else None,
        }
        for job in jd_adapters.board_jobs(data, "lever")
    ]


class BoardVendorError(Exception):
    """The vendor's board could not be fetched or parsed. Expected noise, not a
    bug in our code - the distinction is the whole point of this exception."""


FETCHERS = {"ashby": fetch_ashby, "greenhouse": fetch_greenhouse, "lever": fetch_lever}


async def _fetch(provider: str, slug: str, client=None):
    fetch = FETCHERS.get(provider)
    if fetch is None:
        raise BoardVendorError(f"unknown provider {provider!r}")
    try:
        return await fetch(slug, client)
    except (httpx.HTTPError, ValueError) as e:
        # the type too: an httpx timeout's message is often empty (T30: 6 blank log lines)
        raise BoardVendorError(f"{provider}/{slug}: {type(e).__name__}: {e}") from e


async def _find_moved_board(company: TrackedCompany, client=None) -> list[dict] | None:
    """Companies change ATS. T29 audit: 103 of 348 boards that 404'd were live on
    another vendor under the same slug (Notion, Sentry, Zapier...), and none on
    two. All three vendors 404 a slug they do not host, so a 200 is evidence.
    ponytail: same slug is taken as same company; the vendors expose no stronger
    identity. Worst case is a real board of a same-named company."""
    for provider in FETCHERS:
        if provider == company.provider:
            continue
        _ETAGS.pop((provider, company.slug), None)  # a 304 here would carry no jobs
        try:
            jobs = await _fetch(provider, company.slug, client)
        except BoardVendorError:
            continue
        if jobs is not None:
            print(f"[board] {company.slug} moved {company.provider} -> {provider}")
            company.provider = provider
            return jobs
    return None


async def sync_company_jobs(db, company: TrackedCompany, client=None) -> int | None:
    """Refresh one company's postings and return how many were kept, or None
    when the board is unchanged since its last committed sync (304).
    Raise BoardVendorError/RateLimited for vendor failures; let code bugs propagate.
    """
    raw_jobs = await _fetch(company.provider, company.slug, client)
    if raw_jobs is None:
        raw_jobs = await _find_moved_board(company, client)

    now = board_policy.utcnow()
    company.last_synced_at = now
    if raw_jobs is None:
        # 404 everywhere: we did not observe this board, so we cannot conclude
        # its postings are gone. Closing them here would wipe a company's whole
        # feed on a transient outage; they expire by publication age instead.
        # An empty 200 is different - that we DID observe. Park, recheck weekly.
        company.gone_at = now
        db.commit()
        return 0
    company.gone_at = None
    if raw_jobs is NOT_MODIFIED:
        db.commit()
        return None

    active_urls = []
    expired_urls = []
    for job in raw_jobs:
        if not job.get("title") or not job.get("url"):
            continue
        matches = is_target_role(job["title"]) and is_target_location(job["location"])
        posted_dt = parse_ats_date(job.get("published_at"))
        if not board_policy.is_recent(posted_dt, now):
            # A legacy stored edit timestamp can look fresh. Once a normal
            # harvest establishes an ineligible date, do not retain that row.
            expired_urls.append(job["url"])
            continue
        if not matches:
            continue
        active_urls.append(job["url"])
        fields = {"title": job["title"], "location": job["location"],
                  "status": "open", "created_at": posted_dt, "updated_at": now}
        db.execute(
            insert(JobPosting)
            .values(url=job["url"], company_slug=company.slug, **fields)
            .on_conflict_do_update(index_elements=["url"], set_=fields)
        )

    # Batch expired rows without exceeding older SQLite parameter limits.
    for start in range(0, len(expired_urls), 500):
        db.execute(delete(JobPosting).where(
            JobPosting.company_slug == company.slug,
            JobPosting.url.in_(expired_urls[start:start + 500]),
        ))

    # Listings absent from a valid board are closed until publication-age expiry.
    closing = (
        JobPosting.__table__.update()
        .where(JobPosting.company_slug == company.slug)
        .where(JobPosting.status != "closed")
        .values(status="closed", updated_at=now)
    )
    if active_urls:
        closing = closing.where(JobPosting.url.not_in(active_urls))
    db.execute(closing)

    db.commit()
    _commit_etag(company.provider, company.slug)
    return len(active_urls)


def harvest_interval(now: datetime) -> timedelta:
    """How stale a board may get: tighter in US business hours (13:00-01:00 UTC)."""
    return PEAK_INTERVAL if now.hour >= 13 or now.hour < 1 else HARVEST_INTERVAL


def _strained(error: BoardVendorError) -> bool:
    """The vendor itself is struggling (5xx, timeouts, dropped connections) - as
    opposed to a 4xx, a malformed board or an unknown provider, which say nothing
    about its load. A 429/403 is RateLimited and handled by the lane directly."""
    cause = error.__cause__
    return isinstance(cause, httpx.TransportError) or (
        isinstance(cause, httpx.HTTPStatusError) and cause.response.status_code >= 500)


async def _harvest_lane(provider: str, stats: dict) -> None:
    """One vendor's stale boards, one at a time, with its own paced gap (T30).
    Politeness is per host: the three lanes run side by side, so a pass takes
    as long as the biggest vendor instead of all three end to end, while each
    vendor still gets requests at least JITTER[0] apart. Like Googlebot, a lane
    widens its gap when its vendor strains (429/5xx/timeouts) and narrows it
    again on success; a back-off stalls only this vendor."""
    slowdown = 1.0
    with _db.SessionLocal() as db:
        # Stalest first, never-attempted (new or pasted) at the very front: in
        # insert order a new company waited behind ~1000 others, a full pass.
        companies = db.execute(select(TrackedCompany).where(TrackedCompany.provider == provider)
                               .order_by(TrackedCompany.last_synced_at.asc().nulls_first())).scalars().all()
        now = board_policy.utcnow()
        cutoff, park_cutoff = now - harvest_interval(now), now - PARK_FOR
        async with httpx.AsyncClient(timeout=BOARD_TIMEOUT) as client:
            for company in companies:
                # Skip anything attempted within the interval. This is also what
                # stops a uvicorn restart from re-harvesting every board from scratch.
                if company.last_synced_at is not None and company.last_synced_at > cutoff:
                    stats["skipped_fresh"] += 1
                    continue
                if company.gone_at is not None and company.gone_at > park_cutoff:
                    stats["parked"] += 1
                    continue
                stats["companies"] += 1
                # Stamp the attempt before fetching and outside the rollback below:
                # a failing board waits the interval like any other, instead of
                # being retried on every HARVEST_POLL pass.
                company.last_synced_at = board_policy.utcnow()
                db.commit()
                strained = False
                try:
                    kept = await sync_company_jobs(db, company, client)
                    if kept is None:
                        stats["unchanged"] += 1
                    else:
                        stats["kept"] += kept
                except RateLimited as e:
                    db.rollback()
                    strained = True
                    stats["rate_limited"] += 1
                    wait = min(e.retry_after, MAX_BACKOFF)
                    print(f"[board] {provider} asked us to back off {wait:.0f}s")
                    await asyncio.sleep(wait)
                except BoardVendorError as e:
                    db.rollback()
                    strained = _strained(e)
                    stats["vendor_errors"] += 1
                    print(f"[board] vendor problem: {e}")
                except Exception:
                    db.rollback()
                    stats["bugs"] += 1
                    if stats["bugs"] == 1:  # one traceback is a signal, 900 is noise
                        traceback.print_exc()
                slowdown = min(slowdown * 2, MAX_SLOWDOWN) if strained else max(slowdown / 2, 1.0)
                await asyncio.sleep(random.uniform(*JITTER) * slowdown)


async def _harvest_cycle() -> dict:
    """One pass over every stale company, one lane per vendor. Returns counters so
    the caller (and tests) can see what actually happened instead of guessing."""
    stats = dict.fromkeys(("companies", "kept", "unchanged", "vendor_errors", "rate_limited",
                           "bugs", "skipped_fresh", "parked"), 0)
    with _db.SessionLocal() as db:
        seed_db_if_empty(db)
    await asyncio.gather(*(_harvest_lane(provider, stats) for provider in FETCHERS))
    with _db.SessionLocal() as db:
        board_policy.prune_postings(db)
        db.commit()

    if stats["bugs"]:
        print(f"[board] ERROR {stats['bugs']} companies failed on OUR code, not the vendor's")
    if stats["companies"] and not stats["kept"] and not stats["unchanged"]:
        print("[board] no eligible postings in the last 14 days; see vendor_errors/bugs above")
    if stats["companies"]:  # most passes find nothing stale; stay quiet then
        print(f"[board] cycle done: {stats}")
    return stats


async def harvester_loop():
    """A pass every HARVEST_POLL seconds takes only boards staler than
    harvest_interval(), so each board refreshes on that cadence however long a
    full pass takes, and a newly tracked (or pasted) company is picked up next pass."""
    while True:
        try:
            await _harvest_cycle()
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(HARVEST_POLL)


def claim_background_lock():
    """Only one process may run the harvester/scout/retention loops on a DB.
    T29 found a second server on the same app.db running a stale harvester that
    undid provider moves and re-polled parked boards. An OS lock, not a row: the
    kernel drops it when its holder exits or crashes, so it never goes stale.
    Returns the open lock file (keep it open while the loops run) or None.
    ponytail: fcntl is POSIX-only (macOS/Linux, the dev and Docker targets)."""
    import fcntl
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(config.DATA_DIR / "background.lock", "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def cleanup_postings() -> int:
    with _db.SessionLocal() as db:
        removed = board_policy.prune_postings(db)
        db.commit()
    if removed:
        print(f"[board] expired {removed} postings outside the 14-day window")
    return removed


async def retention_loop():
    """Startup cleanup runs before serving; subsequent sweeps run every 15 min."""
    while True:
        await asyncio.sleep(RETENTION_INTERVAL)
        try:
            cleanup_postings()
        except Exception:
            traceback.print_exc()


_DISCOVERY_PATTERNS = {
    "greenhouse": re.compile(r"boards\.greenhouse\.io/([a-zA-Z0-9_.-]+)"),
    "ashby": re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_.-]+)"),
    "lever": re.compile(r"jobs\.lever\.co/([a-zA-Z0-9_.-]+)"),
}

# SimplifyJobs' new-grad list: several commits a day (verified 2026-09-23), and
# exactly our band. It replaced awesome-easy-apply, frozen since May 2024 and the
# source of 317 of the 348 tracked boards that 404'd. Only `url` is read, from
# listings still `active`, to discover board slugs; nothing is republished (the
# repo declares no license).
SIMPLIFY_LISTINGS = ("https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions"
                     "/dev/.github/scripts/listings.json")

# Serper: Google honours site: reliably only on page 1 (T29, 10 live queries:
# page 2+ and the tbs time filter both fell back to YouTube/Reddit results), so
# reach comes from rotating the phrase daily, not from paging. Page 1 of the
# old fixed query found 0 untracked companies; a rotated phrase found 9.
SERPER_SITES = ("boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.ashbyhq.com", "jobs.lever.co")
SERPER_PHRASES = ("software engineer", "backend engineer", "new grad software engineer",
                  "machine learning engineer", "infrastructure engineer", "full stack engineer",
                  "data engineer")
SCOUT_CHECK = 3600  # seconds between "is the daily scout due?" checks


def discover_slugs(text: str) -> list[tuple[str, str]]:
    """(provider, slug) pairs found in arbitrary text, already validated.

    The capture class permits dots, so a link like "boards.greenhouse.io/../x"
    yields the slug "..". Unfiltered, that is stored once and then fails every
    harvest cycle forever, counted as a vendor error. Reject it at the source.
    """
    found = []
    for provider, pattern in _DISCOVERY_PATTERNS.items():
        # lowercase BEFORE the set, or "Acme"/"acme"/"ACME" survive as three
        slugs = {m.lower() for m in pattern.findall(text)}
        found += [(provider, s) for s in sorted(slugs)
                  # "boards.greenhouse.io/embed/job_app?token=..." carries a job
                  # id, not a board: "embed" 404s on every vendor (2026-09-23).
                  if _SLUG_OK.fullmatch(s) and s != "embed"]
    return found


def track_company(db, provider: str, slug: str, source: str) -> bool:
    """do_nothing, not do_update: the old version overwrote `provider` on every
    sighting, so a company listed under two ATSes flip-flopped and orphaned the
    postings harvested under the other one. A genuine ATS migration is handled
    by the harvester instead: a board that 404s is looked up on the other ATSes
    (T29 - 103 migrations had gone unnoticed). Returns True only when new."""
    if not _SLUG_OK.fullmatch(slug):
        raise ValueError(f"refusing suspicious board slug: {slug!r}")
    if source == "pasted":
        existing = db.get(TrackedCompany, slug)
        if existing is not None:
            # The ATS API just answered for this link, so a board exists. Harvest
            # it on the next pass instead of waiting out the interval or a park.
            # Provider is NOT flipped (T28): if the recorded board 404s, the
            # harvester's re-resolve finds this one; if it is live, it stays.
            existing.gone_at, existing.last_synced_at = None, None
            return False
    return db.execute(
        insert(TrackedCompany)
        .values(slug=slug, provider=provider, discovery_source=source)
        .on_conflict_do_nothing(index_elements=["slug"])
    ).rowcount == 1


async def _scout_github(client, db) -> int:
    """Companies with an active new-grad listing. Returns how many were new."""
    resp = await client.get(SIMPLIFY_LISTINGS)
    if resp.status_code != 200:
        print(f"[scout] {SIMPLIFY_LISTINGS} returned {resp.status_code}")
        return 0
    try:
        listings = resp.json()
    except ValueError as e:  # a bad upstream file is their problem, not a bug of ours
        print(f"[scout] listings.json is not JSON: {e}")
        return 0
    if not isinstance(listings, list):
        print("[scout] listings.json is not a list")
        return 0
    urls = " ".join(str(item.get("url") or "") for item in listings
                    if isinstance(item, dict) and item.get("active") is True)
    added = sum(track_company(db, provider, slug, "simplify") for provider, slug in discover_slugs(urls))
    db.commit()
    return added


async def _scout_serper(client, db) -> int:
    key = os.environ.get("SERPER_API_KEY")
    if not key:
        print("[scout] no SERPER_API_KEY, skipping live discovery")
        return 0
    added = 0
    phrase = SERPER_PHRASES[datetime.now(timezone.utc).toordinal() % len(SERPER_PHRASES)]
    for site in SERPER_SITES:
        query = f'site:{site} "{phrase}"'
        try:
            resp = await client.post("https://google.serper.dev/search",
                                     json={"q": query}, headers={"X-API-KEY": key}, timeout=10)
            if resp.status_code != 200:
                print(f"[scout] serper returned {resp.status_code}")
                continue
            links = [str(item.get("link", "")) for item in resp.json().get("organic", [])]
            found = discover_slugs(" ".join(links))
            new = sum(track_company(db, provider, slug, "serper") for provider, slug in found)
            added += new
            # site: silently falling back to generic results shows up as 0 here
            print(f"[scout] serper {query}: {len(found)} boards in {len(links)} results, {new} new")
            db.commit()
        except httpx.HTTPError as e:      # vendor problem, expected noise
            db.rollback()
            print(f"[scout] serper unreachable: {e}")
    return added


def _scout_due() -> bool:
    """Daily, measured across restarts. Every --reload restart used to rerun the
    scout: a 13.6MB download and Serper credits each time. The marker is touched
    only after a successful run, so a failed one is retried within SCOUT_CHECK."""
    marker = config.DATA_DIR / "scout_last_run"
    try:
        return time.time() - marker.stat().st_mtime >= SCOUT_INTERVAL.total_seconds()
    except FileNotFoundError:
        return True


async def scout_loop():
    while True:
        if _scout_due():
            try:
                async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
                    with _db.SessionLocal() as db:
                        added = await _scout_github(client, db)
                        added += await _scout_serper(client, db)
                        total = db.execute(select(func.count()).select_from(TrackedCompany)).scalar()
                        print(f"[scout] cycle done: {added} new companies, tracking {total}")
                (config.DATA_DIR / "scout_last_run").touch()
            except Exception:
                # Same rule as the harvester: a bug in our own code must be loud,
                # not a one-line warning indistinguishable from a network hiccup.
                traceback.print_exc()
        await asyncio.sleep(SCOUT_CHECK)
