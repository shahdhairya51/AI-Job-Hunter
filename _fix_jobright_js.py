"""
Final Jobright fix: replace _process_jobright_page with JavaScript-based extraction.
Uses page.evaluate() to extract ALL job cards at once via JS — bypasses Playwright
locator chain issues and directly reads the DOM like a real browser script would.
"""

with open('job_discovery.py', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

# Find and replace the entire _process_jobright_page method
method_start = '    async def _process_jobright_page(self, page, db=None):'
method_end   = '\n        return added\n'

start_i = code.find(method_start)
# Find the NEXT top-level method after this one
end_i = code.find('\n        return added\n', start_i)
if end_i == -1:
    print("ERROR: Could not find return statement")
    exit(1)
end_i += len('\n        return added\n')

new_method = '''    async def _process_jobright_page(self, page, db=None):
        """
        Extract jobs from Jobright using page.evaluate() JS — bypasses Playwright
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
            js_data = await page.evaluate("""() => {
                const cards = Array.from(document.querySelectorAll('a[href*="/jobs/info/"]'));
                return cards.map(card => {
                    const h2 = card.querySelector('h2') || card.querySelector('h3');
                    const companyEl = card.querySelector('[class*="company-name"]') ||
                                      card.querySelector('[class*="company"]');
                    const timeEl = card.querySelector('[class*="publish-time"]') ||
                                   card.querySelector('[class*="time"]');
                    const metaEls = Array.from(card.querySelectorAll('[class*="job-metadata-item"]'));
                    const loc = metaEls.map(e => e.innerText.trim()).find(t =>
                        t.includes('United States') || t.includes('Remote') ||
                        /,\\s*[A-Z]{2}$/.test(t)
                    ) || 'United States';
                    const salary = Array.from(card.querySelectorAll('*')).map(e => e.innerText)
                        .find(t => t.includes('$') && (t.includes('/yr') || t.includes('K/yr') || t.includes('/year'))) || '';
                    return {
                        href: card.getAttribute('href') || '',
                        title: h2 ? h2.innerText.trim() : '',
                        company: companyEl ? companyEl.innerText.trim().split('\\n')[0] : '',
                        location: loc,
                        date: timeEl ? timeEl.innerText.trim() : 'today',
                        salary: salary.trim().substring(0, 80),
                        innerText: card.innerText.substring(0, 400),
                    };
                });
            }""")
        except Exception as e:
            print(f"    [Jobright] JS evaluate failed: {e}")
            return 0

        print(f"    [Jobright DEBUG] Found {len(js_data)} raw cards via JS")

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
                    lines = [l.strip() for l in inner.split('\\n') if l.strip()]
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
                    "description": f"JobRight AI: {title} at {company} — {loc}",
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
'''

code = code[:start_i] + new_method + code[end_i:]

with open('job_discovery.py', 'w', encoding='utf-8') as f:
    f.write(code)
print(f"Replaced _process_jobright_page with JS evaluate version. New length: {len(code)}")
