"""
Debug script to test Jobright parsed JSON against the JobDiscovery filtering pipeline.
"""
import sys, os, asyncio
sys.path.insert(0, os.getcwd())
from job_discovery import JobDiscovery

async def test():
    # Instantiate EXACTLY like Run 4
    jd = JobDiscovery(hours_back=24)
    print(f"Cutoff enforced: {jd.cutoff}")
    
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context('playwright_profile', headless=False)
        page = await ctx.new_page()
        await page.goto("https://jobright.ai/jobs/search?value=Software+Engineer+Entry+Level&experienceLevel=Entry+Level&country=US&daysAgo=1")
        await page.wait_for_timeout(6000)
        
        js = """() => {
            const cards = Array.from(document.querySelectorAll('a[href*="/jobs/info/"]'));
            return cards.map(card => {
                const h2 = card.querySelector('h2') || card.querySelector('h3');
                const companyEl = card.querySelector('[class*="company-name"]') || card.querySelector('[class*="company"]');
                const timeEl = card.querySelector('[class*="publish-time"]') || card.querySelector('[class*="time"]');
                const metaEls = Array.from(card.querySelectorAll('[class*="job-metadata-item"]'));
                const loc = metaEls.map(e => e.innerText ? e.innerText.trim() : '').find(t =>
                    t.includes('United States') || t.includes('Remote') || /,\\s*[A-Z]{2}$/.test(t)
                ) || 'United States';
                return {
                    title: h2 && h2.innerText ? h2.innerText.trim() : '',
                    company: companyEl && companyEl.innerText ? companyEl.innerText.trim().split('\\n')[0] : '',
                    location: loc,
                    date: timeEl && timeEl.innerText ? timeEl.innerText.trim() : 'today',
                };
            });
        }"""
        
        res = await page.evaluate(js)
        print(f"Extracted {len(res)} cards using JS.")
        
        # Test filtering
        kept = 0
        for i, item in enumerate(res):
            t = item.get('title','')
            c = item.get('company','')
            d = item.get('date', '')
            
            # Simulated filter
            if not jd._is_role_match(t):
                print(f"[{i}] DROP (Role): {t}")
                continue
                
            posted_dt = jd._parse_date_to_dt(d)
            if posted_dt and posted_dt < jd.cutoff:
                print(f"[{i}] DROP (Date {d}): {t} at {c} (Parsed: {posted_dt} < Cutoff: {jd.cutoff})")
                continue
                
            print(f"[{i}] KEEP: {t} at {c} (Date: {d} -> {posted_dt})")
            kept += 1
            
        print(f"\\nFINAL: Kept {kept} / {len(res)}")
        await ctx.close()

asyncio.run(test())
