import asyncio
from playwright.async_api import async_playwright
import os

async def debug_jobright():
    print("--- DEBUGGING JOBRIGHT ---")
    async with async_playwright() as p:
        user_data_dir = os.path.abspath("playwright_profile")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = await context.new_page()
        await page.goto("https://jobright.ai/jobs/recommend")
        print("Waiting for feed...")
        await page.wait_for_timeout(10000)
        
        # Capture some HTML
        html = await page.content()
        with open("jobright_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        # Test selectors
        selectors = ["a[href*='/jobs/']", "article", "[data-testid='job-card']", ".job-card"]
        for sel in selectors:
            count = await page.locator(sel).count()
            print(f"Selector '{sel}' found {count} elements.")
            
        if count > 0:
            sample = await page.locator(selectors[0]).first.inner_text()
            print(f"Sample text from first '{selectors[0]}':\n{sample}")
            
        await context.close()

async def debug_simplify():
    print("\n--- DEBUGGING SIMPLIFY ---")
    async with async_playwright() as p:
        user_data_dir = os.path.abspath("playwright_profile")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = await context.new_page()
        url = "https://simplify.jobs/jobs?query=SOFTWARE%20ENGINEER&state=United%20States&country=United%20States&experience=Entry%20Level%2FNew%20Grad%3BJunior&category=AI%20%26%20Machine%20Learning%3BSoftware%20Engineering%3BData%20%26%20Analytics&h1b=true&jobType=Full-Time&workArrangement=Remote%3BHybrid%3BIn%20Person"
        await page.goto(url)
        await page.wait_for_timeout(10000)
        
        count = await page.locator("div[data-testid='job-card']").count()
        print(f"Simplify: Found {count} job cards.")
        
        if count > 0:
            sample = await page.locator("div[data-testid='job-card']").first.inner_text()
            print(f"Sample Simplify text:\n{sample}")
            
        await context.close()

if __name__ == "__main__":
    asyncio.run(debug_jobright())
    asyncio.run(debug_simplify())
