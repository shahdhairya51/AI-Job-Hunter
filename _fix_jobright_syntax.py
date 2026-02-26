"""
Definitive fix for Jobright Playwright JS evaluation.
The Playwright JS engine occasionally chokes on multi-line Python strings 
because of hidden tabs/newlines. We minify the JS into a single safe string.
"""

with open('job_discovery.py', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

old_js_block = '''        try:
            js_data = await page.evaluate("""() => {
                const cards = Array.from(document.querySelectorAll('a[href*="/jobs/info/"]'));
                return cards.map(card => {
                    const h2 = card.querySelector('h2') || card.querySelector('h3');
                    const companyEl = card.querySelector('[class*="company-name"]') ||
                                      card.querySelector('[class*="company"]');
                    const timeEl = card.querySelector('[class*="publish-time"]') ||
                                   card.querySelector('[class*="time"]');
                    const metaEls = Array.from(card.querySelectorAll('[class*="job-metadata-item"]'));
                    const loc = metaEls.map(e => e.innerText ? e.innerText.trim() : '').find(t =>
                        t.includes('United States') || t.includes('Remote') ||
                        /,\\s*[A-Z]{2}$/.test(t)
                    ) || 'United States';
                    const salary = Array.from(card.querySelectorAll('*')).map(e => e.innerText || '')
                        .find(t => t.includes('$') && (t.includes('/yr') || t.includes('K/yr') || t.includes('/year'))) || '';
                    return {
                        href: card.getAttribute('href') || '',
                        title: h2 && h2.innerText ? h2.innerText.trim() : '',
                        company: companyEl && companyEl.innerText ? companyEl.innerText.trim().split('\\n')[0] : '',
                        location: loc,
                        date: timeEl && timeEl.innerText ? timeEl.innerText.trim() : 'today',
                        salary: salary.trim().substring(0, 80),
                        innerText: card.innerText ? card.innerText.substring(0, 400) : '',
                    };
                });
            }""")
        except Exception as e:'''

# Minified into a single robust JS string with NO multi-line breaks or ambiguous escapes
new_js_block = '''        try:
            js_script = "() => { const cards = Array.from(document.querySelectorAll('a[href*=\\"/jobs/info/\\"]')); return cards.map(card => { const h2 = card.querySelector('h2, h3'); const companyEl = card.querySelector('[class*=\\"company\\"]'); const timeEl = card.querySelector('[class*=\\"time\\"]'); const metaEls = Array.from(card.querySelectorAll('[class*=\\"job-metadata-item\\"]')); const loc = metaEls.map(e => e.innerText ? e.innerText.trim() : '').find(t => t.includes('United States') || t.includes('Remote') || /,\\\\s*[A-Z]{2}$/.test(t)) || 'United States'; const salary = Array.from(card.querySelectorAll('*')).map(e => e.innerText || '').find(t => t.includes('$') && (t.includes('/yr') || t.includes('K/yr') || t.includes('/year'))) || ''; return { href: card.getAttribute('href') || '', title: h2 && h2.innerText ? h2.innerText.trim() : '', company: companyEl && companyEl.innerText ? companyEl.innerText.trim().split('\\\\n')[0] : 'Unknown', location: loc, date: timeEl && timeEl.innerText ? timeEl.innerText.trim() : 'today', salary: salary.trim().substring(0, 80), innerText: card.innerText ? card.innerText.substring(0, 400) : '' }; }); }"
            js_data = await page.evaluate(js_script)
        except Exception as e:'''

if old_js_block in code:
    code = code.replace(old_js_block, new_js_block)
    # Remove the debug logging from _debug_jobright_drops if it somehow came back
    code = code.replace('''                if not self._is_role_match(title):
                    print(f"      [Drop] Role Match Failed: {title!r}")
                    continue
                if not self._is_us_location(loc):
                    print(f"      [Drop] Loc Match Failed: {loc!r}")
                    continue
                print(f"      [Keep] MATCHED: {title!r} @ {company!r}")''', 
                '''                if not self._is_role_match(title):
                    continue
                if not self._is_us_location(loc):
                    continue''')
    code = code.replace('''                if not title or len(title) < 3:
                    print(f"      [Drop] Empty Title: {title!r} (Inner Text snippet: {inner[:50]!r}...)")
                    continue''', 
                '''                if not title or len(title) < 3:
                    continue''')
    with open('job_discovery.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("job_discovery.py patched with reliable single-line JS extraction!")
else:
    print("WARN: JS block pattern not found.")
