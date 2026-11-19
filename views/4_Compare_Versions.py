"""
Shabd.Craft — Compare Versions

Side-by-side comparison of prompt versions on shared test cases
and head-to-head Multi-Model Arena with position-debiased AI referee.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
from contextvars import copy_context
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.comparison_engine import (
    build_word_diff_html,
    compare_versions,
    get_side_by_side_outputs,
)
from src.config import settings
from src.llm_judge import evaluate_pairwise_position_swap
from src.prompt_engine import execute_prompt, get_provider
from src.schemas import (
    FewShotExample,
    OutputFormat,
    PromptVersion,
    PromptingTechnique,
)
from src.ui_helpers import (
    get_database,
    render_empty_experiment_state,
    render_page_header,
)
from src.ui_theme import status_badge

db = get_database()

render_page_header("Compare versions", "See what changed between prompt versions and how their results differ.")

# ── Select Experiment ──────────────────────────────────────────────────
experiments = db.list_experiments()
if not experiments:
    render_empty_experiment_state("No prompts available yet. Create one in the Prompt Workshop.")
    st.stop()

exp_opts = {e["id"]: f"{e['name']} ({e['category'].replace('_', ' ').title()})" for e in experiments}
default_exp = st.session_state.get("current_experiment_id", experiments[0]["id"])
if default_exp not in exp_opts:
    default_exp = experiments[0]["id"]

sel_exp = st.selectbox(
    "Experiment",
    list(exp_opts.keys()),
    format_func=lambda x: exp_opts[x],
    index=list(exp_opts.keys()).index(default_exp),
    key="compare_exp_selector",
)
st.session_state["current_experiment_id"] = sel_exp

versions = db.get_prompt_versions(sel_exp)
if not versions:
    st.info("No prompt versions available for this experiment.")
    st.stop()

ver_opts = {v["id"]: f"v{v['version_number']}: {v['version_label']}" for v in versions}

compare_mode = st.radio(
    "Comparison View",
    ["Prompt Version Diff (A vs B)", "Multi-Model Arena (Model Battle)"],
    horizontal=True,
    key="compare_view_mode",
)

if compare_mode == "Multi-Model Arena (Model Battle)":
    st.markdown("##### Multi-Model Arena — Head-to-Head Cross-Model Benchmark")
    st.caption("Benchmark the exact same prompt version across two different LLM architectures side-by-side.")

    with st.container(border=True):
        c_pv, c_in = st.columns([1, 1])
        with c_pv:
            arena_ver_id = st.selectbox(
                "Prompt Version",
                list(ver_opts.keys()),
                format_func=lambda x: ver_opts[x],
                key="arena_ver_select",
            )
        with c_in:
            test_cases = db.get_test_cases(sel_exp)
            tc_choices = ["Custom Input"] + [f"TC-{i+1}: {tc['input_data'][:45]}..." for i, tc in enumerate(test_cases)]
            chosen_input_src = st.selectbox("Benchmark Input Source", tc_choices, key="arena_input_src")

        if chosen_input_src == "Custom Input":
            arena_input = st.text_area(
                "Input Data for Model Battle",
                height=80,
                placeholder="Enter input text to test both models...",
                key="arena_custom_input",
            )
        else:
            tc_idx = tc_choices.index(chosen_input_src) - 1
            arena_input = test_cases[tc_idx]["input_data"]
            st.caption(f"Using input from test case TC-{tc_idx+1}")

        m_col1, m_col2 = st.columns(2)
        with m_col1:
            model_a = st.selectbox("Model A", settings.AVAILABLE_MODELS, index=0, key="arena_m_a")
        with m_col2:
            idx_b = 1 if len(settings.AVAILABLE_MODELS) > 1 else 0
            model_b = st.selectbox("Model B", settings.AVAILABLE_MODELS, index=idx_b, key="arena_m_b")

        run_battle = st.button(":material/compare_arrows: Run Model Battle", type="primary", use_container_width=True, key="btn_run_arena")

    if run_battle:
        if not arena_input.strip():
            st.error("Please provide input data for the model battle.")
        else:
            ver_raw = db.get_prompt_version(arena_ver_id)
            few_shots_list = [FewShotExample(**e) for e in json.loads(ver_raw.get("few_shot_examples", "[]"))]

            ver_a_obj = PromptVersion(
                id=ver_raw["id"],
                experiment_id=sel_exp,
                system_prompt=ver_raw.get("system_prompt", ""),
                user_prompt_template=ver_raw.get("user_prompt_template", ""),
                technique=PromptingTechnique(ver_raw["technique"]),
                output_format=OutputFormat(ver_raw["output_format"]),
                model_name=model_a,
                temperature=ver_raw.get("temperature", 0.7),
                max_tokens=ver_raw.get("max_tokens", 1024),
                few_shot_examples=few_shots_list,
            )
            ver_b_obj = PromptVersion(
                id=ver_raw["id"],
                experiment_id=sel_exp,
                system_prompt=ver_raw.get("system_prompt", ""),
                user_prompt_template=ver_raw.get("user_prompt_template", ""),
                technique=PromptingTechnique(ver_raw["technique"]),
                output_format=OutputFormat(ver_raw["output_format"]),
                model_name=model_b,
                temperature=ver_raw.get("temperature", 0.7),
                max_tokens=ver_raw.get("max_tokens", 1024),
                few_shot_examples=few_shots_list,
            )

            with st.status(":material/hourglass_top: Battling Model A vs Model B...", expanded=True) as status_box:
                status_box.write(f"Querying Model A ({model_a})...")
                status_box.write(f"Querying Model B ({model_b})...")
                with ThreadPoolExecutor(max_workers=2) as arena_exec:
                    fut_a = arena_exec.submit(copy_context().run, execute_prompt, ver_a_obj, arena_input)
                    fut_b = arena_exec.submit(copy_context().run, execute_prompt, ver_b_obj, arena_input)
                    resp_a = fut_a.result()
                    resp_b = fut_b.result()
                status_box.update(label=":material/check_circle: Battle complete", state="complete")

            st.session_state["arena_last_result"] = {
                "model_a": model_a,
                "model_b": model_b,
                "resp_a": resp_a.model_dump(),
                "resp_b": resp_b.model_dump(),
                "instruction": ver_raw.get("user_prompt_template", ""),
                "arena_input": arena_input,
            }

    if st.session_state.get("arena_last_result"):
        ar = st.session_state["arena_last_result"]
        ra = ar["resp_a"]
        rb = ar["resp_b"]

        st.divider()
        st.markdown("##### Head-to-Head Outcomes")

        res_c1, res_c2 = st.columns(2)
        with res_c1:
            with st.container(border=True):
                st.markdown(f"**Model A: `{ar['model_a']}`**")
                st.code(ra.get("content", "") or f"Error: {ra.get('error')}", language="text")
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Latency", f"{ra.get('latency_ms', 0):.0f}ms")
                with m2:
                    st.metric("Tokens", ra.get("total_tokens", 0))
                with m3:
                    cost_a = ra.get("cost_estimate", 0)
                    st.metric("Cost", f"${cost_a:.5f}" if cost_a > 0 else "$0.00")

        with res_c2:
            with st.container(border=True):
                st.markdown(f"**Model B: `{ar['model_b']}`**")
                st.code(rb.get("content", "") or f"Error: {rb.get('error')}", language="text")
                m4, m5, m6 = st.columns(3)
                with m4:
                    st.metric("Latency", f"{rb.get('latency_ms', 0):.0f}ms")
                with m5:
                    st.metric("Tokens", rb.get("total_tokens", 0))
                with m6:
                    cost_b = rb.get("cost_estimate", 0)
                    st.metric("Cost", f"${cost_b:.5f}" if cost_b > 0 else "$0.00")

        st.markdown("##### Automated AI Referee Verdict (Position-Debiased)")
        st.caption("Runs bidirectional position swap `(A, B)` vs `(B, A)` to eliminate first-position preference bias.")

        ref_btn = st.button(":material/emoji_events: Crown Winner with AI Referee", type="primary", key="btn_run_referee")
        if ref_btn:
            with st.status(":material/hourglass_top: AI Referee evaluating responses...", expanded=True) as status_box:
                provider = get_provider()
                judge_m = "llama-3.3-70b-versatile" if settings.is_groq and "llama-3.3-70b-versatile" in settings.AVAILABLE_MODELS else settings.default_model
                ref_res = evaluate_pairwise_position_swap(
                    provider=provider,
                    instruction=ar.get("instruction", "Follow instructions precisely."),
                    input_data=ar.get("arena_input", ""),
                    candidate_a=ra.get("content", ""),
                    candidate_b=rb.get("content", ""),
                    model=judge_m,
                )
                st.session_state["arena_referee_result"] = ref_res
                status_box.update(label=":material/check_circle: Verdict reached", state="complete")

        if st.session_state.get("arena_referee_result"):
            ref = st.session_state["arena_referee_result"]
            winner = ref["winner"]
            model_a_name = ar.get("model_a", "Model A")
            model_b_name = ar.get("model_b", "Model B")
            with st.container(border=True):
                if winner == "A":
                    st.markdown(f"**Referee Verdict:** {status_badge('success', f'WINNER: Model A ({model_a_name})')}")
                elif winner == "B":
                    st.markdown(f"**Referee Verdict:** {status_badge('success', f'WINNER: Model B ({model_b_name})')}")
                elif winner == "tie":
                    st.markdown(f"**Referee Verdict:** {status_badge('info', 'STATISTICAL TIE')}")
                else:
                    st.markdown(f"**Referee Verdict:** {status_badge('warn', 'INCONCLUSIVE (Position Bias Detected)')}")

                rf_c1, rf_c2, rf_c3 = st.columns(3)
                with rf_c1:
                    st.metric(f"Score: {ar['model_a']}", f"{ref.get('score_a', 0):.1f}%")
                with rf_c2:
                    st.metric(f"Score: {ar['model_b']}", f"{ref.get('score_b', 0):.1f}%")
                with rf_c3:
                    st.metric("Position Bias", "Detected ⚠️" if ref.get("position_bias_detected") else "None ✅")

                st.markdown(f"**Consensus Rationale:** {ref.get('consensus_rationale', '')}")

    st.stop()

# ── Diff View (Two Versions) ───────────────────────────────────────────
if len(versions) < 2:
    st.info(":material/info: This experiment has only 1 prompt version. Save a second version in Prompt Workshop to compare.")
    st.stop()

c1, c2 = st.columns(2)
with c1:
    ver_a = st.selectbox("Version A", list(ver_opts.keys()), format_func=lambda x: ver_opts[x], index=0)
with c2:
    idx_b = min(1, len(versions) - 1)
    ver_b = st.selectbox("Version B", list(ver_opts.keys()), format_func=lambda x: ver_opts[x], index=idx_b)

if ver_a == ver_b:
    st.warning(":material/warning: Select two different versions to compare.")
    st.stop()

va_data = db.get_prompt_version(ver_a)
vb_data = db.get_prompt_version(ver_b)
if not va_data or not vb_data:
    st.error("Selected prompt version could not be found.")
    st.stop()

st.divider()

# Prompt Diff
st.markdown("##### Prompt Diff")
tab_diff, tab_side = st.tabs(["Inline Diff (A ➔ B)", "Side-by-Side"])

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
        with st.container(border=True):
            st.markdown(f"**{ver_opts[ver_a]}**")
            if va_data.get("system_prompt"):
                st.caption("System Prompt:")
                st.code(va_data["system_prompt"], language="text")
            st.caption("User Prompt Template:")
            st.code(va_data["user_prompt_template"], language="text")
    with pb:
        with st.container(border=True):
            st.markdown(f"**{ver_opts[ver_b]}**")
            if vb_data.get("system_prompt"):
                st.caption("System Prompt:")
                st.code(vb_data["system_prompt"], language="text")
            st.caption("User Prompt Template:")
            st.code(vb_data["user_prompt_template"], language="text")

# Results comparison
run_pairs = db.get_comparable_evaluation_run_pairs(sel_exp, ver_a, ver_b)
if not run_pairs:
    st.info("No matching completed evaluation runs exist for these versions. Run both versions with the same test cases, evaluation method, weights, and constraints to compare them fairly.")
    st.stop()

def _run_pair_label(pair_index):
    pair = run_pairs[pair_index]
    a, b = pair
    return f"Matched run pair · {a['method']} · {a['created_at'][:19]} / {b['created_at'][:19]}"

chosen_pair_index = st.selectbox("Comparable evaluation runs", list(range(len(run_pairs))), format_func=_run_pair_label, key="compare_run_pair")
chosen_pair = run_pairs[chosen_pair_index]
results_a = db.get_evaluation_results(sel_exp, evaluation_run_id=chosen_pair[0]["id"])
results_b = db.get_evaluation_results(sel_exp, evaluation_run_id=chosen_pair[1]["id"])
st.caption("These runs share the same evaluation settings and a snapshot of the same test suite.")

comparison = compare_versions(va_data, vb_data, results_a, results_b)

st.markdown("")
st.markdown("##### Score Comparison")
sc1, sc2, sc3 = st.columns(3)
with sc1:
    with st.container(border=True):
        st.metric(comparison.version_a_label, f"{comparison.version_a_overall:.1f}%")
with sc2:
    with st.container(border=True):
        delta = comparison.version_b_overall - comparison.version_a_overall
        st.metric(comparison.version_b_label, f"{comparison.version_b_overall:.1f}%", f"{delta:+.1f}%")
with sc3:
    with st.container(border=True):
        if delta > 0:
            st.metric("Net Advantage", f"+{delta:.1f}%", f"Favoring {comparison.version_b_label}")
        elif delta < 0:
            st.metric("Net Advantage", f"+{-delta:.1f}%", f"Favoring {comparison.version_a_label}")
        else:
            st.metric("Net Advantage", "0.0%", "Parity")

# Criteria Chart
if comparison.version_a_scores and comparison.version_b_scores:
    st.markdown("##### Criterion Breakdown")
    criteria = list(set(list(comparison.version_a_scores.keys()) + list(comparison.version_b_scores.keys())))
    labels = [c.replace("_", " ").title() for c in criteria]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=comparison.version_a_label,
        x=labels,
        y=[comparison.version_a_scores.get(c, 0) for c in criteria],
        marker_color="#9ca3af",
    ))
    fig.add_trace(go.Bar(
        name=comparison.version_b_label,
        x=labels,
        y=[comparison.version_b_scores.get(c, 0) for c in criteria],
        marker_color="#9b84ff",
    ))
    fig.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9ba3b5", family="Inter"),
        yaxis=dict(range=[0, 105], gridcolor="#2a2d3e", title="Score (%)"),
        xaxis=dict(gridcolor="#2a2d3e"),
        margin=dict(l=40, r=20, t=10, b=40), height=280,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

# Efficiency Metrics
st.markdown("##### Efficiency Telemetry")
succ_a = [r for r in results_a if r.get("execution_status") == "success"]
succ_b = [r for r in results_b if r.get("execution_status") == "success"]

avg_lat_a = round(sum(r.get("latency_ms", 0) for r in succ_a) / len(succ_a), 0) if succ_a else 0
avg_lat_b = round(sum(r.get("latency_ms", 0) for r in succ_b) / len(succ_b), 0) if succ_b else 0
avg_tok_a = round(sum(r.get("tokens_used", 0) for r in succ_a) / len(succ_a), 0) if succ_a else 0
avg_tok_b = round(sum(r.get("tokens_used", 0) for r in succ_b) / len(succ_b), 0) if succ_b else 0

ef1, ef2, ef3, ef4 = st.columns(4)
with ef1:
    with st.container(border=True):
        st.metric(f"{comparison.version_a_label} Latency", f"{avg_lat_a:.0f}ms")
with ef2:
    with st.container(border=True):
        st.metric(f"{comparison.version_b_label} Latency", f"{avg_lat_b:.0f}ms")
with ef3:
    with st.container(border=True):
        st.metric(f"{comparison.version_a_label} Tokens", f"{avg_tok_a:.0f}")
with ef4:
    with st.container(border=True):
        st.metric(f"{comparison.version_b_label} Tokens", f"{avg_tok_b:.0f}")

st.divider()
st.markdown("##### Recommendation")
st.markdown(comparison.recommendation)
