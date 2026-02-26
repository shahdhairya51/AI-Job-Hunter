"""
Script to comment out Jobright AI scraper from the discovery pipeline.
"""

with open('job_discovery.py', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

old_call = '''        print(f"\\n── Phase 3: Browser Scrapers (Playwright) ──")
        # Pass db= so these scrapers flush to disk immediately — no data loss on Ctrl+C
        try:
            await self.fetch_jobright_playwright(db=db)
        except Exception as e:
            print(f"  Jobright failed: {e}")'''

new_call = '''        print(f"\\n── Phase 3: Browser Scrapers (Playwright) ──")
        # Pass db= so these scrapers flush to disk immediately — no data loss on Ctrl+C
        # [Temporarily disabled due to headless bot protection]
        # try:
        #     await self.fetch_jobright_playwright(db=db)
        # except Exception as e:
        #     print(f"  Jobright failed: {e}")'''

if old_call in code:
    code = code.replace(old_call, new_call)
    with open('job_discovery.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Jobright disabled successfully.")
else:
    print("WARN: Could not find Jobright execution block in job_discovery.py")
