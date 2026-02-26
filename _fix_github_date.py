"""
FINAL comprehensive fix script.
Fixes:
  1. self.yesterday → self.cutoff based on --hours argument passed from daily_runner
  2. fetch_github_markdown: actually parse and filter dates against self.cutoff
  3. daily_runner.py: pass hours_back into JobDiscovery.__init__
  4. Stub _standardize_date helper to return a real datetime instead of just a string
"""

import re

# ──────────────────────────────────────────────────────────────────────────────
# FIX 1 + 2: job_discovery.py — cutoff propagation + GitHub date filter
# ──────────────────────────────────────────────────────────────────────────────
with open('job_discovery.py', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

# Fix __init__: accept hours_back param and set self.cutoff from it
old_init = '''    def __init__(self, profile_path="user_profile.json"):
        if os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                self.profile = json.load(f)
        else:
            self.profile = {"preferences": {"roles": ["software engineer", "backend", "frontend", "full stack", "ai", "machine learning", "data"], "locations": ["United States", "Remote"]}}
        
        self.roles = [role.lower() for role in self.profile.get("preferences", {}).get("roles", [])]
        self.locations = [loc.lower() for loc in self.profile.get("preferences", {}).get("locations", [])]
        self.found_jobs = []
        self.seen_signatures = set()
        self.yesterday = datetime.now(timezone.utc) - timedelta(days=7)'''

new_init = '''    def __init__(self, profile_path="user_profile.json", hours_back=24):
        if os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                self.profile = json.load(f)
        else:
            self.profile = {"preferences": {"roles": ["software engineer", "backend", "frontend", "full stack", "ai", "machine learning", "data"], "locations": ["United States", "Remote"]}}
        
        self.roles = [role.lower() for role in self.profile.get("preferences", {}).get("roles", [])]
        self.locations = [loc.lower() for loc in self.profile.get("preferences", {}).get("locations", [])]
        self.found_jobs = []
        self.seen_signatures = set()
        self.hours_back = max(hours_back, 1)
        self.cutoff = datetime.now(timezone.utc) - timedelta(hours=self.hours_back)
        self.yesterday = self.cutoff  # backward-compat alias'''

if old_init in code:
    code = code.replace(old_init, new_init)
    print("Fix 1: __init__ now accepts hours_back")
else:
    print("WARN 1: __init__ pattern not found")

# Fix _standardize_date to also return a real datetime (new overloaded helper)
# Add a new helper _parse_date_to_dt right after _standardize_date
old_after_standardize = '''    def _is_us_location(self, loc_str):'''
new_helper = '''    def _parse_date_to_dt(self, date_str):
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

    def _is_us_location(self, loc_str):'''

if old_after_standardize in code:
    code = code.replace(old_after_standardize, new_helper)
    print("Fix 2a: _parse_date_to_dt helper added")
else:
    print("WARN 2a: _is_us_location anchor not found")

# Fix fetch_github_markdown: replace the no-op date filter with real cutoff check
old_github_filter = '''                # Filter old dates
                if date_str:
                    dl = date_str.lower()
                    other_months = ["jan","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
                    if any(m in dl for m in other_months) and "feb" not in dl:
                        pass  # allow all dates when doing wide scrape'''

new_github_filter = '''                # ── Filter by time window (respect --hours argument) ──────────
                if date_str:
                    posted_dt = self._parse_date_to_dt(date_str)
                    if posted_dt and posted_dt < self.cutoff:
                        continue   # Skip jobs older than the hours window'''

if old_github_filter in code:
    code = code.replace(old_github_filter, new_github_filter)
    print("Fix 2b: GitHub date filter now enforces cutoff")
else:
    print("WARN 2b: GitHub filter pattern not found")

with open('job_discovery.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("job_discovery.py saved")

# ──────────────────────────────────────────────────────────────────────────────
# FIX 3: daily_runner.py — pass hours_back into JobDiscovery()
# ──────────────────────────────────────────────────────────────────────────────
with open('daily_runner.py', 'r', encoding='utf-8') as f:
    dr = f.read().replace('\r\n', '\n')

# Find JobDiscovery() instantiation and add hours_back
patterns = [
    ('discovery = JobDiscovery()', 'discovery = JobDiscovery(hours_back=int(args.hours))'),
    ('jd = JobDiscovery()', 'jd = JobDiscovery(hours_back=int(args.hours))'),
    ('JobDiscovery(profile_path', 'JobDiscovery(hours_back=int(args.hours), profile_path'),
]
found = False
for old, new in patterns:
    if old in dr:
        dr = dr.replace(old, new)
        print(f"Fix 3: daily_runner patched: {old[:40]}...")
        found = True
        break

if not found:
    # Just show what we have
    idx = dr.find('JobDiscovery(')
    print(f"WARN 3: JobDiscovery( context:\n  {dr[max(0,idx-30):idx+80]!r}")

with open('daily_runner.py', 'w', encoding='utf-8') as f:
    f.write(dr)
print("daily_runner.py saved")

print("\nAll fixes applied. Run: python -c \"import py_compile; [py_compile.compile(f) or print(f+' OK') for f in ['job_discovery.py','daily_runner.py']]\"")
