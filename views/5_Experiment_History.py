"""
Shabd.Craft — Experiment History

Manage, edit, duplicate, export, and delete saved prompt experiments and versions.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.experiment_service import duplicate_experiment, get_experiment_summary
from src.export_service import export_results_json
from src.ui_helpers import (
    get_database,
    load_version_into_workshop,
    render_empty_experiment_state,
    render_page_header,
)
from src.ui_theme import status_badge

db = get_database()

render_page_header("Experiment History", "Manage, inspect, duplicate, export, and delete saved prompt experiments.")

# ── Delete Confirmation Dialog ──────────────────────────────────────────
@st.dialog("Delete Experiment")
def delete_experiment_dialog(exp_id: str, exp_name: str):
    st.warning(f"Are you sure you want to permanently delete **{exp_name}** and all its associated prompt versions, test cases, and evaluation results?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button(":material/delete: Yes, Delete", type="primary", use_container_width=True):
            db.delete_experiment(exp_id)
            if st.session_state.get("current_experiment_id") == exp_id:
                st.session_state["current_experiment_id"] = None
                st.session_state["current_version_id"] = None
            if st.session_state.get("ws_editing_exp_id") == exp_id:
                st.session_state["ws_editing_exp_id"] = None
                st.session_state["ws_editing_ver_id"] = None
            st.toast(f"Deleted experiment '{exp_name}'.", icon=":material/delete:")
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


experiments = db.list_experiments(limit=100)
if not experiments:
    render_empty_experiment_state("No experiments yet. Start by creating a prompt in the Workshop.")
    st.stop()

# ── Search & Filter ────────────────────────────────────────────────────
with st.container(border=True):
    f1, f2 = st.columns([3, 1])
    with f1:
        search = st.text_input("Search experiments", placeholder="Search by name or category...", label_visibility="collapsed")
    with f2:
        categories = sorted(set(e["category"] for e in experiments))
        cat_filter = st.selectbox(
            "Category",
            ["All"] + categories,
            format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All Categories",
            label_visibility="collapsed",
        )

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

    with st.container(border=True):
        head_col, stat_col = st.columns([3, 1])
        with head_col:
            st.markdown(f"#### {exp['name']}")
            st.caption(f":material/category: {cat_text} · Created: {exp['created_at'][:10]} · Updated: {exp['updated_at'][:10]}")
        with stat_col:
            st.markdown(f"Status: {status_badge('success' if exp['status'] == 'success' else 'active', status_text)}")

        if exp.get("description"):
            st.caption(f"*{exp['description']}*")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Versions", summary.get("version_count", 0))
        with m2:
            st.metric("Test Cases", summary.get("test_case_count", 0))
        with m3:
            st.metric("Evaluations", summary.get("evaluation_count", 0))
        with m4:
            st.metric("Avg Score", f"{summary.get('avg_score', 0):.1f}%" if summary.get("avg_score") else "—")

        versions = summary.get("versions", [])
        if versions:
            st.divider()
            st.markdown("**Prompt Versions & Lineage:**")
            version_by_id = {item["id"]: item for item in versions}
            for v in versions:
                opt_tag = " · :material/star: :green[Optimized]" if v.get("is_optimized") else ""
                parent = version_by_id.get(v.get("parent_version_id"))
                parent_tag = (
                    f" · from v{parent['version_number']}" if parent
                    else (" · parent revision deleted" if v.get("parent_version_id") else " · root revision")
                )
                vc1, vc2, vc3 = st.columns([4, 1, 1])
                with vc1:
                    st.markdown(f"**v{v['version_number']}:** {v['version_label']}{parent_tag}{opt_tag}")
                with vc2:
                    if st.button(":material/edit_note: Open", key=f"hist_open_v_{v['id']}", use_container_width=True):
                        load_version_into_workshop(db, exp, v)
                        st.switch_page("views/1_Prompt_Workshop.py")
                with vc3:
                    if len(versions) > 1 and st.button(":material/delete: Delete", key=f"hist_del_v_{v['id']}", use_container_width=True):
                        db.delete_prompt_version(v["id"])
                        st.toast("Version deleted.", icon=":material/delete:")
                        st.rerun()

        st.divider()
        a1, a2, a3, a4, a5 = st.columns(5)
        with a1:
            if st.button(":material/biotech: Evaluate", key=f"eval_{exp['id']}", use_container_width=True):
                st.session_state["current_experiment_id"] = exp["id"]
                st.switch_page("views/2_Evaluation_Lab.py")
        with a2:
            if versions:
                if st.button(":material/compare_arrows: Compare", key=f"cmp_{exp['id']}", use_container_width=True):
                    st.session_state["current_experiment_id"] = exp["id"]
                    st.switch_page("views/4_Compare_Versions.py")
        with a3:
            if st.button(":material/content_copy: Duplicate", key=f"dup_{exp['id']}", use_container_width=True):
                new_id = duplicate_experiment(db, exp["id"], f"{exp['name']} (Copy)")
                if new_id:
                    st.toast("Experiment duplicated.", icon=":material/check_circle:")
                    st.rerun()
        with a4:
            results = summary.get("results", [])
            test_cases = summary.get("test_cases", [])
            if results:
                json_export = export_results_json(
                    exp, versions, test_cases, results, summary.get("evaluation_runs", [])
                )
                st.download_button(
                    ":material/download: Export JSON",
                    json_export,
                    file_name=f"{exp['name']}_export.json",
                    mime="application/json",
                    key=f"exp_{exp['id']}",
                    use_container_width=True,
                )
            else:
                st.caption("No results yet")
        with a5:
            if st.button(":material/delete: Delete", key=f"del_{exp['id']}", use_container_width=True):
                delete_experiment_dialog(exp["id"], exp["name"])
