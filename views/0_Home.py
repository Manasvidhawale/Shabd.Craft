"""
Shabd.Craft — Workspace Overview (Home)

System status, workspace metrics, quick navigation, and active prompt experiments.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import plotly.graph_objects as go
import streamlit as st

from src.ui_helpers import (
    clear_workshop_widgets,
    get_database,
    load_template_into_workshop,
    load_version_into_workshop,
    render_page_header,
)
from src.ui_theme import status_badge

db = get_database()

render_page_header("Workspace Overview", "Create prompts, run evaluations, and review experiment performance.")

def _nav_link(page_path: str, label: str, icon: str) -> None:
    """Render page_link with graceful fallback for standalone execution."""
    try:
        st.page_link(page_path, label=label, icon=icon, use_container_width=True)
    except Exception:
        alt_path = Path(page_path).name
        try:
            st.page_link(alt_path, label=label, icon=icon, use_container_width=True)
        except Exception:
            if st.button(label, use_container_width=True):
                st.switch_page(page_path)

with st.container(border=True):
    qa1, qa2, qa3, qa4 = st.columns(4)
    with qa1:
        if st.button(":material/add_circle: New Prompt", use_container_width=True, type="primary"):
            st.session_state["ws_editing_exp_id"] = None
            st.session_state["ws_editing_ver_id"] = None
            st.session_state["ws_exp_name"] = ""
            st.session_state["ws_system"] = ""
            st.session_state["ws_user"] = ""
            st.session_state["ws_sample_input"] = ""
            st.session_state["ws_expected"] = ""
            st.session_state["ws_few_shots"] = []
            st.session_state["ws_last_response"] = None
            clear_workshop_widgets()
            st.switch_page("views/1_Prompt_Workshop.py")
    with qa2:
        _nav_link("views/6_Prompt_Library.py", "Prompt Library", ":material/menu_book:")
    with qa3:
        _nav_link("views/2_Evaluation_Lab.py", "Evaluation Lab", ":material/biotech:")
    with qa4:
        _nav_link("views/7_Settings.py", "Settings", ":material/settings:")

st.markdown("")

# ── Workspace Metrics (3 Columns x 2 Rows) ─────────────────────────────
metrics = db.get_dashboard_metrics()

st.markdown("##### Workspace Summary")
m1, m2, m3 = st.columns(3)
with m1:
    with st.container(border=True):
        st.metric("Active Prompts", metrics["total_experiments"])
with m2:
    with st.container(border=True):
        st.metric("Prompt Versions", metrics["total_versions"])
with m3:
    with st.container(border=True):
        st.metric("Test Runs", metrics["total_test_cases"])

m4, m5, m6 = st.columns(3)
with m4:
    with st.container(border=True):
        st.metric("Average Quality", f"{metrics['avg_score']:.1f}%" if metrics["avg_score"] else "—")
with m5:
    with st.container(border=True):
        st.metric("AI Optimizations", metrics["optimization_count"])
with m6:
    with st.container(border=True):
        best_name = metrics["best_prompt"]
        st.metric("Top Benchmark", (best_name[:18] + "…") if len(best_name) > 18 else (best_name or "—"))

st.markdown("")

if metrics["total_experiments"] > 0:
    st.markdown("##### Active Prompts")
    recent = db.get_recent_experiments(limit=6)
    for exp in recent:
        versions = db.get_prompt_versions(exp["id"])
        avg_sc = exp.get("avg_score")
        score_text = f"Avg {avg_sc:.1f}%" if avg_sc is not None else "Not evaluated"

        with st.container(border=True):
            c_info, c_act1, c_act2 = st.columns([4, 1, 1])
            with c_info:
                st.markdown(
                    f"**{exp['name']}** · {exp['category'].replace('_', ' ').title()} "
                    f"· {len(versions)} version(s) · `{score_text}`"
                )
            with c_act1:
                if versions and st.button(":material/edit: Edit", key=f"home_edit_{exp['id']}", use_container_width=True):
                    load_version_into_workshop(db, exp, versions[-1])
                    st.switch_page(f"{_p_prefix}1_Prompt_Workshop.py")
            with c_act2:
                if st.button(":material/biotech: Eval", key=f"home_eval_{exp['id']}", use_container_width=True):
                    st.session_state["current_experiment_id"] = exp["id"]
                    if versions:
                        st.session_state["current_version_id"] = versions[-1]["id"]
                    st.switch_page(f"{_p_prefix}2_Evaluation_Lab.py")

    st.markdown("")
    col_chart1, col_chart2 = st.columns(2)

    all_scores = db.get_all_evaluation_scores()
    if all_scores:
        with col_chart1:
            with st.container(border=True):
                st.markdown("##### Score Distribution")
                score_values = [s["overall_score"] for s in all_scores]
                fig = go.Figure(data=[go.Histogram(
                    x=score_values, nbinsx=20,
                    marker_color="#9b84ff",
                    marker_line_color="#6842e3",
                    marker_line_width=1,
                )])
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#9ba3b5", family="Inter"),
                    xaxis_title="Score (%)",
                    yaxis_title="Count",
                    margin=dict(l=40, r=20, t=20, b=40),
                    height=240,
                    xaxis=dict(gridcolor="#2a2d3e"),
                    yaxis=dict(gridcolor="#2a2d3e"),
                )
                st.plotly_chart(fig, use_container_width=True)

    criterion_avgs = db.get_criterion_averages()
    if criterion_avgs:
        with col_chart2:
            with st.container(border=True):
                st.markdown("##### Criteria Averages")
                labels = [k.replace("_", " ").title() for k in criterion_avgs.keys()]
                values = list(criterion_avgs.values())
                fig = go.Figure(data=[go.Bar(
                    x=labels, y=values,
                    marker_color=["#9b84ff", "#8b6fff", "#7c5cfc", "#22d3ee", "#34d399"][:len(labels)],
                    text=[f"{v:.0f}%" for v in values],
                    textposition="outside",
                )])
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#9ba3b5", family="Inter"),
                    yaxis_title="Average Score (%)",
                    margin=dict(l=40, r=20, t=20, b=40),
                    height=240,
                    yaxis=dict(range=[0, 105], gridcolor="#2a2d3e"),
                    xaxis=dict(gridcolor="#2a2d3e"),
                )
                st.plotly_chart(fig, use_container_width=True)
else:
    st.markdown("##### Starter Prompts")
    st.caption("Load a curated starter prompt into the workshop or create one from scratch.")

    templates = db.get_prompt_templates()[:6]
    if templates:
        cols = st.columns(3, gap="medium")
        for i, tmpl in enumerate(templates):
            with cols[i % 3]:
                with st.container(border=True):
                    cat_label = tmpl["category"].replace("_", " ").upper()
                    st.caption(f":material/tag: {cat_label}")
                    st.markdown(f"**{tmpl['name']}**")
                    desc = tmpl.get("description", "")
                    st.caption((desc[:75] + "…") if len(desc) > 75 else desc)
                    if st.button(":material/edit_note: Open in Workshop", key=f"qt_{tmpl['id']}", use_container_width=True):
                        load_template_into_workshop(tmpl)
                        st.switch_page(f"{_p_prefix}1_Prompt_Workshop.py")
    else:
        st.info(":material/info: Your workspace is empty. Click '+ New Prompt' above to get started.")
