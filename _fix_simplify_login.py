"""
Add Simplify.jobs login detection + interactive wait.
Simplify requires login to see personalized jobs and to avoid CAPTCHA blocks.
"""

with open('job_discovery.py', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

# ── Patch: add login check right after Simplify page creation ──────────────────
old_simplify_page = '''                page = await context.new_page()
                queries = [
                    "SOFTWARE ENGINEER", "BACKEND", "FULL STACK", "AI ENGINEER",
                    "MACHINE LEARNING", "DATA ENGINEER", "CLOUD ENGINEER",
                    "SWE NEW GRAD", "NEW GRAD", "ENTRY LEVEL"
                ]
                added = 0'''

new_simplify_page = '''                page = await context.new_page()

                # ── One-time Simplify login check ───────────────────────────────
                print("  [Simplify] Checking login status...")
                await page.goto("https://simplify.jobs/")
                await page.wait_for_timeout(4000)

                # Check for login indicators in page content
                page_text = await page.content()
                is_logged_in = (
                    "dashboard" in page.url.lower() or
                    "profile" in page.url.lower() or
                    await page.locator("[href*='/profile'], [href*='/dashboard'], button:has-text('Profile')").count() > 0
                )

                if not is_logged_in:
                    print("  [Simplify] NOT logged in — browser window is opening.")
                    print("  [Simplify] Please log in to Simplify.jobs in the browser window.")
                    print("  [Simplify] You only need to do this ONCE — session will be saved.")
                    await page.goto("https://simplify.jobs/auth/login")
                    # Poll until user completes login (up to 120 seconds)
                    for _ in range(120):
                        await page.wait_for_timeout(1000)
                        cur = page.url
                        if any(x in cur for x in ["/jobs", "/dashboard", "/profile", "/home"]):
                            break
                    if any(x in page.url for x in ["/jobs", "/dashboard", "/profile", "/home"]):
                        print("  [Simplify] Login successful! Proceeding with scraping...")
                    else:
                        print("  [Simplify] Login not detected after 120s — proceeding anyway...")
                else:
                    print("  [Simplify] Already logged in. Scraping...")

                queries = [
                    "SOFTWARE ENGINEER", "BACKEND", "FULL STACK", "AI ENGINEER",
                    "MACHINE LEARNING", "DATA ENGINEER", "CLOUD ENGINEER",
                    "SWE NEW GRAD", "NEW GRAD", "ENTRY LEVEL"
                ]
                added = 0'''

if old_simplify_page in code:
    code = code.replace(old_simplify_page, new_simplify_page)
    print("Fix: Simplify login check added")
else:
    print("WARN: Simplify page creation pattern not found")

with open('job_discovery.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("job_discovery.py saved")
