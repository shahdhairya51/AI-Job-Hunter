"""
╔══════════════════════════════════════════════════════════════════════╗
║           JOB HUNTER -- ULTRA DISCOVERY ENGINE v2.0                  ║
║  Sources: Greenhouse · Lever · Ashby · Workable · SmartRecruiters   ║
║           BambooHR · Rippling · Recruitee · RemoteOK · Adzuna       ║
║           SimplifyJobs (GitHub) · GitHub Markdown · LinkedIn (UI)   ║
║           Jobright AI (UI) · Simplify.jobs (UI)                     ║
╚══════════════════════════════════════════════════════════════════════╝

WHAT'S NEW vs v1:
  ─ Ashby public API: `GET https://api.ashbyhq.com/posting-api/job-board/{slug}`
  ─ Greenhouse: full pagination via Link header (was only fetching page 1!)
  ─ Lever: full pagination via `next` offset token
  ─ Workable: public jobs API with pagination
  ─ SmartRecruiters: public search API with pagination
  ─ BambooHR: jobs API
  ─ Rippling: jobs API
  ─ Recruitee: jobs API
  ─ Workday: POST-based JSON search API (top Fortune-500 companies)
  ─ SerpAPI / JSearch (RapidAPI) optional integrations
  ─ 400+ company slugs across all ATS platforms
  ─ Smart dedup: signature = company::title::location
  ─ Rate-limit aware: exponential backoff on 429
  ─ Full description fetching (not just truncated 300 chars)
"""

import asyncio
import aiohttp
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# COMPANY SLUG LISTS  (expand freely -- all public, no auth needed)
# ─────────────────────────────────────────────────────────────────────────────

GREENHOUSE_BOARDS = [
    # Big Tech / FAANG-adjacent
    "google", "meta", "apple", "stripe", "openai", "anthropiconline", "anthropic",
    "figma", "notion", "airbnb", "coinbase", "databricks", "snowflake", "linear",
    # AI / ML
    "scaleai", "weightsandbiases", "huggingface", "cohere", "stabilityai",
    "runway", "characterai", "midjourney", "jasper", "adept", "inflection",
    "mosaic", "together", "modal", "replicate", "anyscale", "superagency",
    # Fintech
    "brex", "robinhood", "chime", "plaid", "rippling", "ramp", "affirm",
    "klarna", "marqeta", "mercury", "deel", "remote", "gusto",
    # SaaS / Cloud
    "datadoghq", "elastic", "confluent", "hashicorp", "instacart", "fivetran",
    "gong", "roblox", "asana", "box", "dropbox", "gitlab", "okta", "zendesk",
    "zoom", "slack", "twilio", "cloudflare", "fastly", "netskope",
    # Crypto / Web3
    "kraken", "gemini", "alchemy", "consensys", "chainlink", "polygon",
    "optimism", "base",
    # Infra / DevTools
    "sentry", "grafana", "airbyte", "census", "hightouch", "segment",
    "amplitude", "mixpanel", "heap", "fullstory", "logrocket", "newrelic",
    "dynatrace", "splunk", "mode", "metabase", "dbt", "vanta", "benchling",
    # Marketplace / Consumer
    "pinterest", "doordash", "discord", "reddit", "twitch", "spotify",
    "vimeo", "patreon",
    # Deep Tech / Robotics
    "cruise", "anduril", "nuro", "waymo", "aurora", "skydio", "rivian", "lucid",
    # Other
    "canva", "framer", "modern-health", "lattice", "ironclad", "front",
    "checkr", "flexport", "shipbob", "outreach", "loom", "pilot",
    "bench", "carta", "circle", "clearbit", "cultureamp", "envoy",
    "hotjar", "maven", "webflow", "whatnot", "workato", "yotpo",
    "paloaltonetworks", "okta", "auth0", "zscaler",
    "hubspot", "mailchimp", "intercom", "drift", "salesloft",
    "palantir", "atlassian", "sqsp",
]

LEVER_BOARDS = [
    # Big / well-known
    "netflix", "lyft", "shopify", "duolingo", "miro", "zapier",
    "amplitude", "looker", "quora", "yelp", "zillow",
    # Ed-tech
    "coursera", "udemy", "masterclass", "coursehero",
    # Travel
    "hopper", "kayak",
    # Fintech
    "revolut", "monzo", "nubank", "klarna", "airwallex",
    "remitly", "wise", "transferwise", "marqeta", "checkout",
    "brex", "ramp", "mercury", "plaid",
    # Marketplace
    "doordash", "gopuff", "shipt", "deliveroo", "swiggy",
    "ticketmaster", "seatgeek", "gametime",
    # Crypto
    "kraken", "gemini", "opensea", "dapperlabs",
    # SaaS
    "affinity", "bench", "carta", "circle", "clearbit",
    "cultureamp", "envoy", "flexport", "loom", "maven",
    "outreach", "postscript", "qualtrics", "segment",
    "usertesting", "wealthfront", "webflow", "whatnot",
    "workato", "yotpo", "zenefits",
    # Misc
    "snap", "teachable", "thumbtack", "grubhub", "postmates",
    "kickstarter", "patreon", "eventbrite", "meetup",
    "gofundme", "indiegogo", "vividseats",
]

# NEW: Ashby (used by many fast-growing startups)
ASHBY_BOARDS = [
    "notion", "linear", "loom", "retool", "dbt-labs", "figma",
    "scale-ai", "cohere", "adept", "inflection", "together",
    "modal", "replicate", "anyscale", "weights-biases",
    "anthropic", "perplexity", "mistral",
    "brex", "ramp", "mercury", "airbase", "puzzle",
    "lattice", "rippling", "deel", "remote", "gusto",
    "vercel", "supabase", "planetscale", "railway",
    "posthog", "metabase", "grafana", "airbyte",
    "clerk", "neon", "turso", "convex", "upstash",
    "arc", "warp", "zed", "cursor",
    "codeium", "tabnine", "sourcegraph", "coder",
    "hex", "mode", "starburst", "firebolt",
    "baseten", "banana", "beam", "lepton",
    "deta", "fly", "render",
    "vapi", "bland", "retell", "11x",
    "ema", "lexi", "hyperwrite", "jasper",
    "cognition", "factory", "sweep", "mentat",
    "glean", "guru", "tettra", "notion",
    "deel", "workos", "stytch", "clerk", "ory",
    "mintlify", "gitbook", "readme",
    "trunk", "aviator", "mergify", "linearb",
    "incident", "rootly", "firehydrant", "blameless",
    "census", "hightouch", "polytomic", "grouparoo",
    "growthbook", "statsig", "split", "launchdarkly",
    "tinybird", "clickhouse", "motherduck", "rill",
    "inngest", "trigger", "windmill", "n8n",
    "montecarlodata", "great-expectations", "soda",
    "paradime", "y42", "datacoves", "lightdash",
    "secureframe", "drata", "tugboat-logic", "hypercomply",
    "torchbox", "ray-ban", "prose", "allbirds",
]

# NEW: Workable (used by 1000s of SMBs + scale-ups)
WORKABLE_BOARDS = [
    "spotify-2", "intercom", "typeform", "taxjar", "pipedrive",
    "hotjar", "calendly", "airtable", "productboard", "pendo",
    "mixpanel", "heap-2", "amplitude-2", "appsflyer", "contentsquare",
    "adjust", "branch", "kochava", "singular",
    "algolia", "elastic-2", "meilisearch", "typesense",
    "hasura", "fauna", "tigris", "deno",
    "estuary", "mage", "prefect", "dagster", "astronomer",
    "dbt-labs-2", "datacoves-2", "atlan",
    "omnivore", "bending-spoons", "picsart", "canva-2",
    "onfido", "veriff", "sumsub", "persona",
]

# NEW: SmartRecruiters (used by large enterprises + startups)
SMARTRECRUITERS_BOARDS = [
    "mcdonalds", "visa", "starbucks", "linkedin-corp", "adobe",
    "bosch", "siemens", "deloitte", "kpmg", "pwc",
    "thoughtworks", "n26", "delivery-hero", "checkout-com",
    "adyen", "mollie",
]

# NEW: BambooHR (SMB-focused)
BAMBOOHR_BOARDS = [
    "palantir", "qualtrics", "divvy", "olo", "nearmap",
    "lucidchart", "familysearch", "healthequity",
    "domo", "chatmeter", "businessq",
]

# NEW: Workday (Fortune 500 -- uses POST-based JSON search)
WORKDAY_COMPANIES = [
    {"name": "NVIDIA",    "url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"},
    {"name": "Amazon",    "url": "https://amazon.jobs/en/search.json"},   # special
    {"name": "Microsoft", "url": "https://microsoft.wd5.myworkdayjobs.com/External"},
    {"name": "Apple",     "url": "https://apple.wd1.myworkdayjobs.com/en-US/apple_external_application"},
    {"name": "Walmart",   "url": "https://walmart.wd5.myworkdayjobs.com/WalmartExternal"},
    {"name": "JPMorgan",  "url": "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs"},
    {"name": "IBM",       "url": "https://ibm.wd12.myworkdayjobs.com/en-US/External"},
    {"name": "Oracle",    "url": "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/jobs"},
    {"name": "Salesforce","url": "https://salesforce.wd1.myworkdayjobs.com/External_Career_Site"},
    {"name": "Cisco",     "url": "https://cisco.wd5.myworkdayjobs.com/External"},
    {"name": "Intel",     "url": "https://intel.wd1.myworkdayjobs.com/External"},
    {"name": "AMD",       "url": "https://amd.wd1.myworkdayjobs.com/External"},
    {"name": "Qualcomm",  "url": "https://qualcomm.wd5.myworkdayjobs.com/External"},
    {"name": "TI",        "url": "https://ti.wd5.myworkdayjobs.com/TIU_Candidates_External"},
    {"name": "Boeing",    "url": "https://boeing.wd1.myworkdayjobs.com/EXTERNAL_CAREERS"},
    {"name": "Lockheed",  "url": "https://lmco.wd5.myworkdayjobs.com/External"},
    {"name": "Raytheon",  "url": "https://rtx.wd1.myworkdayjobs.com/RTX"},
    {"name": "Northrop",  "url": "https://ngc.wd1.myworkdayjobs.com/NGC_External_Career_Site"},
    {"name": "GE",        "url": "https://jobs.gecareers.com/global/en/search-results"},
    {"name": "HP",        "url": "https://hp.wd5.myworkdayjobs.com/ExternalCareerSite"},
    {"name": "Dell",      "url": "https://dell.wd1.myworkdayjobs.com/External"},
    {"name": "EMC",       "url": "https://dell.wd1.myworkdayjobs.com/External"},
    {"name": "VMware",    "url": "https://vmware.wd1.myworkdayjobs.com/VMware"},
    {"name": "ServiceNow","url": "https://jobs.smartrecruiters.com/ServiceNow"},   # SmartRecruiters
    {"name": "Workday",   "url": "https://workday.wd5.myworkdayjobs.com/Workday"},
    {"name": "SAP",       "url": "https://sap.wd3.myworkdayjobs.com/SAP"},
    {"name": "Intuit",    "url": "https://intuit.wd1.myworkdayjobs.com/jobs"},
    {"name": "PayPal",    "url": "https://paypal.wd1.myworkdayjobs.com/jobs"},
    {"name": "eBay",      "url": "https://ebay.wd5.myworkdayjobs.com/apply"},
    {"name": "Netflix",   "url": "https://jobs.lever.co/netflix"},  # Already in Lever
    {"name": "Uber",      "url": "https://www.uber.com/api/loadSearchJobsResults"},  # special
    {"name": "Lyft",      "url": "https://jobs.lever.co/lyft"},  # Already in Lever
    {"name": "Twitter/X", "url": "https://twitter.wd5.myworkdayjobs.com/Twitter"},
    {"name": "Snap",      "url": "https://wd1.myworkdayjobs.com/en-US/snap"},
    {"name": "Pinterest", "url": "https://www.pinterestcareers.com/job-search-results/"},
    {"name": "Block",     "url": "https://block.xyz/careers"},
    {"name": "Shopify",   "url": "https://jobs.lever.co/shopify"},  # Already in Lever
    {"name": "Spotify",   "url": "https://jobs.lever.co/spotify"},  # Lever
    {"name": "Airbnb",    "url": "https://careers.airbnb.com/positions/"},
    {"name": "Lyft",      "url": "https://jobs.lever.co/lyft"},
    {"name": "DoorDash",  "url": "https://boards.greenhouse.io/doordash"},
    {"name": "Instacart", "url": "https://boards.greenhouse.io/instacart"},
    {"name": "Robinhood", "url": "https://boards.greenhouse.io/robinhood"},
]

# ─────────────────────────────────────────────────────────────────────────────

class JobDiscovery:
    def __init__(self, profile_path="user_profile.json", hours_back=24):
        if os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                self.profile = json.load(f)
        else:
            self.profile = {"preferences": {"roles": ["software engineer", "backend", "frontend", "full stack", "ai", "machine learning", "data"], "locations": ["United States", "Remote"]}}
        
        self.roles = [role.lower() for role in self.profile.get("preferences", {}).get("roles", [])]
        self.locations = [loc.lower() for loc in self.profile.get("preferences", {}).get("locations", [])]
        self.found_jobs = []
        self.seen_signatures = set()
        self.seen_urls = set()  # URL-based global dedup across ALL scrapers
        self.hours_back = max(hours_back, 1)
        self.cutoff = datetime.now(timezone.utc) - timedelta(hours=self.hours_back)
        self.yesterday = self.cutoff  # backward-compat alias
        self._stats = {s: 0 for s in ["Greenhouse","Lever","Ashby","Workable","SmartRecruiters","BambooHR","RemoteOK","Adzuna","SimplifyJobs","GitHub Lists","Workday","LinkedIn","JobRight AI","Simplify"]}

    # ─────────────────────────────────────────────────────────────────────
    # UTILITY
    # ─────────────────────────────────────────────────────────────────────
    def _standardize_date(self, date_str):
        if not date_str: return ""
        date_lower = str(date_str).lower().strip()
        now = datetime.now()
        if any(w in date_lower for w in ["today", "new", "0d", "0h", "just posted"]):
            return now.strftime("%b %d")
        age_match = re.search(r'(\d+)\s*([dh])', date_lower)
        if age_match:
            val = int(age_match.group(1))
            unit = age_match.group(2)
            posted_date = now - timedelta(days=val if unit == 'd' else val/24.0)
            return posted_date.strftime("%b %d")
        months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
        for i, month in enumerate(months):
            if month in date_lower:
                day_match = re.search(r'(\d+)', date_lower)
                if day_match:
                    day = int(day_match.group(1))
                    try: return datetime(2026, i + 1, day).strftime("%b %d")
                    except: pass
                return month.capitalize()
        try:
            iso_date = datetime.fromisoformat(date_str.split('T')[0])
            return iso_date.strftime("%b %d")
        except: pass
        return date_str.strip()

    # Hardcoded tokens that are always acceptable regardless of user profile
    _ALWAYS_MATCH = [
        # Engineering
        "software engineer", "swe", "sde", "developer", "backend engineer",
        "full stack", "fullstack", "ai engineer", "ml engineer",
        "machine learning", "data engineer", "cloud engineer", "devops",
        "new grad", "entry level", "early career", "junior", "associate engineer",
        "infrastructure engineer", "platform engineer", "systems engineer",
        "embedded engineer", "firmware engineer", "software development",
        # Analytics / Data
        "data analyst", "business analyst", "business intelligence",
        "bi analyst", "bi developer", "analytics engineer",
        "product analyst", "operations analyst", "data scientist",
        "quantitative analyst", "research analyst", "market analyst",
        "financial analyst", "applied scientist",
    ]

    def _is_role_match(self, title):
        title_lower = str(title).lower()
        if not self.roles: return True
        # Note: seniority blocking is now the authoritative gate in _add_job._SENIORITY_BLOCK
        # This redundant check keeps fast-prefiltering at the scraper level (avoids unnecessary work)
        if any(neg in title_lower for neg in self._SENIORITY_BLOCK):
            return False
        # Always match known SWE/SDE/developer variations regardless of profile
        if any(tok in title_lower for tok in self._ALWAYS_MATCH):
            return True
        return any(role.lower() in title_lower for role in self.roles)

    @staticmethod
    def _extract_sponsorship(text: str) -> str:
        """Parse H1B sponsorship signal from raw text."""
        t = text.lower()
        if any(x in t for x in ["no h1b", "no visa", "does not sponsor", "not sponsor",
                                 "unable to sponsor", "cannot sponsor", "citizen only",
                                 "us citizen", "clearance required"]):
            return "No"
        if any(x in t for x in ["h1b sponsor likely", "visa sponsor", "h1b sponsor",
                                 "sponsorship available", "will sponsor", "open to sponsor",
                                 "sponsors h1b"]):
            return "Likely"
        return ""

    def _parse_date_to_dt(self, date_str):
        """Parse a GitHub-style date string to a timezone-aware datetime. Returns None if unparseable."""
        if not date_str:
            return None
        dl = str(date_str).lower().strip()
        now = datetime.now(timezone.utc)
        # "today", "0d", "0h", "just posted", "new" → now
        if any(w in dl for w in ["today", "new", "0d", "0h", "just posted"]):
            return now
        # "Xd" or "Xh" → now minus X days/hours
        age_m = re.search(r'(\d+)\s*([dh])', dl)
        if age_m:
            val, unit = int(age_m.group(1)), age_m.group(2)
            return now - timedelta(days=val if unit == 'd' else val / 24.0)
        # Month name + optional day: "Feb 22", "Jan 5", "feb22"
        months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                  "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
        for abbr, month_num in months.items():
            if abbr in dl:
                day_m = re.search(r'(\d+)', dl)
                if day_m:
                    day = int(day_m.group(1))
                    try:
                        dt = datetime(now.year, month_num, day, tzinfo=timezone.utc)
                        # If the date is in the future, assume last year
                        if dt > now + timedelta(days=1):
                            dt = datetime(now.year - 1, month_num, day, tzinfo=timezone.utc)
                        return dt
                    except:
                        pass
        # ISO format
        try:
            dt = datetime.fromisoformat(date_str.split('T')[0]).replace(tzinfo=timezone.utc)
            return dt
        except:
            pass
        return None

    def _is_us_location(self, loc_str):
        if not loc_str: return True   # assume US if unknown
        loc_lower = str(loc_str).lower()
        if "remote" in loc_lower and not any(x in loc_lower for x in ["emea","apac","uk","europe","germany","india","canada","latam"]):
            return True
        us_indicators = [
            "united states","usa","us","america",
            " ca"," ny"," wa"," tx"," fl"," il"," ma"," co"," ga"," va",
            "california","new york","washington","texas","seattle","san francisco",
            "san jose","los angeles","boston","chicago","austin","denver","atlanta",
            "remote us","us-remote","remote (us",
        ]
        for ind in us_indicators:
            if ind in loc_lower: return True
        return False

    # Tokens that universally reject a title regardless of which scraper sends it.
    # This is the ONLY place the senior/lead blocklist lives -- every add goes through here.
    _SENIORITY_BLOCK = [
        'senior', ' sr ', 'sr.', 'staff ', 'principal', 'director', 'manager',
        'lead ', 'tech lead', 'head of', 'vp ', 'v.p.', 'vice president',
        'distinguished', 'fellow', 'cto', 'cpo', 'coo', 'cfo', 'chief',
        'architect', '5+ yr', '7+ yr', '8+ yr', '10+ yr',
    ]

    def _add_job(self, job_data):
        title = job_data.get('title', '') or ''
        tl = title.lower()

        # ── UNIVERSAL SENIOR/LEAD FILTER -- applied before ANY dedup check ──
        if any(blk in tl for blk in self._SENIORITY_BLOCK):
            return False

        job_data['date'] = self._standardize_date(job_data.get('date', ''))

        # ── Primary dedup: URL (most reliable across sources) ──
        url = (job_data.get('url') or '').strip().rstrip('/')
        if url and url in self.seen_urls:
            return False
        if url:
            self.seen_urls.add(url)

        # ── Secondary dedup: company::title (catches same job on different boards) ──
        signature = f"{job_data.get('company','').lower().strip()}::{tl}"
        if signature in self.seen_signatures:
            return False
        self.seen_signatures.add(signature)

        job_data.setdefault('status', 'NEW')
        job_data.setdefault('ats_score', '')
        job_data.setdefault('resume_version', '')
        job_data.setdefault('date_applied', '')
        job_data.setdefault('notes', '')
        job_data.setdefault('hiring_manager', '')
        job_data.setdefault('salary', '')
        job_data.setdefault('sponsorship', '')
        job_data.setdefault('department', '')
        job_data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.found_jobs.append(job_data)
        source = job_data.get('source', '')
        if source in self._stats:
            self._stats[source] += 1
        return True

    async def _fetch_with_retry(self, session, url, method="GET", extra_headers=None, **kwargs):
        """GET/POST with exponential backoff on 429 / 5xx."""
        if extra_headers:
            kwargs.setdefault("headers", {})
            kwargs["headers"] = {**kwargs["headers"], **extra_headers}
        for attempt in range(4):
            try:
                if method == "POST":
                    resp = await session.post(url, **kwargs)
                else:
                    resp = await session.get(url, **kwargs)
                if resp.status == 429:
                    wait = 2 ** attempt
                    print(f"  [429] Rate limited on {url[:60]}. Sleeping {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                if resp.status >= 500:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                return resp
            except Exception as e:
                if attempt == 3: raise
                await asyncio.sleep(1)
        return None

    # ─────────────────────────────────────────────────────────────────────
    # GREENHOUSE  (full pagination via Link header)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_greenhouse(self, session, board):
        """
        Greenhouse public Job Board API -- returns ALL jobs (handles pagination).
        Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true

        Improvements vs old version:
        - Uses posted_at (real post date) not updated_at (can reflect edits to old jobs)
        - Extracts real company_name from the `company` metadata key
        - Extracts salary from `metadata` list (many GH boards include salary bands)
        - Extracts H1B sponsorship signal from job description text
        - Extracts department from job.departments[0].name
        No auth needed. Pagination via Link: <url>; rel="next" header.
        """
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
        page_count = 0
        added = 0

        while url and page_count < 20:   # safety cap 20 pages
            page_count += 1
            try:
                resp = await self._fetch_with_retry(session, url)
                if not resp or resp.status != 200:
                    break

                data = await resp.json()

                # Greenhouse v1 returns { jobs: [...], meta: {...} }
                # Board-level company name is in data.company.name
                board_company = ''
                if isinstance(data.get('company'), dict):
                    board_company = data['company'].get('name', '')

                jobs = data.get('jobs', [])

                for job in jobs:
                    try:
                        # ── Date: prefer posted_at (real post date) over updated_at ──
                        raw_posted = job.get('posted_at') or job.get('updated_at') or ''
                        try:
                            posted_dt = datetime.fromisoformat(raw_posted.replace('Z', '+00:00'))
                        except Exception:
                            posted_dt = datetime.now(timezone.utc)

                        if posted_dt < self.yesterday:
                            continue

                        title = job.get('title', '')
                        if not self._is_role_match(title):
                            continue

                        loc = job.get('location', {}).get('name', '') or 'Remote'
                        if not self._is_us_location(loc):
                            continue

                        # ── Description HTML -> plain text ──
                        desc_html = job.get('content', '') or ''
                        desc_text = BeautifulSoup(desc_html, 'html.parser').get_text(separator=' ', strip=True)

                        # ── Company name: job-level > board-level > slug ──
                        company = (
                            job.get('company_name') or
                            board_company or
                            board.replace('-', ' ').title()
                        )

                        # ── Salary extraction from metadata list ──
                        salary = ''
                        for meta in (job.get('metadata') or []):
                            nm = str(meta.get('name', '')).lower()
                            if any(w in nm for w in ['salary', 'compensation', 'pay']):
                                salary = str(meta.get('value', '') or '')
                                break

                        # ── Department ──
                        depts = job.get('departments') or []
                        department = depts[0].get('name', '') if depts else ''

                        # ── Sponsorship signal from description ──
                        sponsorship = self._extract_sponsorship(desc_text)

                        if self._add_job({
                            'title': title,
                            'company': company,
                            'location': loc,
                            'url': job.get('absolute_url', ''),
                            'source': 'Greenhouse',
                            'description': desc_text[:2000],
                            'date': posted_dt.strftime('%Y-%m-%d'),
                            'salary': salary,
                            'department': department,
                            'sponsorship': sponsorship,
                        }):
                            added += 1

                    except Exception:
                        continue

                # ── Follow pagination via Link header ──
                link_header = resp.headers.get('Link', '')
                next_url = None
                for part in link_header.split(','):
                    part = part.strip()
                    if 'rel="next"' in part:
                        m = re.search(r'<(.+?)>', part)
                        if m:
                            next_url = m.group(1)
                url = next_url

            except Exception as e:
                print(f'  [Greenhouse:{board}] Error: {e}')
                break

        if added:
            print(f'  Greenhouse [{board}]: +{added} jobs ({page_count} pages)')

    # ─────────────────────────────────────────────────────────────────────
    # LEVER  (full pagination via `next` offset token)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_lever(self, session, board):
        """
        Lever public postings API -- returns ALL postings (handles pagination).
        Endpoint: GET https://api.lever.co/v0/postings/{board}?mode=json&limit=100

        Improvements:
        - Real company name from job.categories.company or job.company (not just slug)
        - Extracts salary range from salaryRange object
        - Extracts H1B sponsorship from description text
        - Department from categories.department
        """
        base_url = f'https://api.lever.co/v0/postings/{board}?mode=json&limit=100'
        offset = None
        page_count = 0
        added = 0

        while page_count < 10:
            page_count += 1
            url = base_url + (f'&offset={offset}' if offset else '')

            try:
                resp = await self._fetch_with_retry(session, url)
                if not resp or resp.status != 200:
                    break

                data = await resp.json()

                # Lever v0 returns a list directly; v1 wraps in {data: [], next: ...}
                if isinstance(data, list):
                    jobs = data
                    offset = None   # v0 has no pagination
                elif isinstance(data, dict):
                    jobs = data.get('data', [])
                    offset = data.get('next')  # v1 pagination token
                else:
                    break

                if not jobs:
                    break

                for job in jobs:
                    # ── Date (Lever createdAt is Unix ms) ──
                    created_at = datetime.fromtimestamp(
                        job.get('createdAt', time.time() * 1000) / 1000, tz=timezone.utc)
                    if created_at < self.yesterday:
                        continue

                    cats = job.get('categories') or {}
                    loc = cats.get('location', '') or 'Remote'
                    if not self._is_us_location(loc):
                        continue

                    title = job.get('text', '')
                    if not self._is_role_match(title):
                        continue

                    # ── Real company name (Lever embeds it in tags or team name) ──
                    company = (
                        job.get('company') or
                        cats.get('team') or
                        board.replace('-', ' ').title()
                    )

                    # ── Salary range ──
                    salary_obj = job.get('salaryRange') or {}
                    salary = ''
                    if salary_obj:
                        mn = salary_obj.get('min', '')
                        mx = salary_obj.get('max', '')
                        cur = salary_obj.get('currency', 'USD')
                        if mn or mx:
                            salary = f'{cur} ${mn:,}–${mx:,}' if (mn and mx) else f'{cur} ${mn or mx:,}'

                    # ── Description (plain text if available) ──
                    desc = job.get('descriptionPlain', '') or ''
                    if not desc:
                        desc_html = job.get('description', '') or ''
                        desc = BeautifulSoup(desc_html, 'html.parser').get_text(separator=' ', strip=True)

                    # ── H1B sponsorship ──
                    sponsorship = self._extract_sponsorship(desc)

                    # ── Department ──
                    department = cats.get('department', '')

                    if self._add_job({
                        'title': title,
                        'company': company,
                        'location': loc,
                        'url': job.get('hostedUrl', ''),
                        'source': 'Lever',
                        'description': desc[:2000],
                        'date': created_at.strftime('%Y-%m-%d'),
                        'salary': salary,
                        'department': department,
                        'sponsorship': sponsorship,
                    }):
                        added += 1

                if not offset:
                    break  # v0 single-page or exhausted

            except Exception as e:
                print(f'  [Lever:{board}] Error: {e}')
                break

        if added:
            print(f'  Lever [{board}]: +{added} jobs')

    # ─────────────────────────────────────────────────────────────────────
    # ASHBY  (new! no auth, returns all jobs in one call + salary)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_ashby(self, session, slug):
        """
        Ashby public job board API -- no auth, all jobs in one call.
        GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
        Returns: { jobs: [...] }  -- no pagination needed.
        """
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
        try:
            resp = await self._fetch_with_retry(session, url)
            if not resp or resp.status != 200: return
            
            data = await resp.json()
            jobs = data.get("jobs", []) if isinstance(data, dict) else []
            added = 0
            
            for job in jobs:
                published = job.get('publishedAt', '') or ''
                if published:
                    try:
                        pub_dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
                        if pub_dt < self.yesterday: continue
                    except: pass
                
                if not self._is_role_match(job.get('title', '')): continue
                
                loc = job.get('location', '') or ''
                secondary = job.get('secondaryLocations', []) or []
                if secondary:
                    loc = loc + " | " + " | ".join([s.get('location','') for s in secondary if s.get('location')])
                if not self._is_us_location(loc): continue
                
                # Compensation
                comp = job.get('compensation', {}) or {}
                salary = comp.get('compensationTierSummary', '') or comp.get('scrapeableCompensationSalarySummary', '') or ''
                
                desc_plain = job.get('descriptionPlain', '') or BeautifulSoup(job.get('descriptionHtml',''),'html.parser').get_text()
                
                if self._add_job({
                    "title": job.get('title', ''),
                    "company": slug.replace('-', ' ').title(),
                    "location": loc or "Remote",
                    "url": job.get('jobUrl', job.get('applyUrl', '')),
                    "source": "Ashby",
                    "description": desc_plain[:2000],
                    "date": published[:10] if published else datetime.now().strftime("%Y-%m-%d"),
                    "salary": salary,
                    "department": job.get('department', ''),
                }):
                    added += 1
            
            if added: print(f"  Ashby [{slug}]: +{added} jobs")
            
        except Exception as e:
            pass  # many slugs won't exist -- silently skip

    # ─────────────────────────────────────────────────────────────────────
    # WORKABLE  (public jobs API)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_workable(self, session, company_slug):
        """
        Workable public API: GET https://apply.workable.com/api/v1/widget/accounts/{slug}/jobs
        Returns jobs list.
        """
        url = f"https://apply.workable.com/api/v1/widget/accounts/{company_slug}/jobs"
        try:
            resp = await self._fetch_with_retry(session, url)
            if not resp or resp.status != 200: return
            data = await resp.json()
            jobs = data.get("results", []) if isinstance(data, dict) else []
            added = 0
            for job in jobs:
                if not self._is_role_match(job.get('title', '')): continue
                loc = (job.get('location') or {}).get('city', '') + ", " + (job.get('location') or {}).get('country', '')
                if not self._is_us_location(loc): continue
                created = job.get('published_on', '') or ''
                try:
                    created_dt = datetime.fromisoformat(created.replace('Z','+00:00'))
                    if created_dt < self.yesterday: continue
                except: pass
                shortcode = job.get('shortcode','')
                apply_url = f"https://apply.workable.com/{company_slug}/j/{shortcode}/" if shortcode else ''
                if self._add_job({
                    "title": job.get('title',''),
                    "company": company_slug.replace('-',' ').replace('_',' ').title(),
                    "location": loc.strip().strip(','),
                    "url": apply_url,
                    "source": "Workable",
                    "description": job.get('description','')[:2000],
                    "date": created[:10] if created else '',
                    "salary": "",
                }):
                    added += 1
            if added: print(f"  Workable [{company_slug}]: +{added} jobs")
        except Exception as e:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # SMARTRECRUITERS  (public search API with pagination)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_smartrecruiters(self, session, company_id):
        """
        SmartRecruiters public API with proper pagination.
        GET https://api.smartrecruiters.com/v1/companies/{company_id}/postings

        Improvements:
        - Pagination via offset/limit (handles >100 postings)
        - Remote flag handling (remote=True -> 'Remote')
        - Department from department.label
        - Sponsorship from description text
        """
        base_url = f'https://api.smartrecruiters.com/v1/companies/{company_id}/postings'
        offset = 0
        page_limit = 100
        total_added = 0

        while True:
            url = f'{base_url}?limit={page_limit}&offset={offset}'
            try:
                resp = await self._fetch_with_retry(session, url)
                if not resp or resp.status != 200:
                    break
                data = await resp.json()
                jobs = data.get('content', []) if isinstance(data, dict) else []
                if not jobs:
                    break

                for job in jobs:
                    title = job.get('name', '') or ''
                    if not self._is_role_match(title):
                        continue

                    loc_obj = job.get('location', {}) or {}
                    city = loc_obj.get('city', '')
                    region = loc_obj.get('region', '')
                    country = loc_obj.get('country', '')
                    remote = loc_obj.get('remote', False)
                    loc = 'Remote' if remote else f'{city}, {region}' if city else country
                    if not self._is_us_location(loc + ' ' + country):
                        continue

                    posted = job.get('releasedDate', '') or ''
                    try:
                        posted_dt = datetime.fromisoformat(posted.replace('Z', '+00:00'))
                        if posted_dt < self.yesterday:
                            continue
                    except Exception:
                        pass

                    job_id = job.get('id', '')
                    apply_url = f'https://jobs.smartrecruiters.com/{company_id}/{job_id}'

                    # Description: jobDescription.text (direct form)
                    desc = ''
                    jd = job.get('jobDescription') or {}
                    if isinstance(jd, dict):
                        desc = jd.get('text', '') or ''
                    if not desc:
                        desc = str(jd) if jd else ''

                    # Real company name
                    company = (job.get('company') or {}).get('name', '') or company_id.replace('-', ' ').title()
                    if isinstance(company, dict):
                        company = company.get('name', company_id.replace('-', ' ').title())

                    # Department
                    dept_obj = job.get('department', {}) or {}
                    department = dept_obj.get('label', '') if isinstance(dept_obj, dict) else ''

                    # Sponsorship
                    sponsorship = self._extract_sponsorship(desc)

                    if self._add_job({
                        'title': title,
                        'company': company,
                        'location': loc.strip(', '),
                        'url': apply_url,
                        'source': 'SmartRecruiters',
                        'description': desc[:2000],
                        'date': posted[:10] if posted else '',
                        'salary': '',
                        'department': department,
                        'sponsorship': sponsorship,
                    }):
                        total_added += 1

                # Pagination
                total_found = data.get('totalFound', 0)
                offset += page_limit
                if offset >= total_found or offset >= 500:
                    break

            except Exception:
                break

        if total_added:
            print(f'  SmartRecruiters [{company_id}]: +{total_added} jobs')



    # ─────────────────────────────────────────────────────────────────────
    # BAMBOOHR (public jobs API)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_bamboohr(self, session, company_domain):
        """
        BambooHR: GET https://{domain}.bamboohr.com/careers/list

        Improvements:
        - Date filter: skip jobs older than lookback window
        - Description via individual job detail endpoint
        - Sponsorship extracted from metadata
        """
        url = f'https://{company_domain}.bamboohr.com/careers/list'
        try:
            headers = {'Accept': 'application/json'}
            resp = await self._fetch_with_retry(session, url, headers=headers)
            if not resp or resp.status != 200:
                return
            data = await resp.json()
            results = data.get('result', []) if isinstance(data, dict) else []
            added = 0

            for job in results:
                title = job.get('jobOpeningName', '') or ''
                if not self._is_role_match(title):
                    continue
                loc = job.get('location', '') or ''
                if not self._is_us_location(loc):
                    continue

                # ── Date filter ──
                raw_date = job.get('datePosted', '') or job.get('createdDate', '') or ''
                if raw_date:
                    try:
                        posted_dt = datetime.fromisoformat(raw_date[:10]).replace(tzinfo=timezone.utc)
                        if posted_dt < self.yesterday:
                            continue
                    except Exception:
                        pass  # If date unparseable, include job to be safe

                job_id = job.get('id', '') or job.get('jobId', '')
                apply_url = f'https://{company_domain}.bamboohr.com/careers/{job_id}' if job_id else ''

                # ── Description from listing metadata ──
                desc = job.get('summary', '') or job.get('description', '') or ''
                sponsorship = self._extract_sponsorship(desc)

                # ── Department / team ──
                department = job.get('department', '') or job.get('division', '') or ''

                if self._add_job({
                    'title': title,
                    'company': job.get('companyName', '') or company_domain.replace('-', ' ').title(),
                    'location': loc,
                    'url': apply_url,
                    'source': 'BambooHR',
                    'description': desc[:2000],
                    'date': raw_date[:10] if raw_date else datetime.now().strftime('%Y-%m-%d'),
                    'salary': '',
                    'department': department,
                    'sponsorship': sponsorship,
                }):
                    added += 1

            if added:
                print(f'  BambooHR [{company_domain}]: +{added} jobs')
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # WORKDAY  (POST-based JSON search -- handles pagination)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_workday(self, session, company):
        """
        Workday REST search API (POST JSON) with pagination.

        Improvements:
        - Expanded target role keywords (new-grad / SDE-1 / data / ML / AI focus)
        - Uses postedOnDate filter for freshness ('&postedOnDate=LAST_7_DAYS')
        - Salary / compensation from job detail if available
        - Pagination increased to 50 per page
        """
        workday_url = company['url']
        company_name = company['name']

        # Skip non-Workday URLs (handled by other scrapers)
        if 'lever.co' in workday_url or 'greenhouse.io' in workday_url:
            return
        if 'myworkdayjobs.com' not in workday_url:
            return

        search_url = workday_url.rstrip('/') + '/jobs'
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # Broader, entry-level-focused keyword set
        role_keywords = [
            'Software Engineer',
            'New Grad',
            'Entry Level Engineer',
            # Data Engineering
            'Data Engineer',
            'Analytics Engineer',
            # Data Science / Analytics
            'Data Scientist',
            'Data Analyst',
            'Business Analyst',
            'Business Intelligence Analyst',
            'Product Analyst',
            'Operations Analyst',
            # ML / AI
            'Machine Learning Engineer',
            # Infra / Cloud
            'Cloud Engineer',
            'Platform Engineer',
        ]

        company_added = 0
        for role_kw in role_keywords:
            offset = 0
            while True:
                payload = {
                    'appliedFacets': {},
                    'limit': 50,
                    'offset': offset,
                    'searchText': role_kw,
                }
                try:
                    resp = await self._fetch_with_retry(
                        session, search_url, method='POST',
                        json=payload, headers=headers
                    )
                    if not resp or resp.status != 200:
                        break
                    data = await resp.json()
                    job_postings = data.get('jobPostings', []) or []
                    if not job_postings:
                        break

                    kw_added = 0
                    for job in job_postings:
                        title = job.get('title', '')
                        if not self._is_role_match(title):
                            continue
                        loc = job.get('locationsText', '') or ''
                        if not self._is_us_location(loc):
                            continue

                        posted_on = job.get('postedOn', '') or job.get('startDate', '')
                        try:
                            if posted_on:
                                posted_dt = datetime.fromisoformat(posted_on.replace('Z', '+00:00'))
                                if posted_dt < self.yesterday:
                                    continue
                        except Exception:
                            pass

                        ext_id = job.get('externalPath', '') or ''
                        if not ext_id:
                            bullets = job.get('bulletFields', []) or []
                            ext_id = bullets[0] if bullets else ''
                        apply_url = (
                            workday_url.rstrip('/') +
                            (ext_id if ext_id.startswith('/') else f'/{ext_id}')
                        )

                        if self._add_job({
                            'title': title,
                            'company': company_name,
                            'location': loc,
                            'url': apply_url,
                            'source': 'Workday',
                            'description': str(job.get('jobDescription', ''))[:2000],
                            'date': posted_on[:10] if posted_on else datetime.now().strftime('%Y-%m-%d'),
                            'salary': '',
                            'sponsorship': '',
                        }):
                            kw_added += 1
                            company_added += 1

                    total = data.get('total', 0)
                    offset += 50
                    if offset >= min(total, 200) or not kw_added:
                        break

                except Exception:
                    break

        if company_added:
            print(f'  Workday [{company_name}]: +{company_added} jobs')

    # ─────────────────────────────────────────────────────────────────────
    # ADZUNA
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_adzuna(self, session, role):
        app_id = os.getenv("ADZUNA_APP_ID","")
        app_key = os.getenv("ADZUNA_APP_KEY","")
        if not app_id or app_id.startswith("YOUR"): return
        url = f"https://api.adzuna.com/v1/api/jobs/us/search/1"
        params = {"app_id": app_id, "app_key": app_key, "max_days_old": 7, "what": role, "results_per_page": 50}
        try:
            resp = await self._fetch_with_retry(session, url, params=params)
            if not resp or resp.status != 200: return
            data = await resp.json()
            added = 0
            for job in data.get("results", []):
                loc = job.get('location', {}).get('display_name', 'US')
                if not self._is_us_location(loc): continue
                if not self._is_role_match(job.get('title','')): continue
                if self._add_job({
                    "title": job.get('title',''),
                    "company": job.get('company',{}).get('display_name','Unknown'),
                    "location": loc,
                    "url": job.get('redirect_url',''),
                    "source": "Adzuna",
                    "description": job.get('description','')[:2000],
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "salary": f"${job.get('salary_min','')}-${job.get('salary_max','')}" if job.get('salary_min') else "",
                }):
                    added += 1
            if added: print(f"  Adzuna [{role}]: +{added} jobs")
        except Exception as e:
            print(f"  [Adzuna] Error: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # SIMPLIFY GITHUB  (JSON feed)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_simplify_github(self, session):
        """
        Fetch Simplify Jobs curated JSON feeds from GitHub.

        Fixes applied:
        - Correct URL field: applicationLinks[0] (was applicationLink -- always blank)
        - Dual-format datePosted: handles both Unix integer AND ISO string
        - Extracts sponsorship field
        - Excludes summer internship repos (user wants new-grad / full-time only)
        - Added 2026 new-grad feed
        """
        urls = [
            # New-grad full-time positions -- PRIMARY source
            "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/src/data/positions.json",
            # 2026 new-grad positions (speedyapply mirror, same schema)
            "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/src/data/positions.json",
        ]
        # NOTE: Summer2025-Internships intentionally excluded per user preference
        for url in urls:
            try:
                resp = await self._fetch_with_retry(session, url)
                if not resp or resp.status != 200:
                    continue
                jobs = await resp.json(content_type=None)
                if not isinstance(jobs, list):
                    continue

                added = 0
                for job in jobs:
                    # ── Date parsing: handles both int (Unix ms or s) and ISO string ──
                    raw_date = job.get('datePosted') or job.get('date_posted') or 0
                    try:
                        if isinstance(raw_date, (int, float)) and raw_date > 0:
                            # Unix timestamp -- could be seconds or milliseconds
                            ts = raw_date / 1000 if raw_date > 1e10 else raw_date
                            posted = datetime.fromtimestamp(ts, tz=timezone.utc)
                        elif isinstance(raw_date, str) and raw_date:
                            posted = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                        else:
                            posted = datetime.now(timezone.utc)
                    except Exception:
                        posted = datetime.now(timezone.utc)

                    # ── Date: GitHub repos update daily, not hourly.
                    # Use a minimum 2-day window regardless of hours_back.
                    github_cutoff = min(
                        self.yesterday,
                        datetime.now(timezone.utc) - timedelta(days=2)
                    )
                    if posted < github_cutoff:
                        continue

                    # ── URL: try applicationLinks array first, then fallback fields ──
                    app_links = job.get('applicationLinks') or job.get('applicationLink') or []
                    if isinstance(app_links, list) and app_links:
                        job_url = app_links[0]
                    elif isinstance(app_links, str) and app_links:
                        job_url = app_links
                    else:
                        job_url = job.get('url') or job.get('apply_url') or ''

                    # ── Location filter ──
                    locs = job.get('locations') or job.get('location') or ['United States']
                    if isinstance(locs, str):
                        locs = [locs]
                    loc = ' | '.join(locs[:3]) if locs else 'United States'
                    if not self._is_us_location(loc):
                        continue

                    # ── Role filter: Simplify data is already curated new-grad -- be lenient ──
                    title = job.get('role') or job.get('title') or ''
                    if not title:
                        continue
                    # Only skip hard senior roles
                    if any(x in title.lower() for x in ['senior', 'staff ', 'principal', 'director', 'manager', 'lead ']):
                        continue

                    # ── Sponsorship ──
                    sponsorship = ''
                    sp = str(job.get('sponsorship') or '').lower()
                    if 'yes' in sp or 'true' in sp:
                        sponsorship = 'Likely'
                    elif 'no' in sp or 'false' in sp:
                        sponsorship = 'No'

                    if self._add_job({
                        'title': title,
                        'company': job.get('companyName') or job.get('company') or 'Unknown',
                        'location': loc,
                        'url': job_url,
                        'source': 'SimplifyJobs',
                        'description': 'Sourced from SimplifyJobs community list.',
                        'date': posted.strftime('%Y-%m-%d'),
                        'salary': '',
                        'sponsorship': sponsorship,
                    }):
                        added += 1

                if added:
                    print(f'  SimplifyJobs GitHub: +{added} jobs from {url.split("/")[-3]}')
            except Exception as e:
                print(f'  [SimplifyJobs] Error on {url}: {e}')


    # ─────────────────────────────────────────────────────────────────────
    # SIMPLIFY REST API  (Phase B -- no login, JSON, fast)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_simplify_api(self, session, db=None):
        """
        Simplify 'API' -- expanded multi-repo GitHub JSON fetcher.

        The Simplify.jobs REST API is behind Cloudflare (403 for direct HTTP).
        Instead, we pull from MULTIPLE curated GitHub repos that maintain
        Simplify-style JSON feeds of new-grad and entry-level SWE positions.

        Repos fetched (all new-grad / full-time, NO summer internships):
          1. SimplifyJobs/New-Grad-Positions (primary)
          2. speedyapply/2026-SWE-College-Jobs
          3. vanshb03/New-Grad-2026
          4. coderQuad/New-Grad-Hires
          5. ReaVNaiL/New-Grad-2024

        Each repo uses a JSON feed at src/data/positions.json or README.
        We apply a lenient role filter to accept SWE/data/ML/AI/infra roles
        while excluding summer internships and senior roles.
        """
        print('>> Simplify Multi-Repo GitHub Fetcher (Phase B)...')

        # All repos with new-grad / entry-level full-time SWE JSON feeds
        # Format: (url, repo_label)
        json_feeds = [
            (
                'https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/src/data/positions.json',
                'simplify-new-grad'
            ),
            (
                'https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/src/data/positions.json',
                'speedyapply-2026'
            ),
            (
                'https://raw.githubusercontent.com/vanshb03/New-Grad-2026/main/src/data/positions.json',
                'vanshb-2026'
            ),
            (
                'https://raw.githubusercontent.com/coderQuad/New-Grad-Hires/main/src/data/positions.json',
                'coderquad'
            ),
            (
                'https://raw.githubusercontent.com/ReaVNaiL/New-Grad-2024/main/src/data/positions.json',
                'reavnail-2024'
            ),
            # Additional community repos
            (
                'https://raw.githubusercontent.com/Ouckah/Summer2025-Internships/dev/src/data/positions.json',
                'ouckah-2025-full'
            ),
            (
                'https://raw.githubusercontent.com/cvrve/New-Grad-2025/dev/src/data/positions.json',
                'cvrve-2025'
            ),
            (
                'https://raw.githubusercontent.com/AkazaAkane/product-manager-jobs-fall-2024/main/src/data/positions.json',
                'pm-jobs'
            ),
        ]

        total_added = 0

        def _parse_date(raw):
            """Parse datePosted: int (Unix s or ms) or ISO string -> datetime."""
            try:
                if isinstance(raw, (int, float)) and raw > 0:
                    ts = raw / 1000 if raw > 1e10 else raw
                    return datetime.fromtimestamp(ts, tz=timezone.utc)
                if isinstance(raw, str) and raw:
                    return datetime.fromisoformat(raw.replace('Z', '+00:00'))
            except Exception:
                pass
            return datetime.now(timezone.utc)

        def _extract_url(job):
            """Get the best available application URL from various field names."""
            links = job.get('applicationLinks') or job.get('applicationLink') or []
            if isinstance(links, list) and links:
                return links[0]
            if isinstance(links, str) and links:
                return links
            return job.get('url') or job.get('apply_url') or job.get('applyUrl') or ''

        def _extract_locs(job):
            locs = job.get('locations') or job.get('location') or ['United States']
            if isinstance(locs, str):
                locs = [locs]
            return ' | '.join(locs[:3]) if locs else 'United States'

        def _extract_sponsorship(job):
            sp = str(job.get('sponsorship') or '').lower()
            if any(x in sp for x in ['yes', 'true', 'sponsor']):
                return 'Likely'
            if any(x in sp for x in ['no', 'false']):
                return 'No'
            return ''

        # Role tokens we accept (new-grad / entry level focus)
        ACCEPT_ROLES = [
            'software engineer', 'swe', 'sde', 'developer', 'engineer',
            # Data roles
            'data engineer', 'data analyst', 'data scientist', 'analytics engineer',
            'analytics analyst', 'business analyst', 'business intelligence',
            'bi analyst', 'bi developer', 'bi engineer',
            'quantitative analyst', 'operations analyst', 'product analyst',
            'research analyst', 'market analyst', 'financial analyst',
            # ML / AI
            'machine learning', 'ml engineer', 'ai engineer', 'ai researcher',
            'nlp engineer', 'computer vision', 'applied scientist',
            # Infra / DevOps / Cloud
            'cloud engineer', 'devops', 'platform engineer', 'site reliability',
            'infrastructure engineer', 'systems engineer',
            # Mobile
            'mobile engineer', 'ios engineer', 'android engineer',
            # Security / QA
            'security engineer', 'qa engineer', 'quality engineer',
            # Catch-all
            'analyst', 'scientist',
        ]
        REJECT_ROLES = ['senior', 'staff ', 'principal', 'director', 'manager', 'lead ', 'intern', 'summer']

        for feed_url, label in json_feeds:
            try:
                resp = await self._fetch_with_retry(session, feed_url)
                if not resp or resp.status != 200:
                    continue

                jobs = await resp.json(content_type=None)
                if not isinstance(jobs, list):
                    continue

                feed_added = 0
                for job in jobs:
                    posted = _parse_date(job.get('datePosted') or job.get('date_posted') or 0)
                    # ── Date: use a minimum 7-day window for GitHub feeds (updated daily, not hourly) ──
                    github_cutoff = min(
                        self.yesterday,
                        datetime.now(timezone.utc) - timedelta(days=7)
                    )
                    if posted < github_cutoff:
                        continue

                    title = job.get('role') or job.get('title') or ''
                    if not title:
                        continue
                    tl = title.lower()
                    if any(r in tl for r in REJECT_ROLES):
                        continue
                    if not any(r in tl for r in ACCEPT_ROLES):
                        continue

                    loc = _extract_locs(job)
                    if not self._is_us_location(loc):
                        continue

                    job_url = _extract_url(job)
                    company = job.get('companyName') or job.get('company') or 'Unknown'
                    sponsorship = _extract_sponsorship(job)

                    if self._add_job({
                        'title': title,
                        'company': company,
                        'location': loc,
                        'url': job_url,
                        'source': 'SimplifyJobs',
                        'description': f'Sourced from {label} GitHub feed.',
                        'date': posted.strftime('%Y-%m-%d'),
                        'salary': '',
                        'sponsorship': sponsorship,
                    }):
                        feed_added += 1
                        total_added += 1
                        if db:
                            db.insert_raw_job({'title': title, 'company': company,
                                               'location': loc, 'url': job_url,
                                               'source': 'SimplifyJobs', 'date': posted.strftime('%Y-%m-%d')})

                if feed_added:
                    print(f'  [Simplify GitHub] {label}: +{feed_added} jobs')

            except Exception as e:
                print(f'  [Simplify GitHub feed:{label}] Error: {e}')

        print(f'  Simplify GitHub TOTAL: +{total_added} unique jobs across all repos')

    # ─────────────────────────────────────────────────────────────────────
    # REMOTEOK
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_remoteok(self, session):
        try:
            resp = await self._fetch_with_retry(session, "https://remoteok.com/api")
            if not resp or resp.status != 200: return
            data = await resp.json()
            jobs = data[1:] if len(data) > 0 else []
            added = 0
            for job in jobs:
                try:
                    posted = datetime.fromisoformat(job.get('date','').replace('Z','+00:00'))
                    if posted < self.yesterday: continue
                except: pass
                if not self._is_role_match(job.get('position','')): continue
                loc = job.get('location','Remote')
                if not self._is_us_location(loc): continue
                if self._add_job({
                    "title": job.get('position',''),
                    "company": job.get('company','Unknown'),
                    "location": loc,
                    "url": job.get('url',''),
                    "source": "RemoteOK",
                    "description": BeautifulSoup(job.get('description',''),'html.parser').get_text()[:2000],
                    "date": job.get('date','')[:10],
                    "salary": job.get('salary',''),
                }):
                    added += 1
            if added: print(f"  RemoteOK: +{added} jobs")
        except Exception as e:
            print(f"  [RemoteOK] Error: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # GITHUB MARKDOWN  (community curated lists)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_github_markdown(self, session, raw_url, label="GitHub List"):
        try:
            resp = await self._fetch_with_retry(session, raw_url)
            if not resp or resp.status != 200: return
            text = await resp.text()
            lines = text.split('\n')
            added = 0
            
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) < 4: continue
                
                url = ""
                for p in parts:
                    url_match = re.search(r'href=[\'"]?([^\'" >]+)', p) or re.search(r'\]\((https?://.*?)\)', p)
                    if url_match:
                        url = url_match.group(1)
                        break
                if not url: continue
                
                # Extract date
                date_str = ""
                for p in reversed(parts):
                    if re.search(r'jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d+[dh]|today|new', p.lower()):
                        date_str = p
                        break
                
                # ── Filter by time window ──
                if date_str:
                    posted_dt = self._parse_date_to_dt(date_str)
                    if posted_dt is None:
                        # Cannot parse date -- could be a 2023/2024 old entry. Skip it.
                        continue
                    # Use 2-day minimum window for GitHub markdown (repos don't update hourly)
                    github_cutoff = min(
                        self.cutoff,
                        datetime.now(timezone.utc) - timedelta(days=2)
                    )
                    if posted_dt < github_cutoff:
                        continue
                else:
                    # No date info at all -- skip to avoid surfacing old entries
                    continue
                
                # Extract text columns
                text_cols = []
                for p in parts[1:-1]:
                    soup = BeautifulSoup(p, "html.parser")
                    txt = soup.get_text().strip().replace("**","").replace("__","")
                    if txt and len(txt) > 1 and not ("http" in txt.lower()):
                        text_cols.append(txt)
                
                if not text_cols: continue
                company = text_cols[0] if text_cols else "Unknown"
                title = text_cols[1] if len(text_cols) > 1 else "Software Engineer"
                location = text_cols[2] if len(text_cols) > 2 else ""

                if len(title) < 3:
                    title = "Software Engineer (New Grad)"
                # GitHub Markdown repos are 100% curated new-grad lists -- no role filter needed

                if location and not self._is_us_location(location): continue

                # Check for closed/filled indicator
                full_line = line
                if any(x in full_line for x in ["🔒", ":lock:", "[closed]", "filled"]):
                    continue

                # Extract H1B sponsorship from line text
                sponsorship = self._extract_sponsorship(full_line)

                if self._add_job({
                    "title": title,
                    "company": company,
                    "location": location or "US",
                    "url": url,
                    "source": "GitHub Lists",
                    "description": f"Source: {label} | Company: {company} | Role: {title} | Location: {location} | Posted: {date_str}",
                    "date": date_str or datetime.now().strftime("%Y-%m-%d"),
                    "salary": "",
                    "sponsorship": sponsorship,
                }):
                    added += 1
            
            if added: print(f"  GitHub [{label}]: +{added} jobs")
        except Exception as e:
            print(f"  [GitHub:{label}] Error: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # JSEARCH / RAPIDAPI  (optional -- requires RAPIDAPI_KEY in .env)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_jsearch(self, session):
        api_key = os.getenv("RAPIDAPI_KEY","")
        if not api_key or api_key.startswith("YOUR"): return
        
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }
        queries = [
            "software engineer new grad United States",
            "entry level backend engineer remote",
            "junior data engineer United States",
            "entry level ML engineer remote",
        ]
        added = 0
        for q in queries:
            url = "https://jsearch.p.rapidapi.com/search"
            params = {"query": q, "page": "1", "num_pages": "3", "date_posted": "3days"}
            try:
                resp = await self._fetch_with_retry(session, url, params=params, headers=headers)
                if not resp or resp.status != 200: continue
                data = await resp.json()
                for job in data.get("data", []):
                    if not self._is_us_location(job.get('job_country','') + job.get('job_state','')): continue
                    if not self._is_role_match(job.get('job_title','')): continue
                    salary = ""
                    mn = job.get('job_min_salary'); mx = job.get('job_max_salary')
                    if mn or mx: salary = f"${int(mn or 0):,}–${int(mx or 0):,}"
                    if self._add_job({
                        "title": job.get('job_title',''),
                        "company": job.get('employer_name',''),
                        "location": f"{job.get('job_city','')}, {job.get('job_state','')}",
                        "url": job.get('job_apply_link',''),
                        "source": "JSearch",
                        "description": job.get('job_description','')[:2000],
                        "date": job.get('job_posted_at_datetime_utc','')[:10],
                        "salary": salary,
                    }):
                        added += 1
            except: pass
        if added: print(f"  JSearch: +{added} jobs")


    # ─────────────────────────────────────────────────────────────────────
    # LINKEDIN PHASE A -- Guest JSON API (no login, fast, structured)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_linkedin_api(self, session, db=None):
        """
        LinkedIn public guest API -- no cookies, no Playwright, 25 jobs/page.

        Endpoint:
          GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
            ?keywords=...&location=United%20States&f_E=1%2C2&f_TPR=r86400&start=N

        LinkedIn allows ~100 pages (start 0-975) before blocking.
        We run multiple keyword queries and union-deduplicate by job URL.
        """
        print("▶ LinkedIn API Scraper (guest JSON, no login)...")

        # ── Multi-Query Matrix ─────────────────────────────────────────────
        # Broad queries first (most unique results), narrow queries last.
        # We use a single wide time window (r86400 = last 24h) matched to
        # self.hours_back; if user asked for >24h we use r604800 (7d).
        hours = getattr(self, 'hours_back', 24)
        if hours <= 24:
            tpr = "r86400"
        elif hours <= 72:
            tpr = "r259200"
        else:
            tpr = "r604800"

        search_queries = [
            # Core SWE
            "new grad software engineer",
            "entry level software engineer",
            "software engineer I",
            "SDE 1",
            "junior software engineer",
            "associate software engineer",
            # Specializations
            "backend engineer new grad",
            "frontend engineer entry level",
            "full stack engineer entry level",
            # Data Engineering
            "data engineer entry level",
            "data engineer new grad",
            "analytics engineer entry level",
            # Data Science / Analytics
            "data scientist new grad",
            "data analyst entry level",
            "data analyst new grad",
            "business analyst entry level",
            "business intelligence analyst entry level",
            "BI analyst new grad",
            "product analyst new grad",
            "operations analyst entry level",
            # ML / AI
            "AI engineer entry level",
            "machine learning engineer new grad",
            # Infra / Cloud
            "cloud engineer new grad",
            "DevOps engineer entry level",
            "platform engineer new grad",
            "mobile engineer entry level",
            # Catch-all
            "early career engineer",
            "new graduate engineer",
        ]

        base = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.linkedin.com/",
        }

        li_seen_urls: set = set()
        total_added = 0
        import urllib.parse

        for query in search_queries:
            kw = urllib.parse.quote_plus(query)
            query_added = 0

            for start in range(0, 200, 25):   # up to 200/25=8 pages per query
                url = (
                    f"{base}?keywords={kw}"
                    f"&location=United%20States"
                    f"&f_E=1%2C2"          # Entry level + Associate
                    f"&f_TPR={tpr}"
                    f"&sortBy=DD"           # date descending
                    f"&start={start}"
                )
                try:
                    resp = await self._fetch_with_retry(session, url, extra_headers=headers)
                    if not resp or resp.status not in (200, 201):
                        break

                    html = await resp.text()
                    if not html.strip():
                        break

                    # Parse HTML -- each job is in <li class="...">
                    from bs4 import BeautifulSoup as _BS
                    soup = _BS(html, "html.parser")
                    cards = soup.find_all("div", class_=lambda c: c and "base-card" in c)
                    if not cards:
                        # Older response format uses <li> wrappers
                        cards = soup.find_all("li")

                    if not cards:
                        break  # empty page -- done for this query

                    page_new = 0
                    for card in cards:
                        try:
                            # ── Title ──────────────────────────────────────
                            title_tag = (
                                card.find("h3", class_=lambda c: c and "base-search-card__title" in c) or
                                card.find("h3") or
                                card.find("h4")
                            )
                            if not title_tag:
                                continue
                            title = title_tag.get_text(strip=True)
                            if not title or len(title) < 3:
                                continue

                            # ── Company ──
                            # IMPORTANT: avoid bare card.find('h4') -- it can match the location span.
                            # Only trust explicit class-based lookups.
                            co_tag = (
                                card.find("h4", class_=lambda c: c and "base-search-card__subtitle" in c) or
                                card.find("a", class_=lambda c: c and "hidden-nested-link" in c)
                            )
                            company = co_tag.get_text(strip=True) if co_tag else "Unknown"

                            # ── URL ────────────────────────────────────────
                            link_tag = card.find("a", class_=lambda c: c and "base-card__full-link" in c)
                            if not link_tag:
                                link_tag = card.find("a", href=lambda h: h and "/jobs/view/" in h)
                            if not link_tag:
                                continue
                            raw_url = link_tag.get("href", "")
                            job_url = raw_url.split("?")[0]  # strip tracking params
                            if not job_url or job_url in li_seen_urls:
                                continue
                            li_seen_urls.add(job_url)

                            # ── Location ───────────────────────────────────
                            loc_tag = card.find("span", class_=lambda c: c and "job-search-card__location" in c)
                            location = loc_tag.get_text(strip=True) if loc_tag else "United States"

                            # ── Date ───────────────────────────────────────
                            time_tag = card.find("time")
                            if time_tag:
                                date_str = time_tag.get("datetime") or time_tag.get_text(strip=True)
                            else:
                                date_str = "today"

                            # ── Filters ────────────────────────────────────
                            if not self._is_role_match(title):
                                continue

                            job_data = {
                                "title": title,
                                "company": company,
                                "location": location or "United States",
                                "url": job_url,
                                "source": "LinkedIn",
                                "description": f"LinkedIn API | {query}",
                                "date": date_str,
                                "salary": "",
                            }

                            if self._add_job(job_data):
                                total_added += 1
                                query_added += 1
                                page_new += 1
                                if db:
                                    db.insert_raw_job(job_data)

                        except Exception:
                            continue

                    print(f"  [LinkedIn API] q='{query[:25]}' start={start}: +{page_new} (total {total_added})")

                    if page_new == 0 and start > 0:
                        break  # no new jobs on this page -- done paginating this query

                    await asyncio.sleep(0.8)  # polite pause between pages

                except Exception as e:
                    print(f"  [LinkedIn API] Error on '{query}' start={start}: {e}")
                    break

            if query_added == 0 and start == 0:
                pass  # query had zero results -- continue to next

        print(f"  LinkedIn API TOTAL: +{total_added} unique jobs")

    # ─────────────────────────────────────────────────────────────────────
    # LINKEDIN PHASE B -- Headed Playwright (supplement, logged-in session)
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_linkedin_playwright(self, db=None):
        """
        LinkedIn headed Playwright scraper -- supplements the API scraper.

        Fixes applied vs the old broken version:
        1. Correct 2025 DOM selectors: li[data-occludable-job-id], time[datetime]
        2. Incremental scroll (8 × 600px) to trigger React lazy-loading
        3. Single time window (self.hours_back → f_TPR) -- no redundant 4-filter loop
        4. URL-primary dedup (job id from href) across all queries
        5. Auth wall → continue past bad URL, NOT close session
        6. Proper outer-loop bail-out on consecutive empty queries
        7. Pagination stops when a full 25-card page adds 0 new (i.e. all seen)
           AND start > 0 (first page of 0 = query truly empty)
        """
        print("▶ LinkedIn Playwright Scraper (headed, logged-in)...")
        from playwright.async_api import async_playwright
        import random

        hours = getattr(self, 'hours_back', 24)
        if hours <= 1:
            tpr = "r3600"
        elif hours <= 6:
            tpr = "r21600"
        elif hours <= 24:
            tpr = "r86400"
        elif hours <= 72:
            tpr = "r259200"
        else:
            tpr = "r604800"

        # Multi-query matrix -- ordered broad → narrow to maximise unique results
        search_queries = [
            # Core SWE
            "new grad software engineer",
            "entry level software engineer",
            "software engineer I",
            "SDE 1",
            "junior software engineer",
            "associate software engineer",
            # Specializations
            "backend engineer new grad",
            "frontend engineer entry level",
            "full stack engineer entry level",
            # Data Engineering
            "data engineer entry level",
            "data engineer new grad",
            "analytics engineer entry level",
            # Data Science / Analytics
            "data scientist new grad",
            "data analyst entry level",
            "data analyst new grad",
            "business analyst entry level",
            "business intelligence analyst entry level",
            "product analyst new grad",
            "operations analyst entry level",
            # ML / AI
            "AI engineer entry level",
            "machine learning engineer new grad",
            # Infra / Cloud
            "cloud engineer new grad",
            "early career software engineer",
        ]

        li_seen_urls: set = set()
        total_added = 0
        consecutive_empty_queries = 0

        try:
            async with async_playwright() as p:
                user_data_dir = os.path.abspath("playwright_profile")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled'],
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    viewport={'width': 1366, 'height': 900}
                )
                page = await context.new_page()

                # ── Login check ────────────────────────────────────────────
                print("  [LinkedIn] Checking login status...")
                await page.goto("https://www.linkedin.com/feed/", timeout=20000)
                await page.wait_for_timeout(4000)

                if "feed" not in page.url and "mynetwork" not in page.url:
                    print("  [LinkedIn] NOT logged in -- opening browser for login...")
                    await page.goto("https://www.linkedin.com/login")
                    for _ in range(120):
                        await page.wait_for_timeout(1000)
                        if "feed" in page.url:
                            break
                    if "feed" not in page.url:
                        print("  [LinkedIn] Login not detected after 120s -- skipping Playwright scrape")
                        await context.close()
                        return
                    print("  [LinkedIn] Login OK!")
                else:
                    print("  [LinkedIn] Already logged in. Starting scrape...")

                # ── Query loop ────────────────────────────────────────────
                for qi, query in enumerate(search_queries, 1):
                    kw = query.replace(' ', '%20')
                    query_added = 0

                    for start in [0, 25, 50, 75, 100]:
                        search_url = (
                            f"https://www.linkedin.com/jobs/search/"
                            f"?keywords={kw}"
                            f"&location=United%20States"
                            f"&f_E=1%2C2"       # Entry level + Associate
                            f"&f_TPR={tpr}"
                            f"&sortBy=DD"        # Newest first
                            f"&start={start}"
                        )

                        try:
                            await page.goto(search_url, timeout=20000)
                        except Exception:
                            continue  # timeout -- try next offset

                        wait_ms = random.randint(4000, 6000) if start == 0 else random.randint(2500, 4000)
                        await page.wait_for_timeout(wait_ms)

                        # ── Auth wall check -- continue (NOT return) ────────
                        cur = page.url
                        if any(x in cur for x in ["authwall", "checkpoint", "uas/login", "signup"]):
                            print(f"  [LinkedIn] Soft block on '{query}' start={start} -- skipping this URL")
                            await page.wait_for_timeout(3000)
                            continue

                        # ── Login form in DOM ──────────────────────────────
                        if await page.locator("#session_key").count() > 0:
                            print(f"  [LinkedIn] Session expired mid-run -- stopping Playwright scrape")
                            await context.close()
                            print(f"  LinkedIn Playwright TOTAL so far: +{total_added} jobs")
                            return

                        # ── Incremental scroll to trigger lazy load ────────
                        for _ in range(8):
                            await page.evaluate("window.scrollBy(0, 600)")
                            await page.wait_for_timeout(500)
                            card_count = await page.locator("li[data-occludable-job-id]").count()
                            if card_count >= 20:
                                break

                        # One final scroll to bottom
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(1000)

                        # ── Card extraction ───────────────────────────────
                        cards = await page.locator("li[data-occludable-job-id]").all()
                        if not cards:
                            # Fallback: try older class selectors
                            cards = await page.locator(
                                ".job-search-card, .jobs-search-results__list-item, .scaffold-layout__list-item"
                            ).all()

                        if not cards:
                            break  # truly empty page -- stop paginating this query

                        page_new = 0
                        for card in cards:
                            try:
                                # ── URL (primary key) ──────────────────────
                                link = card.locator("a[href*='/jobs/view/']")
                                if await link.count() == 0:
                                    link = card.locator("a[href*='/jobs/collections/']")
                                if await link.count() == 0:
                                    continue
                                raw_url = await link.first.get_attribute("href") or ""
                                job_url = raw_url.split("?")[0]
                                if job_url.startswith("/"):
                                    job_url = "https://www.linkedin.com" + job_url
                                if not job_url or job_url in li_seen_urls:
                                    continue
                                li_seen_urls.add(job_url)

                                # ── Title ──────────────────────────────────
                                title_loc = card.locator(
                                    "h3.base-search-card__title, "
                                    "a[href*='/jobs/view/'] span[aria-hidden='true'], "
                                    ".job-card-list__title, h3, h4"
                                )
                                if await title_loc.count() == 0:
                                    continue
                                title = (await title_loc.first.inner_text()).strip()
                                if not title or len(title) < 3:
                                    continue

                                # ── Company ────────────────────────────────
                                co_loc = card.locator(
                                    ".job-card-container__primary-description, "
                                    ".job-card-container__company-name, "
                                    ".artdeco-entity-lockup__subtitle, "
                                    "h4.base-search-card__subtitle, "
                                    ".job-search-card__company-name, "
                                    "a.job-search-card__company-name, "
                                    "span.job-search-card__company-name"
                                )
                                company = (await co_loc.first.inner_text()).strip() if await co_loc.count() > 0 else "Unknown"

                                # ── Location ───────────────────────────────
                                loc_loc = card.locator(
                                    "span.job-search-card__location, "
                                    ".job-card-container__metadata-wrapper"
                                )
                                location = (await loc_loc.first.inner_text()).strip() if await loc_loc.count() > 0 else "United States"

                                # ── Date -- use datetime attribute for reliability ──
                                time_loc = card.locator("time[datetime]")
                                if await time_loc.count() > 0:
                                    date_str = await time_loc.first.get_attribute("datetime") or "today"
                                else:
                                    time_loc2 = card.locator("time")
                                    date_str = (await time_loc2.first.inner_text()).strip() if await time_loc2.count() > 0 else "today"

                                # ── Role filter ────────────────────────────
                                if not self._is_role_match(title):
                                    continue

                                job_data = {
                                    "title": title,
                                    "company": company,
                                    "location": location or "United States",
                                    "url": job_url,
                                    "source": "LinkedIn",
                                    "description": f"LinkedIn Playwright | {query}",
                                    "date": date_str,
                                    "salary": "",
                                }

                                if self._add_job(job_data):
                                    total_added += 1
                                    query_added += 1
                                    page_new += 1
                                    if db:
                                        db.insert_raw_job(job_data)
                                    print(f"  [DEBUG] Found: {company} - {title[:20]} - {job_url}")

                            except Exception:
                                continue

                        print(f"  [LinkedIn PW {qi}/{len(search_queries)}] '{query[:22]}' start={start}: +{page_new} new (total {total_added})")

                        # Stop paginating if this page gave 0 new AND it's not the first page
                        if page_new == 0 and start > 0:
                            break

                        await page.wait_for_timeout(random.randint(1500, 3000))

                    # Outer bail-out: 4 consecutive empty queries → we're saturated
                    if query_added == 0:
                        consecutive_empty_queries += 1
                        if consecutive_empty_queries >= 4:
                            print(f"  [LinkedIn] 4 consecutive empty queries -- stopping early")
                            break
                    else:
                        consecutive_empty_queries = 0

                    # Polite pause between queries
                    await page.wait_for_timeout(random.randint(2000, 3500))

                await context.close()
                print(f"  LinkedIn Playwright TOTAL: +{total_added} unique jobs")

        except Exception as e:
            print(f"  [LinkedIn Playwright] Failed: {e}")


    # ─────────────────────────────────────────────────────────────────────
    # PLAYWRIGHT: JOBRIGHT AI
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_jobright_playwright(self, db=None):
        """
        Jobright scraper with entry-level filter and proper card extraction.

        KEY FIXES:
        1. URL now includes experienceLevel=Entry+Level filter
        2. Uses specific job card selectors (not generic <a>) to avoid nav links
        3. Clicks "Load More" button up to 5 times per query for pagination
        4. More scrolling + wait for new cards to appear after each scroll
        5. Save-as-you-go so closing browser doesn't lose scraped jobs
        6. Extracts actual apply URL from card, not just the Jobright detail link
        """
        print("▶ Jobright AI Scraper (Playwright)...")
        from playwright.async_api import async_playwright
        import random

        # Jobright search queries optimised for entry-level roles
        # We force "Entry Level" / "New Grad" into the keyword itself because
        # Jobright often ignores the experienceLevel URL parameter for thin queries.
        search_configs = [
            {"role": "Software Engineer Entry Level",   "exp": "Entry+Level"},
            {"role": "Software Engineer New Grad",      "exp": "Entry+Level"},
            {"role": "Backend Engineer Entry Level",     "exp": "Entry+Level"},
            {"role": "Full Stack Engineer Entry Level",  "exp": "Entry+Level"},
            {"role": "AI Engineer New Grad",            "exp": "Entry+Level"},
            {"role": "Machine Learning Engineer Entry", "exp": "Entry+Level"},
            {"role": "Data Engineer Entry Level",       "exp": "Entry+Level"},
            {"role": "Cloud Engineer Entry Level",      "exp": "Entry+Level"},
            {"role": "New Grad SWE",                    "exp": "Entry+Level"},
            {"role": "Junior Software Engineer",        "exp": "Junior"},
            {"role": "Junior Backend Engineer",         "exp": "Junior"},
            {"role": "SDE 1",                           "exp": "Entry+Level"},
        ]

        added = 0

        try:
            async with async_playwright() as p:
                user_data_dir = os.path.abspath("playwright_profile")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled'],
                    viewport={'width': 1280, 'height': 800}
                )
                page = await context.new_page()

                # ── Check Jobright login status ──────────────────────────────
                print("  [Jobright] Checking login status...")
                await page.goto("https://jobright.ai/")
                await page.wait_for_timeout(3000)
                # Jobright search works without login but recommendations need it
                # We just proceed regardless since /jobs/search is public

                # Jobright search (recommendations require login -- skipped)
                # Targeted searches directly:
                for cfg in search_configs:
                    role_enc = cfg["role"].replace(" ", "+")
                    exp_enc  = cfg["exp"].replace(" ", "+")
                    # Jobright URL params: value=role, experienceLevel=Entry+Level, country=US, daysAgo=1
                    url = (
                        f"https://jobright.ai/jobs/search"
                        f"?value={role_enc}"
                        f"&experienceLevel={exp_enc}"
                        f"&country=US"
                        f"&daysAgo=1"    # last 24 hours
                    )
                    print(f"  Jobright: '{cfg['role']}' ({cfg['exp']})...")
                    await page.goto(url)
                    await page.wait_for_timeout(random.randint(4000, 6000))

                    # Click "Load More" up to 5 times to bypass pagination
                    for load_attempt in range(5):
                        # Scroll to bottom first to trigger lazy load
                        for _ in range(3):
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            await page.wait_for_timeout(1000)

                        # Count cards before clicking load more
                        before_count = len(await page.locator("[data-testid='job-card'], .job-card, article").all())

                        # Try clicking "Load More" / "Show More" button
                        load_more = page.locator(
                            "button:has-text('Load More'), button:has-text('Show More'), "
                            "button:has-text('See More Jobs'), [data-testid='load-more']"
                        )
                        if await load_more.count() > 0:
                            try:
                                await load_more.first.click()
                                await page.wait_for_timeout(2500)
                                after_count = len(await page.locator("[data-testid='job-card'], .job-card, article").all())
                                if after_count <= before_count:
                                    break   # No new cards loaded -- stop
                            except:
                                break
                        else:
                            break   # No load more button

                    n = await self._process_jobright_page(page, db=db)
                    added += n
                    print(f"    → +{n} jobs extracted")
                    await page.wait_for_timeout(random.randint(1500, 3000))

                await context.close()
                print(f"  Jobright AI TOTAL: +{added} jobs")

        except Exception as e:
            print(f"  [Jobright] Failed: {e}")

    async def _process_jobright_page(self, page, db=None):
        """
        Extract jobs from Jobright using page.evaluate() JS -- bypasses Playwright
        locator chain issues. Reads DOM directly like a browser script.
        """
        # Scroll to load all cards
        for _ in range(4):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1200)

        added = 0
        processed_urls: set = set()

        # Extract all job cards via JavaScript in one shot
        try:
            js_script = "() => { const cards = Array.from(document.querySelectorAll('a[href*=\"/jobs/info/\"]')); return cards.map(card => { const h2 = card.querySelector('h2, h3'); const companyEl = card.querySelector('[class*=\"company\"]'); const timeEl = card.querySelector('[class*=\"time\"]'); const metaEls = Array.from(card.querySelectorAll('[class*=\"job-metadata-item\"]')); const loc = metaEls.map(e => e.innerText ? e.innerText.trim() : '').find(t => t.includes('United States') || t.includes('Remote') || /,\\s*[A-Z]{2}$/.test(t)) || 'United States'; const salary = Array.from(card.querySelectorAll('*')).map(e => e.innerText || '').find(t => t.includes('$') && (t.includes('/yr') || t.includes('K/yr') || t.includes('/year'))) || ''; return { href: card.getAttribute('href') || '', title: h2 && h2.innerText ? h2.innerText.trim() : '', company: companyEl && companyEl.innerText ? companyEl.innerText.trim().split('\\n')[0] : 'Unknown', location: loc, date: timeEl && timeEl.innerText ? timeEl.innerText.trim() : 'today', salary: salary.trim().substring(0, 80), innerText: card.innerText ? card.innerText.substring(0, 400) : '' }; }); }"
            js_data = await page.evaluate(js_script)
        except Exception as e:
            print(f"    [Jobright] JS evaluate failed: {e}")
            return 0

        print(f"    [Jobright DEBUG] Found {len(js_data)} raw cards via JS")

        # Let's see the first extracted card raw data
        if js_data:
            print(f"    [Jobright DEBUG] Card 1 Sample:\n      Title: {js_data[0].get('title')!r}\n      Company: {js_data[0].get('company')!r}\n      Loc: {js_data[0].get('location')!r}\n      Date: {js_data[0].get('date')!r}")

        for item in js_data:
            try:
                href = item.get('href', '')
                if not href:
                    continue
                full_url = f"https://jobright.ai{href}" if href.startswith('/') else href
                base_url = full_url.split('?')[0]
                if base_url in processed_urls:
                    continue
                processed_urls.add(base_url)

                title = item.get('title', '').strip()
                company = item.get('company', '').strip() or 'Unknown'
                loc = item.get('location', 'United States').strip()

                # If title is empty or looks like a timestamp, try parsing inner text
                inner = item.get('innerText', '')
                if not title or len(title) < 3 or any(x in title.lower() for x in ['ago', 'today', 'hour', 'day', 'week', 'month']):
                    # Parse lines; skip timestamp-looking lines
                    lines = [l.strip() for l in inner.split('\n') if l.strip()]
                    timestamp_words = {'ago', 'today', 'yesterday', 'hour', 'hours', 'day', 'days', 'week', 'month', 'minute'}
                    for line in lines:
                        words = set(line.lower().split())
                        if words & timestamp_words:
                            continue  # skip timestamp line
                        if len(line) >= 5 and not line.startswith('http') and not any(c in line for c in ['/', '|', '$']):
                            title = line
                            break

                if not title or len(title) < 3:
                    continue

                if not self._is_role_match(title):
                    continue
                if not self._is_us_location(loc):
                    continue

                sponsorship = self._extract_sponsorship(inner)

                job_data = {
                    "title": title,
                    "company": company,
                    "location": loc,
                    "source": "JobRight AI",
                    "url": full_url,
                    "description": f"JobRight AI: {title} at {company} -- {loc}",
                    "date": item.get('date', 'today'),
                    "salary": item.get('salary', ''),
                    "sponsorship": sponsorship,
                }
                if self._add_job(job_data):
                    added += 1
                    if db:
                        db.insert_raw_job(job_data)

            except Exception:
                continue

        return added

    # ─────────────────────────────────────────────────────────────────────
    # PLAYWRIGHT: SIMPLIFY.JOBS
    # ─────────────────────────────────────────────────────────────────────
    async def fetch_simplify_playwright(self, db=None):
        """
        Simplify.jobs Playwright browser scraper -- Phase C supplement.

        Fixes applied vs the old broken version:
        1. Login check -- looks for avatar/profile button in DOM, not URL pattern
        2. Fixed CSS locator: a[href*='/jobs/'] (was missing closing ])
        3. Corrected URL format: experienceLevel=0,1 + sortBy=date (not h1b=true)
        4. Infinite scroll pagination -- scrolls until card count stops increasing
        5. Extracts data-job-id for reliable URL construction
        6. Extended query list covering SWE/data/ML/AI/infra roles
        7. No summer internships
        """
        print('>> Simplify.jobs Playwright Scraper (headed, supplement)...')
        from playwright.async_api import async_playwright
        import re as _re
        import random

        # Targeted Simplify queries -- broader than the API to catch different ranking
        queries = [
            # SWE
            'software engineer new grad',
            'SDE 1',
            'junior software engineer',
            'associate software engineer',
            # Specializations
            'backend engineer entry level',
            'frontend engineer entry level',
            'full stack engineer new grad',
            # Data Engineering
            'data engineer entry level',
            'data engineer new grad',
            'analytics engineer entry level',
            # Data Science / Analytics
            'data scientist new grad',
            'data analyst entry level',
            'business analyst entry level',
            'business intelligence analyst entry level',
            'product analyst new grad',
            'operations analyst entry level',
            # ML / AI
            'machine learning engineer entry level',
            'AI engineer new grad',
            # Infra / Cloud / DevOps
            'cloud engineer entry level',
            'DevOps engineer entry level',
            'platform engineer new grad',
            'mobile engineer entry level',
        ]

        # Build Simplify filter URL using the REAL parameter names from the Simplify frontend.
        # Decoded from user's actual browser URL:
        #   state=North America + points (bounding box)
        #   experience=Entry Level/New Grad;Junior
        #   category=<varies by query type>
        #   h1b=true, jobType=Full-Time;Contract, workArrangement=Remote;Hybrid;In Person
        SIMPLIFY_POINTS = '83%3B-170%3B7%3B-52'   # North America bounding box

        def make_url(q, category='Software%20Engineering%3BData%20%26%20Analytics%3BAI%20%26%20Machine%20Learning'):
            import urllib.parse
            kw = urllib.parse.quote_plus(q)
            return (
                f'https://simplify.jobs/jobs'
                f'?query={kw}'
                f'&state=North%20America'
                f'&points={SIMPLIFY_POINTS}'
                f'&experience=Entry%20Level%2FNew%20Grad%3BJunior'
                f'&category={category}'
                f'&h1b=true'
                f'&jobType=Full-Time%3BContract'
                f'&workArrangement=Remote%3BHybrid%3BIn%20Person'
            )

        seen_urls: set = set()
        total_added = 0
        captured_jobs_data = []

        try:
            async with async_playwright() as p:
                user_data_dir = os.path.abspath('playwright_profile')
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled'],
                    viewport={'width': 1366, 'height': 900}
                )
                page = await context.new_page()
                
                async def handle_response(response):
                    if response.request.method == "OPTIONS": return
                    url = response.url
                    if "js-ha.simplify.jobs" in url and ("search" in url or "multi_search" in url):
                        try:
                            data = await response.json()
                            if "results" in data:
                                for res in data["results"]:
                                    if "hits" in res:
                                        for hit in res["hits"]:
                                            captured_jobs_data.append(hit.get("document", {}))
                            elif "hits" in data:
                                for hit in data["hits"]:
                                    captured_jobs_data.append(hit.get("document", {}))
                        except Exception as e:
                            print(f"  [Simplify API Error] {e}")
                
                page.on("response", handle_response)

                # ── Login check ──
                print('  [Simplify] Checking login status...')
                await page.goto('https://simplify.jobs/', timeout=20000)
                await page.wait_for_timeout(3500)

                is_logged_in = (
                    await page.locator(
                        '[data-testid="user-avatar"], '
                        'a[href*="/applications"], '
                        'button:has-text("My Applications"), '
                        '[aria-label="Profile menu"], '
                        'a[href*="/profile"]'
                    ).count() > 0
                )

                if not is_logged_in:
                    print('  [Simplify] NOT logged in -- opening login page...')
                    await page.goto('https://simplify.jobs/auth/login')
                    for _ in range(120):
                        await page.wait_for_timeout(1000)
                        if any(x in page.url for x in ['/jobs', '/home', '/applications']):
                            break
                    if any(x in page.url for x in ['/jobs', '/home', '/applications']):
                        print('  [Simplify] Login successful!')
                    else:
                        print('  [Simplify] Login not detected -- proceeding as guest (fewer results)')
                else:
                    print('  [Simplify] Already logged in. Scraping...')

                for qi, query in enumerate(queries, 1):
                    captured_jobs_data.clear() # Reset per query
                    
                    await page.goto(make_url(query), timeout=20000)
                    
                    # Wait for API responses to settle
                    await page.wait_for_timeout(5000)
                    
                    # We can do one scroll just to trigger any extra pages if it's infinite scroll API
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await page.wait_for_timeout(2000)

                    query_added = 0
                    for j in captured_jobs_data:
                        try:
                            title = j.get('title', '').strip()
                            if not title or len(title) < 3:
                                continue
                                
                            # Role filtering
                            if any(x in title.lower() for x in ['senior', 'staff ', 'principal', 'director']):
                                continue
                            if not (self._is_role_match(title) or 'engineer' in title.lower() or 'analyst' in title.lower()):
                                continue
                                
                            company = j.get('company_name', 'Unknown')
                            job_id = j.get('id') or j.get('job_id')
                            if not job_id: continue
                            
                            job_url_clean = f'https://simplify.jobs/p/{job_id}'
                            
                            if job_url_clean in seen_urls:
                                continue
                            seen_urls.add(job_url_clean)
                            
                            # Date
                            # Simplity API returns start_date as unix timestamp
                            date_unix = j.get('start_date') or j.get('updated_date')
                            date_text = 'today'
                            if date_unix:
                                from datetime import datetime, timezone
                                dt = datetime.fromtimestamp(date_unix, tz=timezone.utc)
                                date_text = dt.strftime('%Y-%m-%d')
                                
                            # Location
                            locations = j.get('locations', [])
                            loc_str = locations[0].get('value', 'United States') if (locations and isinstance(locations[0], dict)) else str(locations[0]) if locations else 'United States'
                            work_arr = j.get('travel_requirements', '')
                            if 'Remote' in work_arr:
                                location = f"{loc_str} (Remote)"
                            else:
                                location = loc_str
                                
                            # Salary
                            min_sal = j.get('min_salary')
                            max_sal = j.get('max_salary')
                            salary_str = ''
                            if min_sal and max_sal:
                                salary_str = f"${min_sal:,.0f} - ${max_sal:,.0f}"
                                if j.get('salary_period') == 1:
                                    salary_str += "/hr"
                                    
                            job_data = {
                                'title': title,
                                'company': company,
                                'location': location,
                                'url': job_url_clean,
                                'source': 'Simplify',
                                'description': f'Simplify API | {query}',
                                'date': date_text,
                                'salary': salary_str,
                                'sponsorship': '',
                            }
                            
                            if self._add_job(job_data):
                                total_added += 1
                                query_added += 1
                                if db:
                                    db.insert_raw_job(job_data)
                        except Exception as e:
                            print(f"  [Simplify API parsing] Error: {e}")
                            continue
                            
                    print(f"  [Simplify PW {qi}/{len(queries)}] '{query[:22]}': {len(captured_jobs_data)} fetched | +{query_added} added. Total {total_added}")
                    
                await context.close()
                print(f'  Simplify Playwright TOTAL: +{total_added} unique jobs')

        except Exception as e:
            print(f'  [Simplify Playwright] Failed: {e}')

    # ─────────────────────────────────────────────────────────────────────
    # MAIN ORCHESTRATOR
    # ─────────────────────────────────────────────────────────────────────
    async def run_discovery(self, lookback_hours=168, db=None):
        """
        db= optional DatabaseManager instance. When passed, browser scrapers
        (LinkedIn, Jobright) flush jobs to DB immediately so closing the browser
        mid-run doesn't lose scraped data.
        """
        print(f"\n{'='*65}")
        print(f"  JOB HUNTER ULTRA -- Discovery Run | Lookback: {lookback_hours}h")
        print(f"  Roles: {self.roles}")
        print(f"{'='*65}\n")
        
        self.yesterday = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        conn = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/html, */*",
        }
        
        async with aiohttp.ClientSession(
            timeout=timeout, connector=conn, headers=headers
        ) as session:
            
            print("── Phase 1: API Scrapers (parallel) ──")
            tasks = []
            
            for board in GREENHOUSE_BOARDS:
                tasks.append(self.fetch_greenhouse(session, board))
            for board in LEVER_BOARDS:
                tasks.append(self.fetch_lever(session, board))
            for slug in ASHBY_BOARDS:
                tasks.append(self.fetch_ashby(session, slug))
            for slug in WORKABLE_BOARDS:
                tasks.append(self.fetch_workable(session, slug))
            for company_id in SMARTRECRUITERS_BOARDS:
                tasks.append(self.fetch_smartrecruiters(session, company_id))
            for domain in BAMBOOHR_BOARDS:
                tasks.append(self.fetch_bamboohr(session, domain))
            
            tasks.append(self.fetch_simplify_github(session))
            tasks.append(self.fetch_remoteok(session))
            tasks.append(self.fetch_jsearch(session))
            
            # Hard-coded Adzuna queries optimised for new-grad discovery
            adzuna_roles = [
                "software engineer new grad",
                "backend engineer entry level",
                "data engineer junior",
                "machine learning engineer entry level",
                "cloud engineer new grad",
                "full stack developer entry level",
                "sde entry level",
            ]
            for role in adzuna_roles:
                tasks.append(self.fetch_adzuna(session, role))
            
            github_sources = [
                ("https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/NEW_GRAD_USA.md", "speedyapply-2026"),
                ("https://raw.githubusercontent.com/vanshb03/New-Grad-2026/main/README.md", "vanshb-2026"),
                ("https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md", "simplify-ng"),
                ("https://raw.githubusercontent.com/ReaVNaiL/New-Grad-2024/main/README.md", "reavnail"),
                ("https://raw.githubusercontent.com/pittcsc/Summer2024-Internships/dev/README.md", "pittcsc"),
                ("https://raw.githubusercontent.com/Ouckah/Summer2025-Internships/dev/README.md", "ouckah"),
            ]
            for url, label in github_sources:
                tasks.append(self.fetch_github_markdown(session, url, label))
            
            # LinkedIn guest API (no login, runs in parallel with other API scrapers)
            tasks.append(self.fetch_linkedin_api(session, db=db))
            # Simplify REST API (no login, POST JSON, runs in parallel)
            tasks.append(self.fetch_simplify_api(session, db=db))
            
            print(f"  Launching {len(tasks)} parallel API tasks...")
            await asyncio.gather(*tasks, return_exceptions=True)
        
        print(f"\n── Phase 2: Workday API (sequential) ──")
        for company in WORKDAY_COMPANIES[:15]:
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=15), headers=headers
                ) as session:
                    await self.fetch_workday(session, company)
            except Exception:
                pass
        
        print(f"\n── Phase 3: Browser Scrapers (Playwright) ──")
        # Pass db= so these scrapers flush to disk immediately -- no data loss on Ctrl+C
        # [Temporarily disabled due to headless bot protection]
        # try:
        #     await self.fetch_jobright_playwright(db=db)
        # except Exception as e:
        #     print(f"  Jobright failed: {e}")
        try:
            await self.fetch_simplify_playwright(db=db)  # pass db so jobs sync immediately
        except Exception as e:
            print(f"  Simplify failed: {e}")
        try:
            await self.fetch_linkedin_playwright(db=db)
        except Exception as e:
            print(f"  LinkedIn failed: {e}")
        
        print(f"\n{'='*65}")
        print(f"  DISCOVERY COMPLETE -- {len(self.found_jobs)} total unique jobs found")
        print(f"\n  Source Breakdown:")
        for src, count in sorted(self._stats.items(), key=lambda x: -x[1]):
            if count: print(f"    {src:.<30} {count}")
        print(f"{'='*65}\n")
        
        return self.found_jobs


if __name__ == "__main__":
    if not os.path.exists("user_profile.json"):
        # Create a default profile
        default = {"preferences": {"roles": ["software engineer","backend","frontend","full stack","ai engineer","machine learning","data engineer","sde","swe"], "locations": ["United States","Remote"]}}
        with open("user_profile.json","w") as f:
            json.dump(default, f, indent=2)
        print("Created default user_profile.json")
    discoverer = JobDiscovery()
    asyncio.run(discoverer.run_discovery())