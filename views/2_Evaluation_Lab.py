"""
Shabd.Craft — Evaluation Lab

Test prompts against datasets with rule-based and LLM-as-a-Judge evaluation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
from src.config import settings
from src.ui_helpers import (
    get_active_eval_weights,
    get_database,
    render_empty_experiment_state,
    render_page_header,
)
from src.schemas import (
    PromptVersion, TestCase, EvaluationWeights, EvaluationResult,
    EvaluationMethod, PromptingTechnique, OutputFormat, FewShotExample,
    ExecutionStatus, CriterionScore, _new_id, _now,
)
from src.evaluation_engine import evaluate_batch, aggregate_results, calculate_weighted_score
from src.security_evaluator import (
    run_security_audit, audit_prompt_defenses, harden_prompt_suggestion,
)
from src.export_service import (
    export_results_csv, export_results_json, parse_test_cases_csv, parse_test_cases_json,
)

db = get_database()

render_page_header("Evaluation Lab", "Test prompts against datasets, inspect scores, and audit injection resistance.")

# ── Select Experiment ──────────────────────────────────────────────────
experiments = db.list_experiments()

if not experiments:
    render_empty_experiment_state("No prompts saved yet. Create one in the Prompt Workshop first.")
    st.stop()

exp_options = {e["id"]: f"{e['name']} ({e['category'].replace('_', ' ').title()})" for e in experiments}
default_exp = st.session_state.get("current_experiment_id", experiments[0]["id"])
if default_exp not in exp_options:
    default_exp = experiments[0]["id"]

sel_col1, sel_col2 = st.columns(2)
with sel_col1:
    selected_exp_id = st.selectbox("Experiment", list(exp_options.keys()),
                                    format_func=lambda x: exp_options[x],
                                    index=list(exp_options.keys()).index(default_exp))
    st.session_state["current_experiment_id"] = selected_exp_id

versions = db.get_prompt_versions(selected_exp_id)
if not versions:
    st.warning("This experiment has no prompt versions.")
    st.stop()

ver_options = {v["id"]: f"v{v['version_number']}: {v['version_label']}" for v in versions}
default_ver = st.session_state.get("current_version_id", versions[0]["id"])
if default_ver not in ver_options:
    default_ver = versions[0]["id"]
with sel_col2:
    selected_ver_id = st.selectbox("Prompt Version", list(ver_options.keys()),
                                    format_func=lambda x: ver_options[x],
                                    index=list(ver_options.keys()).index(default_ver))
    st.session_state["current_version_id"] = selected_ver_id

st.markdown("")

# ── Tabs ───────────────────────────────────────────────────────────────
tab_data, tab_config, tab_results, tab_security = st.tabs(["Test Cases", "Evaluation Config", "Results", "Security Audit"])

# ── Tab 1: Test Cases ──────────────────────────────────────────────────
with tab_data:
    test_cases = db.get_test_cases(selected_exp_id)

    st.markdown("##### Manage Test Cases")

    # Import controls
    imp1, imp2, imp3 = st.columns([2, 1, 1])
    with imp1:
        uploaded = st.file_uploader("Import test cases (CSV or JSON)", type=["csv", "json"],
                                     key="tc_upload")
    with imp2:
        # Download sample
        sample_path = Path(__file__).parent.parent / "data" / "sample_test_cases.json"
        if sample_path.exists():
            with open(sample_path, "r") as f:
                sample_data = f.read()
            st.download_button("Sample Dataset", sample_data,
                             file_name="sample_test_cases.json", mime="application/json")
    with imp3:
        if test_cases:
            csv_export = export_results_csv([], test_cases)
            st.download_button("Export Test Cases", csv_export,
                             file_name="test_cases.csv", mime="text/csv")

    if uploaded:
        content = uploaded.read().decode("utf-8")
        if uploaded.name.endswith(".csv"):
            parsed, errors = parse_test_cases_csv(content)
        else:
            parsed, errors = parse_test_cases_json(content)

        if errors:
            for err in errors[:5]:
                st.error(err)
        if parsed:
            count = min(len(parsed), settings.max_test_cases)
            for tc_data in parsed[:count]:
                tc = TestCase(input_data=tc_data["input_data"],
                             expected_output=tc_data.get("expected_output", ""))
                db.save_test_case(tc, selected_exp_id)
            st.success(f"Imported {count} test cases.")
            st.rerun()

    st.markdown("")

    # Add manually
    with st.expander("Add Test Case Manually"):
        with st.form("add_tc_form"):
            tc_input = st.text_area("Input Data", height=80, placeholder="Enter test input...")
            tc_expected = st.text_area("Expected Output (optional)", height=60)
            if st.form_submit_button("Add Test Case"):
                if tc_input.strip():
                    if len(test_cases) >= settings.max_test_cases:
                        st.error(f"Maximum {settings.max_test_cases} test cases allowed.")
                    else:
                        tc = TestCase(input_data=tc_input.strip(), expected_output=tc_expected.strip())
                        db.save_test_case(tc, selected_exp_id)
                        st.success("Test case added.")
                        st.rerun()
                else:
                    st.error("Input data is required.")

    # Display current test cases
    test_cases = db.get_test_cases(selected_exp_id)  # refresh
    if test_cases:
        st.markdown(f"**{len(test_cases)} test cases loaded**")
        for i, tc in enumerate(test_cases):
            with st.expander(f"TC-{i+1}: {tc['input_data'][:60]}…" if len(tc['input_data']) > 60 else f"TC-{i+1}: {tc['input_data']}"):
                st.text_area("Input", tc["input_data"], height=60, disabled=True, key=f"tc_v_in_{i}")
                if tc.get("expected_output"):
                    st.text_area("Expected", tc["expected_output"], height=60, disabled=True, key=f"tc_v_exp_{i}")
                if st.button("Delete", key=f"del_tc_{tc['id']}"):
                    db.delete_test_case(tc["id"])
                    st.rerun()
    else:
        st.info("No test cases yet. Add some manually or import from a file.")

# ── Tab 2: Evaluation Config ──────────────────────────────────────────
with tab_config:
    st.markdown("##### Evaluation Settings")

    method = st.radio("Evaluation Method", ["rule_based", "llm_judge", "combined"],
                     format_func=lambda x: {"rule_based": "Rule-Based (deterministic)",
                                           "llm_judge": "LLM-as-a-Judge",
                                           "combined": "Combined (averaged)"}[x],
                     index=0, horizontal=True)

    if method in ("llm_judge", "combined"):
        st.caption("Note: LLM-as-a-Judge scores may vary between runs and are not objective ground truth.")

    st.markdown("##### Evaluation Weights")
    st.caption("Configure the relative importance of each criterion. Weights are normalized automatically.")

    active_w = get_active_eval_weights()
    w1, w2, w3, w4, w5 = st.columns(5)
    with w1:
        w_acc = st.slider("Accuracy", 0.0, 1.0, float(active_w.accuracy), 0.05, key="w_acc")
    with w2:
        w_rel = st.slider("Relevance", 0.0, 1.0, float(active_w.relevance), 0.05, key="w_rel")
    with w3:
        w_ins = st.slider("Instruction Adherence", 0.0, 1.0, float(active_w.instruction_adherence), 0.05, key="w_ins")
    with w4:
        w_cla = st.slider("Clarity", 0.0, 1.0, float(active_w.clarity), 0.05, key="w_cla")
    with w5:
        w_fmt = st.slider("Format Compliance", 0.0, 1.0, float(active_w.format_compliance), 0.05, key="w_fmt")

    total_w = w_acc + w_rel + w_ins + w_cla + w_fmt
    if total_w == 0:
        st.error("At least one weight must be greater than zero.")

    st.markdown("")
    st.markdown("##### Optional Constraints")
    oc1, oc2 = st.columns(2)
    with oc1:
        keywords_str = st.text_input("Required Keywords (comma-separated)", placeholder="JSON, summary, analysis")
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()] if keywords_str else None
    with oc2:
        max_words = st.number_input("Max Word Count (0 = no limit)", 0, 5000, 0)
        max_words = max_words if max_words > 0 else None

# ── Tab 3: Results ─────────────────────────────────────────────────────
with tab_results:
    existing_results = db.get_evaluation_results(selected_exp_id, selected_ver_id)

    if existing_results:
        st.markdown("##### Evaluation Results")

        agg = aggregate_results([
            EvaluationResult(
                test_case_id=r["test_case_id"],
                prompt_version_id=r["prompt_version_id"],
                experiment_id=r["experiment_id"],
                overall_score=r["overall_score"],
                execution_status=ExecutionStatus(r["execution_status"]),
                criterion_scores=[CriterionScore(**s) for s in json.loads(r.get("criterion_scores", "[]"))],
                is_demo=bool(r.get("is_demo")),
            ) for r in existing_results
        ])

        # Summary metrics
        rm1, rm2, rm3, rm4 = st.columns(4)
        rm1.metric("Avg Score", f"{agg['avg_score']:.1f}")
        rm2.metric("Successful", f"{agg['success']}/{agg['total']}")
        rm3.metric("Failed", agg["failed"])
        rm4.metric("Score Range", f"{agg['min_score']:.0f}–{agg['max_score']:.0f}")

        # Criterion chart
        if agg["criterion_averages"]:
            labels = [k.replace("_", " ").title() for k in agg["criterion_averages"].keys()]
            values = list(agg["criterion_averages"].values())
            fig = go.Figure(data=[go.Bar(
                x=labels, y=values,
                marker_color=["#7c5cfc", "#8b6fff", "#9b82ff", "#22d3ee", "#34d399"][:len(labels)],
                text=[f"{v:.0f}" for v in values], textposition="outside",
            )])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#9ba3b5"), yaxis=dict(range=[0, 105], gridcolor="#2a2d3e"),
                xaxis=dict(gridcolor="#2a2d3e"),
                margin=dict(l=40, r=20, t=10, b=40), height=280,
            )
            st.plotly_chart(fig, use_container_width=True)

        # Results table
        st.markdown("##### Detailed Results")
        tc_map = {tc["id"]: tc for tc in db.get_test_cases(selected_exp_id)}
        rows = []
        for r in existing_results:
            tc = tc_map.get(r["test_case_id"], {})
            scores = {s["name"]: s["score"] for s in json.loads(r.get("criterion_scores", "[]"))}
            rows.append({
                "Input": tc.get("input_data", "")[:80],
                "Output": r.get("generated_output", "")[:80],
                "Score": r["overall_score"],
                "Status": r["execution_status"],
                "Accuracy": scores.get("accuracy", "—"),
                "Relevance": scores.get("relevance", "—"),
                "Adherence": scores.get("instruction_adherence", "—"),
                "Clarity": scores.get("clarity", "—"),
                "Format": scores.get("format_compliance", "—"),
            })

        df_results = pd.DataFrame(rows)
        st.dataframe(df_results, use_container_width=True, hide_index=True)

        # Export
        exp_data = db.get_experiment(selected_exp_id) or {}
        csv_data = export_results_csv(existing_results, db.get_test_cases(selected_exp_id))
        json_data = export_results_json(exp_data, versions, db.get_test_cases(selected_exp_id), existing_results)

        ex1, ex2 = st.columns(2)
        with ex1:
            st.download_button("Export CSV", csv_data, file_name="evaluation_results.csv", mime="text/csv")
        with ex2:
            st.download_button("Export JSON", json_data, file_name="evaluation_results.json", mime="application/json")

        # Detail drill-down
        st.markdown("##### Inspect Individual Results")
        for i, r in enumerate(existing_results):
            tc = tc_map.get(r["test_case_id"], {})
            label = f"TC-{i+1}: Score {r['overall_score']:.1f} — {r['execution_status']}"
            with st.expander(label):
                st.markdown("**Input:**")
                st.code(tc.get("input_data", ""), language="text")
                if tc.get("expected_output"):
                    st.markdown("**Expected:**")
                    st.code(tc["expected_output"], language="text")
                st.markdown("**Generated:**")
                st.code(r.get("generated_output", ""), language="text")
                scores = json.loads(r.get("criterion_scores", "[]"))
                for s in scores:
                    st.markdown(f"- **{s['name'].replace('_',' ').title()}**: {s['score']:.0f} — {s.get('explanation', '')}")
                if r.get("error_message"):
                    st.error(f"Error: {r['error_message']}")
                weak = json.loads(r.get("weaknesses", "[]"))
                sugg = json.loads(r.get("suggestions", "[]"))
                if weak:
                    st.markdown("**Weaknesses:** " + ", ".join(weak))
                if sugg:
                    st.markdown("**Suggestions:** " + ", ".join(sugg))

    else:
        st.info("No results yet. Configure settings and run the evaluation below.")

# ── Tab 4: Security Audit ──────────────────────────────────────────────
with tab_security:
    st.markdown("##### Prompt Injection & Security Audit")
    st.caption("Evaluates prompt resistance against direct overrides, system prompt extraction, delimiter escapes, and role hijacking.")

    sec_ver_data = db.get_prompt_version(selected_ver_id)
    if not sec_ver_data:
        st.warning("Prompt version not found.")
    else:
        sec_few_shot = [FewShotExample(**e) for e in json.loads(sec_ver_data.get("few_shot_examples", "[]"))]
        sec_version = PromptVersion(
            id=sec_ver_data["id"],
            experiment_id=selected_exp_id,
            version_number=sec_ver_data["version_number"],
            version_label=sec_ver_data["version_label"],
            system_prompt=sec_ver_data["system_prompt"],
            user_prompt_template=sec_ver_data["user_prompt_template"],
            technique=PromptingTechnique(sec_ver_data["technique"]),
            output_format=OutputFormat(sec_ver_data["output_format"]),
            model_name=sec_ver_data["model_name"],
            temperature=sec_ver_data["temperature"],
            max_tokens=sec_ver_data["max_tokens"],
            few_shot_examples=sec_few_shot,
        )

        static_posture = audit_prompt_defenses(sec_version)
        st.markdown("**Static Defense Posture**")
        sc1, sc2, sc3 = st.columns(3)
        for col, chk in zip((sc1, sc2, sc3), static_posture["checks"]):
            with col:
                status_text = "PASS" if chk["passed"] else "MISSING"
                st.metric(chk["name"], status_text)
                st.caption(chk["detail"])

        st.markdown("")
        if st.button("Run Security Audit", type="primary", key=f"run_sec_{selected_ver_id}"):
            with st.spinner("Running adversarial prompt injection suite..."):
                audit_report = run_security_audit(sec_version)
                st.session_state[f"sec_audit_{selected_ver_id}"] = audit_report

        audit_report = st.session_state.get(f"sec_audit_{selected_ver_id}")
        if audit_report:
            am1, am2, am3 = st.columns(3)
            am1.metric("Robustness Score", f"{audit_report['robustness_score']:.1f}%")
            am2.metric("Attacks Resisted", f"{audit_report['resisted_count']}/{audit_report['total_count']}")
            am3.metric("Static Posture", f"{static_posture['static_score']:.0f}%")

            sec_rows = []
            for item in audit_report["results"]:
                sec_rows.append({
                    "Category": item["category"],
                    "Attack": item["attack_name"],
                    "Result": "RESISTED" if item["resisted"] else "VULNERABLE",
                    "Reason": item["reason"],
                })
            st.dataframe(pd.DataFrame(sec_rows), use_container_width=True, hide_index=True)

            with st.expander("Inspect Attack Payloads & Model Responses"):
                for item in audit_report["results"]:
                    badge = "RESISTED" if item["resisted"] else "VULNERABLE"
                    st.markdown(f"**[{badge}] {item['category']} — {item['attack_name']}**")
                    st.code(item["payload"], language="text")
                    st.caption(f"Response preview: {item['response_preview']}")

        st.divider()
        with st.expander("Hardening Suggestion (XML Delimiters + Security Boundary)"):
            hard_sys, hard_user = harden_prompt_suggestion(sec_version)
            st.markdown("**Suggested System Prompt:**")
            st.code(hard_sys, language="text")
            st.markdown("**Suggested User Prompt Template:**")
            st.code(hard_user, language="text")

            if st.button("Save Hardened Copy as New Version", key=f"save_hard_{selected_ver_id}"):
                next_num = db.get_next_version_number(selected_exp_id)
                hardened_ver = PromptVersion(
                    experiment_id=selected_exp_id,
                    version_number=next_num,
                    version_label=f"{sec_version.version_label} (Hardened)",
                    system_prompt=hard_sys,
                    user_prompt_template=hard_user,
                    technique=sec_version.technique,
                    output_format=sec_version.output_format,
                    model_name=sec_version.model_name,
                    temperature=sec_version.temperature,
                    max_tokens=sec_version.max_tokens,
                    few_shot_examples=sec_version.few_shot_examples,
                    is_optimized=True,
                    optimization_strategy="Security Hardening",
                )
                new_ver_id = db.save_prompt_version(hardened_ver)
                st.session_state["current_version_id"] = new_ver_id
                st.success(f"Saved hardened version v{next_num}.")
                st.rerun()

# ── Run Evaluation ─────────────────────────────────────────────────────
st.divider()
test_cases = db.get_test_cases(selected_exp_id)

if not test_cases:
    st.warning("Add test cases before running evaluation.")
elif total_w == 0:
    st.warning("Fix evaluation weights before running.")
else:
    if st.button("Run Evaluation", type="primary", use_container_width=True):
        weights = EvaluationWeights(accuracy=w_acc, relevance=w_rel,
                                    instruction_adherence=w_ins, clarity=w_cla,
                                    format_compliance=w_fmt)

        ver_data = db.get_prompt_version(selected_ver_id)
        if not ver_data:
            st.error("Prompt version not found.")
        else:
            few_shot_ex = [FewShotExample(**e) for e in json.loads(ver_data.get("few_shot_examples", "[]"))]
            version = PromptVersion(
                id=ver_data["id"],
                experiment_id=selected_exp_id,
                version_number=ver_data["version_number"],
                version_label=ver_data["version_label"],
                system_prompt=ver_data["system_prompt"],
                user_prompt_template=ver_data["user_prompt_template"],
                technique=PromptingTechnique(ver_data["technique"]),
                output_format=OutputFormat(ver_data["output_format"]),
                model_name=ver_data["model_name"],
                temperature=ver_data["temperature"],
                max_tokens=ver_data["max_tokens"],
                few_shot_examples=few_shot_ex,
            )

            tc_objects = [TestCase(id=tc["id"], input_data=tc["input_data"],
                                  expected_output=tc.get("expected_output", ""))
                         for tc in test_cases]

            progress_bar = st.progress(0, text="Evaluating...")

            def update_progress(current, total):
                progress_bar.progress(current / total, text=f"Evaluating {current}/{total}...")

            results = evaluate_batch(
                version=version,
                test_cases=tc_objects,
                experiment_id=selected_exp_id,
                weights=weights,
                method=EvaluationMethod(method),
                required_keywords=keywords,
                max_words=max_words,
                progress_callback=update_progress,
            )

            for r in results:
                db.save_evaluation_result(r)

            db.update_experiment_status(selected_exp_id, ExecutionStatus.SUCCESS.value)
            progress_bar.progress(1.0, text="Evaluation complete!")

            agg = aggregate_results(results)
            st.success(f"Evaluated {agg['total']} test cases. Average score: {agg['avg_score']:.1f}")
            st.rerun()
