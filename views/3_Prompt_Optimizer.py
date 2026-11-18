"""
Shabd.Craft — Prompt Optimizer

Generate, test, and benchmark improved prompt candidates using
autonomous hill-climbing genetic mutations and 1-shot candidate generation.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
import plotly.graph_objects as go
import streamlit as st

from src.config import settings
from src.evaluation_engine import aggregate_results, evaluate_batch
from src.experiment_service import create_revision_branch
from src.optimizer import generate_candidates, recommend_best, run_iterative_optimization
from src.schemas import (
    CriterionScore,
    EvaluationMethod,
    EvaluationResult,
    ExecutionStatus,
    FewShotExample,
    OutputFormat,
    PromptVersion,
    PromptingTechnique,
    TestCase,
)
from src.ui_helpers import (
    get_active_eval_weights,
    get_database,
    render_empty_experiment_state,
    render_page_header,
)
from src.ui_theme import status_badge

db = get_database()

render_page_header("Prompt Optimizer", "Generate improved prompt candidates, benchmark them, and promote winners.")

# ── Select Experiment & Version ─────────────────────────────────────────
experiments = db.list_experiments()
if not experiments:
    render_empty_experiment_state("Create and evaluate a prompt first.")
    st.stop()

exp_opts = {e["id"]: f"{e['name']} ({e['category'].replace('_', ' ').title()})" for e in experiments}
default_exp = st.session_state.get("current_experiment_id", experiments[0]["id"])
if default_exp not in exp_opts:
    default_exp = experiments[0]["id"]

sel_c1, sel_c2 = st.columns(2)
with sel_c1:
    sel_exp = st.selectbox(
        "Experiment",
        list(exp_opts.keys()),
        format_func=lambda x: exp_opts[x],
        index=list(exp_opts.keys()).index(default_exp),
        key="opt_exp_selector",
    )
    st.session_state["current_experiment_id"] = sel_exp

versions = db.get_prompt_versions(sel_exp)
if not versions:
    st.warning("No prompt versions in this experiment.")
    st.stop()

ver_opts = {v["id"]: f"v{v['version_number']}: {v['version_label']}" for v in versions}
default_ver = st.session_state.get("current_version_id", versions[0]["id"])
if default_ver not in ver_opts:
    default_ver = versions[0]["id"]
with sel_c2:
    sel_ver = st.selectbox(
        "Base Prompt Version",
        list(ver_opts.keys()),
        format_func=lambda x: ver_opts[x],
        index=list(ver_opts.keys()).index(default_ver),
        key="opt_ver_selector",
    )
    st.session_state["current_version_id"] = sel_ver

ver_data = db.get_prompt_version(sel_ver)
existing_candidates = db.get_optimization_candidates(sel_exp)

# Current Prompt inspection
with st.expander("Base Prompt Template", expanded=not bool(existing_candidates)):
    if ver_data.get("system_prompt"):
        st.markdown("**System Prompt:**")
        st.code(ver_data["system_prompt"], language="text")
    st.markdown("**User Prompt Template:**")
    st.code(ver_data["user_prompt_template"], language="text")

# Current baseline evaluation results
results = db.get_evaluation_results(sel_exp, sel_ver)
successful = [r for r in results if r.get("execution_status") == "success"]
original_avg = round(sum(r["overall_score"] for r in successful) / len(successful), 1) if successful else 0.0

if successful:
    with st.container(border=True):
        st.metric("Current Baseline Score", f"{original_avg:.1f}%")
else:
    st.info(":material/info: No evaluation results for this version. Consider running evaluation first for guided optimization.")

st.divider()

opt_mode = st.radio(
    "Optimization Strategy",
    ["Autonomous Multi-Generation Hill-Climbing (Iterative)", "Manual Candidate Generation (1-Shot)"],
    horizontal=True,
    key="opt_mode_radio",
)

if opt_mode == "Autonomous Multi-Generation Hill-Climbing (Iterative)":
    st.markdown("##### :material/auto_fix_high: Autonomous Multi-Generation Hill-Climbing")
    st.caption("Mutates prompts across generations, benchmarks each generation against test cases, keeps winning mutations, and tracks the generational learning curve.")

    test_cases_raw = db.get_test_cases(sel_exp)
    if not test_cases_raw:
        st.warning(":material/warning: Autonomous optimization requires test cases to benchmark each generation. Add test cases in the Evaluation Lab first.")
    else:
        with st.container(border=True):
            r_col1, r_col2 = st.columns([2, 1])
            with r_col1:
                rounds = st.slider("Generations / Rounds", 1, 5, settings.max_optimization_rounds, key="auto_opt_rounds")
            with r_col2:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                start_auto_btn = st.button(":material/play_arrow: Start Optimization", type="primary", use_container_width=True, key="btn_start_auto_opt")

        if start_auto_btn:
            active_w = get_active_eval_weights()
            tc_objs = [TestCase(id=tc["id"], input_data=tc["input_data"], expected_output=tc.get("expected_output", "")) for tc in test_cases_raw]
            exp_data = db.get_experiment(sel_exp) or {}
            cat = exp_data.get("category", "general")
            few_shots = [FewShotExample(**e) for e in json.loads(ver_data.get("few_shot_examples", "[]"))]
            base_ver_obj = PromptVersion(
                id=ver_data["id"],
                experiment_id=sel_exp,
                version_number=ver_data["version_number"],
                version_label=ver_data["version_label"],
                system_prompt=ver_data.get("system_prompt", ""),
                user_prompt_template=ver_data.get("user_prompt_template", ""),
                technique=PromptingTechnique(ver_data["technique"]),
                output_format=OutputFormat(ver_data["output_format"]),
                model_name=ver_data.get("model_name", settings.default_model),
                temperature=ver_data.get("temperature", 0.7),
                max_tokens=ver_data.get("max_tokens", 1024),
                few_shot_examples=few_shots,
            )

            prog_bar = st.progress(0, text="Initializing generation 0...")
            def _prog(cur, tot, msg):
                prog_bar.progress(cur / tot, text=msg)

            with st.status(":material/hourglass_top: Running autonomous generational hill-climbing...", expanded=True) as status_box:
                auto_res = run_iterative_optimization(
                    original_version=base_ver_obj,
                    test_cases=tc_objs,
                    experiment_id=sel_exp,
                    weights=active_w,
                    max_rounds=rounds,
                    category=cat,
                    progress_callback=_prog,
                )
                prog_bar.progress(1.0, text="Autonomous optimization complete!")
                status_box.update(label=":material/check_circle: Optimization complete", state="complete")
                st.session_state["auto_opt_result"] = auto_res

        if st.session_state.get("auto_opt_result"):
            ares = st.session_state["auto_opt_result"]
            st.divider()
            st.markdown("##### Generational Progression")
            init_sc = ares["initial_score"]
            final_sc = ares["final_score"]
            delta = round(final_sc - init_sc, 1)

            m_c1, m_c2, m_c3, m_c4 = st.columns(4)
            with m_c1:
                with st.container(border=True):
                    st.metric("Baseline Score", f"{init_sc:.1f}%")
            with m_c2:
                with st.container(border=True):
                    st.metric("Optimized Score", f"{final_sc:.1f}%", f"+{delta}%" if delta > 0 else f"{delta}%")
            with m_c3:
                with st.container(border=True):
                    st.metric("Generations Run", f"{ares['rounds_executed']}/{rounds}")
            with m_c4:
                with st.container(border=True):
                    st.metric("Status", "Converged" if ares.get("converged") else "Completed")

            hist = ares.get("history", [])
            if len(hist) > 1:
                fig_prog = go.Figure()
                fig_prog.add_trace(go.Scatter(
                    x=[f"Gen {h['round']}: {h['strategy']}" for h in hist],
                    y=[h["score"] for h in hist],
                    mode="lines+markers+text",
                    text=[f"{h['score']:.1f}%" for h in hist],
                    textposition="top center",
                    line=dict(color="#9b84ff", width=3),
                    marker=dict(size=9, color="#22d3ee"),
                ))
                fig_prog.update_layout(
                    title="Generational Fitness Progression",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#9ba3b5", family="Inter"),
                    margin=dict(l=40, r=20, t=40, b=40),
                    yaxis=dict(range=[max(0, min(h['score'] for h in hist) - 10), 105], gridcolor="#2a2d3e"),
                    xaxis=dict(gridcolor="#2a2d3e"),
                    height=280,
                )
                st.plotly_chart(fig_prog, use_container_width=True)

            best_v = ares["best_version"]
            with st.container(border=True):
                st.markdown(f"##### Best Evolved Prompt ({best_v.optimization_strategy})")
                if best_v.system_prompt:
                    st.markdown("**System Prompt:**")
                    st.code(best_v.system_prompt, language="text")
                st.markdown("**User Prompt Template:**")
                st.code(best_v.user_prompt_template, language="text")

                if delta > 0:
                    if st.button(":material/star: Promote Winner as New Version", type="primary", key="btn_save_evolved"):
                        next_n = db.get_next_version_number(sel_exp)
                        branch_id, branch_name = create_revision_branch(
                            db, sel_exp, sel_ver, f"optimized-v{next_n}",
                            "Prompt optimizer result",
                        )
                        evolved_ver = PromptVersion(
                            experiment_id=sel_exp,
                            branch_id=branch_id,
                            version_number=next_n,
                            parent_version_id=sel_ver,
                            version_label=f"Evolved ({best_v.optimization_strategy})",
                            system_prompt=best_v.system_prompt,
                            user_prompt_template=best_v.user_prompt_template,
                            technique=best_v.technique,
                            output_format=best_v.output_format,
                            model_name=best_v.model_name,
                            temperature=best_v.temperature,
                            max_tokens=best_v.max_tokens,
                            few_shot_examples=best_v.few_shot_examples,
                            is_optimized=True,
                            optimization_strategy=best_v.optimization_strategy,
                        )
                        new_id = db.save_prompt_version(evolved_ver)
                        st.session_state["current_version_id"] = new_id
                        st.session_state["current_branch_id"] = branch_id
                        st.toast(f"Saved v{next_n} on '{branch_name}'.", icon=":material/check_circle:")
                        st.rerun()

else:
    # ── Manual Single-Turn Candidate Generation ────────────────────────
    st.markdown("##### Generate Optimization Candidates (1-Shot)")

    with st.container(border=True):
        num_cands = st.slider("Number of Candidates", 1, 3, 3)
        gen_btn = st.button(":material/auto_awesome: Generate Candidates", type="primary", use_container_width=True)

    if gen_btn:
        if not ver_data:
            st.error("Version not found.")
        else:
            few_shot_ex = [FewShotExample(**e) for e in json.loads(ver_data.get("few_shot_examples", "[]"))]
            version = PromptVersion(
                id=ver_data["id"],
                experiment_id=sel_exp,
                system_prompt=ver_data["system_prompt"],
                user_prompt_template=ver_data["user_prompt_template"],
                technique=PromptingTechnique(ver_data["technique"]),
                output_format=OutputFormat(ver_data["output_format"]),
                model_name=ver_data["model_name"],
                temperature=ver_data["temperature"],
                max_tokens=ver_data["max_tokens"],
                few_shot_examples=few_shot_ex,
            )

            eval_results = []
            for r in results:
                if r.get("execution_status") == "success":
                    eval_results.append(EvaluationResult(
                        test_case_id=r["test_case_id"],
                        prompt_version_id=r["prompt_version_id"],
                        experiment_id=r["experiment_id"],
                        overall_score=r["overall_score"],
                        execution_status=ExecutionStatus.SUCCESS,
                        criterion_scores=[CriterionScore(**s) for s in json.loads(r.get("criterion_scores", "[]"))],
                        weaknesses=json.loads(r.get("weaknesses", "[]")),
                        suggestions=json.loads(r.get("suggestions", "[]")),
                    ))

            exp_data = db.get_experiment(sel_exp)
            category = exp_data.get("category", "general") if exp_data else "general"

            with st.status(":material/hourglass_top: Generating candidates...", expanded=True) as status_box:
                candidates = generate_candidates(
                    original_version=version,
                    evaluation_results=eval_results,
                    experiment_id=sel_exp,
                    num_candidates=num_cands,
                    category=category,
                )
                for c in candidates:
                    db.save_optimization_candidate(c)
                status_box.update(label=":material/check_circle: Candidates ready", state="complete")
            st.toast(f"Generated {len(candidates)} candidates.", icon=":material/check_circle:")
            st.rerun()

# ── Display Candidates ─────────────────────────────────────────────────
existing_candidates = db.get_optimization_candidates(sel_exp)

if existing_candidates:
    st.markdown("##### Optimization Candidates")

    for i, cand in enumerate(existing_candidates):
        stat = cand.get("status", "pending")
        with st.expander(f"{cand['candidate_label']} — {cand['strategy']} ({stat.upper()})", expanded=(i == 0)):
            st.markdown(f"**Strategy:** {cand['strategy']}")
            st.markdown(f"**Changes:** {cand['changes_description']}")
            st.markdown(f"**Rationale:** {cand['rationale']}")

            if cand.get("system_prompt"):
                st.markdown("**System Prompt:**")
                st.code(cand["system_prompt"], language="text")
            st.markdown("**User Prompt Template:**")
            st.code(cand["user_prompt_template"], language="text")

            if cand["status"] == "success":
                st.metric("Benchmark Score", f"{cand['overall_score']:.1f}%")

            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                if cand["status"] == "pending":
                    if st.button(":material/play_arrow: Test Candidate", key=f"test_{cand['id']}", use_container_width=True):
                        test_cases = db.get_test_cases(sel_exp)
                        if not test_cases:
                            st.error("No test cases available.")
                        else:
                            next_num = db.get_next_version_number(sel_exp)
                            branch_id, _branch_name = create_revision_branch(
                                db, sel_exp, sel_ver, f"candidate-v{next_num}",
                                "Prompt optimizer candidate",
                            )
                            cand_version = PromptVersion(
                                experiment_id=sel_exp,
                                branch_id=branch_id,
                                version_number=next_num,
                                parent_version_id=sel_ver,
                                version_label=cand["candidate_label"],
                                system_prompt=cand["system_prompt"],
                                user_prompt_template=cand["user_prompt_template"],
                                technique=PromptingTechnique(ver_data["technique"]),
                                output_format=OutputFormat(ver_data["output_format"]),
                                model_name=ver_data["model_name"],
                                temperature=ver_data["temperature"],
                                max_tokens=ver_data["max_tokens"],
                                is_optimized=True,
                                optimization_strategy=cand["strategy"],
                            )
                            cand_ver_id = db.save_prompt_version(cand_version)

                            tc_objects = [
                                TestCase(id=tc["id"], input_data=tc["input_data"], expected_output=tc.get("expected_output", ""))
                                for tc in test_cases
                            ]
                            weights = get_active_eval_weights()
                            cand_method = EvaluationMethod.COMBINED if settings.has_api_key and not settings.demo_mode else EvaluationMethod.RULE_BASED

                            with st.spinner(f"Testing {cand['candidate_label']}..."):
                                eval_results = evaluate_batch(
                                    version=cand_version,
                                    test_cases=tc_objects,
                                    experiment_id=sel_exp,
                                    weights=weights,
                                    method=cand_method,
                                )

                            for er in eval_results:
                                db.save_evaluation_result(er)

                            agg = aggregate_results(eval_results)
                            db.update_candidate_score(cand["id"], agg["avg_score"], "success")
                            st.toast(f"{cand['candidate_label']} scored {agg['avg_score']:.1f}%", icon=":material/check_circle:")
                            st.rerun()

            with ac2:
                if cand["status"] == "success":
                    if not cand.get("is_accepted"):
                        if st.button(":material/thumb_up: Accept Candidate", key=f"accept_{cand['id']}", use_container_width=True):
                            db.accept_candidate(cand["id"])
                            st.toast("Candidate accepted.", icon=":material/check_circle:")
                            st.rerun()
                    else:
                        st.success("Accepted")

            with ac3:
                if st.button(":material/delete: Remove", key=f"remove_{cand['id']}", use_container_width=True):
                    db.update_candidate_score(cand["id"], cand.get("overall_score", 0), "failed")
                    st.rerun()

    # Recommendation
    tested = {c["candidate_label"]: c["overall_score"] for c in existing_candidates if c["status"] == "success"}
    if tested:
        st.divider()
        st.markdown("##### Optimization Recommendation")
        test_cases = db.get_test_cases(sel_exp)
        rec = recommend_best(original_avg, tested, len(test_cases))

        if rec["improvement"]:
            st.success(rec["recommendation"])
        else:
            st.info(rec["recommendation"])

        all_labels = ["Baseline"] + list(tested.keys())
        all_scores = [original_avg] + list(tested.values())
        colors = ["#9ca3af"] + ["#9b84ff"] * len(tested)

        fig = go.Figure(data=[go.Bar(
            x=all_labels, y=all_scores,
            marker_color=colors,
            text=[f"{s:.1f}%" for s in all_scores], textposition="outside",
        )])
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#9ba3b5", family="Inter"),
            yaxis=dict(range=[0, 105], gridcolor="#2a2d3e", title="Score (%)"),
            xaxis=dict(gridcolor="#2a2d3e"),
            margin=dict(l=40, r=20, t=10, b=40), height=260,
        )
        st.plotly_chart(fig, use_container_width=True)
