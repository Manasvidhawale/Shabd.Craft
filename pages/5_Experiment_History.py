"""
Shabd.Craft — Experiment History

Persistent experiment management with search, actions, and export.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import json
import pandas as pd
from src.config import settings
from src.database import Database
from src.experiment_service import duplicate_experiment, get_experiment_summary
from src.export_service import export_results_csv, export_results_json

st.set_page_config(page_title="Experiment History — Shabd.Craft", page_icon="✦", layout="wide")

@st.cache_resource
def get_db():
    return Database(settings.db_path)

db = get_db()

st.markdown("## Experiment History")
st.caption("View, manage, and export your prompt engineering experiments.")
st.divider()

experiments = db.list_experiments(limit=100)

if not experiments:
    st.info("No experiments yet. Start by creating one in the Prompt Workshop.")
    if st.button("Go to Prompt Workshop", type="primary"):
        st.switch_page("pages/1_Prompt_Workshop.py")
    st.stop()

# ── Search & Filter ────────────────────────────────────────────────────
f1, f2 = st.columns([3, 1])
with f1:
    search = st.text_input("Search experiments", placeholder="Search by name...")
with f2:
    categories = sorted(set(e["category"] for e in experiments))
    cat_filter = st.selectbox("Category", ["All"] + categories)

# Filter experiments
filtered = experiments
if search:
    filtered = [e for e in filtered if search.lower() in e["name"].lower()]
if cat_filter != "All":
    filtered = [e for e in filtered if e["category"] == cat_filter]

st.caption(f"Showing {len(filtered)} of {len(experiments)} experiments")
st.markdown("")

# ── Experiment List ────────────────────────────────────────────────────
for exp in filtered:
    summary = get_experiment_summary(db, exp["id"])
    status_label = {"pending": "[PENDING]", "running": "[RUNNING]", "success": "[SUCCESS]",
                    "failed": "[FAILED]", "partial": "[PARTIAL]"}.get(exp["status"], "[PENDING]")

    with st.expander(f"{status_label} {exp['name']} — {exp['category'].replace('_',' ').title()}", expanded=False):
        # Info row
        ic1, ic2, ic3, ic4 = st.columns(4)
        ic1.metric("Versions", summary.get("version_count", 0))
        ic2.metric("Test Cases", summary.get("test_case_count", 0))
        ic3.metric("Evaluations", summary.get("evaluation_count", 0))
        ic4.metric("Avg Score", f"{summary.get('avg_score', 0):.1f}" if summary.get("avg_score") else "—")

        st.caption(f"Created: {exp['created_at'][:19]} · Updated: {exp['updated_at'][:19]}")
        if exp.get("description"):
            st.markdown(f"*{exp['description']}*")

        # Prompt versions
        versions = summary.get("versions", [])
        if versions:
            st.markdown("**Prompt Versions:**")
            for v in versions:
                opt_badge = " (Optimized)" if v.get("is_optimized") else ""
                st.markdown(f"- v{v['version_number']}: {v['version_label']}{opt_badge}")

        st.markdown("")

        # Action buttons
        a1, a2, a3, a4, a5 = st.columns(5)

        with a1:
            if st.button("Evaluate", key=f"eval_{exp['id']}"):
                st.session_state["current_experiment_id"] = exp["id"]
                st.switch_page("pages/2_Evaluation_Lab.py")

        with a2:
            if len(versions) >= 2:
                if st.button("Compare", key=f"cmp_{exp['id']}"):
                    st.session_state["current_experiment_id"] = exp["id"]
                    st.switch_page("pages/4_Compare_Versions.py")

        with a3:
            if st.button("Duplicate", key=f"dup_{exp['id']}"):
                new_id = duplicate_experiment(db, exp["id"], f"{exp['name']} (copy)")
                if new_id:
                    st.success("Experiment duplicated!")
                    st.rerun()

        with a4:
            # Export
            results = summary.get("results", [])
            test_cases = summary.get("test_cases", [])
            if results:
                json_export = export_results_json(exp, versions, test_cases, results)
                st.download_button("Export", json_export,
                                  file_name=f"{exp['name']}_export.json",
                                  mime="application/json",
                                  key=f"exp_{exp['id']}")

        with a5:
            if st.button("Delete", key=f"del_{exp['id']}"):
                st.session_state[f"confirm_del_{exp['id']}"] = True

            if st.session_state.get(f"confirm_del_{exp['id']}"):
                st.warning("Are you sure?")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("Yes, delete", key=f"yes_del_{exp['id']}"):
                        db.delete_experiment(exp["id"])
                        del st.session_state[f"confirm_del_{exp['id']}"]
                        st.rerun()
                with dc2:
                    if st.button("Cancel", key=f"no_del_{exp['id']}"):
                        del st.session_state[f"confirm_del_{exp['id']}"]
                        st.rerun()
