"""
Shabd.Craft — Compare Versions

Side-by-side comparison of prompt versions on shared test cases.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
from src.ui_helpers import (
    get_database,
    render_empty_experiment_state,
    render_page_header,
)
from src.comparison_engine import (
    compare_versions, get_side_by_side_outputs, build_word_diff_html,
)

db = get_database()

render_page_header("Compare Versions", "Inspect word-level prompt changes, metric deltas, and test case outputs.")

# ── Select experiment ──────────────────────────────────────────────────
experiments = db.list_experiments()
if not experiments:
    render_empty_experiment_state("No prompts available yet. Create one in the Prompt Workshop.")
    st.stop()

exp_opts = {e["id"]: f"{e['name']} ({e['category'].replace('_', ' ').title()})" for e in experiments}
default_exp = st.session_state.get("current_experiment_id", experiments[0]["id"])
if default_exp not in exp_opts:
    default_exp = experiments[0]["id"]
sel_exp = st.selectbox("Experiment", list(exp_opts.keys()),
                       format_func=lambda x: exp_opts[x],
                       index=list(exp_opts.keys()).index(default_exp))
st.session_state["current_experiment_id"] = sel_exp

versions = db.get_prompt_versions(sel_exp)
if len(versions) < 2:
    st.info("This experiment only has 1 prompt version. Save a second version in Prompt Workshop or generate candidates in Prompt Optimizer to compare.")
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Add Version in Workshop", type="primary", use_container_width=True):
            st.switch_page("views/1_Prompt_Workshop.py")
    with cb2:
        if st.button("Open Prompt Optimizer", use_container_width=True):
            st.switch_page("views/3_Prompt_Optimizer.py")
    st.stop()

# ── Select two versions ───────────────────────────────────────────────
ver_opts = {v["id"]: f"v{v['version_number']}: {v['version_label']}" for v in versions}

c1, c2 = st.columns(2)
with c1:
    ver_a = st.selectbox("Version A", list(ver_opts.keys()), format_func=lambda x: ver_opts[x], index=0)
with c2:
    idx_b = min(1, len(versions) - 1)
    ver_b = st.selectbox("Version B", list(ver_opts.keys()), format_func=lambda x: ver_opts[x], index=idx_b)

if ver_a == ver_b:
    st.warning("Select two different versions to compare.")
    st.stop()

va_data = db.get_prompt_version(ver_a)
vb_data = db.get_prompt_version(ver_b)

st.divider()

# ── A. Side-by-Side & Word-Level Diff ──────────────────────────────────
st.markdown("##### Prompt Comparison")

tab_diff, tab_side = st.tabs(["Inline Diff (A -> B)", "Side-by-Side"])

with tab_diff:
    st.caption("Red strikethrough = removed from Version A | Green highlight = added in Version B")
    sys_a = va_data.get("system_prompt", "") or ""
    sys_b = vb_data.get("system_prompt", "") or ""
    if sys_a or sys_b:
        st.markdown("**System Prompt Diff:**")
        if sys_a == sys_b:
            st.caption("No changes in system prompt.")
        else:
            st.markdown(build_word_diff_html(sys_a, sys_b), unsafe_allow_html=True)

    st.markdown("**User Prompt Diff:**")
    usr_a = va_data.get("user_prompt_template", "") or ""
    usr_b = vb_data.get("user_prompt_template", "") or ""
    if usr_a == usr_b:
        st.caption("No changes in user prompt template.")
    else:
        st.markdown(build_word_diff_html(usr_a, usr_b), unsafe_allow_html=True)

with tab_side:
    pa, pb = st.columns(2)
    with pa:
        st.markdown(f"**{ver_opts[ver_a]}**")
        if va_data.get("system_prompt"):
            st.caption("System:")
            st.code(va_data["system_prompt"], language="text")
        st.caption("User Prompt:")
        st.code(va_data["user_prompt_template"], language="text")

    with pb:
        st.markdown(f"**{ver_opts[ver_b]}**")
        if vb_data.get("system_prompt"):
            st.caption("System:")
            st.code(vb_data["system_prompt"], language="text")
        st.caption("User Prompt:")
        st.code(vb_data["user_prompt_template"], language="text")

# ── Get results ────────────────────────────────────────────────────────
results_a = db.get_evaluation_results(sel_exp, ver_a)
results_b = db.get_evaluation_results(sel_exp, ver_b)

if not results_a and not results_b:
    st.info("No evaluation results available. Run evaluations in the Evaluation Lab first.")
    st.stop()

# ── B. Score Comparison ────────────────────────────────────────────────
comparison = compare_versions(va_data, vb_data, results_a, results_b)

st.markdown("##### Score Comparison")
sc1, sc2, sc3 = st.columns(3)
with sc1:
    score_class = "score-good" if comparison.version_a_overall >= 70 else ("score-mid" if comparison.version_a_overall >= 50 else "score-low")
    st.markdown(f"**{comparison.version_a_label}**")
    st.markdown(f'<span class="score-display {score_class}">{comparison.version_a_overall:.1f}</span>', unsafe_allow_html=True)
with sc2:
    score_class = "score-good" if comparison.version_b_overall >= 70 else ("score-mid" if comparison.version_b_overall >= 50 else "score-low")
    st.markdown(f"**{comparison.version_b_label}**")
    st.markdown(f'<span class="score-display {score_class}">{comparison.version_b_overall:.1f}</span>', unsafe_allow_html=True)
with sc3:
    diff = comparison.version_a_overall - comparison.version_b_overall
    st.markdown("**Difference**")
    if diff > 0:
        st.markdown(f"<span style='color:#34d399;font-size:1.5rem;font-weight:700;'>+{diff:.1f}</span> ({comparison.version_a_label})", unsafe_allow_html=True)
    elif diff < 0:
        st.markdown(f"<span style='color:#34d399;font-size:1.5rem;font-weight:700;'>+{-diff:.1f}</span> ({comparison.version_b_label})", unsafe_allow_html=True)
    else:
        st.markdown("<span style='color:#9ba3b5;font-size:1.5rem;font-weight:700;'>Tied</span>", unsafe_allow_html=True)

# ── C. Criterion Chart ─────────────────────────────────────────────────
if comparison.version_a_scores and comparison.version_b_scores:
    st.markdown("##### Criterion Performance")
    criteria = list(set(list(comparison.version_a_scores.keys()) + list(comparison.version_b_scores.keys())))
    labels = [c.replace("_", " ").title() for c in criteria]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=comparison.version_a_label,
        x=labels,
        y=[comparison.version_a_scores.get(c, 0) for c in criteria],
        marker_color="#7c5cfc",
    ))
    fig.add_trace(go.Bar(
        name=comparison.version_b_label,
        x=labels,
        y=[comparison.version_b_scores.get(c, 0) for c in criteria],
        marker_color="#22d3ee",
    ))
    fig.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9ba3b5"),
        yaxis=dict(range=[0, 105], gridcolor="#2a2d3e", title="Score"),
        xaxis=dict(gridcolor="#2a2d3e"),
        margin=dict(l=40, r=20, t=10, b=40), height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── D. Response Comparison ─────────────────────────────────────────────
side_by_side = get_side_by_side_outputs(results_a, results_b)
if side_by_side:
    tc_map = {tc["id"]: tc.get("input_data", "") for tc in db.get_test_cases(sel_exp)}
    st.markdown("##### Output Comparison (by test case)")
    for idx, row in enumerate(side_by_side[:10], 1):
        tc_preview = tc_map.get(row["test_case_id"], "").replace("\n", " ")
        tc_label = (tc_preview[:55] + "…") if len(tc_preview) > 55 else (tc_preview or f"Case {idx}")
        with st.expander(f"TC {idx}: {tc_label} — A: {row['score_a']:.0f} vs B: {row['score_b']:.0f}"):
            oa, ob = st.columns(2)
            with oa:
                st.markdown(f"**{comparison.version_a_label}** (Score: {row['score_a']:.1f})")
                st.code(row["output_a"][:500] if row["output_a"] else "—", language="text")
            with ob:
                st.markdown(f"**{comparison.version_b_label}** (Score: {row['score_b']:.1f})")
                st.code(row["output_b"][:500] if row["output_b"] else "—", language="text")

# ── E. Efficiency ──────────────────────────────────────────────────────
if results_a or results_b:
    st.markdown("##### Efficiency Metrics")
    succ_a = [r for r in results_a if r.get("execution_status") == "success"]
    succ_b = [r for r in results_b if r.get("execution_status") == "success"]

    avg_lat_a = round(sum(r.get("latency_ms", 0) for r in succ_a) / len(succ_a), 0) if succ_a else 0
    avg_lat_b = round(sum(r.get("latency_ms", 0) for r in succ_b) / len(succ_b), 0) if succ_b else 0
    avg_tok_a = round(sum(r.get("tokens_used", 0) for r in succ_a) / len(succ_a), 0) if succ_a else 0
    avg_tok_b = round(sum(r.get("tokens_used", 0) for r in succ_b) / len(succ_b), 0) if succ_b else 0

    ef1, ef2, ef3, ef4 = st.columns(4)
    ef1.metric(f"{comparison.version_a_label} Latency", f"{avg_lat_a:.0f}ms")
    ef2.metric(f"{comparison.version_b_label} Latency", f"{avg_lat_b:.0f}ms")
    ef3.metric(f"{comparison.version_a_label} Tokens", f"{avg_tok_a:.0f}")
    ef4.metric(f"{comparison.version_b_label} Tokens", f"{avg_tok_b:.0f}")

# ── F. Recommendation ─────────────────────────────────────────────────
st.divider()
st.markdown("##### Recommendation")
st.markdown(comparison.recommendation)
if comparison.limitations:
    st.caption("**Limitations:** " + " · ".join(comparison.limitations))
