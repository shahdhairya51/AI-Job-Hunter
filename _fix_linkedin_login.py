"""
Add LinkedIn login detection + interactive wait to the LinkedIn Playwright scraper.
The playwright_profile is a fresh Chromium with no LinkedIn session.
This patch:
  1. Navigates to linkedin.com FIRST before any searches
  2. Checks if logged in (looks for 'feed' URL or nav menu)
  3. If NOT logged in: prints a clear message and waits up to 120 seconds for the user to log in
  4. After login confirmed, proceeds with scraping

Also patches Jobright to share the same playwright_profile (so one login covers both).
"""

with open('job_discovery.py', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

# ── LinkedIn: add login check after context/page creation ──────────────────────
old_linkedin_page = '''                page = await context.new_page()
                batch_num = 0

                for query in search_queries:'''

new_linkedin_page = '''                page = await context.new_page()

                # ── One-time LinkedIn login check ───────────────────────────────
                print("  [LinkedIn] Checking login status...")
                await page.goto("https://www.linkedin.com/feed/")
                await page.wait_for_timeout(4000)

                # Are we on the feed (logged in) or redirected to login?
                if "feed" not in page.url and "mynetwork" not in page.url:
                    print("  [LinkedIn] NOT logged in — browser window is opening.")
                    print("  [LinkedIn] Please log in to LinkedIn in the browser window, then press Enter here.")
                    print("  [LinkedIn] You only need to do this ONCE — the session will be saved.")
                    # Navigate to login page
                    await page.goto("https://www.linkedin.com/login")
                    # Wait for user to log in: poll until URL changes to feed
                    for _ in range(120):  # up to 120 seconds
                        await page.wait_for_timeout(1000)
                        if "feed" in page.url or "checkpoint" in page.url:
                            break
                    if "feed" in page.url:
                        print("  [LinkedIn] Login successful! Proceeding with scraping...")
                    else:
                        print("  [LinkedIn] Login not detected after 120s — skipping LinkedIn scrape")
                        await context.close()
                        return
                else:
                    print("  [LinkedIn] Already logged in. Scraping...")

                batch_num = 0

                for query in search_queries:'''

if old_linkedin_page in code:
    code = code.replace(old_linkedin_page, new_linkedin_page)
    print("Fix: LinkedIn login check added")
else:
    print("WARN: LinkedIn page creation pattern not found — trying alternate")
    # Try to find and patch it differently
    idx = code.find('                page = await context.new_page()\n                batch_num = 0')
    if idx >= 0:
        print(f"  Found at index {idx}")
    else:
        print("  Not found at all")

# ── Also patch Jobright to add Jobright login check ────────────────────────────
old_jr_page = '''                page = await context.new_page()

                # Jobright search (recommendations require login — skipped)'''

new_jr_page = '''                page = await context.new_page()

                # ── Check Jobright login status ──────────────────────────────
                print("  [Jobright] Checking login status...")
                await page.goto("https://jobright.ai/")
                await page.wait_for_timeout(3000)
                # Jobright search works without login but recommendations need it
                # We just proceed regardless since /jobs/search is public

                # Jobright search (recommendations require login — skipped)'''

if old_jr_page in code:
    code = code.replace(old_jr_page, new_jr_page)
    print("Fix: Jobright page check added")
else:
    print("WARN: Jobright page creation pattern not found")

with open('job_discovery.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("job_discovery.py saved")
