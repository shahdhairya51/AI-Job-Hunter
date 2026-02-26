"""
Job Hunter AI — Command Center v4
Professional mission-control dashboard for entry-level job hunting.
No emojis. No clutter. Pure productivity.
"""

import sys
import os
import subprocess
import sqlite3
import json
import re
import base64
import timeago
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta
from local_db_manager import DatabaseManager

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Hunter AI",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

DB_PATH = "applications.db"

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg:          #050505;
  --bg1:         #0c0c0c;
  --bg2:         #131313;
  --bg3:         #1a1a1a;
  --border:      #252525;
  --border-hl:   #FF6B00;
  --orange:      #FF6B00;
  --orange-lt:   #FF8C33;
  --orange-dim:  rgba(255,107,0,0.12);
  --green:       #22c55e;
  --red:         #ef4444;
  --yellow:      #eab308;
  --blue:        #3b82f6;
  --purple:      #8b5cf6;
  --text:        #e8e8e8;
  --text2:       #999;
  --text3:       #555;
  --mono:        'JetBrains Mono', monospace;
  --sans:        'Inter', sans-serif;
  --radius:      6px;
  --radius-lg:   10px;
}

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"] {
  font-family: var(--sans) !important;
  background: var(--bg) !important;
  color: var(--text) !important;
}

.stApp { background: var(--bg); }

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="collapsedControl"] { display: none; }
.stDeployButton { display: none; }
section[data-testid="stSidebarNav"] { display: none; }

/* Remove default padding */
.main .block-container {
  padding: 0 !important;
  max-width: 100% !important;
}

/* ── Top Command Bar ── */
.cmd-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 24px;
  background: var(--bg1);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}
.cmd-bar-logo {
  font-size: 0.85rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--orange);
  white-space: nowrap;
  font-family: var(--mono);
  padding-right: 8px;
  border-right: 1px solid var(--border);
}
.cmd-bar-search-wrap { flex: 1; }

/* ── Pills / Chips ── */
.chip-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 24px;
  background: var(--bg1);
  border-bottom: 1px solid var(--border);
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border: 1px solid var(--border);
  background: var(--bg2);
  color: var(--text2);
  cursor: pointer;
  user-select: none;
  transition: all 0.15s;
}
.chip:hover { border-color: var(--orange); color: var(--orange); }
.chip-active { border-color: var(--orange); background: var(--orange-dim); color: var(--orange); }

/* ── KPI Row ── */
.kpi-row {
  display: flex;
  gap: 1px;
  background: var(--border);
  border-bottom: 1px solid var(--border);
}
.kpi-card {
  flex: 1;
  padding: 16px 20px;
  background: var(--bg1);
  cursor: default;
  transition: background 0.15s;
}
.kpi-card:hover { background: var(--bg2); }
.kpi-label {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text3);
  margin-bottom: 6px;
}
.kpi-val {
  font-size: 2rem;
  font-weight: 800;
  color: var(--text);
  line-height: 1;
  font-family: var(--mono);
}
.kpi-val.orange { color: var(--orange); }
.kpi-val.green  { color: var(--green); }
.kpi-val.blue   { color: var(--blue); }
.kpi-val.purple { color: var(--purple); }
.kpi-sub {
  font-size: 0.68rem;
  color: var(--text3);
  margin-top: 4px;
}

/* ── Status Badges ── */
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-family: var(--mono);
}
.badge-NEW      { background: rgba(255,107,0,0.15); color: #FF8C33; border: 1px solid rgba(255,107,0,0.3); }
.badge-APPLIED  { background: rgba(34,197,94,0.12); color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
.badge-INTERVIEW{ background: rgba(59,130,246,0.12); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3); }
.badge-OFFER    { background: rgba(234,179,8,0.12); color: #eab308; border: 1px solid rgba(234,179,8,0.3); }
.badge-REJECTED { background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.25); }
.badge-MANUAL_NEEDED { background: rgba(139,92,246,0.12); color: #a78bfa; border: 1px solid rgba(139,92,246,0.3); }
.badge-SKIPPED  { background: rgba(100,100,100,0.12); color: #666; border: 1px solid rgba(100,100,100,0.2); }

/* H1B badge */
.h1b-yes   { color: var(--green); font-weight: 700; font-size: 0.72rem; }
.h1b-no    { color: var(--red);   font-weight: 700; font-size: 0.72rem; }
.h1b-blank { color: var(--text3); font-size: 0.72rem; }

/* ── Section bar ── */
.section-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 24px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  font-size: 0.72rem;
  color: var(--text3);
}
.section-bar b { color: var(--orange); }

/* ── Streamlit overrides ── */
div[data-testid="stTabs"] [role="tablist"] {
  background: var(--bg1);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  gap: 0;
}
button[data-baseweb="tab"] {
  font-size: 0.78rem !important;
  font-weight: 600 !important;
  font-family: var(--sans) !important;
  color: var(--text3) !important;
  padding: 12px 18px !important;
  border-radius: 0 !important;
  border-bottom: 2px solid transparent !important;
  background: transparent !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
  color: var(--orange) !important;
  border-bottom-color: var(--orange) !important;
}

/* Metric containers */
div[data-testid="metric-container"] {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.2rem;
  transition: border-color 0.15s;
}
div[data-testid="metric-container"]:hover { border-color: var(--border-hl); }
div[data-testid="metric-container"] > label { color: var(--text3) !important; font-size: 0.68rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important; font-weight: 700 !important; }
div[data-testid="metric-container"] > div[data-testid="metric-value"] > div { color: var(--text) !important; font-size: 1.8rem !important; font-weight: 800 !important; font-family: var(--mono) !important; }

/* Buttons */
.stButton > button {
  border-radius: var(--radius) !important;
  font-weight: 600 !important;
  font-size: 0.78rem !important;
  letter-spacing: 0.03em !important;
  border: 1px solid var(--border) !important;
  background: var(--bg2) !important;
  color: var(--text) !important;
  transition: all 0.15s !important;
}
.stButton > button:hover {
  border-color: var(--orange) !important;
  color: var(--orange) !important;
  background: var(--orange-dim) !important;
}
.stButton > button[kind="primary"] {
  background: var(--orange) !important;
  border-color: var(--orange) !important;
  color: white !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--orange-lt) !important;
  box-shadow: 0 0 20px rgba(255,107,0,0.35) !important;
}

/* Inputs */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stMultiSelect > div > div {
  background: var(--bg2) !important;
  border-color: var(--border) !important;
  color: var(--text) !important;
  border-radius: var(--radius) !important;
  font-size: 0.82rem !important;
}
.stTextInput > div > div > input:focus { border-color: var(--orange) !important; box-shadow: 0 0 0 2px rgba(255,107,0,0.2) !important; }
.stTextInput > label { font-size: 0.72rem !important; color: var(--text3) !important; font-weight: 600 !important; letter-spacing: 0.08em !important; text-transform: uppercase !important; }

/* Slider */
.stSlider > div > div > div > div { background: var(--orange) !important; }

/* Data editor */
div[data-testid="stDataEditor"] { border: 1px solid var(--border) !important; border-radius: var(--radius-lg) !important; overflow: hidden; }
div[data-testid="stDataEditor"] * { font-family: var(--sans) !important; font-size: 0.8rem !important; }

/* Expander */
details { border: 1px solid var(--border) !important; border-radius: var(--radius) !important; background: var(--bg2) !important; }
summary { color: var(--text) !important; font-weight: 600 !important; font-size: 0.82rem !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--orange); }

/* Toast */
div[data-testid="stToast"] { background: var(--bg2) !important; border: 1px solid var(--border) !important; color: var(--text) !important; }

/* Plotly */
.js-plotly-plot .plotly { background: transparent !important; }

/* File uploader, info */
.stInfo, .stSuccess, .stWarning, .stError { border-radius: var(--radius) !important; }

/* PDF iframe */
.pdf-frame { border-radius: var(--radius); border: 1px solid var(--border); width: 100%; height: 600px; }

/* Launch button row */
.launch-row {
  display: flex;
  gap: 8px;
  padding: 10px 24px;
  background: var(--bg1);
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
  align-items: center;
}
.launch-label {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text3);
  margin-right: 4px;
  white-space: nowrap;
}
</style>
""", unsafe_allow_html=True)


# ─── CONSTANTS ────────────────────────────────────────────────────────────────
STATUS_OPTIONS = ["NEW", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "MANUAL_NEEDED", "SKIPPED"]
PYTHON = sys.executable    # guaranteed to be the correct venv python
CWD    = os.path.dirname(os.path.abspath(__file__))


# ─── DB HELPERS ───────────────────────────────────────────────────────────────
@st.cache_resource
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Ensure sponsorship column exists
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN sponsorship TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    return conn


@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    expected_cols = [
        'id', 'company', 'title', 'location', 'source', 'url', 'description', 
        'date_posted', 'scraped_date', 'salary', 'sponsorship', 'department',
        'status', 'ats_score', 'notes', 'resume_pdf_path', 'cover_letter_pdf_path', 
        'applied_date'
    ]
    
    conn = get_db()
    try:
        df = pd.read_sql_query("""
            SELECT
                j.id, j.company, j.title, j.location, j.source,
                j.url, j.description, j.date_posted, j.scraped_date,
                COALESCE(j.salary,'')       AS salary,
                COALESCE(j.sponsorship,'')  AS sponsorship,
                COALESCE(j.department,'')   AS department,
                a.status, a.ats_score, a.notes,
                a.resume_pdf_path, a.cover_letter_pdf_path, a.applied_date
            FROM jobs j
            LEFT JOIN applications a ON j.id = a.job_id
            ORDER BY j.scraped_date DESC
        """, conn)
    except Exception:
        df = pd.DataFrame(columns=expected_cols)

    # Ensure all columns exist with correct dtypes
    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.Series(dtype='object' if col != 'ats_score' else 'float64')
    df['scraped_date'] = pd.to_datetime(df['scraped_date'], errors='coerce')
    df['applied_date'] = pd.to_datetime(df['applied_date'], errors='coerce')
    df['ats_score']    = pd.to_numeric(df['ats_score'], errors='coerce')
    
    now = datetime.now()
    if not df.empty:
        df['Posted'] = df['scraped_date'].apply(
            lambda x: timeago.format(x, now) if pd.notna(x) else ""
        )
        def _mode(loc):
            ll = str(loc).lower()
            if 'remote' in ll: return 'Remote'
            if 'hybrid' in ll: return 'Hybrid'
            return 'On-site'
        df['work_mode'] = df['location'].apply(_mode)
    else:
        df['Posted'] = pd.Series(dtype='object')
        df['work_mode'] = pd.Series(dtype='object')

    df['status'] = df['status'].fillna('NEW')
    return df


def save_application(job_id: str, status: str | None = None, notes: str | None = None):
    conn = get_db()
    fields, vals = [], []
    if status is not None:
        fields.append("status = ?"); vals.append(status)
        if status == "APPLIED":
            fields.append("applied_date = ?")
            vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if notes is not None:
        fields.append("notes = ?"); vals.append(notes)
    if not fields:
        return
    vals.append(job_id)
    cur = conn.cursor()
    cur.execute(f"UPDATE applications SET {', '.join(fields)} WHERE job_id=?", vals)
    if cur.rowcount == 0:
        cur.execute("INSERT OR IGNORE INTO applications(job_id,status) VALUES(?,?)",
                    (job_id, status or "NEW"))
        if fields:
            cur.execute(f"UPDATE applications SET {', '.join(fields)} WHERE job_id=?", vals)
    conn.commit()
    st.cache_data.clear()


def display_pdf_b64(path):
    if not path or not os.path.exists(str(path)):
        st.info("No file available.")
        return
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}" class="pdf-frame"></iframe>',
        unsafe_allow_html=True
    )


# ─── QUICK LAUNCH ─────────────────────────────────────────────────────────────
def launch_discovery(hours: float | None = None, full_pipeline: bool = False, tailor_only: bool = False):
    """Spawn daily_runner.py in a new visible console using the correct venv Python."""
    cmd = [PYTHON, "daily_runner.py"]
    if hours is not None:
        cmd += ["--hours", str(hours), "--skip-apply"]
    elif tailor_only:
        cmd += ["--skip-apply"]
    # full_pipeline: no extra flags
    try:
        subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,
            cwd=CWD,
        )
        label = f"{hours}h Discovery" if hours else ("Tailor Only" if tailor_only else "Full Pipeline")
        st.toast(f"Launched: {label}", icon=None)
    except Exception as e:
        st.error(f"Launch failed: {e}")


def launch_apply_single(job_id: str, job_url: str):
    """Spawn browser_agent for a single job application."""
    cmd = [PYTHON, "daily_runner.py", "--single-job", job_id]
    try:
        subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,
            cwd=CWD,
        )
        save_application(job_id, "APPLIED")
        st.toast(f"Application launched for job {job_id[:8]}...", icon=None)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Apply failed: {e}")


# ─── DATA LOAD ─────────────────────────────────────────────────────────────────
raw_df = load_data()


# ─── NAVIGATION / SELECTOR DEFAULTS ──────────────────────────────────────────
all_statuses = sorted(raw_df['status'].dropna().unique().tolist()) if not raw_df.empty else []
all_sources  = sorted(raw_df['source'].dropna().unique().tolist()) if not raw_df.empty else []


# ─── TOP BAR ─────────────────────────────────────────────────────────────────
tb_logo, tb_search, tb_refresh = st.columns([1.5, 9, 1.5])
with tb_logo:
    st.markdown("<p style='color:#FF6B00;font-family:JetBrains Mono,monospace;font-weight:800;font-size:0.85rem;margin:0;'>JOB HUNTER AI</p>", unsafe_allow_html=True)
with tb_search:
    search_q = st.text_input(
        "SEARCH", placeholder="Search company, title, location, keyword...",
        label_visibility="collapsed", key="global_search"
    )
with tb_refresh:
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ─── QUICK LAUNCH BAR ─────────────────────────────────────────────────────────
lc1, lc2, lc3, lc4, lc5, lc6 = st.columns([1, 1, 1, 1, 2, 1.5])
with lc1:
    if st.button("10 min", use_container_width=True):
        launch_discovery(0.17)
with lc2:
    if st.button("1 hour", use_container_width=True):
        launch_discovery(1)
with lc3:
    if st.button("6 hours", use_container_width=True):
        launch_discovery(6)
with lc4:
    if st.button("24 hours", use_container_width=True):
        launch_discovery(24)
with lc5:
    if st.button("Full Discovery (24h)", use_container_width=True):
        launch_discovery(24)
with lc6:
    if st.button("Run Full Pipeline", type="primary", use_container_width=True):
        launch_discovery(full_pipeline=True)


# ─── KPI METRICS ──────────────────────────────────────────────────────────────
total      = len(raw_df)
new_cnt    = int((raw_df['status'] == 'NEW').sum())
applied    = int((raw_df['status'] == 'APPLIED').sum())
interviews = int((raw_df['status'] == 'INTERVIEW').sum())
offers     = int((raw_df['status'] == 'OFFER').sum())
avg_ats    = raw_df['ats_score'].dropna()
avg_ats_v  = f"{avg_ats.mean():.1f}" if len(avg_ats) else "—"
tailored   = int(raw_df['resume_pdf_path'].fillna('').str.len().gt(0).sum())

kc = st.columns(7)
with kc[0]: st.metric("Total Jobs",      f"{total:,}")
with kc[1]: st.metric("New / Unreviewed", f"{new_cnt:,}")
with kc[2]: st.metric("Applied",         f"{applied:,}")
with kc[3]: st.metric("Interviews",      f"{interviews:,}")
with kc[4]: st.metric("Offers",          f"{offers:,}")
with kc[5]: st.metric("Avg ATS Score",   avg_ats_v)
with kc[6]: st.metric("Tailored Resumes", f"{tailored:,}")

st.markdown("<hr style='margin:0;border-color:#252525;'>", unsafe_allow_html=True)


# ─── FILTER STATE ─────────────────────────────────────────────────────────────
# ─── FILTERS (always visible) ───────────────────────────────────────────────────
fc1, fc2, fc3, fc4, fc5 = st.columns([3, 3, 2, 2, 2])
with fc1:
    all_statuses = sorted(raw_df['status'].dropna().unique().tolist())
    sel_status = st.multiselect("Status", all_statuses, default=all_statuses, key="f_status")
with fc2:
    all_sources = sorted(raw_df['source'].dropna().unique().tolist())
    sel_source = st.multiselect("Source", all_sources, key="f_source")
with fc3:
    sel_mode = st.multiselect("Work Mode", ["Remote", "Hybrid", "On-site"], key="f_mode")
with fc4:
    sel_h1b = st.multiselect("H1B Sponsorship", ["Likely", "No", "Unknown"], key="f_h1b")
with fc5:
    sort_by = st.selectbox("Sort By", [
        "Newest First", "ATS Score (High to Low)", "Company A-Z",
        "Status Priority", "Source"
    ], key="f_sort")

fc6, fc7, fc8 = st.columns([3, 3, 2])
with fc6:
    ats_range = st.slider("ATS Score Range", 0.0, 10.0, (0.0, 10.0), step=0.5, key="f_ats")
with fc7:
    time_window = st.selectbox("Time Window", [
        "All Time", "Last Hour", "Last 6 Hours",
        "Last 24 Hours", "Last 3 Days", "Last 7 Days"
    ], key="f_time")
with fc8:
    hide_senior = st.checkbox("Entry Level Only", value=True, key="f_hide_senior",
                               help="Hides roles with: senior, lead, staff, principal, director, vp, manager")


# ─── APPLY FILTERS ────────────────────────────────────────────────────────────
df = raw_df.copy()

if not df.empty:
    # Time window
    now = datetime.now()
    time_map = {
        "Last Hour": timedelta(hours=1),
        "Last 6 Hours": timedelta(hours=6),
        "Last 24 Hours": timedelta(hours=24),
        "Last 3 Days": timedelta(days=3),
        "Last 7 Days": timedelta(days=7),
    }
    tw = st.session_state.get("f_time", "All Time")
    if tw in time_map:
        cutoff = now - time_map[tw]
        if 'scraped_date' in df.columns:
            df = df[df['scraped_date'] >= pd.Timestamp(cutoff)]

    # Status
    ss = st.session_state.get("f_status", all_statuses)
    if ss:
        df = df[df['status'].isin(ss)]

    # Source
    src = st.session_state.get("f_source", [])
    if src:
        df = df[df['source'].isin(src)]

    # Work mode
    mode_sel = st.session_state.get("f_mode", [])
    if mode_sel:
        df = df[df['work_mode'].isin(mode_sel)]

    # H1B
    h1b_sel = st.session_state.get("f_h1b", [])
    if h1b_sel:
        mask = pd.Series([False] * len(df), index=df.index)
        if "Likely" in h1b_sel:
            mask |= df['sponsorship'].str.lower().str.contains("likely|yes|sponsor", na=False)
        if "No" in h1b_sel:
            mask |= df['sponsorship'].str.lower().str.contains("^no$|does not", na=False, regex=True)
        if "Unknown" in h1b_sel:
            mask |= df['sponsorship'].fillna('').eq('')
        df = df[mask]

    # ATS
    ats_r = st.session_state.get("f_ats", (0.0, 10.0))
    if 'ats_score' in df.columns:
        ats_mask = df['ats_score'].isna() | (
            (df['ats_score'] >= ats_r[0]) & (df['ats_score'] <= ats_r[1])
        )
        df = df[ats_mask]

    # Entry-level-only filter
    if st.session_state.get("f_hide_senior", True):
        _snr = ["senior", " sr ", "sr.", "staff", "principal", "director",
                " vp ", "v.p.", "head of", "manager", "lead engineer", "tech lead",
                "distinguished", "fellow", "architect"]
        snr_mask = ~df['title'].str.lower().apply(lambda t: any(x in t for x in _snr))
        df = df[snr_mask]

    # Search
    if search_q:
        q = search_q.lower()
        df = df[
            df['company'].str.lower().str.contains(q, na=False) |
            df['title'].str.lower().str.contains(q, na=False) |
            df['location'].str.lower().str.contains(q, na=False) |
            df['description'].str.lower().str.contains(q, na=False)
        ]

# Sort
sort_key = st.session_state.get("f_sort", "Newest First")
if sort_key == "ATS Score (High to Low)":
    df = df.sort_values('ats_score', ascending=False, na_position='last')
elif sort_key == "Company A-Z":
    df = df.sort_values('company')
elif sort_key == "Status Priority":
    order = {"INTERVIEW": 0, "OFFER": 1, "APPLIED": 2, "MANUAL_NEEDED": 3, "NEW": 4, "REJECTED": 5, "SKIPPED": 6}
    df['_s'] = df['status'].map(lambda x: order.get(x, 9))
    df = df.sort_values('_s').drop(columns=['_s'])
elif sort_key == "Source":
    if not df.empty and 'source' in df.columns:
        df = df.sort_values('source')
else:
    if not df.empty and 'scraped_date' in df.columns:
        df = df.sort_values('scraped_date', ascending=False)

# Stats bar
st.markdown(
    f"<div style='padding:6px 24px;background:#0c0c0c;border-bottom:1px solid #252525;"
    f"font-size:0.72rem;color:#555;'>"
    f"Showing <b style='color:#FF6B00'>{len(df):,}</b> of {len(raw_df):,} jobs &nbsp;|&nbsp; "
    f"<b style='color:#FF6B00'>{df['company'].nunique()}</b> companies &nbsp;|&nbsp; "
    f"<b style='color:#FF6B00'>{df['source'].nunique()}</b> sources"
    f"</div>",
    unsafe_allow_html=True
)

# ─── MAIN TABS ────────────────────────────────────────────────────────────────
tab_jobs, tab_pipeline, tab_analytics, tab_settings = st.tabs([
    "Jobs Board", "Pipeline & Resumes", "Analytics", "Settings"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: JOBS BOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_jobs:

    # Column selector
    visible = st.multiselect(
        "COLUMNS",
        ['status', 'company', 'title', 'work_mode', 'location', 'source',
         'department', 'sponsorship', 'salary', 'Posted', 'ats_score',
         'notes', 'url', 'resume_pdf_path', 'cover_letter_pdf_path'],
        default=['status', 'company', 'title', 'department', 'work_mode',
                 'sponsorship', 'salary', 'source', 'Posted', 'ats_score', 'notes', 'url'],
        key="col_selector",
        label_visibility="collapsed"
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # Build editor dataframe (include id invisibly for row identification)
    display_cols = [c for c in visible if c in df.columns]
    editor_df = df[['id'] + display_cols].copy()
    editor_display = editor_df.drop(columns=['id'])

    # Column config
    col_cfg = {
        "status": st.column_config.SelectboxColumn(
            "Status",
            options=STATUS_OPTIONS,
            width="small",
            required=True,
        ),
        "company":    st.column_config.TextColumn("Company", width="medium"),
        "title":      st.column_config.TextColumn("Title", width="large"),
        "location":   st.column_config.TextColumn("Location", width="medium"),
        "work_mode":  st.column_config.TextColumn("Mode", width="small"),
        "department": st.column_config.TextColumn("Dept", width="medium"),
        "source":     st.column_config.TextColumn("Source", width="small"),
        "sponsorship":st.column_config.TextColumn("H1B", width="small"),
        "salary":     st.column_config.TextColumn("Salary", width="medium"),
        "Posted":     st.column_config.TextColumn("Posted", width="small"),
        "ats_score":  st.column_config.NumberColumn("ATS", format="%.1f", width="small"),
        "notes":      st.column_config.TextColumn("Notes", width="large"),
        "url":        st.column_config.LinkColumn("Apply Link", display_text="Open", width="small"),
        "resume_pdf_path":       st.column_config.TextColumn("Resume", width="small"),
        "cover_letter_pdf_path": st.column_config.TextColumn("Cover Letter", width="small"),
    }

    edited = st.data_editor(
        editor_display,
        use_container_width=True,
        hide_index=True,
        height=min(750, 36 * len(editor_display) + 42),
        num_rows="fixed",
        column_config={k: v for k, v in col_cfg.items() if k in editor_display.columns},
        key="jobs_editor"
    )

    # Detect and persist changes
    try:
        changed = (editor_display.reset_index(drop=True) != edited.reset_index(drop=True)).any(axis=1)
        if changed.any():
            for i in changed[changed].index:
                row_id = editor_df.iloc[i]['id']
                new_status = edited.iloc[i].get('status') if 'status' in edited.columns else None
                new_notes  = edited.iloc[i].get('notes')  if 'notes'  in edited.columns else None
                save_application(row_id, new_status, new_notes)
            st.toast(f"Saved {changed.sum()} change(s).")
    except Exception:
        pass

    # ── Per-row Apply buttons ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Apply to Selected Jobs")
    st.caption("Enter a job's row number (0-indexed from the table above) to trigger our automation for that job.")

    apply_col1, apply_col2, apply_col3 = st.columns([2, 2, 4])
    with apply_col1:
        apply_idx = st.number_input("Row index", min_value=0, max_value=max(len(df)-1, 0), step=1, key="apply_idx")
    with apply_col2:
        if st.button("Run Automation for This Job", type="primary"):
            if 0 <= int(apply_idx) < len(df):
                selected_row = df.iloc[int(apply_idx)]
                launch_apply_single(selected_row['id'], selected_row['url'])
                st.success(f"Launched automation for: {selected_row['company']} — {selected_row['title']}")
            else:
                st.error("Invalid row index")
    with apply_col3:
        if st.button("Tailor Resumes (No Apply)"):
            launch_discovery(tailor_only=True)

    # ── Bulk Status Update ─────────────────────────────────────────────────
    with st.expander("Bulk Status Update"):
        bulk1, bulk2, bulk3 = st.columns(3)
        with bulk1:
            bulk_ids = st.text_area("Job IDs (one per line)", height=100, placeholder="Paste job IDs here")
        with bulk2:
            bulk_status = st.selectbox("Set Status To", STATUS_OPTIONS, key="bulk_status")
            bulk_notes  = st.text_area("Notes (optional)", height=60, key="bulk_notes")
        with bulk3:
            st.write("")
            st.write("")
            if st.button("Apply Bulk Update", type="primary"):
                ids = [x.strip() for x in bulk_ids.split('\n') if x.strip()]
                for jid in ids:
                    save_application(jid, bulk_status, bulk_notes or None)
                st.success(f"Updated {len(ids)} jobs to {bulk_status}")

    # ── Export ────────────────────────────────────────────────────────────
    with st.expander("Export"):
        ec1, ec2 = st.columns(2)
        with ec1:
            csv_filtered = df.drop(columns=['id', '_s'], errors='ignore').to_csv(index=False)
            st.download_button("Download Filtered CSV", csv_filtered, "jobs_filtered.csv", "text/csv")
        with ec2:
            csv_all = raw_df.drop(columns=['id', '_s'], errors='ignore').to_csv(index=False)
            st.download_button("Download All Jobs CSV", csv_all, "jobs_all.csv", "text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: PIPELINE & RESUMES
# ══════════════════════════════════════════════════════════════════════════════
with tab_pipeline:
    st.markdown("<div style='padding:16px 24px;'>", unsafe_allow_html=True)

    pipeline_sub = st.tabs(["Tailoring Queue", "Applied Jobs", "View Documents"])

    # ── Tailoring Queue ───────────────────────────────────────────────────
    with pipeline_sub[0]:
        queue = raw_df[
            (raw_df['status'] == 'NEW') &
            (raw_df['resume_pdf_path'].fillna('').eq(''))
        ][['company', 'title', 'source', 'Posted', 'salary', 'url']].copy()

        if queue.empty:
            st.info("No jobs awaiting tailoring. Run a discovery to fetch new jobs.")
        else:
            st.caption(f"{len(queue):,} jobs need tailored resumes.")
            st.dataframe(
                queue,
                use_container_width=True,
                hide_index=True,
                column_config={"url": st.column_config.LinkColumn("Link", display_text="Open")}
            )
            if st.button(f"Generate Tailored Resumes for All ({len(queue)})", type="primary"):
                launch_discovery(tailor_only=True)

    # ── Applied Jobs ──────────────────────────────────────────────────────
    with pipeline_sub[1]:
        applied_df = raw_df[raw_df['status'].isin(['APPLIED', 'INTERVIEW', 'OFFER'])].copy()
        if applied_df.empty:
            st.info("No applied jobs yet.")
        else:
            st.caption(f"{len(applied_df):,} active applications.")

            display_applied = applied_df[
                ['company', 'title', 'status', 'applied_date', 'ats_score',
                 'resume_pdf_path', 'cover_letter_pdf_path', 'notes', 'url']
            ]
            st.dataframe(
                display_applied,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "status": st.column_config.TextColumn("Status", width="small"),
                    "ats_score": st.column_config.NumberColumn("ATS", format="%.1f", width="small"),
                    "url": st.column_config.LinkColumn("Link", display_text="Open"),
                    "resume_pdf_path": st.column_config.TextColumn("Resume Path"),
                    "cover_letter_pdf_path": st.column_config.TextColumn("CL Path"),
                }
            )

    # ── Document Viewer ────────────────────────────────────────────────────
    with pipeline_sub[2]:
        jobs_with_docs = raw_df[raw_df['resume_pdf_path'].fillna('').str.len() > 0][
            ['company', 'title', 'resume_pdf_path', 'cover_letter_pdf_path']
        ].copy()

        if jobs_with_docs.empty:
            st.info("No tailored documents yet.")
        else:
            doc_company = st.selectbox("Select Company", jobs_with_docs['company'].tolist(), key="doc_company")
            selected_doc = jobs_with_docs[jobs_with_docs['company'] == doc_company].iloc[0]

            doc_tab1, doc_tab2 = st.tabs(["Tailored Resume", "Cover Letter"])
            with doc_tab1:
                display_pdf_b64(selected_doc.get('resume_pdf_path', ''))
            with doc_tab2:
                display_pdf_b64(selected_doc.get('cover_letter_pdf_path', ''))

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
with tab_analytics:
    st.markdown("<div style='padding:16px 24px;'>", unsafe_allow_html=True)

    chart_theme = {
        "plot_bgcolor":  "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "font":          {"color": "#888", "family": "Inter"},
        "margin":        {"l": 0, "r": 0, "t": 36, "b": 0},
    }

    ac1, ac2 = st.columns(2)

    # Source bar chart
    with ac1:
        src_counts = df['source'].value_counts().reset_index()
        src_counts.columns = ['source', 'count']
        fig = px.bar(
            src_counts, x='count', y='source', orientation='h',
            title="Jobs by Source",
            color='count', color_continuous_scale=["#1a1a1a", "#FF6B00", "#FF8C33"],
            template="plotly_dark"
        )
        fig.update_layout(**chart_theme, showlegend=False, coloraxis_showscale=False, height=380)
        fig.update_layout(yaxis=dict(categoryorder='total ascending',
                                     tickfont=dict(size=11, color="#888")))
        st.plotly_chart(fig, use_container_width=True)

    # Status donut
    with ac2:
        status_counts = df['status'].value_counts().reset_index()
        status_counts.columns = ['status', 'count']
        color_map = {
            "NEW": "#FF6B00", "APPLIED": "#22c55e", "INTERVIEW": "#3b82f6",
            "OFFER": "#eab308", "REJECTED": "#ef4444",
            "MANUAL_NEEDED": "#8b5cf6", "SKIPPED": "#555"
        }
        fig2 = px.pie(
            status_counts, values='count', names='status',
            title="Status Breakdown", hole=0.55,
            color='status', color_discrete_map=color_map,
            template="plotly_dark"
        )
        fig2.update_traces(textinfo='label+percent', textfont_size=11)
        fig2.update_layout(**chart_theme, height=380, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    ac3, ac4 = st.columns(2)

    # Daily velocity
    with ac3:
        vel_df = raw_df.copy()
        vel_df['Day'] = vel_df['scraped_date'].dt.date
        daily = vel_df.groupby('Day').size().reset_index(name='Count')
        daily = daily.tail(21)  # last 3 weeks
        fig3 = px.bar(
            daily, x='Day', y='Count', title="Daily Jobs Discovered (Last 21 Days)",
            color_discrete_sequence=["#FF6B00"], template="plotly_dark"
        )
        fig3.update_traces(marker_line_width=0)
        fig3.update_layout(**chart_theme, height=320, bargap=0.3)
        st.plotly_chart(fig3, use_container_width=True)

    # H1B breakdown
    with ac4:
        h1b_df = raw_df.copy()
        def h1b_label(v):
            v = str(v).lower()
            if 'likely' in v or 'yes' in v: return 'Likely Sponsor'
            if v == 'no' or 'does not' in v: return 'No Sponsorship'
            return 'Unknown'
        h1b_df['H1B'] = h1b_df['sponsorship'].apply(h1b_label)
        h1b_counts = h1b_df['H1B'].value_counts().reset_index()
        h1b_counts.columns = ['H1B', 'Count']
        fig4 = px.pie(
            h1b_counts, values='Count', names='H1B',
            title="H1B Sponsorship Breakdown", hole=0.55,
            color='H1B',
            color_discrete_map={
                'Likely Sponsor': '#22c55e',
                'No Sponsorship': '#ef4444',
                'Unknown': '#555'
            },
            template="plotly_dark"
        )
        fig4.update_traces(textinfo='label+percent', textfont_size=11)
        fig4.update_layout(**chart_theme, height=320, showlegend=False)
        st.plotly_chart(fig4, use_container_width=True)

    # ATS distribution
    ats_data = raw_df['ats_score'].dropna()
    if len(ats_data) > 0:
        fig5 = px.histogram(
            raw_df, x='ats_score', nbins=20,
            title="ATS Score Distribution",
            color_discrete_sequence=["#FF6B00"], template="plotly_dark"
        )
        fig5.update_layout(**chart_theme, height=280)
        st.plotly_chart(fig5, use_container_width=True)

    # Source x Status heatmap
    if len(df) > 0 and df['source'].nunique() > 1:
        pivot = df.pivot_table(
            index='source', columns='status', values='id',
            aggfunc='count', fill_value=0
        )
        fig6 = px.imshow(
            pivot, title="Source vs Status Heatmap",
            color_continuous_scale=["#000000", "#FF6B00", "#FF8C33"],
            template="plotly_dark", aspect="auto"
        )
        fig6.update_layout(**chart_theme, height=max(300, len(pivot) * 40))
        st.plotly_chart(fig6, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
with tab_settings:
    st.markdown("<div style='padding:16px 24px;'>", unsafe_allow_html=True)
    st.markdown("#### Configuration")

    sc1, sc2 = st.columns(2)

    with sc1:
        st.markdown("**User Profile**")
        profile_path = os.path.join(CWD, "user_profile.json")
        if os.path.exists(profile_path):
            with open(profile_path) as pf:
                profile_raw = pf.read()
            edited_profile = st.text_area("user_profile.json", value=profile_raw, height=400, key="profile_editor")
            if st.button("Save Profile", type="primary"):
                try:
                    json.loads(edited_profile)  # validate JSON
                    with open(profile_path, 'w') as pf:
                        pf.write(edited_profile)
                    st.success("Profile saved.")
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")
        else:
            st.warning("user_profile.json not found.")

    with sc2:
        st.markdown("**Environment Variables**")
        env_path = os.path.join(CWD, ".env")
        if os.path.exists(env_path):
            with open(env_path) as ef:
                env_raw = ef.read()
            edited_env = st.text_area(".env (sensitive — do not share)", value=env_raw, height=300, key="env_editor")
            if st.button("Save .env"):
                try:
                    with open(env_path, 'w') as ef:
                        ef.write(edited_env)
                    st.success(".env saved.")
                except Exception as ex:
                    st.error(str(ex))
        else:
            st.warning(".env not found.")

        st.markdown("**Database Actions**")
        if st.button("Clear Cache"):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.warning("⚠️ **Danger Zone**")
        confirm_delete = st.checkbox("I understand this will permanently delete ALL jobs and applications.")
        if st.button("Delete Entire Database", type="secondary", disabled=not confirm_delete):
            db_mgr = DatabaseManager(DB_PATH)
            db_mgr.clear_all_data()
            db_mgr.close()
            st.cache_data.clear()
            st.success("Database cleared successfully.")
            st.rerun()
        db_stats_df = pd.DataFrame([{
            "Total Jobs":    len(raw_df),
            "Applied":       applied,
            "Interviews":    interviews,
            "Offers":        offers,
            "New":           new_cnt,
            "Tailored":      tailored,
        }]).T.reset_index()
        db_stats_df.columns = ["Metric", "Value"]
        st.dataframe(db_stats_df, use_container_width=True, hide_index=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ─── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown(
    f"<div style='text-align:center;color:#2a2a2a;font-size:0.65rem;"
    f"padding:16px;border-top:1px solid #151515;margin-top:12px;font-family:JetBrains Mono,monospace;'>"
    f"JOB HUNTER AI v4.0 &nbsp;|&nbsp; {len(raw_df):,} jobs in database "
    f"&nbsp;|&nbsp; Last loaded: {datetime.now().strftime('%H:%M:%S')}</div>",
    unsafe_allow_html=True
)