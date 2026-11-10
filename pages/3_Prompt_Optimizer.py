"""
Shabd.Craft — Prompt Optimizer

Generate, test, and compare improved prompt candidates.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
from src.config import settings
from src.database import Database
from src.schemas import (
    PromptVersion, TestCase, EvaluationWeights, EvaluationResult,
    EvaluationMethod, ExecutionStatus, PromptingTechnique, OutputFormat,
    FewShotExample, CriterionScore, OptimizationCandidate, _new_id, _now,
)
from src.optimizer import generate_candidates, recommend_best
from src.evaluation_engine import evaluate_batch, aggregate_results

st.set_page_config(page_title="Prompt Optimizer — Shabd.Craft", page_icon="✦", layout="wide")

@st.cache_resource
def get_db():
    return Database(settings.db_path)

db = get_db()

st.markdown("## Prompt Optimizer")
st.caption("Generate improved prompt candidates, test them, and compare results.")

if settings.is_demo_mode:
    st.markdown('<span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;background:rgba(251,191,36,0.15);color:#fbbf24;border:1px solid rgba(251,191,36,0.3);">Demo Mode — optimization uses simulated responses</span>', unsafe_allow_html=True)

st.divider()

# ── Select experiment & version ────────────────────────────────────────
experiments = db.list_experiments()
if not experiments:
    st.info("Create and evaluate an experiment first.")
    if st.button("Go to Prompt Workshop", type="primary"):
        st.switch_page("pages/1_Prompt_Workshop.py")
    st.stop()

exp_opts = {e["id"]: e["name"] for e in experiments}
sel_exp = st.selectbox("Experiment", list(exp_opts.keys()), format_func=lambda x: exp_opts[x])

versions = db.get_prompt_versions(sel_exp)
if not versions:
    st.warning("No prompt versions in this experiment.")
    st.stop()

ver_opts = {v["id"]: f"v{v['version_number']}: {v['version_label']}" for v in versions}
sel_ver = st.selectbox("Base Prompt Version", list(ver_opts.keys()), format_func=lambda x: ver_opts[x])

ver_data = db.get_prompt_version(sel_ver)

# Show current prompt
with st.expander("Current Prompt", expanded=True):
    if ver_data.get("system_prompt"):
        st.markdown("**System:**")
        st.code(ver_data["system_prompt"], language="text")
    st.markdown("**User Prompt:**")
    st.code(ver_data["user_prompt_template"], language="text")

# Show existing evaluation results
results = db.get_evaluation_results(sel_exp, sel_ver)
successful = [r for r in results if r.get("execution_status") == "success"]
original_avg = round(sum(r["overall_score"] for r in successful) / len(successful), 1) if successful else 0.0

if successful:
    st.metric("Current Average Score", f"{original_avg:.1f}/100")
else:
    st.info("No evaluation results for this version. Consider running evaluation first for better optimization.")

st.divider()

# ── Generate Candidates ────────────────────────────────────────────────
st.markdown("##### Generate Optimization Candidates")

num_cands = st.slider("Number of candidates", 1, 3, 3)

if st.button("Generate Candidates", type="primary", use_container_width=True):
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

        with st.spinner("Generating optimization candidates..."):
            candidates = generate_candidates(
                original_version=version,
                evaluation_results=eval_results,
                experiment_id=sel_exp,
                num_candidates=num_cands,
                category=category,
            )

        for c in candidates:
            db.save_optimization_candidate(c)

        st.success(f"Generated {len(candidates)} candidates!")
        st.rerun()

# ── Display Candidates ─────────────────────────────────────────────────
existing_candidates = db.get_optimization_candidates(sel_exp)

if existing_candidates:
    st.markdown("##### Optimization Candidates")

    for i, cand in enumerate(existing_candidates):
        status_label = {"pending": "[PENDING]", "success": "[TESTED]", "failed": "[REMOVED]"}.get(cand["status"], "[PENDING]")
        with st.expander(f"{status_label} {cand['candidate_label']} — {cand['strategy']}", expanded=(i == 0)):
            st.markdown(f"**Strategy:** {cand['strategy']}")
            st.markdown(f"**Changes:** {cand['changes_description']}")
            st.markdown(f"**Rationale:** {cand['rationale']}")

            if cand.get("system_prompt"):
                st.markdown("**System Prompt:**")
                st.code(cand["system_prompt"], language="text")
            st.markdown("**User Prompt:**")
            st.code(cand["user_prompt_template"], language="text")

            if cand["status"] == "success":
                st.metric("Score", f"{cand['overall_score']:.1f}/100")

            # Action buttons
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                if cand["status"] == "pending":
                    if st.button("Test Candidate", key=f"test_{cand['id']}"):
                        test_cases = db.get_test_cases(sel_exp)
                        if not test_cases:
                            st.error("No test cases available.")
                        else:
                            # Create a temporary version for this candidate
                            next_num = db.get_next_version_number(sel_exp)
                            cand_version = PromptVersion(
                                experiment_id=sel_exp,
                                version_number=next_num,
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

                            tc_objects = [TestCase(id=tc["id"], input_data=tc["input_data"],
                                                   expected_output=tc.get("expected_output", ""))
                                         for tc in test_cases]
                            weights = EvaluationWeights()

                            with st.spinner(f"Testing {cand['candidate_label']}..."):
                                eval_results = evaluate_batch(
                                    version=cand_version,
                                    test_cases=tc_objects,
                                    experiment_id=sel_exp,
                                    weights=weights,
                                    method=EvaluationMethod.RULE_BASED,
                                )

                            for er in eval_results:
                                db.save_evaluation_result(er)

                            agg = aggregate_results(eval_results)
                            db.update_candidate_score(cand["id"], agg["avg_score"], "success")
                            st.success(f"{cand['candidate_label']} scored {agg['avg_score']:.1f}")
                            st.rerun()

            with ac2:
                if cand["status"] == "success" and not cand.get("is_accepted"):
                    if st.button("Accept", key=f"accept_{cand['id']}"):
                        db.accept_candidate(cand["id"])
                        st.success("Candidate accepted.")
                        st.rerun()

            with ac3:
                if st.button("Remove", key=f"remove_{cand['id']}"):
                    # Just mark as rejected - data preserved
                    db.update_candidate_score(cand["id"], cand.get("overall_score", 0), "failed")
                    st.rerun()

    # ── Recommendation ─────────────────────────────────────────────────
    tested = {c["candidate_label"]: c["overall_score"]
              for c in existing_candidates if c["status"] == "success"}
    if tested:
        st.divider()
        st.markdown("##### Optimization Recommendation")

        test_cases = db.get_test_cases(sel_exp)
        rec = recommend_best(original_avg, tested, len(test_cases))

        if rec["improvement"]:
            st.success(rec["recommendation"])
        else:
            st.info(rec["recommendation"])

        if rec["limitations"]:
            st.caption("**Limitations:** " + " · ".join(rec["limitations"]))

        # Comparison chart
        all_labels = ["Original"] + list(tested.keys())
        all_scores = [original_avg] + list(tested.values())
        colors = ["#6b7280"] + ["#7c5cfc"] * len(tested)

        fig = go.Figure(data=[go.Bar(
            x=all_labels, y=all_scores,
            marker_color=colors,
            text=[f"{s:.1f}" for s in all_scores], textposition="outside",
        )])
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#9ba3b5"),
            yaxis=dict(range=[0, 105], gridcolor="#2a2d3e", title="Score"),
            xaxis=dict(gridcolor="#2a2d3e"),
            margin=dict(l=40, r=20, t=10, b=40), height=300,
        )
        st.plotly_chart(fig, use_container_width=True)
