"""
Shabd.Craft — Dashboard Page

Overview metrics, charts, and recent experiment timeline.
All data sourced from SQLite.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from src.config import settings
from src.database import Database

st.set_page_config(page_title="Dashboard — Shabd.Craft", page_icon="✦", layout="wide")

@st.cache_resource
def get_db():
    return Database(settings.db_path)

db = get_db()

# ── Header ─────────────────────────────────────────────────────────────
st.markdown("## ✦ Overview Dashboard")
st.caption("Real-time metrics from your prompt engineering experiments.")
st.divider()

# ── Metrics ────────────────────────────────────────────────────────────
metrics = db.get_dashboard_metrics()

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Experiments", metrics["total_experiments"])
m2.metric("Prompt Versions", metrics["total_versions"])
m3.metric("Test Cases Run", metrics["total_test_cases"])
m4.metric("Avg Score", f"{metrics['avg_score']:.1f}" if metrics["avg_score"] else "—")
m5.metric("Optimizations", metrics["optimization_count"])
m6.metric("Best Prompt", metrics["best_prompt"][:25] if metrics["best_prompt"] else "—")

st.markdown("")

if metrics["total_experiments"] == 0:
    st.info("No experiments yet. Head to the **Prompt Workshop** to start crafting!")
    if st.button("✦ Open Prompt Workshop", type="primary"):
        st.switch_page("pages/2_Prompt_Workshop.py")
    st.stop()

# ── Charts ─────────────────────────────────────────────────────────────
all_scores = db.get_all_evaluation_scores()

col1, col2 = st.columns(2)

if all_scores:
    with col1:
        st.markdown("##### Score Distribution")
        score_values = [s["overall_score"] for s in all_scores]
        fig = go.Figure(data=[go.Histogram(
            x=score_values, nbinsx=15,
            marker_color="#7c5cfc", marker_line_color="#6344e0", marker_line_width=1,
        )])
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#9ba3b5", family="Inter"),
            xaxis_title="Score", yaxis_title="Count",
            margin=dict(l=40, r=20, t=10, b=40), height=300,
            xaxis=dict(gridcolor="#2a2d3e"), yaxis=dict(gridcolor="#2a2d3e"),
        )
        st.plotly_chart(fig, use_container_width=True)

criterion_avgs = db.get_criterion_averages()
if criterion_avgs:
    with col2:
        st.markdown("##### Evaluation Criteria Averages")
        labels = [k.replace("_", " ").title() for k in criterion_avgs.keys()]
        values = list(criterion_avgs.values())
        colors = ["#7c5cfc", "#8b6fff", "#9b82ff", "#22d3ee", "#34d399"]
        fig = go.Figure(data=[go.Bar(
            x=labels, y=values,
            marker_color=colors[:len(labels)],
            text=[f"{v:.0f}" for v in values], textposition="outside",
        )])
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#9ba3b5", family="Inter"),
            yaxis_title="Average Score",
            margin=dict(l=40, r=20, t=10, b=40), height=300,
            yaxis=dict(range=[0, 105], gridcolor="#2a2d3e"),
            xaxis=dict(gridcolor="#2a2d3e"),
        )
        st.plotly_chart(fig, use_container_width=True)

# Performance trend
if len(all_scores) > 1:
    st.markdown("##### Score Trend")
    df_sc = pd.DataFrame(all_scores).sort_values("created_at")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(df_sc))), y=df_sc["overall_score"],
        mode="lines+markers",
        line=dict(color="#7c5cfc", width=2),
        marker=dict(size=5, color="#7c5cfc"),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9ba3b5", family="Inter"),
        xaxis_title="Evaluation #", yaxis_title="Score",
        margin=dict(l=40, r=20, t=10, b=40), height=250,
        yaxis=dict(range=[0, 105], gridcolor="#2a2d3e"),
        xaxis=dict(gridcolor="#2a2d3e"),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Recent Experiments ─────────────────────────────────────────────────
st.markdown("##### Recent Experiments")
recent = db.get_recent_experiments(limit=15)
if recent:
    df = pd.DataFrame(recent)
    cols_map = {"name": "Experiment", "category": "Category", "status": "Status",
                "version_count": "Versions", "avg_score": "Avg Score", "updated_at": "Updated"}
    avail = [c for c in cols_map if c in df.columns]
    st.dataframe(df[avail].rename(columns={k: cols_map[k] for k in avail}),
                 use_container_width=True, hide_index=True)
