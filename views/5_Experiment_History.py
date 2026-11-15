"""
Shabd.Craft — Experiment History

Manage, edit, duplicate, export, and delete saved prompt experiments and versions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from src.experiment_service import duplicate_experiment, get_experiment_summary
from src.export_service import export_results_json
from src.ui_helpers import (
    get_database,
    load_version_into_workshop,
    render_empty_experiment_state,
    render_page_header,
)

db = get_database()

render_page_header("Experiment History", "Manage, edit, export, and delete saved prompt experiments.")

experiments = db.list_experiments(limit=100)

if not experiments:
    render_empty_experiment_state("No experiments yet. Start by creating a prompt in the Workshop.")
    st.stop()

# ── Search & Filter ────────────────────────────────────────────────────
f1, f2 = st.columns([3, 1])
with f1:
    search = st.text_input("Search experiments", placeholder="Search by name...")
with f2:
    categories = sorted(set(e["category"] for e in experiments))
    cat_filter = st.selectbox("Category", ["All"] + categories, format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All")

filtered = experiments
if search:
    filtered = [e for e in filtered if search.lower() in e["name"].lower()]
if cat_filter != "All":
    filtered = [e for e in filtered if e["category"] == cat_filter]

st.caption(f"Showing {len(filtered)} of {len(experiments)} experiments")

# ── Experiment List ────────────────────────────────────────────────────
for exp in filtered:
    summary = get_experiment_summary(db, exp["id"])
    status_text = exp["status"].replace("_", " ").title()
    cat_text = exp["category"].replace("_", " ").title()

    with st.expander(f"{exp['name']} — {cat_text} · {status_text}", expanded=False):
        ic1, ic2, ic3, ic4 = st.columns(4)
        ic1.metric("Versions", summary.get("version_count", 0))
        ic2.metric("Test Cases", summary.get("test_case_count", 0))
        ic3.metric("Evaluations", summary.get("evaluation_count", 0))
        ic4.metric("Avg Score", f"{summary.get('avg_score', 0):.1f}" if summary.get("avg_score") else "—")

        st.caption(f"Created: {exp['created_at'][:19]} · Updated: {exp['updated_at'][:19]}")
        if exp.get("description"):
            st.markdown(f"*{exp['description']}*")

        versions = summary.get("versions", [])
        if versions:
            st.markdown("**Prompt Versions:**")
            for v in versions:
                opt_badge = " (Optimized)" if v.get("is_optimized") else ""
                vc1, vc2, vc3 = st.columns([4, 1, 1])
                with vc1:
                    st.markdown(f"- v{v['version_number']}: {v['version_label']}{opt_badge}")
                with vc2:
                    if st.button("Open", key=f"hist_open_v_{v['id']}", use_container_width=True):
                        load_version_into_workshop(db, exp, v)
                        st.switch_page("views/1_Prompt_Workshop.py")
                with vc3:
                    if len(versions) > 1 and st.button("Delete", key=f"hist_del_v_{v['id']}", use_container_width=True):
                        db.delete_prompt_version(v["id"])
                        st.rerun()

        st.markdown("")
        a1, a2, a3, a4, a5 = st.columns(5)

        with a1:
            if st.button("Evaluate", key=f"eval_{exp['id']}", use_container_width=True):
                st.session_state["current_experiment_id"] = exp["id"]
                st.switch_page("views/2_Evaluation_Lab.py")

        with a2:
            if len(versions) >= 2:
                if st.button("Compare", key=f"cmp_{exp['id']}", use_container_width=True):
                    st.session_state["current_experiment_id"] = exp["id"]
                    st.switch_page("views/4_Compare_Versions.py")

        with a3:
            if st.button("Duplicate", key=f"dup_{exp['id']}", use_container_width=True):
                new_id = duplicate_experiment(db, exp["id"], f"{exp['name']} (copy)")
                if new_id:
                    st.success("Experiment duplicated.")
                    st.rerun()

        with a4:
            results = summary.get("results", [])
            test_cases = summary.get("test_cases", [])
            if results:
                json_export = export_results_json(exp, versions, test_cases, results)
                st.download_button(
                    "Export",
                    json_export,
                    file_name=f"{exp['name']}_export.json",
                    mime="application/json",
                    key=f"exp_{exp['id']}",
                    use_container_width=True,
                )

        with a5:
            if st.button("Delete", key=f"del_{exp['id']}", use_container_width=True):
                st.session_state[f"confirm_del_{exp['id']}"] = True

        if st.session_state.get(f"confirm_del_{exp['id']}"):
            st.warning("Delete this experiment and all its versions and results?")
            dc1, dc2 = st.columns(2)
            with dc1:
                if st.button("Yes, Delete", key=f"yes_del_{exp['id']}", type="primary", use_container_width=True):
                    db.delete_experiment(exp["id"])
                    st.session_state.pop(f"confirm_del_{exp['id']}", None)
                    if st.session_state.get("current_experiment_id") == exp["id"]:
                        st.session_state["current_experiment_id"] = None
                        st.session_state["current_version_id"] = None
                    st.rerun()
            with dc2:
                if st.button("Cancel", key=f"no_del_{exp['id']}", use_container_width=True):
                    st.session_state.pop(f"confirm_del_{exp['id']}", None)
                    st.rerun()
