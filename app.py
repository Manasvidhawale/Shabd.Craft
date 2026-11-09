"""
Shabd.Craft — Main Application Entry Point

Intelligent Prompt Engineering & Optimization Platform.
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import json
from src.config import settings
from src.database import Database
from src.schemas import PromptTemplate, FewShotExample, TaskCategory, PromptingTechnique, OutputFormat

# ── Page Config ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Shabd.Craft — Prompt Engineering Platform",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global Styles ──────────────────────────────────────────────────────

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

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
}

section[data-testid="stSidebar"] .stMarkdown h1 {
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, var(--accent-violet), var(--accent-cyan));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 16px 20px;
}

div[data-testid="stMetric"] label {
    color: var(--text-secondary) !important;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
}

div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-weight: 700;
    font-size: 1.6rem;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--bg-secondary);
    border-radius: 10px;
    padding: 4px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.stTabs [aria-selected="true"] {
    background: var(--accent-violet-dim);
    color: var(--accent-violet) !important;
}

/* Buttons */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.85rem;
    transition: all 0.2s ease;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent-violet), #6344e0);
    border: none;
    color: white;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(124, 92, 252, 0.25);
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

/* Expander */
.streamlit-expanderHeader {
    background: var(--bg-card);
    border-radius: 8px;
    border: 1px solid var(--border-color);
    font-weight: 500;
}

/* Dataframe */
.stDataFrame {
    border: 1px solid var(--border-color);
    border-radius: 8px;
}

/* Custom classes */
.shabd-hero {
    text-align: center;
    padding: 2rem 0 1.5rem;
}

.shabd-hero h1 {
    font-size: 2.6rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.15;
    background: linear-gradient(135deg, var(--accent-violet), var(--accent-cyan));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem;
}

.shabd-hero p {
    color: var(--text-secondary);
    font-size: 1.05rem;
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
    border-radius: 12px;
    padding: 1.25rem;
    margin-bottom: 1rem;
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

.mono-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
}

/* Hide default streamlit footer & header */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ── Initialize Database & State ────────────────────────────────────────

@st.cache_resource
def get_database():
    db = Database(settings.db_path)
    _seed_builtin_templates(db)
    return db


def _seed_builtin_templates(db: Database):
    """Seed built-in prompt templates on first run."""
    existing = db.get_prompt_templates(builtin_only=True)
    if existing:
        return

    data_path = Path(__file__).parent / "data" / "sample_prompts.json"
    if not data_path.exists():
        return

    with open(data_path, "r") as f:
        data = json.load(f)

    for t in data.get("builtin_templates", []):
        examples = [FewShotExample(**e) for e in t.get("few_shot_examples", [])]
        template = PromptTemplate(
            name=t["name"],
            description=t.get("description", ""),
            category=TaskCategory(t.get("category", "general")),
            system_prompt=t.get("system_prompt", ""),
            user_prompt_template=t["user_prompt_template"],
            variables=t.get("variables", []),
            technique=PromptingTechnique(t.get("technique", "zero_shot")),
            few_shot_examples=examples,
            output_format=OutputFormat(t.get("output_format", "text")),
            example_input=t.get("example_input", ""),
            example_output=t.get("example_output", ""),
            eval_criteria=t.get("eval_criteria", {}),
            is_builtin=True,
        )
        db.save_prompt_template(template)


def init_session_state():
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
db = get_database()

# ── Sidebar ────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("# ✦ Shabd.Craft")
    st.caption("Craft Better Prompts. Measure Better Intelligence.")
    st.divider()

    # Mode badge
    if settings.is_demo_mode:
        st.markdown('<span class="status-badge badge-demo">⚡ Demo Mode</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge badge-live">● Live Mode</span>', unsafe_allow_html=True)

    st.caption(f"Provider: **{settings.active_provider}** · Model: **{settings.active_model}**")
    st.divider()

# ── Main Content — Overview Dashboard ──────────────────────────────────

# Header
st.markdown("""
<div class="shabd-hero">
    <h1>Shabd.Craft</h1>
    <p>From raw instructions to tested intelligence — design, evaluate, and optimize your prompts.</p>
</div>
""", unsafe_allow_html=True)

# Quick actions
col_a, col_b, col_c = st.columns([1, 1, 1])
with col_a:
    if st.button("✦ Start Crafting", use_container_width=True, type="primary"):
        st.switch_page("pages/2_Prompt_Workshop.py")
with col_b:
    if st.button("📚 Prompt Library", use_container_width=True):
        st.switch_page("pages/7_Prompt_Library.py")
with col_c:
    if st.button("⚙ Settings", use_container_width=True):
        st.switch_page("pages/8_Settings.py")

st.markdown("")

# Dashboard Metrics
metrics = db.get_dashboard_metrics()

st.markdown('<p class="section-label">Experiment Overview</p>', unsafe_allow_html=True)
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Experiments", metrics["total_experiments"])
m2.metric("Prompt Versions", metrics["total_versions"])
m3.metric("Test Cases Run", metrics["total_test_cases"])
m4.metric("Avg Score", f"{metrics['avg_score']:.1f}" if metrics["avg_score"] else "—")
m5.metric("Optimizations", metrics["optimization_count"])
m6.metric("Best Prompt", metrics["best_prompt"][:20] + "…" if len(metrics["best_prompt"]) > 20 else (metrics["best_prompt"] or "—"))

st.markdown("")

# Charts & Recent Experiments
if metrics["total_experiments"] > 0:
    import plotly.graph_objects as go
    import plotly.express as px

    col_chart1, col_chart2 = st.columns(2)

    # Score Distribution
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

    # Criteria Averages
    criterion_avgs = db.get_criterion_averages()
    if criterion_avgs:
        with col_chart2:
            st.markdown('<p class="section-label">Evaluation Criteria Averages</p>', unsafe_allow_html=True)
            labels = [k.replace("_", " ").title() for k in criterion_avgs.keys()]
            values = list(criterion_avgs.values())
            fig = go.Figure(data=[go.Bar(
                x=labels, y=values,
                marker_color=["#7c5cfc", "#8b6fff", "#9b82ff", "#22d3ee", "#34d399"],
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

    # Recent Experiments
    st.markdown('<p class="section-label">Recent Experiments</p>', unsafe_allow_html=True)
    recent = db.get_recent_experiments(limit=8)
    if recent:
        import pandas as pd
        df = pd.DataFrame(recent)
        display_cols = {
            "name": "Experiment",
            "category": "Category",
            "status": "Status",
            "version_count": "Versions",
            "avg_score": "Avg Score",
            "updated_at": "Last Updated",
        }
        available = [c for c in display_cols.keys() if c in df.columns]
        st.dataframe(
            df[available].rename(columns={k: v for k, v in display_cols.items() if k in available}),
            use_container_width=True,
            hide_index=True,
        )

    # Performance trend
    if len(all_scores) > 1:
        st.markdown('<p class="section-label">Score Trend Across Evaluations</p>', unsafe_allow_html=True)
        import pandas as pd
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
    # Empty state
    st.markdown("")
    st.markdown("""
    <div style="text-align: center; padding: 3rem 1rem;">
        <div style="font-size: 3rem; margin-bottom: 1rem;">✦</div>
        <h3 style="color: var(--text-primary); font-weight: 600;">Welcome to Shabd.Craft</h3>
        <p style="color: var(--text-secondary); max-width: 500px; margin: 0.5rem auto 1.5rem;">
            Start by creating your first prompt experiment. Use the Prompt Workshop to craft,
            test, and refine your prompts with measurable evaluation.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("✦ Create Your First Experiment", use_container_width=True, type="primary"):
            st.switch_page("pages/2_Prompt_Workshop.py")

    # Quick-start templates
    st.markdown("")
    st.markdown('<p class="section-label">Quick-Start Templates</p>', unsafe_allow_html=True)

    templates = db.get_prompt_templates(builtin_only=True)
    if templates:
        cols = st.columns(3)
        icons = {"summarization": "📝", "extraction": "🔍", "sentiment": "💬",
                 "question_answering": "❓", "email_generation": "✉️",
                 "classification": "🏷️", "json_generation": "{ }",
                 "customer_support": "🤝", "data_analysis": "📊", "general": "📄"}
        for i, tmpl in enumerate(templates[:6]):
            with cols[i % 3]:
                icon = icons.get(tmpl["category"], "📄")
                st.markdown(f"""
                <div class="card-surface">
                    <div style="font-size: 1.5rem; margin-bottom: 0.3rem;">{icon}</div>
                    <div style="font-weight: 600; color: var(--text-primary); font-size: 0.9rem;">{tmpl['name']}</div>
                    <div style="color: var(--text-secondary); font-size: 0.78rem; margin-top: 0.2rem;">{tmpl.get('description', '')[:80]}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Use Template", key=f"qt_{tmpl['id']}", use_container_width=True):
                    st.session_state["prompt_system"] = tmpl.get("system_prompt", "")
                    st.session_state["prompt_user"] = tmpl["user_prompt_template"]
                    st.session_state["prompt_technique"] = tmpl.get("technique", "zero_shot")
                    st.session_state["prompt_output_format"] = tmpl.get("output_format", "text")
                    st.switch_page("pages/2_Prompt_Workshop.py")
