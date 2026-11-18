"""
Shabd.Craft — Evaluation Lab

Test prompts against datasets with rule-based and LLM-as-a-Judge evaluation,
background threaded execution with Stop/Cancel support, and security auditing.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import settings
from src.experiment_service import create_revision_branch
from src.evaluation_engine import (
    aggregate_results,
    calculate_weighted_score,
    evaluate_single,
)
from src.export_service import (
    export_results_csv,
    export_results_json,
    parse_test_cases_csv,
    parse_test_cases_json,
)
from src.harness import evaluate_quality_gate
from src.schemas import (
    CriterionScore,
    EvaluationMethod,
    EvaluationResult,
    EvaluationWeights,
    ExecutionStatus,
    FewShotExample,
    OutputFormat,
    PromptVersion,
    PromptingTechnique,
    TestCase,
    _now,
)
from src.security_evaluator import (
    audit_prompt_defenses,
    harden_prompt_suggestion,
    run_security_audit,
)
from src.test_synthesizer import generate_synthetic_test_cases
from src.ui_helpers import (
    get_active_eval_weights,
    get_database,
    render_empty_experiment_state,
    render_page_header,
)
from src.ui_theme import status_badge

db = get_database()

render_page_header("Test prompts", "Run prompts on sample inputs and review their results.")


# ── Concurrency Run Handle & Coordinator Thread ─────────────────────────
class EvalRunHandle:
    """Thread-safe state handle for background evaluation runs."""
    def __init__(self, experiment_id: str, version_id: str, total: int, run_id: str):
        self.experiment_id = experiment_id
        self.version_id = version_id
        self.total = total
        self.run_id = run_id
        self.completed = 0
        self.results: list[EvaluationResult] = []
        self.errors: list[str] = []
        self.status = "running"  # "running", "stopped", "done"
        self.lock = threading.Lock()
        self.stop_event = threading.Event()


def _eval_coordinator_thread(
    handle: EvalRunHandle,
    version: PromptVersion,
    test_cases: list[TestCase],
    weights: EvaluationWeights,
    method: EvaluationMethod,
    keywords: list[str] | None,
    max_words: int | None,
    judge_model: str | None,
    max_workers: int = 4,
):
    """
    Background coordinator: owns ThreadPoolExecutor and workers.
    Strictly isolated: does not call st.* or touch st.session_state.
    """
    num_workers = min(max(1, max_workers), len(test_cases))

    def _worker(tc: TestCase) -> EvaluationResult | None:
        if handle.stop_event.is_set():
            return None
        try:
            result = evaluate_single(
                version=version,
                test_case=tc,
                experiment_id=handle.experiment_id,
                weights=weights,
                method=method,
                required_keywords=keywords,
                max_words=max_words,
                judge_model=judge_model,
            )
            result.evaluation_run_id = handle.run_id
            return result
        except Exception as e:
            return EvaluationResult(
                test_case_id=tc.id,
                prompt_version_id=version.id,
                experiment_id=handle.experiment_id,
                evaluation_run_id=handle.run_id,
                input_data_snapshot=tc.input_data,
                expected_output_snapshot=tc.expected_output,
                execution_status=ExecutionStatus.FAILED,
                error_message=str(e),
                created_at=_now(),
            )

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(_worker, tc): tc for tc in test_cases}
        for future in as_completed(futures):
            if handle.stop_event.is_set():
                break
            try:
                res = future.result()
                if res is not None:
                    with handle.lock:
                        handle.results.append(res)
                        handle.completed += 1
            except Exception as e:
                with handle.lock:
                    handle.errors.append(str(e))
                    handle.completed += 1

    with handle.lock:
        handle.status = "stopped" if handle.stop_event.is_set() else "done"


# ── Select Experiment & Version ─────────────────────────────────────────
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
    selected_exp_id = st.selectbox(
        "Experiment",
        list(exp_options.keys()),
        format_func=lambda x: exp_options[x],
        index=list(exp_options.keys()).index(default_exp),
        key="eval_exp_selector",
    )
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
    selected_ver_id = st.selectbox(
        "Prompt Version",
        list(ver_options.keys()),
        format_func=lambda x: ver_options[x],
        index=list(ver_options.keys()).index(default_ver),
        key="eval_ver_selector",
    )
    st.session_state["current_version_id"] = selected_ver_id

st.markdown("")

# ── Background Run Monitor Fragment ─────────────────────────────────────
@st.fragment(run_every=1)
def render_live_eval_monitor():
    handle: EvalRunHandle | None = st.session_state.get("eval_run_handle")
    if not handle:
        return

    with handle.lock:
        curr = handle.completed
        tot = handle.total
        stat = handle.status
        res_count = len(handle.results)

    with st.container(border=True):
        st.markdown(f"##### {status_badge('running' if stat == 'running' else 'complete', 'Evaluation In Progress' if stat == 'running' else 'Run Completed')}")
        ratio = curr / max(1, tot)
        st.progress(ratio, text=f"Evaluating test suite: {curr} / {tot} cases processed ({ratio:.0%})")

        m1, m2 = st.columns([3, 1])
        with m1:
            st.caption(f"Status: **{stat.upper()}** · Completed: **{curr}** · Collected Results: **{res_count}**")
        with m2:
            if stat == "running":
                if st.button("⏹ Stop Evaluation", type="primary", use_container_width=True, key="btn_stop_eval"):
                    handle.stop_event.set()
                    st.toast("Stop signal sent. Waiting for in-flight requests...", icon=":material/stop_circle:")

        if stat in ("done", "stopped"):
            # Main thread persists bulk results and clears handle safely
            for result in handle.results:
                result.evaluation_run_id = handle.run_id
            db.save_evaluation_results_bulk(handle.results)
            db.update_evaluation_run_status(handle.run_id, stat)
            db.update_experiment_status(handle.experiment_id, ExecutionStatus.SUCCESS.value)
            st.session_state.pop("eval_run_handle", None)
            st.toast(f"Evaluation {stat}: {res_count} results saved to database.", icon=":material/check_circle:")
            st.rerun()


render_live_eval_monitor()

# ── Tabs ───────────────────────────────────────────────────────────────
tab_data, tab_config, tab_results, tab_security = st.tabs([
    "Test Cases",
    "Evaluation Config",
    "Results & Telemetry",
    "Security Audit",
])

# ── Tab 1: Test Cases ──────────────────────────────────────────────────
with tab_data:
    test_cases = db.get_test_cases(selected_exp_id)
    st.markdown("##### Manage Test Suite")

    with st.container(border=True):
        imp1, imp2, imp3 = st.columns([2, 1, 1])
        with imp1:
            uploaded = st.file_uploader(
                "Import Test Cases (CSV or JSON)",
                type=["csv", "json"],
                key="tc_file_upload",
            )
        with imp2:
            sample_path = _ROOT / "data" / "sample_test_cases.json"
            if sample_path.exists():
                with open(sample_path, "r", encoding="utf-8") as f:
                    sample_data = f.read()
                st.download_button(
                    ":material/download: Sample Dataset",
                    sample_data,
                    file_name="sample_test_cases.json",
                    mime="application/json",
                    use_container_width=True,
                )
        with imp3:
            if test_cases:
                csv_export = export_results_csv([], test_cases)
                st.download_button(
                    ":material/download: Export Dataset",
                    csv_export,
                    file_name="test_cases.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        if uploaded:
            content = uploaded.read().decode("utf-8")
            if uploaded.name.endswith(".csv"):
                parsed, errors = parse_test_cases_csv(content)
            else:
                parsed, errors = parse_test_cases_json(content)

            if errors:
                for err in errors[:5]:
                    st.error(f":material/error: {err}")
            if parsed:
                count = min(len(parsed), settings.max_test_cases)
                for tc_data in parsed[:count]:
                    tc = TestCase(
                        input_data=tc_data["input_data"],
                        expected_output=tc_data.get("expected_output", ""),
                    )
                    db.save_test_case(tc, selected_exp_id)
                st.toast(f"Imported {count} test cases.", icon=":material/check_circle:")
                st.rerun()

    # Inline Dataset Editor
    st.markdown("##### Inline Dataset Table")
    tc_data_list = [
        {"#": i + 1, "id": tc["id"], "input_data": tc["input_data"], "expected_output": tc.get("expected_output", "")}
        for i, tc in enumerate(test_cases)
    ]
    df_tc = pd.DataFrame(tc_data_list)

    if not df_tc.empty:
        edited_df = st.data_editor(
            df_tc,
            column_config={
                "#": st.column_config.NumberColumn("#", disabled=True, width="small"),
                "id": None,  # Hide internal ID
                "input_data": st.column_config.TextColumn("Input Data (Prompt Input)", required=True, width="large"),
                "expected_output": st.column_config.TextColumn("Expected Output (Ground Truth)", width="medium"),
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="tc_data_editor",
        )
        col_ed1, col_ed2 = st.columns([1, 4])
        with col_ed1:
            if st.button(":material/save: Apply Table Edits", key="btn_apply_tc_edits"):
                # Re-sync modified rows
                current_ids = set()
                for _, row in edited_df.iterrows():
                    inp = str(row.get("input_data", "")).strip()
                    exp = str(row.get("expected_output", "")).strip()
                    row_id = row.get("id")
                    if inp:
                        if pd.notna(row_id) and row_id:
                            db.update_test_case(str(row_id), inp, exp)
                            current_ids.add(str(row_id))
                        else:
                            new_tc = TestCase(input_data=inp, expected_output=exp)
                            nid = db.save_test_case(new_tc, selected_exp_id)
                            current_ids.add(nid)

                # Delete removed rows
                for tc in test_cases:
                    if tc["id"] not in current_ids:
                        db.delete_test_case(tc["id"])
                st.toast("Test dataset updated successfully.", icon=":material/check_circle:")
                st.rerun()
    else:
        st.info(":material/info: No test cases found. Add some below or synthesize with AI.")

    # AI Test Synthesizer
    with st.expander("AI Synthetic Test Suite Generator", expanded=(not bool(test_cases))):
        st.caption("Synthesize diverse test cases (happy path, edge case, and stress) tailored to your prompt.")
        sc1, sc2 = st.columns([2, 1])
        with sc1:
            synth_count = st.slider("Test Cases to Synthesize", 1, 5, 3, key="synth_count_slider")
        with sc2:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            run_synth = st.button(":material/auto_awesome: Synthesize Test Suite", type="primary", use_container_width=True, key="btn_synth_cases")

        if run_synth:
            ver_raw = db.get_prompt_version(selected_ver_id)
            exp_raw = db.get_experiment(selected_exp_id) or {}
            if not ver_raw:
                st.error("No active prompt version found.")
            else:
                synth_ver = PromptVersion(
                    id=ver_raw["id"],
                    experiment_id=selected_exp_id,
                    system_prompt=ver_raw.get("system_prompt", ""),
                    user_prompt_template=ver_raw.get("user_prompt_template", ""),
                    model_name=ver_raw.get("model_name", ""),
                )
                with st.spinner("Synthesizing test suite with AI..."):
                    new_cases = generate_synthetic_test_cases(
                        synth_ver,
                        count=synth_count,
                        category=exp_raw.get("category", "general"),
                    )
                for tc in new_cases:
                    db.save_test_case(tc, selected_exp_id)
                st.toast(f"Synthesized {len(new_cases)} test cases.", icon=":material/auto_awesome:")
                st.rerun()

    # Manual Single Test Case Add
    with st.expander("Add Test Case Manually"):
        with st.form("add_tc_form", clear_on_submit=True):
            tc_input = st.text_area("Input Data", height=80, placeholder="Enter test input...")
            tc_expected = st.text_area("Expected Output (Optional)", height=60)
            if st.form_submit_button(":material/add: Add Test Case"):
                if tc_input.strip():
                    tc = TestCase(input_data=tc_input.strip(), expected_output=tc_expected.strip())
                    db.save_test_case(tc, selected_exp_id)
                    st.toast("Test case added.", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.error("Input data is required.")

# ── Tab 2: Evaluation Config ──────────────────────────────────────────
with tab_config:
    st.markdown("##### Evaluation Method & Arbiter Judge")
    with st.container(border=True):
        method = st.radio(
            "Evaluation Method",
            ["rule_based", "llm_judge", "combined"],
            format_func=lambda x: {
                "rule_based": "Rule-Based (Deterministic keyword, length, regex)",
                "llm_judge": "LLM-as-a-Judge (Qualitative semantic evaluation)",
                "combined": "Combined (Hybrid normalized average)",
            }[x],
            index=0,
            horizontal=True,
            key="eval_method_radio",
        )

        judge_model = None
        if method in ("llm_judge", "combined"):
            st.caption("Decoupled Arbiter: Evaluates candidate outputs independently.")
            judge_options = settings.AVAILABLE_MODELS
            default_judge = "llama-3.3-70b-versatile" if settings.is_groq and "llama-3.3-70b-versatile" in judge_options else judge_options[0]
            judge_idx = judge_options.index(default_judge) if default_judge in judge_options else 0
            judge_model = st.selectbox("Arbiter / Judge Model", judge_options, index=judge_idx, key="sel_judge_model")

    st.markdown("")
    st.markdown("##### Evaluation Criteria Weights")
    active_w = get_active_eval_weights()
    with st.container(border=True):
        with st.form("tab_weights_form"):
            w1, w2, w3, w4, w5 = st.columns(5)
            with w1:
                w_acc = st.slider("Accuracy", 0.0, 1.0, float(active_w.accuracy), 0.05, key="lab_w_acc")
            with w2:
                w_rel = st.slider("Relevance", 0.0, 1.0, float(active_w.relevance), 0.05, key="lab_w_rel")
            with w3:
                w_ins = st.slider("Adherence", 0.0, 1.0, float(active_w.instruction_adherence), 0.05, key="lab_w_ins")
            with w4:
                w_cla = st.slider("Clarity", 0.0, 1.0, float(active_w.clarity), 0.05, key="lab_w_cla")
            with w5:
                w_fmt = st.slider("Format", 0.0, 1.0, float(active_w.format_compliance), 0.05, key="lab_w_fmt")
            st.form_submit_button(":material/check: Update Criteria Weights")

        total_w = w_acc + w_rel + w_ins + w_cla + w_fmt
        if total_w == 0:
            st.error("At least one weight must be greater than zero.")

    st.markdown("")
    st.markdown("##### Optional Constraints")
    with st.container(border=True):
        oc1, oc2 = st.columns(2)
        with oc1:
            keywords_str = st.text_input("Required Keywords (comma-separated)", placeholder="JSON, summary, analysis", key="tc_kw_filter")
            keywords = [k.strip() for k in keywords_str.split(",") if k.strip()] if keywords_str else None
        with oc2:
            max_words = st.number_input("Max Word Count (0 = no limit)", 0, 5000, 0, key="tc_max_words")
            max_words = max_words if max_words > 0 else None

# ── Tab 3: Results & Telemetry ─────────────────────────────────────────
with tab_results:
    all_version_results = db.get_evaluation_results(selected_exp_id, selected_ver_id)
    evaluation_runs = db.get_evaluation_runs(selected_exp_id, selected_ver_id)
    legacy_results = [r for r in all_version_results if not r.get("evaluation_run_id")]
    run_options = [run["id"] for run in evaluation_runs]
    if legacy_results:
        run_options.append("__legacy__")

    if run_options:
        run_by_id = {run["id"]: run for run in evaluation_runs}
        def _evaluation_run_label(run_id):
            if run_id == "__legacy__":
                return "Older results (run settings unavailable)"
            run = run_by_id[run_id]
            return f"{run['status'].title()} · {run['method']} · {run['created_at'][:19]}"

        selected_run_id = st.selectbox(
            "Evaluation run", run_options,
            format_func=_evaluation_run_label,
            key=f"eval_results_run_{selected_ver_id}",
        )
        if selected_run_id == "__legacy__":
            existing_results = legacy_results
            selected_run_records = []
            st.warning("These results predate saved evaluation run context. They remain available for review, but are excluded from version comparisons.")
        else:
            existing_results = db.get_evaluation_results(selected_exp_id, evaluation_run_id=selected_run_id)
            selected_run_records = [run_by_id[selected_run_id]]
            run_config = json.loads(selected_run_records[0].get("config", "{}"))
            st.caption(f"Settings: {selected_run_records[0]['method']} · {run_config.get('provider', 'unknown')} · {run_config.get('generation_model', 'default model')}")
    else:
        existing_results = []
        selected_run_records = []

    if existing_results:
        st.markdown("##### Summary Scorecard")
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

        # Summary Metric Tiles inside border=True containers
        rm1, rm2, rm3, rm4 = st.columns(4)
        with rm1:
            with st.container(border=True):
                st.metric("Avg Quality Score", f"{agg['avg_score']:.1f}%", f"±{agg.get('score_std_dev', 0.0):.1f}σ")
        with rm2:
            with st.container(border=True):
                st.metric("Successful Runs", f"{agg['success']}/{agg['total']}")
        with rm3:
            with st.container(border=True):
                st.metric("Latency (p50 / p95)", f"{agg.get('p50_latency_ms', 0):.0f} / {agg.get('p95_latency_ms', 0):.0f}ms")
        with rm4:
            with st.container(border=True):
                st.metric("Score Range", f"{agg['min_score']:.0f}% – {agg['max_score']:.0f}%")

        # Regression Quality Gate
        with st.expander("Regression Quality Gate", expanded=False):
            gc1, gc2, gc3 = st.columns(3)
            with gc1:
                min_avg_gate = st.number_input("Min Avg Score", 0.0, 100.0, 75.0, 5.0, key="gate_min_avg")
            with gc2:
                min_fmt_gate = st.number_input("Min Format Score", 0.0, 100.0, 80.0, 5.0, key="gate_min_fmt")
            with gc3:
                min_sec_gate = st.number_input("Min Security Score (%)", 0.0, 100.0, 80.0, 5.0, key="gate_min_sec")

            sec_rep = st.session_state.get(f"sec_audit_{selected_ver_id}")
            gate = evaluate_quality_gate(
                existing_results,
                security_report=sec_rep,
                min_avg_score=min_avg_gate,
                min_format_score=min_fmt_gate,
                min_security_score=min_sec_gate,
            )
            gate_badge = status_badge("pass" if gate["passed"] else "fail", gate["status"])
            st.markdown(f"**Gate Outcome:** {gate_badge}")

            gate_rows = [
                {
                    "Assertion": c["name"],
                    "Actual": c["actual"],
                    "Threshold": c["threshold"],
                    "Status": "PASS" if c["passed"] else "FAIL",
                }
                for c in gate["checks"]
            ]
            st.dataframe(pd.DataFrame(gate_rows), use_container_width=True, hide_index=True)

        # Criteria Chart
        if agg["criterion_averages"]:
            labels = [k.replace("_", " ").title() for k in agg["criterion_averages"].keys()]
            values = list(agg["criterion_averages"].values())
            fig = go.Figure(data=[go.Bar(
                x=labels, y=values,
                marker_color=["#9b84ff", "#8b6fff", "#7c5cfc", "#22d3ee", "#34d399"][:len(labels)],
                text=[f"{v:.0f}%" for v in values], textposition="outside",
            )])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#9ba3b5", family="Inter"),
                yaxis=dict(range=[0, 105], gridcolor="#2a2d3e"),
                xaxis=dict(gridcolor="#2a2d3e"),
                margin=dict(l=40, r=20, t=10, b=40), height=260,
            )
            st.plotly_chart(fig, use_container_width=True)

        # Detailed Results Table
        st.markdown("##### Detailed Test Results")
        tc_map = {tc["id"]: tc for tc in db.get_test_cases(selected_exp_id)}
        rows = []
        for r in existing_results:
            tc = tc_map.get(r["test_case_id"], {})
            scores = {s["name"]: s["score"] for s in json.loads(r.get("criterion_scores", "[]"))}
            rows.append({
                "Input": (r.get("input_data_snapshot") or tc.get("input_data", ""))[:80],
                "Output": r.get("generated_output", "")[:80],
                "Score": float(r["overall_score"]),
                "Status": r["execution_status"],
                "Accuracy": scores.get("accuracy", 0.0),
                "Format": scores.get("format_compliance", 0.0),
            })

        df_results = pd.DataFrame(rows)
        st.dataframe(
            df_results,
            column_config={
                "Score": st.column_config.ProgressColumn("Overall Score", min_value=0, max_value=100, format="%.1f%%"),
                "Accuracy": st.column_config.ProgressColumn("Accuracy", min_value=0, max_value=100, format="%.1f%%"),
                "Format": st.column_config.ProgressColumn("Format", min_value=0, max_value=100, format="%.1f%%"),
            },
            use_container_width=True,
            hide_index=True,
        )

        # Export Controls
        exp_data = db.get_experiment(selected_exp_id) or {}
        csv_data = export_results_csv(existing_results, db.get_test_cases(selected_exp_id))
        json_data = export_results_json(
            exp_data, versions, db.get_test_cases(selected_exp_id), existing_results,
            selected_run_records,
        )

        ex1, ex2 = st.columns(2)
        with ex1:
            st.download_button(":material/download: Export Results CSV", csv_data, file_name="evaluation_results.csv", mime="text/csv", use_container_width=True)
        with ex2:
            st.download_button(":material/download: Export Results JSON", json_data, file_name="evaluation_results.json", mime="application/json", use_container_width=True)

        # Detailed Inspection Drill-down
        st.markdown("##### Inspect Test Cases")
        for i, r in enumerate(existing_results):
            tc = tc_map.get(r["test_case_id"], {})
            with st.expander(f"TC-{i+1}: Score {r['overall_score']:.1f}% — {r['execution_status']}"):
                st.markdown("**Input:**")
                st.code(r.get("input_data_snapshot") or tc.get("input_data", ""), language="text")
                expected_snapshot = r.get("expected_output_snapshot") or tc.get("expected_output", "")
                if expected_snapshot:
                    st.markdown("**Expected:**")
                    st.code(expected_snapshot, language="text")
                st.markdown("**Generated Output:**")
                st.code(r.get("generated_output", ""), language="text")
    else:
        st.info(":material/info: No evaluation results found for this version. Run an evaluation below.")

# ── Tab 4: Security Audit ──────────────────────────────────────────────
with tab_security:
    st.markdown("##### Prompt Injection & Defense Audit")
    st.caption("Tests resilience against system prompt leaks, role hijacking, and delimiter escapes.")

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
                with st.container(border=True):
                    st.markdown(f"**{chk['name']}**")
                    st.markdown(status_badge("pass" if chk["passed"] else "fail", "PASS" if chk["passed"] else "MISSING"))
                    st.caption(chk["detail"])

        st.markdown("")
        if st.button(":material/shield: Run Security Audit", type="primary", key=f"run_sec_{selected_ver_id}"):
            with st.status(":material/hourglass_top: Running adversarial security suite...", expanded=True) as status_box:
                status_box.write("Injecting delimiter breaking probes...")
                status_box.write("Executing system prompt extraction attempts...")
                status_box.write("Testing role override vectors...")
                audit_report = run_security_audit(sec_version)
                st.session_state[f"sec_audit_{selected_ver_id}"] = audit_report
                status_box.update(label=":material/check_circle: Security audit complete", state="complete")

        audit_report = st.session_state.get(f"sec_audit_{selected_ver_id}")
        if audit_report:
            with st.container(border=True):
                am1, am2, am3 = st.columns(3)
                with am1:
                    st.metric("Robustness Score", f"{audit_report['robustness_score']:.1f}%")
                with am2:
                    st.metric("Attacks Resisted", f"{audit_report['resisted_count']}/{audit_report['total_count']}")
                with am3:
                    st.metric("Static Defense", f"{static_posture['static_score']:.0f}%")

                sec_rows = [
                    {
                        "Category": item["category"],
                        "Attack": item["attack_name"],
                        "Result": "RESISTED" if item["resisted"] else "VULNERABLE",
                        "Reason": item["reason"],
                    }
                    for item in audit_report["results"]
                ]
                st.dataframe(pd.DataFrame(sec_rows), use_container_width=True, hide_index=True)

        st.divider()
        with st.expander("Security Hardening Suggestion (XML Enclosure & Anti-Extraction)"):
            hard_sys, hard_user = harden_prompt_suggestion(sec_version)
            st.markdown("**Suggested Hardened System Prompt:**")
            st.code(hard_sys, language="text")
            st.markdown("**Suggested Hardened User Prompt:**")
            st.code(hard_user, language="text")

            if st.button(":material/add_circle: Save Hardened Copy as New Version", key=f"save_hard_{selected_ver_id}"):
                next_num = db.get_next_version_number(selected_exp_id)
                branch_id, branch_name = create_revision_branch(
                    db, selected_exp_id, selected_ver_id, f"hardened-v{next_num}",
                    "Prompt hardening experiment",
                )
                hardened_ver = PromptVersion(
                    experiment_id=selected_exp_id,
                    branch_id=branch_id,
                    version_number=next_num,
                    parent_version_id=selected_ver_id,
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
                st.session_state["current_branch_id"] = branch_id
                st.toast(f"Saved v{next_num} on '{branch_name}'.", icon=":material/check_circle:")
                st.rerun()

# ── Action Bar: Dispatch Background Coordinator Thread ────────────────
st.divider()
test_cases = db.get_test_cases(selected_exp_id)
active_handle = st.session_state.get("eval_run_handle")
is_running = bool(active_handle and getattr(active_handle, "status", "") == "running")

if not test_cases:
    st.warning("Please add or import test cases before running evaluation.")
elif total_w == 0:
    st.warning("Fix evaluation criteria weights before running.")
else:
    btn_col, _ = st.columns([2, 3])
    with btn_col:
        run_btn = st.button(
            ":material/play_arrow: Run Evaluation",
            type="primary",
            use_container_width=True,
            disabled=is_running,
            help="Executes evaluation across worker threads in the background",
            key="btn_dispatch_eval",
        )

    if run_btn:
        ver_data = db.get_prompt_version(selected_ver_id)
        if not ver_data:
            st.error("Prompt version not found.")
        else:
            few_shot_ex = [FewShotExample(**e) for e in json.loads(ver_data.get("few_shot_examples", "[]"))]
            version_obj = PromptVersion(
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

            tc_objects = [
                TestCase(id=tc["id"], input_data=tc["input_data"], expected_output=tc.get("expected_output", ""), metadata=json.loads(tc.get("metadata", "{}")) if isinstance(tc.get("metadata"), str) else tc.get("metadata", {}))
                for tc in test_cases
            ]

            weights_obj = EvaluationWeights(
                accuracy=w_acc,
                relevance=w_rel,
                instruction_adherence=w_ins,
                clarity=w_cla,
                format_compliance=w_fmt,
            )

            # Spawn coordinator background thread
            run_config = {
                "provider": settings.active_provider,
                "provider_base_url": "https://api.groq.com/openai/v1" if settings.is_groq else (settings.openai_base_url or "https://api.openai.com/v1"),
                "generation_model": version_obj.model_name or settings.active_model,
                "generation_temperature": version_obj.temperature,
                "generation_max_tokens": version_obj.max_tokens,
                "judge_model": judge_model,
                "required_keywords": keywords or [],
                "max_words": max_words,
                "max_workers": 4,
            }
            run_id = db.create_evaluation_run(
                experiment_id=selected_exp_id,
                prompt_version_id=selected_ver_id,
                method=EvaluationMethod(method).value,
                weights=weights_obj.model_dump(),
                config=run_config,
                test_cases=[tc.model_dump() for tc in tc_objects],
            )
            new_handle = EvalRunHandle(selected_exp_id, selected_ver_id, len(tc_objects), run_id)
            st.session_state["eval_run_handle"] = new_handle

            coord_thread = threading.Thread(
                target=_eval_coordinator_thread,
                args=(
                    new_handle,
                    version_obj,
                    tc_objects,
                    weights_obj,
                    EvaluationMethod(method),
                    keywords,
                    max_words,
                    judge_model,
                    4,  # max_workers
                ),
                daemon=True,
            )
            coord_thread.start()
            st.rerun()
