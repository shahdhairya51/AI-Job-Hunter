import asyncio
from playwright.async_api import async_playwright
import os

async def repair_login():
    print("="*60)
    print("🔧 BROWSER SESSION REPAIR TOOL")
    print("="*60)
    print("Opening browser in HEADED mode...")
    print("1. Log in to JobRight.ai")
    print("2. Log in to Simplify.jobs")
    print("3. Ensure you are on the main feed/jobs page.")
    print("4. Close the browser window when finished to save the session.")
    print("="*60)
    
    async with async_playwright() as p:
        user_data_dir = os.path.abspath("playwright_profile")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=['--disable-blink-features=AutomationControlled'],
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        await page.goto("https://jobright.ai/jobs/recommend")
        
        print("\n[READY] Browser is open. Please complete your logins.")
        print("Waiting for you to close the browser...")
        
        # Keep it open until the user closes it manually
        while True:
            try:
                if context.pages == []: break
                await asyncio.sleep(5)
            except: break
            
        print("\nSession saved. You can now run the discovery agent.")

if __name__ == "__main__":
    asyncio.run(repair_login())
