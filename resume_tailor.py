
"""
ResumeTailor v3 — Dhairya Shah
═══════════════════════════════════════════════════════════════
THREE-RESUME ROUTING:
  AI/ML jobs   → master_resume_ai.txt   (AI Engineer resume)
  Data jobs    → master_resume_data.txt (Data Analyst resume)
  SWE/Default  → master_resume_swe.txt  (Amazon SDE resume)

RESEARCH-BACKED ATS (2025 studies):
  - Job title mirroring → 10.6x interview rate (Jobscan 2025)
  - Keyword in 3 zones: Summary + Skills + Bullets
  - Selective acronym handling: full-form only for niche terms, once on first mention
  - Problem → Solution → Impact bullet format (reads naturally to humans)
  - No keyword stuffing (NLP-based ATS will flag it)
  - Strong past-tense action verbs only

PDF FORMAT matches uploaded resume visually:
  - Single-column only (ATS-safe)
  - Contact in body, not header (25% ATS parse failure in headers)
  - Arial 10pt, section dividers, role+date on same row
═══════════════════════════════════════════════════════════════
"""

import os
import re
import json
import asyncio
import markdown
from datetime import datetime
from playwright.async_api import async_playwright
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# JOB CLASSIFICATION — which master resume to use
# ─────────────────────────────────────────────────────────────────────────────
AI_KEYWORDS = [
    "machine learning", "ml engineer", "ai engineer", "deep learning",
    "llm", "nlp", "natural language", "computer vision", "generative ai",
    "gen ai", "pytorch", "tensorflow", "hugging face", "rag",
    "fine-tun", "langchain", "vector", "embeddings", "model training",
    "data science", "research engineer", "applied scientist",
    "reinforcement learning", "diffusion", "transformer", "mlops",
    "sagemaker", "model deployment", "inference", "quantization",
]

DATA_KEYWORDS = [
    "data analyst", "data engineer", "analytics engineer", "bi engineer",
    "business intelligence", "business analyst", "tableau", "power bi",
    "looker", "data pipeline", "data warehouse", "redshift", "bigquery",
    "dbt", "airflow analyst", "etl", "cohort analysis", "reporting",
    "dashboard", "data visualization", "product analyst", "growth analyst",
    "a/b test", "sql analyst", "kpi", "metrics analyst",
]


def _classify_job(title: str, description: str) -> str:
    text       = (title + " " + description[:1500]).lower()
    ai_score   = sum(1 for kw in AI_KEYWORDS   if kw in text)
    data_score = sum(1 for kw in DATA_KEYWORDS if kw in text)
    if ai_score >= 2 and ai_score >= data_score:
        return "ai"
    if data_score >= 2 and data_score > ai_score:
        return "data"
    return "swe"


# ─────────────────────────────────────────────────────────────────────────────
# STATIC HTML BLOCKS (education, achievements — LLM never touches these)
# ─────────────────────────────────────────────────────────────────────────────
EDUCATION_HTML = """
<div class="section">
  <div class="section-title">EDUCATION</div>
  <table class="etable"><tr>
    <td><b>The George Washington University</b>, Washington DC &nbsp;&mdash;&nbsp;
        M.S. Computer Science &nbsp;<i>(GPA: 4.0/4.0)</i></td>
    <td class="dates">Aug 2024 &ndash; May 2026</td>
  </tr></table>
  <div class="sub">Teaching Assistant: Machine Learning I &amp; II
  (Deep Learning, NLP, Statistical Learning, Neural Networks)</div>
  <table class="etable" style="margin-top:5px"><tr>
    <td><b>University of Mumbai</b> &nbsp;&mdash;&nbsp;
        B.Tech Information Technology, Honors AI &amp; ML &nbsp;<i>(GPA: 3.9/4.0)</i></td>
    <td class="dates">Jul 2020 &ndash; May 2024</td>
  </tr></table>
</div>
"""

ACHIEVEMENTS_HTML = """
<div class="section">
  <div class="section-title">LEADERSHIP &amp; ACHIEVEMENTS</div>
  <div class="plain">
    Winner, United Nations Tech Over Hackathon 2025 &nbsp;&middot;&nbsp;
    Winner, George Hacks 2025 &nbsp;&middot;&nbsp;
    1<sup>st</sup> Runner Up, IIT Bombay Techfest 2023 &nbsp;&middot;&nbsp;
    INTECH 2022 &nbsp;&middot;&nbsp;
    Top 20 Open Source Contributor, Winter of Code 2.0
  </div>
</div>
"""

# ─────────────────────────────────────────────────────────────────────────────
# CSS — single-column, ATS-safe, matches actual resume PDFs
# ─────────────────────────────────────────────────────────────────────────────
RESUME_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Arial', sans-serif;
  font-size: 9.8pt;
  line-height: 1.35;
  color: #000;
  padding: 0.42in 0.5in 0.38in 0.5in;
}
.name {
  font-size: 16.5pt; font-weight: 700; text-align: center;
  letter-spacing: 0.03em; margin-bottom: 2px;
}
.contact {
  text-align: center; font-size: 8.4pt; color: #111; margin-bottom: 9px;
}
.contact a { color: #000; text-decoration: none; }
.section { margin-bottom: 7px; }
.section-title {
  font-size: 9.8pt; font-weight: 700; text-transform: uppercase;
  border-bottom: 1.1px solid #000; padding-bottom: 1px;
  margin-bottom: 4px; letter-spacing: 0.07em;
}
.etable, .rtable { width: 100%; border-collapse: collapse; }
.etable td, .rtable td { vertical-align: top; padding: 0; }
.dates {
  text-align: right; white-space: nowrap; font-size: 8.9pt;
  padding-left: 5px; min-width: 105px;
}
.role { font-weight: 700; font-size: 9.8pt; }
.co   { font-style: italic; font-size: 9.1pt; }
.sub  { font-size: 8.9pt; color: #222; margin-top: 1px; margin-bottom: 1px; margin-left: 2px; }
.plain { font-size: 9pt; }
ul { margin: 2px 0 4px 14px; padding: 0; }
li { font-size: 9.1pt; margin-bottom: 2px; line-height: 1.32; }
.skill-row { margin-bottom: 1.5px; font-size: 9.1pt; }
p { font-size: 9.1pt; margin-bottom: 3px; }
@page { size: letter; margin: 0; }
"""


class ResumeTailor:
    def __init__(self, profile_path="user_profile.json"):
        self.primary_key  = os.getenv("GROQ_API_KEY", "")
        self.fallback_key = os.getenv("GROQ_API_KEY_FALLBACK", self.primary_key)
        self.client       = Groq(api_key=self.primary_key)

        with open(profile_path, "r", encoding="utf-8") as f:
            self.profile = json.load(f)
        self.personal = self.profile.get("personal_info", {})

        # Load all 3 master resumes
        self.resumes = {
            "ai":   self._load_file("master_resume_ai.txt"),
            "data": self._load_file("master_resume_data.txt"),
            "swe":  self._load_file("master_resume_swe.txt"),
        }
        os.makedirs("resumes", exist_ok=True)

    def _load_file(self, path: str) -> str:
        for p in [path, "master_resume_swe.txt", "master_resume.txt"]:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    if p != path:
                        print(f"  [WARN] {path} not found, falling back to {p}")
                    return f.read()
        return ""

    def _get_master(self, title: str, description: str) -> tuple[str, str]:
        track  = _classify_job(title, description)
        master = self.resumes.get(track) or self.resumes["swe"]
        return master, track

    # ── Groq with key rotation ──────────────────────────────────────────────
    def _call_groq(self, system_prompt, user_prompt, temperature=0.3, max_tokens=2400):
        for key, label in [(self.primary_key, "primary"), (self.fallback_key, "fallback")]:
            try:
                client = Groq(api_key=key)
                return client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    print(f"   [!] Groq {label} rate-limited, trying next key...")
                    continue
                raise
        raise RuntimeError("Both Groq keys exhausted")

    # ── Main: generate tailored resume ──────────────────────────────────────
    def generate_tailored_resume(self, job_title: str, job_desc: str) -> tuple[int, str, str]:
        """Returns (ats_score, clean_markdown, track)"""
        master, track = self._get_master(job_title, job_desc)
        track_label   = {"ai": "AI Engineer", "data": "Data Analyst", "swe": "SWE"}[track]
        print(f"  [Tailor] {track_label.upper()} track | {job_title}")

        SYSTEM = f"""You are an elite ATS Resume Optimization Specialist.
Task: Rewrite this candidate's resume bullets to perfectly match the job description.

════════════════════════════════════════════════════
ATS RULES — 2025 RECRUITER DATA (follow all of these)
════════════════════════════════════════════════════

RULE 1 — JOB TITLE MIRRORING (10.6x interview rate per Jobscan 2025 study)
The exact job title from the JD MUST appear in the Professional Summary.
Use the precise wording from the posting, not your own variation.

RULE 2 — KEYWORD ZONES (ATS weights keywords by location)
Place important JD keywords in ALL THREE zones:
  Zone A: Professional Summary → broad positioning
  Zone B: Technical Skills section → searchable category list
  Zone C: Bullet points → contextual proof of skill

RULE 3 — ACRONYM HANDLING (selective, not universal)
Only introduce long-form for terms that older ATS may not recognize (niche certifications,
domain-specific abbreviations). Common tech terms (API, SQL, CI/CD, AWS, ML) are fine as-is.
For ambiguous terms: write full form ONCE on first mention, then acronym freely after.
Example: "Retrieval-Augmented Generation (RAG) pipeline... later references just say RAG."
Do NOT write long-form for: Python, AWS, SQL, Docker, REST, API, CI/CD, ML, AI, GPU, ETL —
these are universally recognized by modern ATS and human readers.

RULE 4 — PROBLEM → SOLUTION → IMPACT BULLET FORMAT
Every bullet must tell a mini-story in this order:
  [What was broken / what was needed] → [what you specifically built or did] → [measurable result]

This is not a template to fill in mechanically. Write it as ONE natural, confident sentence.
The problem can be implicit (e.g. "to handle 500K daily events") — it doesn't need to be spelled out
if it's obvious from the solution. The impact MUST always be explicit with a number or scope.

Good example: "Designed a real-time anomaly detection system using PyTorch autoencoders to catch
fraudulent transactions in a 500K+ daily event stream, reducing false positives by 30%."

Good example: "Replaced a brittle monolithic ETL job with an Airflow-orchestrated pipeline,
cutting data processing time from 4 hours to under 20 minutes for 5,000+ active users."

Bad: "Responsible for building anomaly detection system that helped reduce issues."
Bad: "Worked on ETL pipeline using Airflow." (no problem, no impact)
Bad: "Leveraged PyTorch to build an amazing anomaly detection solution." (buzzword, vague)

BANNED openers: "Responsible for", "Worked on", "Helped", "Assisted", "Was in charge of"
BANNED words: "leveraged", "utilized", "spearheaded", "synergized", "orchestrated", "thrilled",
"amazing", "innovative", "cutting-edge", "dynamic", "passionate", "transformative", "robust",
"seamlessly", "world-class", "best-in-class", "groundbreaking"
BANNED formatting — these make it look AI-generated to any human reader:
- No emojis or symbols anywhere (no rocket ships, checkmarks, arrows, stars, diamonds, dots)
- No hyphens (-) as bullet starters — the markdown list handles bullets, just write the sentence
- No em-dashes (—) used as a stylistic mid-sentence flourish — use a comma or period instead
- No bold or italic formatting inside bullets — plain prose only
- No colons at the end of a bullet introducing sub-points

Action verbs to rotate (pick the most accurate, not the most impressive-sounding):
Built, Designed, Engineered, Implemented, Deployed, Optimized, Automated, Migrated, Refactored,
Reduced, Scaled, Trained, Fine-tuned, Integrated, Replaced, Rewrote, Accelerated, Resolved.

RULE 5 — METRICS IN EVERY BULLET
Preserve ALL numbers from master resume (%, ms, users, records).
Never invent metrics not present in the original.
For bullets without numbers, use scope: "across 5 production services", "for 3M+ data points"

RULE 6 — KEYWORD EXTRACTION CHECKLIST (extract from JD before writing):
✓ Programming languages  ✓ Frameworks & libraries  ✓ Cloud services (specific, not just "AWS")
✓ Databases & stores     ✓ Tools & platforms        ✓ Methodologies (Agile, TDD, etc.)
✓ Domain terms (microservices, event-driven, distributed, etc.)

RULE 7 — NO KEYWORD STUFFING
Modern ATS uses NLP. Unnatural keyword lists lower your score. Each keyword must appear
in context within a real sentence.

RULE 8 — HONEST BRIDGING ONLY
Related tech is fine: "Flask background with exposure to FastAPI async patterns"
Invented experience is not acceptable under any circumstances.

════════════════════════════════════════════════════
OUTPUT FORMAT — return EXACTLY this, nothing else:
════════════════════════════════════════════════════

## SUMMARY
[2-3 sentence professional summary. Include: exact job title from JD, 2-3 top JD keywords,
one concrete strength or achievement. No "I". Example:
"Results-driven {track_label} with hands-on experience in [top JD tech]. At Empyron Solutions,
[specific achievement with metric]. Adept at [second top JD skill] and [third]."]

## EXPERIENCE

### [Exact Job Title you held] | [Company Name] | [Start Date – End Date]
- [Problem→Solution→Impact: one natural sentence, past tense, ends with metric]
- [Problem→Solution→Impact: one natural sentence, past tense, ends with metric]
- [Problem→Solution→Impact: one natural sentence, past tense, ends with metric]
- [3-5 bullets per role — never fewer than 3]

[Repeat for each role — include ALL roles from master resume, no dropping]

## PROJECTS

### [Project Name] | [Tech stack] | [Date or Award]
- [Problem→Solution→Impact bullet]
- [Problem→Solution→Impact bullet]
- [2-3 bullets per project]

[Include ALL projects from master resume]

## TECHNICAL SKILLS
**[Logical Category e.g. Languages]:** skill1, Skill Two (ST), skill3
**[Category]:** ...
**[Category]:** ...
**Certifications:** AWS Machine Learning Engineer Associate

[ATS_SCORE: X/10]
Score rubric: keyword match density 40% + metric inclusion 30% + verb quality 20% + completeness 10%
Be honest. 7-8 = good tailoring. 9 = excellent. 10 = near-perfect match.

CANDIDATE TRACK: {track_label}"""

        USER = f"""MASTER RESUME ({track_label} track):
{master}

═══════════════════════════════════
TARGET JOB TITLE: {job_title}
═══════════════════════════════════
JOB DESCRIPTION:
{job_desc[:3000]}

Generate the tailored resume now. Remember to:
1. Mirror job title "{job_title}" in Summary
2. Acronyms: spell out niche terms ONCE on first mention only, skip for common ones (Python, AWS, API, SQL, ML)
3. Every bullet = Problem → Solution → Impact, one natural sentence with a real metric
4. Keywords woven into Summary, Skills, and Bullets naturally — no keyword dumping
"""
        resp = self._call_groq(SYSTEM, USER, temperature=0.3, max_tokens=2400)
        raw  = resp.choices[0].message.content
        score, clean = self.parse_score(raw)
        return score, clean, track

    # ── Cover letter generation ─────────────────────────────────────────────
    def generate_cover_letter(self, job_title: str, company: str, job_desc: str) -> str:
        master, _ = self._get_master(job_title, job_desc)

        SYSTEM = """Write a cover letter body for a software/AI/data engineer applying to a tech company.

OUTPUT: Exactly 3 paragraphs. No salutation. No sign-off. No headers.

Para 1 (2-3 sentences): Company-specific hook. Reference something REAL and specific from the JD
— their tech stack, product challenge, or mission. Show you read the posting.

Para 2 (3-4 sentences): Your strongest match. Name specific technology + the measurable outcome.
Map it directly to what this role needs. One or two experiences, not a laundry list.

Para 3 (1-2 sentences): Confident forward close. What specifically you'd contribute.

HARD RULES:
- Max 170 words total
- BANNED words: "thrilled", "passionate about", "leverage", "spearhead", "delve", "orchestrate",
  "aligns perfectly", "dynamic team", "fast-paced environment", "I am writing to apply",
  "transformative", "robust", "seamlessly", "innovative", "cutting-edge"
- BANNED formatting: no emojis, no hyphens as starters, no em-dashes for style, no bold/italic
- No invented statistics
- Write like a real competent engineer typing into a form, not a cover letter template"""

        USER = f"""MY BACKGROUND:
{master[:2000]}

COMPANY: {company}
ROLE: {job_title}
JD: {job_desc[:1500]}

Write the 3-paragraph body now."""

        resp = self._call_groq(SYSTEM, USER, temperature=0.6, max_tokens=350)
        return resp.choices[0].message.content.strip()

    # ── Parse ATS score from LLM output ────────────────────────────────────
    def parse_score(self, content: str) -> tuple[int, str]:
        marker = "[ATS_SCORE:"
        if marker in content:
            idx   = content.rfind(marker)
            raw   = content[idx + len(marker):].split("]")[0].split("/")[0].strip()
            clean = content[:idx].strip()
            try:
                return int(raw), clean
            except ValueError:
                return 8, clean
        return 8, content.strip()

    # ── RESUME PDF ──────────────────────────────────────────────────────────
    async def convert_markdown_to_pdf(self, md_text: str, output_path: str):
        pi        = self.personal
        full_name = f"{pi.get('first_name','')} {pi.get('last_name','')}".strip()

        c_parts = []
        if pi.get("address"):  c_parts.append(pi["address"])
        if pi.get("phone"):    c_parts.append(pi["phone"])
        if pi.get("email"):    c_parts.append(f'<a href="mailto:{pi["email"]}">{pi["email"]}</a>')
        if pi.get("linkedin"): c_parts.append(f'<a href="{pi["linkedin"]}">{pi["linkedin"].replace("https://","")}</a>')
        if pi.get("github"):   c_parts.append(f'<a href="{pi["github"]}">{pi["github"].replace("https://","")}</a>')
        contact = " &nbsp;|&nbsp; ".join(c_parts)

        body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])

        # h3: "Role | Company | Dates" → proper two-column table row
        def h3_to_row(m):
            parts = [p.strip() for p in m.group(1).split("|")]
            if len(parts) >= 3:
                role, co = parts[0], parts[1]
                dates    = " | ".join(parts[2:])
                return (f'<table class="rtable"><tr>'
                        f'<td><span class="role">{role}</span>'
                        f' &nbsp;|&nbsp; <span class="co">{co}</span></td>'
                        f'<td class="dates">{dates}</td></tr></table>')
            elif len(parts) == 2:
                return (f'<table class="rtable"><tr>'
                        f'<td><span class="role">{parts[0]}</span></td>'
                        f'<td class="dates">{parts[1]}</td></tr></table>')
            return f'<div class="role">{m.group(1)}</div>'

        body = re.sub(r'<h3>(.*?)</h3>', h3_to_row, body)
        body = re.sub(r'<h2>(.*?)</h2>',
                      r'<div class="section"><div class="section-title">\1</div>', body)
        # Close the section divs — approximate: insert before each new section-title
        body = re.sub(r'(<div class="section"><div class="section-title">(?!SUMMARY))',
                      r'</div>\1', body, count=10)
        body = re.sub(r'<p><strong>(.*?):</strong>(.*?)</p>',
                      r'<div class="skill-row"><strong>\1:</strong>\2</div>', body)

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>{RESUME_CSS}</style></head><body>
<div class="name">{full_name}</div>
<div class="contact">{contact}</div>
{EDUCATION_HTML}
{body}
{ACHIEVEMENTS_HTML}
</body></html>"""

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        async with async_playwright() as p:
            br   = await p.chromium.launch(headless=True)
            page = await br.new_page()
            await page.set_content(html, wait_until="networkidle")
            await page.pdf(path=output_path, format="Letter",
                           margin={"top":"0in","right":"0in","bottom":"0in","left":"0in"},
                           print_background=True)
            await br.close()
        print(f"  [PDF] Resume saved → {output_path}")

    # ── COVER LETTER PDF ────────────────────────────────────────────────────
    async def convert_cover_letter_to_pdf(self, body_text: str, company: str,
                                           job_title: str, output_path: str):
        pi        = self.personal
        full_name = f"{pi.get('first_name','')} {pi.get('last_name','')}".strip()
        today     = datetime.now().strftime("%B %d, %Y")
        paras     = [p.strip() for p in body_text.split("\n\n") if p.strip()]
        body_html = "\n".join(f"<p>{para}</p>" for para in paras)

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: Arial, sans-serif; font-size: 10.5pt;
       line-height: 1.65; color: #000; padding: 0.85in 0.9in; }}
.nm {{ font-size: 16pt; font-weight: 700; margin-bottom: 3px; }}
.ct {{ font-size: 9pt; color: #333; margin-bottom: 18px; }}
.ct a {{ color: #000; text-decoration: none; }}
hr {{ border: none; border-top: 1.5px solid #000; margin-bottom: 16px; }}
.dt {{ margin-bottom: 13px; font-size: 10pt; color: #333; }}
.rc {{ margin-bottom: 16px; }}
.rc .co {{ font-weight: 700; }}
.rc .ro {{ font-size: 9.5pt; color: #444; }}
.sal {{ font-weight: 600; margin-bottom: 13px; }}
p {{ margin-bottom: 13px; text-align: justify; }}
.sf {{ margin-top: 20px; }}
.sg {{ margin-bottom: 30px; }}
.sn {{ font-weight: 700; font-size: 11pt; }}
</style></head><body>
<div class="nm">{full_name}</div>
<div class="ct">
  {pi.get('address','')} &nbsp;|&nbsp; {pi.get('phone','')} &nbsp;|&nbsp;
  <a href="mailto:{pi.get('email','')}">{pi.get('email','')}</a> &nbsp;|&nbsp;
  <a href="{pi.get('linkedin','')}">{pi.get('linkedin','').replace('https://','')}</a>
</div>
<hr>
<div class="dt">{today}</div>
<div class="rc">
  <div class="co">Hiring Team, {company}</div>
  <div class="ro">Re: {job_title}</div>
</div>
<div class="sal">Dear Hiring Team,</div>
{body_html}
<div class="sf">
  <div class="sg">Sincerely,</div>
  <div class="sn">{full_name}</div>
</div>
</body></html>"""

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        async with async_playwright() as p:
            br   = await p.chromium.launch(headless=True)
            page = await br.new_page()
            await page.set_content(html, wait_until="networkidle")
            await page.pdf(path=output_path, format="Letter",
                           margin={"top":"0in","right":"0in","bottom":"0in","left":"0in"},
                           print_background=True)
            await br.close()
        print(f"  [PDF] Cover letter saved → {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tailor = ResumeTailor()
    tests  = [
        ("AI Research Engineer",         "OpenAI",     "PyTorch LLM fine-tuning RLHF RAG LangChain Hugging Face vLLM SageMaker MLOps distributed training inference"),
        ("Data Engineer",                "Databricks",  "Apache Spark dbt Airflow BigQuery SQL Python ETL pipeline data warehouse A/B testing cohort analysis"),
        ("Software Development Engineer","Amazon",      "Java Python distributed systems AWS Lambda DynamoDB S3 REST APIs microservices Kubernetes CI/CD system design"),
    ]
    for title, company, desc in tests:
        print(f"\n{'='*55}\nTesting: {title} @ {company}")
        score, clean, track = tailor.generate_tailored_resume(title, desc)
        print(f"Track={track} | ATS Score={score}/10")
        cl = tailor.generate_cover_letter(title, company, desc)
        asyncio.run(tailor.convert_markdown_to_pdf(clean, f"resumes/test_{track}_resume.pdf"))
        asyncio.run(tailor.convert_cover_letter_to_pdf(cl, company, title, f"resumes/test_{track}_coverletter.pdf"))
    print("\nDone. Check resumes/ folder.")