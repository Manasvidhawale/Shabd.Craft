"""
Shabd.Craft — Main Application Entry Point

Intelligent Prompt Engineering & Optimization Platform.
Unified navigation shell, global theme styles, and shared sidebar.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from src.config import settings
from src.ui_helpers import apply_user_settings_to_runtime
from src.ui_theme import inject_custom_fonts

_ASSETS_DIR = _ROOT / "assets"

# ── 1. Page Config (Called exactly once, first, for the entire app) ─────
st.set_page_config(
    page_title="Shabd.Craft — Prompt Engineering Platform",
    page_icon=str(_ASSETS_DIR / "icon.svg") if (_ASSETS_DIR / "icon.svg").exists() else "⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 2. Global Styles (The one deliberate font & focus ring injection) ───
inject_custom_fonts()

# ── 3. Initialize Runtime, Database & Durable State ─────────────────────
def init_session_state() -> None:
    """Initialize top-level session state defaults and deep-link query parameters."""
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

    # Restore from query parameters on initial load (Deep linking)
    qp = st.query_params
    if "exp" in qp and qp["exp"]:
        st.session_state["current_experiment_id"] = qp["exp"]
    if "ver" in qp and qp["ver"]:
        st.session_state["current_version_id"] = qp["ver"]


init_session_state()
apply_user_settings_to_runtime()

# ── 4. Brand Logo & Structured Navigation ──────────────────────────────
if (_ASSETS_DIR / "logo.svg").exists() and (_ASSETS_DIR / "icon.svg").exists():
    st.logo(str(_ASSETS_DIR / "logo.svg"), icon_image=str(_ASSETS_DIR / "icon.svg"))

workflow_pages = [
    st.Page("views/0_Home.py", title="Home", icon=":material/dashboard:", default=True, url_path="home"),
st.Page("views/1_Prompt_Workshop.py", title="Write", icon=":material/edit_note:", url_path="workshop"),
st.Page("views/2_Evaluation_Lab.py", title="Test", icon=":material/biotech:", url_path="eval-lab"),
st.Page("views/3_Prompt_Optimizer.py", title="Improve", icon=":material/auto_fix_high:", url_path="optimizer"),
st.Page("views/4_Compare_Versions.py", title="Compare", icon=":material/compare_arrows:", url_path="compare"),
]

management_pages = [
st.Page("views/8_Branches.py", title="Branches", icon=":material/account_tree:", url_path="branches"),
st.Page("views/5_Experiment_History.py", title="History", icon=":material/history:", url_path="history"),
st.Page("views/6_Prompt_Library.py", title="Templates", icon=":material/menu_book:", url_path="library"),
    st.Page("views/7_Settings.py", title="Settings", icon=":material/settings:", url_path="settings"),
]

nav = st.navigation(
    {
        "Build": workflow_pages,
        "Your work": management_pages,
    },
    position="sidebar",
)

nav.run()
