
"""
Daily Runner v2 — Job Hunter Agent
───────────────────────────────────
Key fixes vs v1:
  1. DEDUP GUARD: skips jobs that already have resume_pdf_path set in DB
     (was re-generating PDFs on every run → Roblox × 8 problem)
  2. --single-job <job_id> flag so dashboard can trigger individual tailoring
  3. Uses new cover_letter PDF method (convert_cover_letter_to_pdf) for proper formatting
  4. Explicit resumes/ directory creation before any PDF writes
  5. Tailor batch limit configurable via --max-tailor (default 20)
"""

import asyncio
import os
import json
import time
import argparse
from job_discovery import JobDiscovery
from local_db_manager import DatabaseManager
from resume_tailor import ResumeTailor
from browser_agent import BrowserAgent
from dotenv import load_dotenv

load_dotenv()

os.makedirs("resumes", exist_ok=True)
os.makedirs("resumes/screenshots", exist_ok=True)


async def tailor_single_job(job: dict, tailor: ResumeTailor, db: DatabaseManager) -> dict | None:
    """
    Tailors resume + cover letter for ONE job.
    Returns the application dict, or None if skipped.
    
    DEDUP RULE: if the DB record already has a non-empty resume_pdf_path
    that points to an existing file, we skip re-generation entirely.
    """
    # ── Dedup guard ──────────────────────────────────────────────────────
    existing_path = job.get("resume_pdf_path", "")
    if existing_path and os.path.exists(str(existing_path)):
        print(f"  [SKIP] Already tailored: {job['company']} — {job['title']}")
        return {
            "id":                job["id"],
            "url":               job["url"],
            "source":            job["source"],
            "title":             job["title"],
            "company":           job["company"],
            "resume_path":       existing_path,
            "cover_letter_path": job.get("cover_letter_pdf_path", ""),
        }

    # ── Safe filename components ──────────────────────────────────────────
    def sanitize(s):
        return "".join(c for c in str(s) if c.isalnum() or c in "_- ").strip()[:40]

    co    = sanitize(job["company"])
    title = sanitize(job["title"])
    ts    = int(time.time())

    resume_path = f"resumes/{co}_{title}_{ts}_resume.pdf"
    cl_path     = f"resumes/{co}_{title}_{ts}_coverletter.pdf"

    try:
        # 1. Tailored resume — auto-selects AI/Data/SWE master resume
        score, clean, track = tailor.generate_tailored_resume(job["title"], job["description"])
        await tailor.convert_markdown_to_pdf(clean, resume_path)
        print(f"    ✓ Resume saved  (ATS {score}/10, track={track}) → {resume_path}")

        # 2. Cover letter
        cl_body = tailor.generate_cover_letter(job["title"], job["company"], job["description"])
        await tailor.convert_cover_letter_to_pdf(cl_body, job["company"], job["title"], cl_path)
        print(f"    ✓ Cover letter saved → {cl_path}")

    except Exception as e:
        print(f"    [ERROR] Tailoring failed for {job['company']}: {e}")
        score       = 0
        resume_path = ""
        cl_path     = ""

    # ── Persist to DB (status stays NEW until applied) ───────────────────
    db.update_application(
        job_id=job["id"],
        status=None,
        resume_path=resume_path,
        cover_letter_path=cl_path,
        ats_score=score,
    )

    return {
        "id":                job["id"],
        "url":               job["url"],
        "source":            job["source"],
        "title":             job["title"],
        "company":           job["company"],
        "resume_path":       resume_path,
        "cover_letter_path": cl_path,
    }


async def main():
    parser = argparse.ArgumentParser(description="Job Hunter Daily Agent")
    parser.add_argument("--hours",       type=float, default=168.0,
                        help="Lookback window in hours (default 168h/7d)")
    parser.add_argument("--skip-apply",  action="store_true",
                        help="Skip the browser application step")
    parser.add_argument("--max-tailor",  type=int, default=20,
                        help="Max jobs to tailor per run (default 20)")
    parser.add_argument("--single-job",  type=str, default=None,
                        help="Tailor + apply a single job by its DB id (used by dashboard)")
    parser.add_argument("--skip-discovery", action="store_true",
                        help="Skip the job discovery step and only process existing new jobs")
    args = parser.parse_args()

    print("=" * 65)
    print("🤖  JOB HUNTER AGENT")
    print(f"    Lookback : {args.hours}h  |  Max tailor: {args.max_tailor}  |  Apply: {not args.skip_apply}")
    print("=" * 65)

    db     = DatabaseManager()
    tailor = ResumeTailor()

    # ── SINGLE-JOB MODE (triggered from dashboard) ───────────────────────
    if args.single_job:
        print(f"\n[SINGLE-JOB MODE] job_id = {args.single_job}")
        jobs = db.get_job_by_id(args.single_job)
        if not jobs:
            print(f"Job {args.single_job} not found in database.")
            return
        app = await tailor_single_job(jobs[0], tailor, db)
        if app and not args.skip_apply:
            agent   = BrowserAgent()
            results = await agent.run_application_loop([app])
            for res in results:
                db.update_application(job_id=res["job_id"], status=res["status"], notes=res["notes"])
                print(f"  {res['job_id'][:40]} → {res['status']}: {res['notes']}")
        return

    # ── STEP 1: Discovery ─────────────────────────────────────────────────
    if not args.skip_discovery:
        print(f"\n[STEP 1] Job Discovery (last {args.hours}h)...")
        discoverer = JobDiscovery()
        # Pass db so LinkedIn/Jobright flush jobs immediately — no data loss on Ctrl+C
        jobs       = await discoverer.run_discovery(lookback_hours=args.hours, db=db)

        if not jobs:
            print("No jobs found. Exiting.")
            return

        # ── STEP 2: Sync to DB ────────────────────────────────────────────────
        print(f"\n[STEP 2] Syncing {len(jobs)} discovered jobs to DB...")
        new_inserts = sum(1 for job in jobs if db.insert_raw_job(job))
    else:
        print("\n[STEP 1 & 2] Skipped discovery phase. Proceeding to Tailoring.")
        new_inserts = 0
    print(f"  → {new_inserts} new jobs inserted.")

    # ── Fetch NEW jobs that need tailoring ───────────────────────────────
    # get_new_applications() should return only jobs where:
    #   status = 'NEW'  AND  (resume_pdf_path IS NULL OR resume_pdf_path = '')
    new_jobs = db.get_new_applications()

    if not new_jobs:
        print("No new un-tailored jobs to process. Done.")
        return

    # ── STEP 3: Tailor (with dedup built into tailor_single_job) ─────────
    batch         = new_jobs[: args.max_tailor]
    print(f"\n[STEP 3] Tailoring {len(batch)} jobs (of {len(new_jobs)} pending)...")

    applications_queue = []
    for job in batch:
        print(f"\n  → {job['company']} — {job['title']}")
        app = await tailor_single_job(job, tailor, db)
        if app and app.get("resume_path"):
            applications_queue.append(app)

    # ── STEP 4: Apply ─────────────────────────────────────────────────────
    if not args.skip_apply and applications_queue:
        print(f"\n[STEP 4] Submitting {len(applications_queue)} applications via Playwright...")
        agent   = BrowserAgent()
        results = await agent.run_application_loop(applications_queue)

        print("\n" + "=" * 65)
        print("STATUS REPORT:")
        for res in results:
            print(f"  {str(res['job_id'])[:45]:<45} → {res['status']}: {res['notes']}")
            db.update_application(job_id=res["job_id"], status=res["status"], notes=res["notes"])
        print("=" * 65)

        print("\n[STEP 4] Skipped (--skip-apply). All resumes/CLs generated.")
        print("=" * 65)
        print("PREVIEW MODE COMPLETE")
        print("=" * 65)

    # ── STEP 5: Auto-Sync to GitHub (for Live Dashboard) ──────────────────
    print("\n[STEP 5] Auto-syncing database to GitHub...")
    try:
        # We use subprocess to run the git commands quietly
        import subprocess
        
        # Add the database file
        subprocess.run(["git", "add", "applications.db"], check=True, capture_output=True)
        subprocess.run(["git", "add", "jobs_found.json"], check=False, capture_output=True)
        
        # Commit with a skip-ci message (optional, but good practice)
        subprocess.run(["git", "commit", "-m", "Auto-update database [skip ci]"], check=False, capture_output=True)
        
        # Push to main
        push_result = subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True, text=True)
        
        print("  ✓ Successfully pushed database to GitHub!")
        print("  → Your Streamlit live dashboard will update automatically in a few seconds.")
    except Exception as e:
        print(f"  [WARNING] Failed to auto-sync to GitHub: {e}")
        print("  Is your Git branch set up correctly with a remote origin?")

if __name__ == "__main__":
    asyncio.run(main())