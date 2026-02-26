"""
Hot-patch for Jobright _process_jobright_page.
The live DOM (Feb 2026) has:
  - Card:    a[href*='/jobs/info/'] (class: index_job-card__oqX1M)
  - Title:   h2[class*='job-title']  (e.g. index_job-title__Riiip)
  - Company: div[class*='company-name'] (e.g. index_company-name__jnxCX)
  - Meta:    div[class*='job-metadata-item'] (location, type, etc.)
  - Time:    span[class*='publish-time'] (e.g. index_publish-time__iYAbR)

Inner-text order: timestamp / title / company / tags / location...
Old code used lines[0] = timestamp as title → always failed _is_role_match.
"""

with open('job_discovery.py', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

# Replace the entire _process_jobright_page method
old_method_start = '    async def _process_jobright_page(self, page, db=None):'
old_method_end = '        return added'

start_idx = code.find(old_method_start)
# Find the next method definition after _process_jobright_page
end_idx = code.find('\n        return added', start_idx) + len('\n        return added')

if start_idx == -1:
    print("ERROR: _process_jobright_page not found")
else:
    new_method = '''    async def _process_jobright_page(self, page, db=None):
        """
        Extract jobs from Jobright page using confirmed DOM selectors (Feb 2026).
        Card:    a[href*='/jobs/info/']
        Title:   h2[class*='job-title']
        Company: div[class*='company-name']
        Meta:    div[class*='job-metadata-item'] → location, type
        Time:    span[class*='publish-time']
        """
        import random
        # Scroll to load all lazy-loaded cards
        for _ in range(4):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

        added = 0
        processed_urls: set = set()

        # All job cards on the page
        cards = await page.locator("a[href*='/jobs/info/']").all()
        if not cards:
            # Broader fallback if selector misses
            cards = await page.locator("a[class*='job-card']").all()

        for card in cards:
            try:
                # ── URL ──────────────────────────────────────────────────
                href = await card.get_attribute("href")
                if not href:
                    continue
                full_url = f"https://jobright.ai{href}" if href.startswith("/") else href
                # Strip query params for dedup
                base_url = full_url.split("?")[0]
                if base_url in processed_urls:
                    continue
                processed_urls.add(base_url)

                # ── Title — use specific h2 with job-title in class ──────
                title_el = card.locator("h2[class*='job-title'], h3[class*='job-title'], h2, h3")
                if await title_el.count() == 0:
                    continue
                title = (await title_el.first.inner_text()).strip()
                if not title or len(title) < 3:
                    continue

                # ── Company — div with company-name in class ─────────────
                comp_el = card.locator("div[class*='company-name'], span[class*='company']")
                company = (await comp_el.first.inner_text()).strip() if await comp_el.count() > 0 else "Unknown"

                # ── Location ─────────────────────────────────────────────
                meta_els = card.locator("div[class*='job-metadata-item'], span[class*='metadata']")
                loc = "United States"
                for i in range(await meta_els.count()):
                    txt = (await meta_els.nth(i).inner_text()).strip()
                    if any(x in txt.lower() for x in ["united states", "remote", ", ca", ", ny", ", wa", ", tx", ", fl"]):
                        loc = txt
                        break

                # ── Date ─────────────────────────────────────────────────
                time_el = card.locator("span[class*='publish-time'], span[class*='time']")
                date_text = (await time_el.first.inner_text()).strip() if await time_el.count() > 0 else "today"

                # ── Salary ───────────────────────────────────────────────
                salary = ""
                full_text = await card.inner_text()
                for line in full_text.split("\\n"):
                    if "$" in line and any(x in line.lower() for x in ["/yr", "/year", "k/", "per year"]):
                        salary = line.strip()[:80]
                        break

                # ── H1B Sponsorship ───────────────────────────────────────
                sponsorship = self._extract_sponsorship(full_text)

                # ── Filter ───────────────────────────────────────────────
                if not self._is_role_match(title):
                    continue
                if not self._is_us_location(loc):
                    continue

                job_data = {
                    "title": title,
                    "company": company,
                    "location": loc,
                    "source": "JobRight AI",
                    "url": full_url,
                    "description": f"JobRight AI: {title} at {company} — {loc}",
                    "date": date_text,
                    "salary": salary,
                    "sponsorship": sponsorship,
                }
                if self._add_job(job_data):
                    added += 1
                    if db:
                        db.insert_raw_job(job_data)

            except Exception:
                continue

        return added'''

    code = code[:start_idx] + new_method + code[end_idx:]
    print(f"Replaced _process_jobright_page. New code length: {len(code)}")

with open('job_discovery.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("job_discovery.py saved")
