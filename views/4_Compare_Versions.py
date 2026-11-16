"""
Shabd.Craft — Compare Versions

Side-by-side comparison of prompt versions on shared test cases.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import json
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import plotly.graph_objects as go
from src.config import settings
from src.prompt_engine import execute_prompt, get_provider
from src.llm_judge import evaluate_pairwise_position_swap
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
        arena_input = st.text_area("Input Data for Model Battle", height=80, placeholder="Enter input text to test both models...", key="arena_custom_input")
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

    if st.button("Run Model Battle", type="primary", use_container_width=True, key="btn_run_arena"):
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

            with st.spinner(f"Battling {model_a} vs {model_b} concurrently..."):
                with ThreadPoolExecutor(max_workers=2) as arena_exec:
                    fut_a = arena_exec.submit(execute_prompt, ver_a_obj, arena_input)
                    fut_b = arena_exec.submit(execute_prompt, ver_b_obj, arena_input)
                    resp_a = fut_a.result()
                    resp_b = fut_b.result()

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
        st.markdown("##### Battle Results")

        res_c1, res_c2 = st.columns(2)
        with res_c1:
            st.markdown(f"**Model A: `{ar['model_a']}`**")
            st.text_area("Output A", value=ra.get("content", "") or (f"Error: {ra.get('error')}" if ra.get("error") else ""), height=220, disabled=True, key="arena_out_a")
            m1, m2, m3 = st.columns(3)
            m1.metric("Latency", f"{ra.get('latency_ms', 0):.0f}ms")
            m2.metric("Tokens", ra.get("total_tokens", 0))
            cost_a = ra.get("cost_estimate", 0)
            m3.metric("Cost", f"${cost_a:.5f}" if cost_a > 0 else "$0.00")

        with res_c2:
            st.markdown(f"**Model B: `{ar['model_b']}`**")
            st.text_area("Output B", value=rb.get("content", "") or (f"Error: {rb.get('error')}" if rb.get("error") else ""), height=220, disabled=True, key="arena_out_b")
            m4, m5, m6 = st.columns(3)
            m4.metric("Latency", f"{rb.get('latency_ms', 0):.0f}ms")
            m5.metric("Tokens", rb.get("total_tokens", 0))
            cost_b = rb.get("cost_estimate", 0)
            m6.metric("Cost", f"${cost_b:.5f}" if cost_b > 0 else "$0.00")

        chart_df = pd.DataFrame([
            {"Metric": "Latency (ms)", ar["model_a"]: ra.get("latency_ms", 0), ar["model_b"]: rb.get("latency_ms", 0)},
            {"Metric": "Total Tokens", ar["model_a"]: ra.get("total_tokens", 0), ar["model_b"]: rb.get("total_tokens", 0)},
        ])
        fig_arena = go.Figure(data=[
            go.Bar(name=ar["model_a"], x=chart_df["Metric"], y=chart_df[ar["model_a"]], marker_color="#7c5cfc"),
            go.Bar(name=ar["model_b"], x=chart_df["Metric"], y=chart_df[ar["model_b"]], marker_color="#22d3ee"),
        ])
        fig_arena.update_layout(
            barmode="group",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#9ba3b5"),
            margin=dict(l=40, r=20, t=20, b=40),
            height=260,
        )
        st.plotly_chart(fig_arena, use_container_width=True)

        st.markdown("##### ⚖️ Automated AI Referee Verdict (Zheng et al. Position-Debiased)")
        st.caption("Runs bidirectional position swap `(A, B)` vs `(B, A)` to eliminate first-position preference bias and crowns the true empirical winner.")

        ref_btn = st.button("Crown Winner with AI Referee", type="primary", key="btn_run_referee")
        if ref_btn:
            with st.spinner("AI Referee evaluating responses with position-swap debiasing..."):
                provider = get_provider()
                # Use a dedicated strong judge if available
                judge_m = "llama-3.3-70b-versatile" if settings.is_groq and "llama-3.3-70b-versatile" in settings.AVAILABLE_MODELS else ("gpt-4o" if "gpt-4o" in settings.AVAILABLE_MODELS else settings.default_model)
                ref_res = evaluate_pairwise_position_swap(
                    provider=provider,
                    instruction=ar.get("instruction", "Follow instructions precisely."),
                    input_data=ar.get("arena_input", ""),
                    candidate_a=ra.get("content", ""),
                    candidate_b=rb.get("content", ""),
                    model=judge_m,
                )
                st.session_state["arena_referee_result"] = ref_res

        if st.session_state.get("arena_referee_result"):
            ref = st.session_state["arena_referee_result"]
            winner = ref["winner"]
            if winner == "A":
                st.success(f"🏆 **Winner: Model A (`{ar['model_a']}`)**")
            elif winner == "B":
                st.success(f"🏆 **Winner: Model B (`{ar['model_b']}`)**")
            elif winner == "tie":
                st.info("🤝 **Result: Statistical Tie** (Both models performed at parity)")
            else:
                st.warning("⚠️ **Result: Inconclusive Position Bias** (Model favored whichever candidate was shown first)")

            rf_c1, rf_c2, rf_c3 = st.columns(3)
            rf_c1.metric(f"Score: {ar['model_a']}", f"{ref.get('score_a', 0):.1f}/100")
            rf_c2.metric(f"Score: {ar['model_b']}", f"{ref.get('score_b', 0):.1f}/100")
            rf_c3.metric("Position Bias Detected", "YES ⚠️" if ref.get("position_bias_detected") else "CLEAN ✅")

            st.markdown(f"**Consensus Rationale:** {ref.get('consensus_rationale', '')}")

    st.stop()

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
if not va_data or not vb_data:
    st.error("Selected prompt version could not be found.")
    st.stop()

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
