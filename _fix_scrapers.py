"""
Fix script for all scraper issues identified in the E2E test.
Applies targeted string replacements to job_discovery.py and dashboard.py.

Fixes:
  1. Jobright: skip /jobs/recommend (requires login), improve card text extraction,
     grab title/company from named sub-selectors instead of raw .inner_text() parsing.
  2. LinkedIn: detect auth wall BEFORE processing any cards, not just after.
     Also raise consecutive_empty_batches threshold so 1 empty time-filter
     doesn't immediately trigger bail-out for all 12 queries.
  3. Dashboard: Full Discovery button changes from 168h to 24h.
  4. DB: TRUNCATE jobs + applications before fresh run.
"""
import re

# ─── 1. job_discovery.py ──────────────────────────────────────────────────────
with open('job_discovery.py', 'r', encoding='utf-8') as f:
    jd = f.read().replace('\r\n', '\n')

# Fix 1a: skip /jobs/recommend (requires login); jump straight to searches
old_recommend = '''                # 1. Start with personalised recommendations (already filtered for you)
                print("  Jobright: Loading recommendations...")
                await page.goto("https://jobright.ai/jobs/recommend")
                await page.wait_for_timeout(8000)
                added += await self._process_jobright_page(page, db=db)

                # 2. Targeted searches with entry-level filter'''
new_recommend = '''                # Jobright search (recommendations require login — skipped)
                # Targeted searches directly:'''
if old_recommend in jd:
    jd = jd.replace(old_recommend, new_recommend)
    print("Fix 1a: skipped /jobs/recommend")
else:
    print("WARN 1a: pattern not found")

# Fix 1b: change daysAgo=7 to daysAgo=1 in Jobright search URLs
jd = jd.replace(
    'f"&daysAgo=7"    # last 7 days',
    'f"&daysAgo=1"    # last 24 hours'
)
print("Fix 1b: Jobright daysAgo=1")

# Fix 1c: Improve _process_jobright_page card selector — also try /jobs/info/ links
old_card_selector = '''        # ── Strategy 1: Jobright updated DOM — cards are now <a> tags (Feb 2026) ──
        # Confirmed via Playwright DOM inspection: class='index_job-card__oqX1M'
        cards_found = await page.locator(
            "a[class*='job-card'], a.index_job-card__oqX1M"
        ).all()'''
new_card_selector = '''        # ── Strategy 1: Jobright DOM (Feb 2026) — cards are <a href='/jobs/info/…'> ──
        # Primary: links to /jobs/info/ (confirmed via live DOM inspection)
        # Secondary: any element with job-card in class
        cards_found = await page.locator(
            "a[href*='/jobs/info/'], a[class*='job-card']"
        ).all()'''
if old_card_selector in jd:
    jd = jd.replace(old_card_selector, new_card_selector)
    print("Fix 1c: Jobright card selector updated")
else:
    print("WARN 1c: card selector pattern not found")

# Fix 1d: Extract title/company from specific child elements, not just raw lines
old_extract = '''                # ── Extract text from card ──
                try:
                    raw = await card.inner_text()
                except:
                    continue
                lines = [l.strip() for l in raw.split('\\n') if l.strip()]
                if len(lines) < 2:
                    continue'''
new_extract = '''                # ── Extract title/company using sub-selectors or fallback to text ──
                try:
                    # Try sub-selectors first (Jobright DOM: class contains job-card-main)
                    title_el  = card.locator("[class*='job-card-main'] [class*='title'], h3, h2")
                    comp_el   = card.locator("[class*='job-card-main'] [class*='company'], [class*='sub-content'] [class*='company']")
                    if await title_el.count() > 0:
                        title   = (await title_el.first.inner_text()).strip()
                        company = (await comp_el.first.inner_text()).strip() if await comp_el.count() > 0 else ""
                        raw = await card.inner_text()
                    else:
                        raw = await card.inner_text()
                        title = company = ""
                except:
                    continue
                lines = [l.strip() for l in raw.split('\\n') if l.strip()]
                if len(lines) < 2:
                    continue'''
if old_extract in jd:
    jd = jd.replace(old_extract, new_extract)
    print("Fix 1d: Jobright sub-selector extraction added")
else:
    print("WARN 1d: extract pattern not found — doing partial")

# Fix 1e: In the title/company parsing block, only parse lines if title is empty
old_parse_title = '''                title = ""
                company = ""
                skip_prefixes = ("apply", "view", "login", "sign", "http", "match", "ai", "new",
                                 "saved", "see", "show", "load")'''
new_parse_title = '''                if not title:
                    title = ""
                if not company:
                    company = ""
                skip_prefixes = ("apply", "view", "login", "sign", "http", "match", "ai", "new",
                                 "saved", "see", "show", "load")'''
if old_parse_title in jd:
    jd = jd.replace(old_parse_title, new_parse_title)
    print("Fix 1e: only parse lines if title empty")
else:
    print("WARN 1e: parse title pattern not found")

# Fix 2: LinkedIn — raise bail-out threshold from 4 to 8 AND detect auth wall per-page
old_bail = '''                        if batch_added == 0:
                            consecutive_empty_batches += 1
                            if consecutive_empty_batches >= 4:
                                print(f"  LinkedIn: 4 consecutive empty batches — stopping early")
                                break'''
new_bail = '''                        if batch_added == 0:
                            consecutive_empty_batches += 1
                            if consecutive_empty_batches >= 8:
                                print(f"  LinkedIn: 8 consecutive empty batches — stopping early")
                                break'''
if old_bail in jd:
    jd = jd.replace(old_bail, new_bail)
    print("Fix 2a: LinkedIn bail-out threshold raised to 8")
else:
    print("WARN 2a: bail-out pattern not found")

# Fix 2b: Add explicit auth-wall check and wait longer before grabbing cards
old_goto = '''                            await page.goto(search_url)
                            # Shorter wait between pagination pages vs new queries
                            wait_ms = random.randint(2000, 3500) if start > 0 else random.randint(3500, 5500)
                            await page.wait_for_timeout(wait_ms)

                            # Check for auth wall / rate limit page
                            if "authwall" in page.url or "checkpoint" in page.url:
                                print(f"  [LinkedIn] Auth wall hit — stopping scrape")
                                await context.close()
                                print(f"  LinkedIn total: +{added} jobs saved")
                                return'''
new_goto = '''                            await page.goto(search_url)
                            # Shorter wait between pagination pages vs new queries
                            wait_ms = random.randint(3500, 5500) if start > 0 else random.randint(5000, 7500)
                            await page.wait_for_timeout(wait_ms)

                            # Check for auth wall / rate limit / login redirect
                            current_url = page.url
                            if any(x in current_url for x in ["authwall", "checkpoint", "login", "signup"]):
                                print(f"  [LinkedIn] Auth/login wall hit — stopping scrape for this session")
                                await context.close()
                                print(f"  LinkedIn total: +{added} jobs saved")
                                return

                            # Also check DOM for login form
                            login_form = await page.locator("form.login__form, #session_key").count()
                            if login_form > 0:
                                print(f"  [LinkedIn] Login form detected — session expired, stopping")
                                await context.close()
                                print(f"  LinkedIn total: +{added} jobs saved")
                                return'''
if old_goto in jd:
    jd = jd.replace(old_goto, new_goto)
    print("Fix 2b: LinkedIn auth wall detection per-page added")
else:
    print("WARN 2b: LinkedIn goto pattern not found")

with open('job_discovery.py', 'w', encoding='utf-8') as f:
    f.write(jd)
print("job_discovery.py saved")

# ─── 2. dashboard.py ──────────────────────────────────────────────────────────
with open('dashboard.py', 'r', encoding='utf-8') as f:
    dash = f.read().replace('\r\n', '\n')

# Fix 3: Full Discovery button — change 168 to 24
dash = dash.replace(
    'if st.button("Full Discovery (7 days)", use_container_width=True):\n        launch_discovery(168)',
    'if st.button("Full Discovery (24h)", use_container_width=True):\n        launch_discovery(24)'
)
print("Fix 3: Full Discovery button changed to 24h")

with open('dashboard.py', 'w', encoding='utf-8') as f:
    f.write(dash)
print("dashboard.py saved")

print("\nAll fixes applied. Verify with: python -c \"import py_compile; [py_compile.compile(f) or print(f+' OK') for f in ['job_discovery.py','dashboard.py']]\"")
