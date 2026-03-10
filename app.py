"""
app.py  —  PhotoMeta Restorer
Streamlit UI for Google Photos Takeout metadata restoration.
Run: streamlit run app.py
"""

import threading
import queue
import time
from pathlib import Path
from datetime import datetime

import streamlit as st

from processor import (
    scan_folder,
    scan_folder_deep,
    process_all,
    verify_output,
    check_ffmpeg,
    get_folder_stats,
    export_errors_csv,
    ALL_EXTS,
    JPEG_EXTS,
    VIDEO_EXTS,
)

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PhotoMeta Restorer",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS — professional dark theme, full mobile support, high-contrast text
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Fonts ─────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

/* ── Reset & Base ───────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0d0f14 !important;
    color: #e8eaf0 !important;
}

/* ── CSS Variables ──────────────────────────────────────────────────────── */
:root {
    --green:   #22c55e;
    --blue:    #3b82f6;
    --amber:   #f59e0b;
    --red:     #ef4444;
    --purple:  #a855f7;
    --surface: rgba(255,255,255,0.04);
    --border:  rgba(255,255,255,0.09);
    --text-primary: #f1f3f9;
    --text-secondary: #9ca3af;
    --text-muted: #6b7280;
    --radius: 14px;
}

/* ── Remove Streamlit chrome ────────────────────────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding: 2rem 1.5rem 4rem !important;
    max-width: 1100px !important;
}

/* ── Hero ───────────────────────────────────────────────────────────────── */
.hero {
    text-align: center;
    padding: 3rem 1rem 2rem;
}
.hero-eyebrow {
    display: inline-block;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--green);
    background: rgba(34,197,94,0.1);
    border: 1px solid rgba(34,197,94,0.25);
    padding: 5px 14px;
    border-radius: 100px;
    margin-bottom: 20px;
}
.hero-title {
    font-size: clamp(2.2rem, 5vw, 3.6rem);
    font-weight: 700;
    letter-spacing: -1px;
    line-height: 1.1;
    color: var(--text-primary);
    margin: 0 0 12px;
}
.hero-title span {
    background: linear-gradient(135deg, #22c55e 0%, #3b82f6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero-sub {
    font-size: 16px;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.6;
}

/* ── Status Bar ─────────────────────────────────────────────────────────── */
.status-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: center;
    margin: 1.5rem 0;
}
.status-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 8px 16px;
    border-radius: 100px;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    border: 1px solid var(--border);
    background: var(--surface);
}
.chip-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.chip-ok   .chip-dot { background: var(--green); box-shadow: 0 0 6px var(--green); }
.chip-warn .chip-dot { background: var(--amber); box-shadow: 0 0 6px var(--amber); }

/* ── Card / Panel ───────────────────────────────────────────────────────── */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px 22px;
    margin-bottom: 18px;
}
.card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 20px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border);
}
.card-icon {
    width: 36px; height: 36px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
}
.icon-green  { background: rgba(34,197,94,0.15); }
.icon-blue   { background: rgba(59,130,246,0.15); }
.icon-amber  { background: rgba(245,158,11,0.15); }
.icon-purple { background: rgba(168,85,247,0.15); }
.icon-red    { background: rgba(239,68,68,0.15); }

.card-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
}
.card-subtitle {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
}

/* ── God Mode Banner ────────────────────────────────────────────────────── */
.god-mode-banner {
    background: linear-gradient(135deg, rgba(168,85,247,0.15) 0%, rgba(59,130,246,0.1) 100%);
    border: 1px solid rgba(168,85,247,0.35);
    border-radius: var(--radius);
    padding: 20px 22px;
    margin-bottom: 16px;
}
.god-mode-title {
    font-size: 16px;
    font-weight: 700;
    color: #c084fc;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.god-mode-desc {
    font-size: 13px;
    color: #9ca3af;
    line-height: 1.6;
}
.god-mode-features {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
}
.god-feature-tag {
    font-size: 11px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 6px;
    background: rgba(168,85,247,0.15);
    color: #c084fc;
    border: 1px solid rgba(168,85,247,0.2);
}

/* ── Metric Cards ───────────────────────────────────────────────────────── */
.metrics-row {
    display: grid;
    gap: 12px;
    margin: 16px 0;
}
.metrics-5 { grid-template-columns: repeat(5, 1fr); }
.metrics-4 { grid-template-columns: repeat(4, 1fr); }
.metrics-3 { grid-template-columns: repeat(3, 1fr); }

@media (max-width: 768px) {
    .metrics-5, .metrics-4 { grid-template-columns: repeat(2, 1fr); }
    .metrics-3              { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
    .metrics-5, .metrics-4, .metrics-3 { grid-template-columns: 1fr 1fr; }
}

.metric-box {
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 14px;
    text-align: center;
}
.metric-number {
    font-family: 'DM Mono', monospace;
    font-size: 2rem;
    font-weight: 500;
    line-height: 1;
    margin-bottom: 6px;
}
.metric-name {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 1px;
}
.metric-note {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 3px;
    font-family: 'DM Mono', monospace;
}

/* ── Year Distribution ──────────────────────────────────────────────────── */
.year-chart { margin-top: 4px; }
.year-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}
.year-lbl {
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    color: var(--text-secondary);
    min-width: 42px;
    text-align: right;
}
.year-track {
    flex: 1;
    height: 16px;
    background: rgba(255,255,255,0.05);
    border-radius: 4px;
    overflow: hidden;
}
.year-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--green), var(--blue));
    border-radius: 4px;
    transition: width 0.5s ease;
}
.year-cnt {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
    min-width: 36px;
}

/* ── Terminal Log ───────────────────────────────────────────────────────── */
.terminal-wrap {
    background: #080a10;
    border: 1px solid #1a1d26;
    border-radius: var(--radius);
    overflow: hidden;
    margin-top: 14px;
}
.terminal-bar {
    background: #0e1018;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 1px solid #1a1d26;
}
.tb-dot { width: 11px; height: 11px; border-radius: 50%; }
.tbd-r { background: #ef4444; }
.tbd-y { background: #f59e0b; }
.tbd-g { background: #22c55e; }
.terminal-label {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: #374151;
    margin-left: 4px;
    letter-spacing: 2px;
    text-transform: uppercase;
}
.terminal-body {
    padding: 14px 16px;
    max-height: 360px;
    overflow-y: auto;
    font-family: 'DM Mono', monospace;
    font-size: 12.5px;
    line-height: 1.7;
}
.terminal-body::-webkit-scrollbar { width: 5px; }
.terminal-body::-webkit-scrollbar-track { background: #080a10; }
.terminal-body::-webkit-scrollbar-thumb { background: #1a1d26; border-radius: 3px; }

.log-success { color: #4ade80; }
.log-error   { color: #f87171; }
.log-warn    { color: #fbbf24; }
.log-info    { color: #4b5563; }

/* ── Verify Table ───────────────────────────────────────────────────────── */
.vtable-wrap {
    background: #080a10;
    border: 1px solid #1a1d26;
    border-radius: var(--radius);
    overflow: hidden;
    margin-top: 14px;
    overflow-x: auto;
}
.vtable-head {
    display: grid;
    grid-template-columns: 2.5fr 0.8fr 1.5fr 0.6fr 1fr;
    background: #0e1018;
    padding: 11px 16px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    border-bottom: 1px solid #1a1d26;
    min-width: 540px;
}
.vtable-row {
    display: grid;
    grid-template-columns: 2.5fr 0.8fr 1.5fr 0.6fr 1fr;
    padding: 9px 16px;
    font-size: 13px;
    border-bottom: 1px solid #0e1018;
    align-items: center;
    transition: background 0.1s;
    min-width: 540px;
    font-family: 'DM Mono', monospace;
}
.vtable-row:hover { background: rgba(255,255,255,0.02); }
.vtable-row:last-child { border-bottom: none; }

/* ── Divider ────────────────────────────────────────────────────────────── */
.section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
    margin: 24px 0;
}

/* ── Info box ───────────────────────────────────────────────────────────── */
.info-box {
    background: rgba(59,130,246,0.08);
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 13px;
    color: #93c5fd;
    line-height: 1.6;
}

/* ── Streamlit widget overrides ─────────────────────────────────────────── */
div[data-testid="stTextInput"] label,
div[data-testid="stRadio"] label,
div[data-testid="stCheckbox"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stDateInput"] label,
div[data-testid="stSelectbox"] label,
.stMarkdown p, .stMarkdown li, .stMarkdown h3, .stMarkdown h4 {
    color: var(--text-primary) !important;
    font-size: 14px !important;
}

div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 10px !important;
    color: #f1f3f9 !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus {
    border-color: rgba(34,197,94,0.4) !important;
    box-shadow: 0 0 0 2px rgba(34,197,94,0.1) !important;
    outline: none !important;
}

/* Radio buttons */
div[data-testid="stRadio"] > div {
    gap: 6px !important;
}
div[data-testid="stRadio"] label {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    margin: 2px 0 !important;
    cursor: pointer !important;
    transition: all 0.15s !important;
    color: var(--text-primary) !important;
}
div[data-testid="stRadio"] label:hover {
    border-color: rgba(34,197,94,0.3) !important;
    background: rgba(34,197,94,0.05) !important;
}

/* Checkbox */
div[data-testid="stCheckbox"] label {
    color: var(--text-primary) !important;
    font-weight: 500 !important;
}

/* Buttons */
.stButton > button {
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 10px 22px !important;
    transition: all 0.2s !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(34,197,94,0.2) !important;
}
button[kind="primary"] {
    background: linear-gradient(135deg, #16a34a, #2563eb) !important;
    color: white !important;
    border: none !important;
}

/* Progress */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--green), var(--blue)) !important;
    border-radius: 4px !important;
}

/* Expander */
div[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}
div[data-testid="stExpander"] summary {
    color: var(--text-primary) !important;
    font-weight: 500 !important;
}

/* Success/Warning/Error messages */
div[data-testid="stAlert"] {
    border-radius: 10px !important;
}

/* Column spacing */
div[data-testid="stColumns"] { gap: 16px; }

/* Mobile responsive */
@media (max-width: 640px) {
    .block-container { padding: 1.2rem 1rem 3rem !important; }
    .hero-title { font-size: 2rem !important; }
    .hero { padding: 2rem 0.5rem 1.5rem; }
    .card { padding: 18px 14px; }
    .god-mode-banner { padding: 16px 14px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
for key, default in {
    "logs":         [],
    "stats":        None,
    "processing":   False,
    "done":         False,
    "scan_result":  None,
    "folder_stats": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ─────────────────────────────────────────────────────────────────────────────
# Hero
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="hero">
  <div class="hero-eyebrow">Google Takeout Rescue Tool</div>
  <h1 class="hero-title">PhotoMeta <span>Restorer</span></h1>
  <p class="hero-sub">
    Restore lost dates, GPS locations, and timestamps<br>
    from your Google Photos Takeout export — automatically.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# System status
# ─────────────────────────────────────────────────────────────────────────────
ffmpeg_ok = check_ffmpeg()
st.markdown(
    f"""
<div class="status-bar">
  <div class="status-chip {'chip-ok' if ffmpeg_ok else 'chip-warn'}">
    <div class="chip-dot"></div>
    {'FFmpeg Ready — Video metadata supported' if ffmpeg_ok else 'FFmpeg Missing — Video timestamps only'}
  </div>
  <div class="status-chip chip-ok">
    <div class="chip-dot"></div>
    JPEG EXIF — Date + GPS embed enabled
  </div>
  <div class="status-chip chip-ok">
    <div class="chip-dot"></div>
    File Timestamps — All file types
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if not ffmpeg_ok:
    st.markdown(
        """
<div class="info-box">
  <strong>Install FFmpeg</strong> to enable full video metadata embedding:<br>
  Windows: <code>winget install ffmpeg</code> &nbsp;|&nbsp;
  Mac: <code>brew install ffmpeg</code> &nbsp;|&nbsp;
  Linux: <code>sudo apt install ffmpeg</code>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# God Mode section
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="god-mode-banner">
  <div class="god-mode-title">⚡ God Mode</div>
  <div class="god-mode-desc">
    <strong style="color:#e2e8f0;">For messy, deeply nested, or mixed folder structures.</strong><br>
    God Mode recursively scans every sub-folder at any depth — no matter how disorganized
    your Takeout export is. It automatically finds all media files and their JSON sidecars,
    so you never have to manually sort or arrange folders beforehand.
  </div>
  <div class="god-mode-features">
    <span class="god-feature-tag">Unlimited folder depth</span>
    <span class="god-feature-tag">Auto-detects all media</span>
    <span class="god-feature-tag">No pre-sorting needed</span>
    <span class="god-feature-tag">Handles all Takeout structures</span>
    <span class="god-feature-tag">Works on any drive or path</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

god_mode = st.checkbox(
    "Enable God Mode  (deep recursive scan — recommended for large or complex exports)",
    value=False,
    help="Scans all sub-folders recursively. Use this when Google has nested your photos in multiple layers of folders.",
)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="card-header" style="margin-bottom:16px">
  <div class="card-icon icon-blue">⚙️</div>
  <div>
    <div class="card-title">Configuration</div>
    <div class="card-subtitle">Set your source and destination paths, then choose how to organize the output</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2, gap="large")

with col1:
    takeout_path = st.text_input(
        "Source Folder Path",
        value=r"D:\Takeout\Google Photos",
        help="The root folder of your Google Photos Takeout export (or any folder in God Mode)",
        placeholder=r"e.g.  D:\Takeout\Google Photos",
    )

    structure_mode = st.radio(
        "Output Folder Structure",
        options=[
            "Original  (preserve Google album folders)",
            "Flat  (all files in one folder)",
            "By Year  (2022/, 2023/, 2024/ ...)",
            "By Year & Month  (2023/05/, 2023/06/ ...)",
        ],
        index=0,
        help="How should processed photos be organized in the output folder?",
    )

with col2:
    output_path = st.text_input(
        "Output Folder Path",
        value=r"D:\Photos_Fixed",
        help="Where to save the fixed files. Original files are never modified.",
        placeholder=r"e.g.  D:\Photos_Fixed",
    )

    conflict_mode = st.radio(
        "If a file already exists in output",
        options=[
            "Rename  (add _1, _2 ... suffix)",
            "Skip  (leave existing, useful for resuming)",
            "Overwrite  (replace existing file)",
        ],
        index=0,
        help="What to do when a file with the same name already exists in the output folder.",
    )

    st.markdown("**Advanced Options**")

    skip_dupes = st.checkbox(
        "Skip duplicate files  (MD5 hash comparison)",
        value=False,
        help="Detects identical files by content hash and skips them — saves storage space.",
    )

    use_date_filter = st.checkbox(
        "Filter by date range  (process only specific years)",
        value=False,
        help="Only process photos taken within a specific date range.",
    )

date_from_val = date_to_val = None
if use_date_filter:
    dc1, dc2 = st.columns(2)
    with dc1:
        date_from_val = st.date_input("From Date", value=None, help="Start of date range")
    with dc2:
        date_to_val = st.date_input("To Date", value=None, help="End of date range")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Scan Button
# ─────────────────────────────────────────────────────────────────────────────
scan_col, opt_col = st.columns([3, 1])
with scan_col:
    scan_btn = st.button("🔍 Scan Folder & Preview Stats", use_container_width=True)
with opt_col:
    deep_stats = st.checkbox("Full stats scan", value=True, help="Also compute year distribution and file sizes (slower for large libraries)")

if scan_btn:
    tp = Path(takeout_path)
    if not tp.exists():
        st.error(f"Path not found: `{takeout_path}`  —  Please check the folder path and try again.")
    else:
        with st.spinner("Scanning folder ..."):
            date_from_dt = datetime.combine(date_from_val, datetime.min.time()) if (use_date_filter and date_from_val) else None
            date_to_dt   = datetime.combine(date_to_val, datetime.max.time())   if (use_date_filter and date_to_val)   else None

            if god_mode:
                files = scan_folder_deep(takeout_path, date_from_dt, date_to_dt)
            else:
                files = scan_folder(takeout_path, date_from_dt, date_to_dt)

            fstats = get_folder_stats(takeout_path, deep=god_mode) if deep_stats else {}

        total   = len(files)
        matched = sum(1 for _, j in files if j)
        jpegs   = sum(1 for p, _ in files if p.suffix.lower() in JPEG_EXTS)
        videos  = sum(1 for p, _ in files if p.suffix.lower() in VIDEO_EXTS)
        others  = total - jpegs - videos

        st.session_state["scan_result"] = {
            "total":   total,
            "matched": matched,
            "jpegs":   jpegs,
            "videos":  videos,
            "others":  others,
            "no_json": total - matched,
        }
        st.session_state["folder_stats"] = fstats

# ─────────────────────────────────────────────────────────────────────────────
# Scan Results
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state["scan_result"]:
    r = st.session_state["scan_result"]

    st.markdown(
        f"""
<div class="card-header" style="margin-bottom:8px">
  <div class="card-icon icon-green">📊</div>
  <div>
    <div class="card-title">Scan Results</div>
    <div class="card-subtitle">{r['total']} media files found</div>
  </div>
</div>
<div class="metrics-row metrics-5">
  <div class="metric-box">
    <div class="metric-number" style="color:#f1f3f9">{r['total']}</div>
    <div class="metric-name">Total Files</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#22c55e">{r['jpegs']}</div>
    <div class="metric-name">JPEG / JPG</div>
    <div class="metric-note">EXIF embed</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#3b82f6">{r['videos']}</div>
    <div class="metric-name">Videos</div>
    <div class="metric-note">stream copy</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#a855f7">{r['others']}</div>
    <div class="metric-name">PNG / Other</div>
    <div class="metric-note">timestamp</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#f59e0b">{r['no_json']}</div>
    <div class="metric-name">No Sidecar</div>
    <div class="metric-note">copied as-is</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    fs = st.session_state.get("folder_stats", {})
    if fs:
        info_col, chart_col = st.columns(2, gap="large")
        with info_col:
            match_pct = round(fs.get("with_json", 0) / max(fs.get("total", 1), 1) * 100)
            st.markdown(
                f"""
<div class="card" style="margin-top:0">
  <div style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;
              letter-spacing:1.5px;margin-bottom:14px;">Storage Info</div>
  <div style="display:flex;flex-direction:column;gap:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <span style="color:var(--text-secondary);font-size:14px;">Total Size</span>
      <span style="font-family:'DM Mono',monospace;font-size:16px;font-weight:500;
                  color:var(--text-primary)">{fs.get('total_size_mb',0)} MB</span>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <span style="color:var(--text-secondary);font-size:14px;">Albums / Folders</span>
      <span style="font-family:'DM Mono',monospace;font-size:16px;font-weight:500;
                  color:var(--text-primary)">{fs.get('folders',0)}</span>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <span style="color:var(--text-secondary);font-size:14px;">JSON Match Rate</span>
      <span style="font-family:'DM Mono',monospace;font-size:16px;font-weight:500;
                  color:{'#22c55e' if match_pct>80 else '#f59e0b'}">{match_pct}%</span>
    </div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

        with chart_col:
            year_dist = fs.get("year_dist", {})
            if year_dist:
                sorted_years = sorted(year_dist.items())
                max_count    = max(v for _, v in sorted_years) if sorted_years else 1
                rows_html    = ""
                for yr, cnt in sorted_years:
                    pct = int(cnt / max_count * 100)
                    rows_html += f"""
                    <div class="year-row">
                      <span class="year-lbl">{yr}</span>
                      <div class="year-track">
                        <div class="year-fill" style="width:{pct}%"></div>
                      </div>
                      <span class="year-cnt">{cnt}</span>
                    </div>"""
                st.markdown(
                    f"""
<div class="card" style="margin-top:0">
  <div style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;
              letter-spacing:1.5px;margin-bottom:14px;">Year Distribution</div>
  <div class="year-chart">{rows_html}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Process Button
# ─────────────────────────────────────────────────────────────────────────────
process_btn = st.button(
    "⚡  Start Metadata Restoration",
    use_container_width=True,
    type="primary",
    disabled=st.session_state["processing"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Processing logic
# ─────────────────────────────────────────────────────────────────────────────
if process_btn:
    tp = Path(takeout_path)
    if not tp.exists():
        st.error(f"Source path not found: `{takeout_path}`")
    else:
        st.session_state["processing"] = True
        st.session_state["done"]       = False
        st.session_state["logs"]       = []
        st.session_state["stats"]      = None

        log_q  = queue.Queue()
        prog_q = queue.Queue()

        struct_map = {
            "Original  (preserve Google album folders)": "original",
            "Flat  (all files in one folder)":           "flat",
            "By Year  (2022/, 2023/, 2024/ ...)":        "year",
            "By Year & Month  (2023/05/, 2023/06/ ...)": "year_month",
        }
        conf_map = {
            "Rename  (add _1, _2 ... suffix)":          "rename",
            "Skip  (leave existing, useful for resuming)": "skip",
            "Overwrite  (replace existing file)":        "overwrite",
        }

        date_from_dt = datetime.combine(date_from_val, datetime.min.time()) if (use_date_filter and date_from_val) else None
        date_to_dt   = datetime.combine(date_to_val, datetime.max.time())   if (use_date_filter and date_to_val)   else None

        result_holder = {}

        def thread_target():
            result_holder["stats"] = process_all(
                takeout_root      = takeout_path,
                output_folder     = output_path,
                structure_mode    = struct_map[structure_mode],
                conflict_mode     = conf_map[conflict_mode],
                skip_duplicates   = skip_dupes,
                god_mode          = god_mode,
                date_from         = date_from_dt,
                date_to           = date_to_dt,
                progress_callback = lambda c, t, f: prog_q.put((c, t, f)),
                log_callback      = lambda m, l: log_q.put((m, l)),
            )
            prog_q.put(None)
            log_q.put(None)

        t = threading.Thread(target=thread_target, daemon=True)
        t.start()

        progress_bar  = st.progress(0)
        progress_text = st.empty()
        log_area      = st.empty()
        logs          = []
        start_time    = time.time()

        while True:
            try:
                item = prog_q.get(timeout=0.1)
                if item is None:
                    progress_bar.progress(1.0)
                    elapsed = int(time.time() - start_time)
                    progress_text.markdown(
                        f"<span style='font-family:DM Mono,monospace;font-size:13px;color:#22c55e'>"
                        f"✅ Processing complete in {elapsed}s</span>",
                        unsafe_allow_html=True,
                    )
                    break
                c, total_f, fname = item
                pct     = c / total_f if total_f else 0
                elapsed = int(time.time() - start_time)
                eta     = int(elapsed / pct * (1 - pct)) if pct > 0.01 else 0
                progress_bar.progress(pct)
                progress_text.markdown(
                    f"<span style='font-family:DM Mono,monospace;font-size:12px;color:#9ca3af'>"
                    f"[{c} / {total_f}]  "
                    f"<span style='color:#e8eaf0'>{fname}</span>  "
                    f"·  {elapsed}s  ·  ~{eta}s remaining</span>",
                    unsafe_allow_html=True,
                )
            except queue.Empty:
                pass

            while not log_q.empty():
                item = log_q.get_nowait()
                if item is None:
                    break
                logs.append(item)

            if logs:
                lines_html = ""
                for msg, lvl in logs[-150:]:
                    safe        = msg.replace("<", "&lt;").replace(">", "&gt;")
                    lines_html += f"<div class='log-{lvl}'>{safe}</div>"

                log_area.markdown(
                    f"""
<div class="terminal-wrap">
  <div class="terminal-bar">
    <div class="tb-dot tbd-r"></div>
    <div class="tb-dot tbd-y"></div>
    <div class="tb-dot tbd-g"></div>
    <span class="terminal-label">Processing Log</span>
  </div>
  <div class="terminal-body" id="tb">{lines_html}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

            if not t.is_alive():
                break

        t.join()
        st.session_state["stats"]      = result_holder.get("stats", {})
        st.session_state["logs"]       = logs
        st.session_state["processing"] = False
        st.session_state["done"]       = True

# ─────────────────────────────────────────────────────────────────────────────
# Final Results
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state["done"] and st.session_state["stats"]:
    s = st.session_state["stats"]

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="card-header" style="margin-bottom:8px">
  <div class="card-icon icon-green">🎉</div>
  <div>
    <div class="card-title">Restoration Complete</div>
    <div class="card-subtitle">Files saved to: {output_path}</div>
  </div>
</div>
<div class="metrics-row metrics-5">
  <div class="metric-box">
    <div class="metric-number" style="color:#22c55e">{s.get('jpeg_ok',0)}</div>
    <div class="metric-name">JPEG Fixed</div>
    <div class="metric-note">EXIF embedded</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#3b82f6">{s.get('video_ok',0)}</div>
    <div class="metric-name">Videos Fixed</div>
    <div class="metric-note">metadata updated</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#a855f7">{s.get('other_ok',0)}</div>
    <div class="metric-name">Other Fixed</div>
    <div class="metric-note">timestamps set</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#22c55e">{s.get('gps_added',0)}</div>
    <div class="metric-name">GPS Added</div>
    <div class="metric-note">location restored</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:{'#ef4444' if s.get('error',0) else '#22c55e'}">{s.get('error',0)}</div>
    <div class="metric-name">Errors</div>
    <div class="metric-note">{'see details below' if s.get('error',0) else 'all clean'}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if s.get("duplicates", 0) or s.get("skipped", 0):
        st.markdown(
            f"""
<div class="info-box" style="margin-top:12px">
  {f"<strong>{s['duplicates']}</strong> duplicate files were skipped (identical content). &nbsp;" if s.get('duplicates') else ""}
  {f"<strong>{s['skipped']}</strong> files were skipped (already existed in output)." if s.get('skipped') else ""}
</div>
""",
            unsafe_allow_html=True,
        )

    if s.get("err_list"):
        err_col1, err_col2 = st.columns(2)
        with err_col1:
            st.warning(f"{s['error']} errors occurred during processing.")
        with err_col2:
            if st.button("Download Error Report  (CSV)", use_container_width=True):
                try:
                    path = export_errors_csv(s["err_list"], output_path)
                    st.success(f"Saved: `{path}`")
                except Exception as e:
                    st.error(f"Could not save CSV: {e}")
        with st.expander(f"View {len(s['err_list'])} error details"):
            for name, err in s["err_list"][:100]:
                st.code(f"{name}\n{err}", language=None)
    else:
        st.success(f"All files processed successfully. Output saved to: `{output_path}`")

# ─────────────────────────────────────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state["done"]:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="card-header" style="margin-bottom:8px">
  <div class="card-icon icon-blue">🔎</div>
  <div>
    <div class="card-title">Verification</div>
    <div class="card-subtitle">Sample-check output files to confirm metadata was correctly written</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    v1, v2 = st.columns([3, 1])
    with v2:
        sample_size = st.number_input(
            "Files to check",
            min_value=10, max_value=500, value=50, step=10,
        )
    with v1:
        verify_btn = st.button("Run Verification Check", use_container_width=True)

    if verify_btn:
        op = Path(output_path)
        if not op.exists():
            st.error("Output folder not found. Please verify the output path.")
        else:
            with st.spinner("Checking files ..."):
                results = verify_output(output_path, sample=sample_size)

            if not results:
                st.warning("No files found in the output folder.")
            else:
                ok_cnt   = sum(1 for r in results if r["status"] == "ok")
                warn_cnt = sum(1 for r in results if r["status"] == "warn")
                err_cnt  = sum(1 for r in results if r["status"] == "error")
                gps_cnt  = sum(1 for r in results if r.get("has_gps"))

                st.markdown(
                    f"""
<div class="metrics-row metrics-4">
  <div class="metric-box">
    <div class="metric-number" style="color:#22c55e">{ok_cnt}</div>
    <div class="metric-name">Date OK</div>
    <div class="metric-note">metadata verified</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#f59e0b">{warn_cnt}</div>
    <div class="metric-name">No Sidecar</div>
    <div class="metric-note">copied as-is</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#ef4444">{err_cnt}</div>
    <div class="metric-name">Errors</div>
    <div class="metric-note">date not found</div>
  </div>
  <div class="metric-box">
    <div class="metric-number" style="color:#22c55e">{gps_cnt}</div>
    <div class="metric-name">GPS Present</div>
    <div class="metric-note">location data</div>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )

                rows_html = ""
                for r in results:
                    if r["status"] == "ok":
                        color, badge = "#d1fae5", "✅"
                    elif r["status"] == "warn":
                        color, badge = "#fef3c7", "⚠️"
                    else:
                        color, badge = "#fee2e2", "❌"
                    gps_icon = "📍" if r.get("has_gps") else "—"
                    safe_name = r["name"].replace("<", "&lt;").replace(">", "&gt;")
                    rows_html += f"""
<div class="vtable-row" style="color:{color}">
  <div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{safe_name}">{safe_name}</div>
  <div>{r['type']}</div>
  <div>{r['date']}</div>
  <div>{gps_icon}</div>
  <div>{badge}  {r['size_kb']}KB</div>
</div>"""

                st.markdown(
                    f"""
<div class="vtable-wrap">
  <div class="vtable-head">
    <div>File Name</div>
    <div>Type</div>
    <div>Date Found</div>
    <div>GPS</div>
    <div>Status</div>
  </div>
  {rows_html}
</div>
""",
                    unsafe_allow_html=True,
                )

# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<br><br>
<div style="text-align:center;font-family:'DM Mono',monospace;font-size:11px;
            color:#374151;padding-bottom:2rem;letter-spacing:2px;">
  PHOTOMETA RESTORER  ·  BUILT FOR RECOVERING MEMORIES
</div>
""",
    unsafe_allow_html=True,
)