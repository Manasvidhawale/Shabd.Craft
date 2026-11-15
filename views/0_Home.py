"""
Shabd.Craft — Workspace Overview (Home)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.ui_helpers import (
    clear_workshop_widgets,
    get_database,
    load_template_into_workshop,
    load_version_into_workshop,
    render_page_header,
)

db = get_database()

render_page_header("Workspace Overview", "Create prompts, run evaluations, and review experiment performance.")

# ── Quick Actions ──────────────────────────────────────────────────────
qa1, qa2, qa3, qa4 = st.columns(4)
with qa1:
    if st.button("+ New Prompt", use_container_width=True, type="primary"):
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
    if st.button("Prompt Library", use_container_width=True):
        st.switch_page("views/6_Prompt_Library.py")
with qa3:
    if st.button("Evaluation Lab", use_container_width=True):
        st.switch_page("views/2_Evaluation_Lab.py")
with qa4:
    if st.button("Settings", use_container_width=True):
        st.switch_page("views/7_Settings.py")

st.markdown("")

# ── Workspace Metrics ──────────────────────────────────────────────────
metrics = db.get_dashboard_metrics()

st.markdown('<p class="section-label">Workspace Summary</p>', unsafe_allow_html=True)
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Prompts", metrics["total_experiments"])
m2.metric("Versions", metrics["total_versions"])
m3.metric("Tests Run", metrics["total_test_cases"])
m4.metric("Avg Score", f"{metrics['avg_score']:.1f}" if metrics["avg_score"] else "—")
m5.metric("Optimizations", metrics["optimization_count"])
best_name = metrics["best_prompt"]
m6.metric("Top Score", (best_name[:18] + "…") if len(best_name) > 18 else (best_name or "—"))

st.markdown("")

if metrics["total_experiments"] > 0:
    st.markdown('<p class="section-label">Active Prompts</p>', unsafe_allow_html=True)
    recent = db.get_recent_experiments(limit=6)
    for exp in recent:
        versions = db.get_prompt_versions(exp["id"])
        avg_sc = exp.get("avg_score")
        score_text = f"Avg {avg_sc:.1f}" if avg_sc is not None else "Not evaluated"
        c_info, c_act1, c_act2 = st.columns([4, 1, 1])
        with c_info:
            st.markdown(
                f"**{exp['name']}** · {exp['category'].replace('_', ' ').title()} "
                f"· {len(versions)} version(s) · `{score_text}`"
            )
        with c_act1:
            if versions and st.button("Edit", key=f"home_edit_{exp['id']}", use_container_width=True):
                load_version_into_workshop(db, exp, versions[-1])
                st.switch_page("views/1_Prompt_Workshop.py")
        with c_act2:
            if st.button("Evaluate", key=f"home_eval_{exp['id']}", use_container_width=True):
                st.session_state["current_experiment_id"] = exp["id"]
                if versions:
                    st.session_state["current_version_id"] = versions[-1]["id"]
                st.switch_page("views/2_Evaluation_Lab.py")

    st.markdown("")
    col_chart1, col_chart2 = st.columns(2)

    all_scores = db.get_all_evaluation_scores()
    if all_scores:
        with col_chart1:
            st.markdown('<p class="section-label">Score Distribution</p>', unsafe_allow_html=True)
            score_values = [s["overall_score"] for s in all_scores]
            fig = go.Figure(data=[go.Histogram(
                x=score_values, nbinsx=20,
                marker_color="#7c5cfc",
                marker_line_color="#6344e0",
                marker_line_width=1,
            )])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#9ba3b5", family="Inter"),
                xaxis_title="Score",
                yaxis_title="Count",
                margin=dict(l=40, r=20, t=20, b=40),
                height=260,
                xaxis=dict(gridcolor="#2a2d3e"),
                yaxis=dict(gridcolor="#2a2d3e"),
            )
            st.plotly_chart(fig, use_container_width=True)

    criterion_avgs = db.get_criterion_averages()
    if criterion_avgs:
        with col_chart2:
            st.markdown('<p class="section-label">Criteria Averages</p>', unsafe_allow_html=True)
            labels = [k.replace("_", " ").title() for k in criterion_avgs.keys()]
            values = list(criterion_avgs.values())
            fig = go.Figure(data=[go.Bar(
                x=labels, y=values,
                marker_color=["#7c5cfc", "#8b6fff", "#9b82ff", "#22d3ee", "#34d399"][:len(labels)],
                text=[f"{v:.0f}" for v in values],
                textposition="outside",
            )])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#9ba3b5", family="Inter"),
                yaxis_title="Average Score",
                margin=dict(l=40, r=20, t=20, b=40),
                height=260,
                yaxis=dict(range=[0, 105], gridcolor="#2a2d3e"),
                xaxis=dict(gridcolor="#2a2d3e"),
            )
            st.plotly_chart(fig, use_container_width=True)
else:
    st.markdown('<p class="section-label">Starter Prompts</p>', unsafe_allow_html=True)
    st.caption("Open a starter prompt in the Workshop or create your own from scratch.")

    templates = db.get_prompt_templates()[:6]
    if templates:
        cols = st.columns(3, gap="medium")
        for i, tmpl in enumerate(templates):
            with cols[i % 3]:
                cat_label = tmpl["category"].replace("_", " ").upper()
                desc = tmpl.get("description", "")
                desc_short = (desc[:85] + "...") if len(desc) > 85 else desc
                st.markdown(f"""
                <div class="card-surface" style="min-height:118px;">
                    <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent-cyan); margin-bottom: 0.35rem;">{cat_label}</div>
                    <div style="font-weight: 600; color: var(--text-primary); font-size: 0.92rem;">{tmpl['name']}</div>
                    <div style="color: var(--text-secondary); font-size: 0.78rem; margin-top: 0.25rem;">{desc_short}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Open in Workshop", key=f"qt_{tmpl['id']}", use_container_width=True):
                    load_template_into_workshop(tmpl)
                    st.switch_page("views/1_Prompt_Workshop.py")
    else:
        st.info("Your workspace is empty. Click '+ New Prompt' above to get started.")
