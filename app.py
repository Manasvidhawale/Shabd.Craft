"""
Shabd.Craft — Main Application Entry Point

Intelligent Prompt Engineering & Optimization Platform.
Unified navigation shell, global theme styles, and shared sidebar.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from src.config import settings
from src.ui_helpers import get_database, apply_user_settings_to_runtime

_ASSETS_DIR = Path(__file__).parent / "assets"

# ── Page Config (called once for the whole app) ────────────────────────
st.set_page_config(
    page_title="Shabd.Craft — Prompt Engineering Platform",
    page_icon=str(_ASSETS_DIR / "icon.svg"),
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global Styles (applied consistently across every page) ─────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-primary: #0f1117;
    --bg-secondary: #1a1d29;
    --bg-card: #1e2130;
    --bg-card-hover: #252840;
    --accent-violet: #7c5cfc;
    --accent-violet-dim: rgba(124, 92, 252, 0.15);
    --accent-cyan: #22d3ee;
    --accent-cyan-dim: rgba(34, 211, 238, 0.12);
    --text-primary: #e8eaed;
    --text-secondary: #9ba3b5;
    --text-muted: #6b7280;
    --border-color: #2a2d3e;
    --success: #34d399;
    --warning: #fbbf24;
    --error: #f87171;
}

/* Global */
.stApp {
    background-color: var(--bg-primary);
    font-family: 'Inter', -apple-system, sans-serif;
}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2.5rem !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
}

[data-testid="stSidebarNav"] {
    padding-top: 0.25rem !important;
}

[data-testid="stSidebarNavItems"] {
    max-height: none !important;
    overflow-y: visible !important;
}

[data-testid="stSidebarNavSeparator"] {
    margin: 0.4rem 0 !important;
}

section[data-testid="stSidebar"] details[data-testid="stExpander"] {
    background: transparent !important;
    border: none !important;
    margin-bottom: 0.2rem;
}

section[data-testid="stSidebar"] details[data-testid="stExpander"] summary {
    padding: 0.35rem 0.4rem !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary) !important;
}

section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
    padding: 0.35rem 0.65rem !important;
    border-radius: 8px !important;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 14px 18px;
}

div[data-testid="stMetric"] label {
    color: var(--text-secondary) !important;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
}

div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-weight: 700;
    font-size: 1.5rem;
}

/* Tabs: override default red highlight bar with accent violet */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--bg-secondary);
    border-radius: 10px;
    padding: 4px;
    border: 1px solid var(--border-color);
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.85rem;
    color: var(--text-secondary);
    padding: 6px 14px;
}

.stTabs [aria-selected="true"] {
    background: var(--accent-violet-dim);
    color: var(--text-primary) !important;
}

.stTabs [data-baseweb="tab-highlight"] {
    background-color: var(--accent-violet) !important;
}

/* Buttons */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.85rem;
    border-color: var(--border-color);
    transition: all 0.15s ease;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent-violet), #6344e0);
    border: none;
    color: white;
}

.stButton > button:hover {
    border-color: var(--accent-violet);
}

/* Text inputs and areas */
.stTextInput > div > div, .stTextArea > div > div {
    border-color: var(--border-color);
    border-radius: 8px;
    background: var(--bg-card);
}

.stTextInput > div > div:focus-within, .stTextArea > div > div:focus-within {
    border-color: var(--accent-violet);
    box-shadow: 0 0 0 2px var(--accent-violet-dim);
}

/* Select boxes */
.stSelectbox > div > div {
    border-color: var(--border-color);
    border-radius: 8px;
    background: var(--bg-card);
}

/* Progress bar */
.stProgress > div > div > div > div {
    background-color: var(--accent-violet);
}

/* Expander */
details[data-testid="stExpander"] {
    background: var(--bg-card);
    border-radius: 10px;
    border: 1px solid var(--border-color);
}

/* Dataframe */
.stDataFrame {
    border: 1px solid var(--border-color);
    border-radius: 8px;
}

/* Custom classes */
.shabd-hero {
    text-align: center;
    padding: 1.25rem 0 1rem;
}

.shabd-hero h1 {
    font-size: 2.3rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.15;
    background: linear-gradient(135deg, var(--accent-violet), var(--accent-cyan));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.4rem;
}

.shabd-hero p {
    color: var(--text-secondary);
    font-size: 1rem;
    max-width: 600px;
    margin: 0 auto;
    font-weight: 400;
}

.status-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.badge-demo {
    background: rgba(251, 191, 36, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3);
}

.badge-live {
    background: rgba(52, 211, 153, 0.15);
    color: #34d399;
    border: 1px solid rgba(52, 211, 153, 0.3);
}

.card-surface {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 1.1rem;
    margin-bottom: 0.6rem;
}

.card-surface:hover {
    border-color: var(--accent-violet);
    background: var(--bg-card-hover);
}

.score-display {
    font-size: 2rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}

.score-good { color: #34d399; }
.score-mid { color: #fbbf24; }
.score-low { color: #f87171; }

.section-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
}

/* Keep sidebar toggle accessible while hiding Deploy button & footer */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stAppDeployButton"] {display: none;}
[data-testid="stHeader"] {background: transparent;}
</style>
""", unsafe_allow_html=True)

# ── Initialize Database & State ────────────────────────────────────────
def init_session_state() -> None:
    """Initialize session state with defaults."""
    defaults = {
        "current_experiment_id": None,
        "current_version_id": None,
        "prompt_system": "",
        "prompt_user": "",
        "prompt_technique": "zero_shot",
        "prompt_output_format": "text",
        "prompt_temperature": 0.7,
        "prompt_max_tokens": 1024,
        "few_shot_examples": [],
        "last_response": None,
        "eval_results": [],
        "optimization_candidates": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()
apply_user_settings_to_runtime()
get_database()

# ── Top-left Brand Logo & Navigation ───────────────────────────────────
st.logo(str(_ASSETS_DIR / "logo.svg"), icon_image=str(_ASSETS_DIR / "icon.svg"))

workflow_pages = [
    st.Page("views/0_Home.py", title="Home", default=True),
    st.Page("views/1_Prompt_Workshop.py", title="Prompt Workshop"),
    st.Page("views/2_Evaluation_Lab.py", title="Evaluation Lab"),
    st.Page("views/3_Prompt_Optimizer.py", title="Prompt Optimizer"),
    st.Page("views/4_Compare_Versions.py", title="Compare Versions"),
]
manage_pages = [
    st.Page("views/5_Experiment_History.py", title="Experiment History"),
    st.Page("views/6_Prompt_Library.py", title="Prompt Library"),
    st.Page("views/7_Settings.py", title="Settings"),
]

pg = st.navigation(workflow_pages + manage_pages, position="hidden")

with st.sidebar:
    with st.expander("Workflow", expanded=True):
        for p in workflow_pages:
            st.page_link(p, label=p.title)
    with st.expander("Manage", expanded=True):
        for p in manage_pages:
            st.page_link(p, label=p.title)

pg.run()
