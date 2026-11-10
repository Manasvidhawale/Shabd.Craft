"""
Shabd.Craft — Home & Overview Dashboard
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.ui_helpers import get_database, load_template_into_workshop

db = get_database()

# ── Hero & Quick Actions ───────────────────────────────────────────────
st.markdown("""
<div class="shabd-hero">
    <h1>Shabd.Craft</h1>
    <p>From raw instructions to tested intelligence — design, evaluate, and optimize your prompts.</p>
</div>
""", unsafe_allow_html=True)

col_a, col_b, col_c = st.columns(3)
with col_a:
    if st.button("Start Crafting", use_container_width=True, type="primary"):
        st.switch_page("views/1_Prompt_Workshop.py")
with col_b:
    if st.button("Prompt Library", use_container_width=True):
        st.switch_page("views/6_Prompt_Library.py")
with col_c:
    if st.button("Settings", use_container_width=True):
        st.switch_page("views/7_Settings.py")

st.markdown("""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:1rem 0 1.25rem;">
    <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px 14px;">
        <div style="font-size:0.68rem;font-weight:600;color:var(--accent-violet);letter-spacing:0.06em;">STEP 1</div>
        <div style="font-size:0.88rem;font-weight:600;color:var(--text-primary);margin-top:2px;">Prompt Workshop</div>
        <div style="font-size:0.75rem;color:var(--text-secondary);">Craft and test prompt templates</div>
    </div>
    <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px 14px;">
        <div style="font-size:0.68rem;font-weight:600;color:var(--accent-violet);letter-spacing:0.06em;">STEP 2</div>
        <div style="font-size:0.88rem;font-weight:600;color:var(--text-primary);margin-top:2px;">Evaluation Lab</div>
        <div style="font-size:0.75rem;color:var(--text-secondary);">Run datasets and security checks</div>
    </div>
    <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px 14px;">
        <div style="font-size:0.68rem;font-weight:600;color:var(--accent-violet);letter-spacing:0.06em;">STEP 3</div>
        <div style="font-size:0.88rem;font-weight:600;color:var(--text-primary);margin-top:2px;">Prompt Optimizer</div>
        <div style="font-size:0.75rem;color:var(--text-secondary);">Generate and test candidates</div>
    </div>
    <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px 14px;">
        <div style="font-size:0.68rem;font-weight:600;color:var(--accent-violet);letter-spacing:0.06em;">STEP 4</div>
        <div style="font-size:0.88rem;font-weight:600;color:var(--text-primary);margin-top:2px;">Compare Versions</div>
        <div style="font-size:0.75rem;color:var(--text-secondary);">Review diffs and pick winner</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Dashboard Metrics ──────────────────────────────────────────────────
metrics = db.get_dashboard_metrics()

st.markdown('<p class="section-label">Experiment Overview</p>', unsafe_allow_html=True)
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Experiments", metrics["total_experiments"])
m2.metric("Prompt Versions", metrics["total_versions"])
m3.metric("Test Cases Run", metrics["total_test_cases"])
m4.metric("Avg Score", f"{metrics['avg_score']:.1f}" if metrics["avg_score"] else "—")
m5.metric("Optimizations", metrics["optimization_count"])
best_name = metrics["best_prompt"]
m6.metric("Best Prompt", (best_name[:18] + "…") if len(best_name) > 18 else (best_name or "—"))

st.markdown("")

# ── Charts & Recent Experiments OR Quick-Start Templates ───────────────
if metrics["total_experiments"] > 0:
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
                height=280,
                xaxis=dict(gridcolor="#2a2d3e"),
                yaxis=dict(gridcolor="#2a2d3e"),
            )
            st.plotly_chart(fig, use_container_width=True)

    criterion_avgs = db.get_criterion_averages()
    if criterion_avgs:
        with col_chart2:
            st.markdown('<p class="section-label">Evaluation Criteria Averages</p>', unsafe_allow_html=True)
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
                height=280,
                yaxis=dict(range=[0, 105], gridcolor="#2a2d3e"),
                xaxis=dict(gridcolor="#2a2d3e"),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown('<p class="section-label">Recent Experiments</p>', unsafe_allow_html=True)
    recent = db.get_recent_experiments(limit=8)
    if recent:
        df = pd.DataFrame(recent)
        display_cols = {
            "name": "Experiment",
            "category": "Category",
            "status": "Status",
            "version_count": "Versions",
            "avg_score": "Avg Score",
            "updated_at": "Last Updated",
        }
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available].rename(columns={k: display_cols[k] for k in available}),
            use_container_width=True,
            hide_index=True,
        )

    if len(all_scores) > 1:
        st.markdown('<p class="section-label">Score Trend Across Evaluations</p>', unsafe_allow_html=True)
        df_scores = pd.DataFrame(all_scores)
        if "created_at" in df_scores.columns:
            df_scores = df_scores.sort_values("created_at")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(len(df_scores))),
                y=df_scores["overall_score"],
                mode="lines+markers",
                line=dict(color="#7c5cfc", width=2),
                marker=dict(size=6, color="#7c5cfc"),
                name="Score",
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#9ba3b5", family="Inter"),
                xaxis_title="Evaluation Sequence",
                yaxis_title="Score",
                margin=dict(l=40, r=20, t=20, b=40),
                height=250,
                yaxis=dict(range=[0, 105], gridcolor="#2a2d3e"),
                xaxis=dict(gridcolor="#2a2d3e"),
            )
            st.plotly_chart(fig, use_container_width=True)
else:
    st.markdown('<p class="section-label">Quick-Start Templates</p>', unsafe_allow_html=True)
    st.caption("Pick a built-in template below to jump straight into the Prompt Workshop, or click Start Crafting above.")

    templates = db.get_prompt_templates(builtin_only=True)
    if templates:
        cols = st.columns(3)
        for i, tmpl in enumerate(templates[:6]):
            with cols[i % 3]:
                cat_label = tmpl["category"].replace("_", " ").upper()
                st.markdown(f"""
                <div class="card-surface" style="min-height:112px;">
                    <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent-cyan); margin-bottom: 0.35rem;">{cat_label}</div>
                    <div style="font-weight: 600; color: var(--text-primary); font-size: 0.92rem;">{tmpl['name']}</div>
                    <div style="color: var(--text-secondary); font-size: 0.78rem; margin-top: 0.25rem;">{tmpl.get('description', '')[:80]}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Use Template", key=f"qt_{tmpl['id']}", use_container_width=True):
                    load_template_into_workshop(tmpl)
                    st.switch_page("views/1_Prompt_Workshop.py")
