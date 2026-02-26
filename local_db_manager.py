"""
DatabaseManager — local SQLite tracker for Job Hunter Agent
─────────────────────────────────────────────────────────────
Key fix: get_new_applications() now returns ONLY jobs where
  status = 'NEW'  AND  (resume_pdf_path IS NULL OR resume_pdf_path = '')
This prevents re-tailoring on every run (the duplicate PDF problem).
"""

import sqlite3
import uuid
import os
from datetime import datetime


DB_PATH = os.getenv("JOB_DB_PATH", "applications.db")


class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn    = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cur = self.conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id             TEXT PRIMARY KEY,
                company        TEXT,
                title          TEXT,
                location       TEXT,
                source         TEXT,
                url            TEXT UNIQUE,
                description    TEXT,
                date_posted    TEXT,
                scraped_date   TEXT,
                hiring_manager TEXT,
                salary         TEXT DEFAULT '',
                department     TEXT DEFAULT '',
                sponsorship    TEXT DEFAULT ''
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                job_id              TEXT PRIMARY KEY REFERENCES jobs(id),
                status              TEXT DEFAULT 'NEW',
                ats_score           REAL,
                resume_pdf_path     TEXT DEFAULT '',
                cover_letter_pdf_path TEXT DEFAULT '',
                applied_date        TEXT,
                notes               TEXT DEFAULT ''
            )
        """)

        # Add columns that may be missing in older DBs (safe to run repeatedly)
        for col_def in [
            ("jobs",         "salary",     "TEXT DEFAULT ''"),
            ("jobs",         "department", "TEXT DEFAULT ''"),
            ("jobs",         "sponsorship", "TEXT DEFAULT ''"),
            ("applications", "cover_letter_pdf_path", "TEXT DEFAULT ''"),
        ]:
            try:
                cur.execute(f"ALTER TABLE {col_def[0]} ADD COLUMN {col_def[1]} {col_def[2]}")
            except sqlite3.OperationalError:
                pass   # column already exists

        self.conn.commit()

    # ──────────────────────────────────────────────────────────────────────
    # INSERT
    # ──────────────────────────────────────────────────────────────────────
    def insert_raw_job(self, job: dict) -> bool:
        """
        Insert a discovered job.  Returns True if it was a brand-new insert,
        False if the URL already existed (duplicate).
        """
        job_id = str(uuid.uuid4())
        cur    = self.conn.cursor()

        try:
            cur.execute("""
                INSERT INTO jobs
                    (id, company, title, location, source, url, description,
                     date_posted, scraped_date, hiring_manager, salary, department, sponsorship)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                job_id,
                job.get("company", ""),
                job.get("title",   ""),
                job.get("location",""),
                job.get("source",  ""),
                job.get("url",     ""),
                job.get("description", ""),
                job.get("date",    ""),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                job.get("hiring_manager", ""),
                job.get("salary",  ""),
                job.get("department", ""),
                job.get("sponsorship", ""),
            ))

            # Create a matching application row with status NEW
            cur.execute("""
                INSERT INTO applications (job_id, status)
                VALUES (?, 'NEW')
            """, (job_id,))

            self.conn.commit()
            return True

        except sqlite3.IntegrityError:
            # URL already in DB — not a new job
            return False

    # ──────────────────────────────────────────────────────────────────────
    # QUERY: jobs that NEED tailoring
    # ──────────────────────────────────────────────────────────────────────
    def get_new_applications(self) -> list[dict]:
        """
        Returns jobs where:
          - status = 'NEW'
          - resume_pdf_path is NULL or empty string
          - url is not empty (we need somewhere to apply)

        *** This is the critical fix — previously this returned ALL NEW jobs
            including ones already tailored, causing duplicate PDFs. ***
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT
                j.id, j.company, j.title, j.location, j.source, j.url,
                j.description, j.date_posted, j.hiring_manager, j.salary,
                a.status, a.resume_pdf_path, a.cover_letter_pdf_path, a.ats_score
            FROM jobs j
            JOIN applications a ON j.id = a.job_id
            WHERE
                a.status = 'NEW'
                AND (a.resume_pdf_path IS NULL OR a.resume_pdf_path = '')
                AND j.url != ''
            ORDER BY j.scraped_date DESC
        """)
        return [dict(row) for row in cur.fetchall()]

    # ──────────────────────────────────────────────────────────────────────
    # QUERY: single job by id (used by --single-job CLI flag)
    # ──────────────────────────────────────────────────────────────────────
    def get_job_by_id(self, job_id: str) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT
                j.id, j.company, j.title, j.location, j.source, j.url,
                j.description, j.date_posted, j.hiring_manager, j.salary,
                a.status, a.resume_pdf_path, a.cover_letter_pdf_path, a.ats_score
            FROM jobs j
            LEFT JOIN applications a ON j.id = a.job_id
            WHERE j.id = ?
        """, (job_id,))
        return [dict(row) for row in cur.fetchall()]

    # ──────────────────────────────────────────────────────────────────────
    # UPDATE: application record
    # ──────────────────────────────────────────────────────────────────────
    def update_application(
        self,
        job_id:            str,
        status:            str | None = None,
        resume_path:       str | None = None,
        cover_letter_path: str | None = None,
        ats_score:         float | None = None,
        notes:             str | None = None,
    ):
        cur    = self.conn.cursor()
        fields = []
        values = []

        if status is not None:
            fields.append("status = ?")
            values.append(status)
            if status == "APPLIED":
                fields.append("applied_date = ?")
                values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if resume_path is not None:
            fields.append("resume_pdf_path = ?")
            values.append(resume_path)

        if cover_letter_path is not None:
            fields.append("cover_letter_pdf_path = ?")
            values.append(cover_letter_path)

        if ats_score is not None:
            fields.append("ats_score = ?")
            values.append(ats_score)

        if notes is not None:
            fields.append("notes = ?")
            values.append(notes)

        if not fields:
            return

        values.append(job_id)
        cur.execute(
            f"UPDATE applications SET {', '.join(fields)} WHERE job_id = ?",
            values,
        )

        if cur.rowcount == 0:
            # Row doesn't exist yet — insert it
            cur.execute(
                "INSERT OR IGNORE INTO applications (job_id, status) VALUES (?, 'NEW')",
                (job_id,),
            )
            # Retry update
            cur.execute(
                f"UPDATE applications SET {', '.join(fields[:-0] if status else fields)} WHERE job_id = ?",
                values,
            )

        self.conn.commit()

    # ──────────────────────────────────────────────────────────────────────
    # UTILITY
    # ──────────────────────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT status, COUNT(*) FROM applications GROUP BY status")
        return dict(cur.fetchall())

    def clear_all_data(self):
        """Truncate all data from jobs and applications tables."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM applications")
        cur.execute("DELETE FROM jobs")
        self.conn.commit()

    def close(self):
        self.conn.close()