import asyncio
import json
import os
import random
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
from app.models import TrackedCompany, JobPosting
from app.services import board_policy, jd_adapters

# Identify honestly. These are public, unauthenticated board APIs and the project's
# stated ethic is assisted-never-autonomous, so pretending to be Chrome is both
# unnecessary and off-brand. Mirrors jd_fetch._UA.
USER_AGENT = "Mozilla/5.0 (compatible; resume-agent/1.0; +job-board)"

BOARD_TIMEOUT = 10.0          # unchanged: worst real board (lever/palantir, 6MB) takes ~1.8s
BOARD_MAX_BYTES = 32 * 1024 * 1024   # largest real board is Ashby/openai at ~13.6MB

# Slugs come from untrusted sources (a GitHub README, Serper results) and are
# interpolated into a vendor URL path. The host is always a literal, so this is
# not an SSRF vector, but a traversal-shaped slug has no business being fetched.
_SLUG_OK = re.compile(r"^[A-Za-z0-9_.-]+$")

HARVEST_INTERVAL = timedelta(hours=2)
SCOUT_INTERVAL = timedelta(hours=24)
RETENTION_INTERVAL = 15 * 60    # independent of the potentially long harvest cycle
JITTER = (2.0, 10.0)             # polite gap between vendor requests
MAX_BACKOFF = 300.0              # cap on an honoured Retry-After

SEED_COMPANIES = {
    "ashby": ["vercel", "notion", "ramp", "figma", "linear"],
    "greenhouse": ["airbnb", "stripe", "plaid", "discord", "anthropic"]
}

# A title names the ROLE first and the TEAM second: "Software Engineer, Sales
# Platform" is a SWE role, "Account Executive, AI Sales" is not. So the role,
# seniority and discipline gates read the HEAD, while unwanted domains are
# checked against the WHOLE title ("Software Engineer, iOS" is a mobile role
# even though its head is generic).
_HEAD = re.compile(r"[,–—(]| - ")

# Gate 1: the head must actually name an engineering role.
_ENG_ROLE = re.compile(
    r"\b(software engineer|engineer|engineering|developer|programmer|swe|sde"
    r"|member of technical staff)\b", re.I)

# Gate 2: above the target band (new grad through mid). "staff" is excluded
# EXCEPT after "technical", so "Staff Machine Learning Engineer" is rejected
# while "Member of Technical Staff" survives.
_TOO_SENIOR = re.compile(
    r"\b(senior|sr\.?|principal|distinguished|lead|manager|director|vp|head of"
    r"|architect)\b|(?<!technical )\bstaff\b", re.I)

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


def is_target_role(title: str) -> bool:
    """Backend/infra/devops/full-stack/AI-ML and generalist SWE, new grad to mid.

    Four gates rather than a keyword soup. The old "match any target word, reject
    any exclude word" design fought itself: bare "staff" rejected "Member of
    Technical Staff", and a bare "ai" admitted "AI Recruiter" while no rule
    required the posting to be an engineering role at all.
    """
    head = _HEAD.split(title, 1)[0]
    if not _ENG_ROLE.search(head):
        return False
    if _TOO_SENIOR.search(head) or _NOT_SOFTWARE.search(head):
        return False
    return not _UNWANTED_DOMAIN.search(title)


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
_DOMESTIC_ABBR = re.compile(r"\b(SF|NYC|DC|CHI|SEA)\b")

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
    r"|costa rica|panama|uruguay|montevideo|laos|vientiane|emea|apac|latam|anz)\b", re.I)


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
    if not date_str:
        return UNDATED
    try:
        if str(date_str).isdigit():
            # Lever returns Unix epoch in milliseconds
            return datetime.fromtimestamp(int(date_str) / 1000, tz=timezone.utc).replace(tzinfo=None)

        date_str = str(date_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(date_str)
        # If naive, assume it's already UTC. If aware, convert to UTC and strip.
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return UNDATED


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


async def _get_board(provider: str, slug: str) -> list | dict | None:
    """The single network path for every board. Returns parsed JSON, or None when
    the board is gone (404). Raises RateLimited on 429/403 and HTTPStatusError on
    anything else, so the caller can tell "this vendor is unhappy" from "our code
    is broken". Endpoint URLs come from jd_adapters so they live in one module.
    """
    if not _SLUG_OK.match(slug) or ".." in slug:
        raise ValueError(f"refusing suspicious board slug: {slug!r}")
    try:
        adapter = jd_adapters.by_name(provider)
        url = adapter.list_url(slug)
    except (LookupError, AttributeError) as e:  # unknown ATS, or one with no board endpoint
        raise ValueError(f"cannot list a board for provider {provider!r}") from e
    async with httpx.AsyncClient(timeout=BOARD_TIMEOUT) as client:
        async with client.stream("GET", url, headers={"User-Agent": USER_AGENT}) as resp:
            if resp.status_code == 404:
                return None
            if resp.status_code in (403, 429):
                raise RateLimited(_retry_after_seconds(resp))
            resp.raise_for_status()
            total, chunks = 0, []
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > BOARD_MAX_BYTES:
                    raise ValueError(f"{provider}/{slug}: board exceeds {BOARD_MAX_BYTES} bytes")
                chunks.append(chunk)
    return json.loads(b"".join(chunks))


async def fetch_ashby(slug: str) -> list[dict] | None:
    """None means the board could not be observed (404); [] means it is empty."""
    data = await _get_board("ashby", slug)
    if data is None:
        return None
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


async def fetch_greenhouse(slug: str) -> list[dict] | None:
    data = await _get_board("greenhouse", slug)
    if data is None:
        return None
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


async def fetch_lever(slug: str) -> list[dict] | None:
    data = await _get_board("lever", slug)
    if data is None:
        return None
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


async def sync_company_jobs(db, company: TrackedCompany) -> int:
    """Refresh one company's postings and return how many were kept.
    Raise BoardVendorError/RateLimited for vendor failures; let code bugs propagate.
    """
    try:
        if company.provider == "ashby":
            raw_jobs = await fetch_ashby(company.slug)
        elif company.provider == "greenhouse":
            raw_jobs = await fetch_greenhouse(company.slug)
        elif company.provider == "lever":
            raw_jobs = await fetch_lever(company.slug)
        else:
            raise BoardVendorError(f"unknown provider {company.provider!r}")
    except (httpx.HTTPError, ValueError) as e:
        raise BoardVendorError(f"{company.provider}/{company.slug}: {e}") from e

    now = board_policy.utcnow()
    if raw_jobs is None:
        # 404: we did not observe this board, so we cannot conclude its postings
        # are gone. Closing them here would wipe a company's whole feed on a
        # transient outage. An empty 200 is different - that we DID observe.
        company.last_synced_at = now
        db.commit()
        return 0

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

    company.last_synced_at = now
    db.commit()
    return len(active_urls)


async def _harvest_cycle() -> dict:
    """One pass over every stale company. Returns counters so the caller (and
    tests) can see what actually happened instead of guessing from stdout."""
    stats = {"companies": 0, "kept": 0, "vendor_errors": 0, "bugs": 0, "skipped_fresh": 0}
    with _db.SessionLocal() as db:
        seed_db_if_empty(db)
        companies = db.execute(select(TrackedCompany)).scalars().all()
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - HARVEST_INTERVAL

        for company in companies:
            # Skip anything synced within the interval. This is also what stops a
            # uvicorn restart from re-harvesting all ~1000 boards from scratch.
            if company.last_synced_at is not None and company.last_synced_at > cutoff:
                stats["skipped_fresh"] += 1
                continue
            stats["companies"] += 1
            try:
                stats["kept"] += await sync_company_jobs(db, company)
            except RateLimited as e:
                db.rollback()
                wait = min(e.retry_after, MAX_BACKOFF)
                print(f"[board] {company.provider} asked us to back off {wait:.0f}s")
                await asyncio.sleep(wait)
            except BoardVendorError as e:
                db.rollback()
                stats["vendor_errors"] += 1
                print(f"[board] vendor problem: {e}")
            except Exception:
                db.rollback()
                stats["bugs"] += 1
                if stats["bugs"] == 1:  # one traceback is a signal, 900 is noise
                    traceback.print_exc()
            await asyncio.sleep(random.uniform(*JITTER))

        board_policy.prune_postings(db)
        db.commit()

    if stats["bugs"]:
        print(f"[board] ERROR {stats['bugs']} companies failed on OUR code, not the vendor's")
    if stats["companies"] and not stats["kept"]:
        print("[board] no eligible postings in the last 14 days; see vendor_errors/bugs above")
    print(f"[board] cycle done: {stats}")
    return stats


async def harvester_loop():
    while True:
        try:
            await _harvest_cycle()
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(HARVEST_INTERVAL.total_seconds())


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

GITHUB_SOURCES = [
    # A curated list of 800+ SWE companies on Greenhouse/Lever. Verified live:
    # returns 200 and is the source of ~700 of the tracked companies.
    "https://raw.githubusercontent.com/sample-resume/awesome-easy-apply/main/README.md",
]


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
                  if _SLUG_OK.match(s) and ".." not in s]
    return found


def _track(db, provider: str, slug: str, source: str) -> None:
    """do_nothing, not do_update: the old version overwrote `provider` on every
    sighting, so a company listed under two ATSes flip-flopped and orphaned the
    postings harvested under the other one. A genuine ATS migration is rare and
    self-heals - the old board stops listing the jobs and GC removes them."""
    db.execute(
        insert(TrackedCompany)
        .values(slug=slug, provider=provider, discovery_source=source)
        .on_conflict_do_nothing(index_elements=["slug"])
    )


async def _scout_github(client, db) -> int:
    added = 0
    for source_url in GITHUB_SOURCES:
        resp = await client.get(source_url)
        if resp.status_code != 200:
            print(f"[scout] {source_url} returned {resp.status_code}")
            continue
        for provider, slug in discover_slugs(resp.text):
            _track(db, provider, slug, "github")
            added += 1
    db.commit()
    return added


async def _scout_serper(client, db) -> int:
    key = os.environ.get("SERPER_API_KEY")
    if not key:
        print("[scout] no SERPER_API_KEY, skipping live discovery")
        return 0
    added = 0
    for query in ('site:boards.greenhouse.io "software engineer"',
                  'site:jobs.ashbyhq.com "software engineer"',
                  'site:jobs.lever.co "software engineer"'):
        try:
            resp = await client.post("https://google.serper.dev/search",
                                     json={"q": query}, headers={"X-API-KEY": key}, timeout=10)
            if resp.status_code != 200:
                print(f"[scout] serper returned {resp.status_code}")
                continue
            for item in resp.json().get("organic", []):
                for provider, slug in discover_slugs(item.get("link", "")):
                    _track(db, provider, slug, "serper")
                    added += 1
            db.commit()
        except httpx.HTTPError as e:      # vendor problem, expected noise
            db.rollback()
            print(f"[scout] serper unreachable: {e}")
    return added


async def scout_loop():
    while True:
        try:
            async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
                with _db.SessionLocal() as db:
                    added = await _scout_github(client, db)
                    added += await _scout_serper(client, db)
                    total = db.execute(select(func.count()).select_from(TrackedCompany)).scalar()
                    print(f"[scout] cycle done: {added} slugs seen, tracking {total} companies")
        except Exception:
            # Same rule as the harvester: a bug in our own code must be loud, not
            # a one-line warning indistinguishable from a network hiccup.
            traceback.print_exc()
        await asyncio.sleep(SCOUT_INTERVAL.total_seconds())
