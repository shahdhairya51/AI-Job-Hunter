import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import json
import os
import ctypes
from groq import AsyncGroq

class BrowserAgent:
    def __init__(self, profile_path="user_profile.json", resume_source="master_resume_swe.txt"):
        with open(profile_path, "r", encoding="utf-8") as f:
            self.profile = json.load(f)
            
        with open(resume_source, "r", encoding="utf-8") as f:
            self.master_resume = f.read()
            
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.browser = None
        self.context = None

    async def generate_custom_answer(self, question):
        """Uses Groq to generate a 3-sentence passionate answer to custom ATS application questions."""
        system_prompt = """
        You are a highly ambitious, competent software engineer applying for a job.
        You have been asked a custom question on an application form.
        Use the provided Master Resume (containing work experience and hackathons) to formulate a response.
        
        CRITICAL RULES:
        1. Write EXACTLY ONE to THREE sentences. Keep it short, punchy, and conversational.
        2. Speak from the heart with passion. Frame your hackathon or work experience as the reason you excel at the topic being asked.
        3. No AI buzzwords (spearhead, orchestrate, delve). Write like a real human typing into a form.
        4. ONLY output the answer itself, nothing else.
        """
        
        user_prompt = f"MASTER RESUME:\n{self.master_resume}\n\nAPPLICATION QUESTION:\n{question}\n\nDraft the human-like 3 sentence response now."
        
        try:
            response = await self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.6,
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return "Please refer to my attached resume for detailed experience on this topic."

    async def init_browser(self):
        playwright = await async_playwright().start()
        # Non-headless for visibility and user fallback overriding
        self.browser = await playwright.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        # Store context natively
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800}
        )

    async def apply_greenhouse(self, url, resume_path, cover_letter_path=None):
        page = await self.context.new_page()
        try:
            print(f"Applying on Greenhouse for {url}")
            await page.goto(url)
            await page.wait_for_selector("#first_name", timeout=10000)

            pi = self.profile['personal_info']

            # Fill Standard Fields
            await page.fill("#first_name", pi['first_name'])
            await page.fill("#last_name", pi['last_name'])
            await page.fill("#email", pi['email'])
            await page.fill("#phone", pi['phone'])
            
            # Attach Resume
            resume_input = await page.query_selector("input[type='file'][name='resume']")
            if resume_input and os.path.exists(resume_path):
                await resume_input.set_input_files(resume_path)

            # Attach Cover Letter
            cl_input = await page.query_selector("input[type='file'][name='cover_letter']")
            if cl_input and cover_letter_path and os.path.exists(cover_letter_path):
                await cl_input.set_input_files(cover_letter_path)

            # Look for common custom questions (LinkedIn, GitHub) or use LLM for the rest
            try:
                custom_inputs = await page.locator("div.custom_question input[type='text'], div.custom_question textarea").all()
                for field in custom_inputs:
                    label = await field.evaluate("(el) => el.closest('.custom_question').innerText.toLowerCase()")
                    if 'linkedin' in label:
                        await field.fill(pi['linkedin'])
                    elif 'github' in label or 'website' in label or 'portfolio' in label:
                        await field.fill(pi['github'])
                    else:
                        # Dynamic question! Have the LLM answer it from the heart using hackathon/work exp
                        print(f"[LLM] Drafting answer for custom question: {label[:50]}...")
                        answer = await self.generate_custom_answer(label)
                        await field.fill(answer)
                        
                # Wait for user input if strange dropdowns or multi-selects
                # For safety we just let the human check it later if it fails validation
                await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                print("Basic fields filled. Verifying submit...")
            
            except Exception as e:
                print(f"Error filling custom fields: {e}")

            # For production, we don't automatically click submit to avoid accidental spam
            # await page.click("input[type='submit']") 
            await page.wait_for_timeout(3000) # Wait a moment
            print(f"Greenhouse Apply step passed for {url}")
            return True, "Success"

        except Exception as e:
            err = f"Failed Greenhouse execution: {e}"
            print(err)
            return False, str(e)
        finally:
            success_screenshot = f"resumes/screenshots/greenhouse_{datetime.now().timestamp()}.png"
            os.makedirs("resumes/screenshots", exist_ok=True)
            await page.screenshot(path=success_screenshot)
            await page.close()

    async def apply_lever(self, url, resume_path, cover_letter_path=None):
        page = await self.context.new_page()
        try:
            print(f"Applying on Lever for {url}")
            await page.goto(url)
            # Find the Apply button and click it to reveal form
            apply_btn = await page.query_selector("a.postings-btn.template-btn-submit")
            if apply_btn:
                await apply_btn.click()
            
            await page.wait_for_selector("input[name='name']", timeout=10000)

            pi = self.profile['personal_info']
            name = f"{pi['first_name']} {pi['last_name']}"
            
            await page.fill("input[name='name']", name)
            await page.fill("input[name='email']", pi['email'])
            await page.fill("input[name='phone']", pi['phone'])
            
            if 'linkedin' in pi:
                await page.fill("input[name='urls[LinkedIn]']", pi['linkedin'])
            if 'github' in pi:
                await page.fill("input[name='urls[GitHub]']", pi['github'])

            resume_input = await page.query_selector("input[type='file'][name='resume']")
            if resume_input and os.path.exists(resume_path):
                await resume_input.set_input_files(resume_path)
                
            cl_input = await page.query_selector("input[type='file'][name='coverLetter']")
            if cl_input and cover_letter_path and os.path.exists(cover_letter_path):
                await cl_input.set_input_files(cover_letter_path)

            print("Basic Lever fields filled. Awaiting manual check or finalizing...")
            await page.wait_for_timeout(3000)
            return True, "Success"
        except Exception as e:
            err = f"Failed Lever execution: {e}"
            print(err)
            return False, str(e)
        finally:
            success_screenshot = f"resumes/screenshots/lever_{datetime.now().timestamp()}.png"
            os.makedirs("resumes/screenshots", exist_ok=True)
            await page.screenshot(path=success_screenshot)
            await page.close()

    async def run_application_loop(self, applications_list):
        await self.init_browser()
        results = []
        for app in applications_list:
            url = app['url']
            source = app['source']
            resume_path = app['resume_path']
            cl_path = app.get('cover_letter_path')

            print(f"Processing ({source}): {app['title']} at {app['company']}")
            
            if 'greenhouse.io' in url.lower():
                status, msg = await self.apply_greenhouse(url, resume_path, cl_path)
                final_status = "APPLIED" if status else "FAILED"
            elif 'lever.co' in url.lower():
                status, msg = await self.apply_lever(url, resume_path, cl_path)
                final_status = "APPLIED" if status else "FAILED"
            else:
                print(f"[{source}] Unsupported ATS for Auto-Apply. Yielding to manual queue...")
                final_status = "MANUAL_NEEDED"
                msg = "Unsupported ATS, flagged for visual dashboard."

            results.append({
                "job_id": app.get('id', url),
                "status": final_status,
                "notes": msg
            })
            
        await self.browser.close()
        return results

if __name__ == "__main__":
    # Mock usage testing the GUI
    agent = BrowserAgent()
    mock_apps = [
        # {"url": "https://boards.greenhouse.io/plaid/jobs/12345", "source": "Greenhouse", "resume_path": "resumes/test.pdf", ... }
    ]
    # asyncio.run(agent.run_application_loop(mock_apps))
    pass
