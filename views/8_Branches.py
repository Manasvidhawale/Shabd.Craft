"""Manage named prompt branches and their version histories."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.ui_helpers import get_database, load_version_into_workshop, render_empty_experiment_state, render_page_header

db = get_database()
render_page_header("Branches", "Try different prompt ideas without changing the main line of work.")


@st.dialog("Remove branch")
def confirm_remove_branch(branch_id: str, branch_name: str):
    st.write(f"Remove **{branch_name}** from this experiment?")
    st.caption("Its saved versions will stay in history and can be used to start another branch.")
    yes, no = st.columns(2)
    with yes:
        if st.button("Remove branch", type="primary", use_container_width=True):
            branch = db.get_prompt_branch(branch_id)
            db.delete_prompt_branch(branch_id)
            if st.session_state.get("current_branch_id") == branch_id:
                st.session_state.pop("current_branch_id", None)
                if branch:
                    st.session_state.pop(f"ws_branch_selector_{branch['experiment_id']}", None)
            st.toast(f"Removed branch '{branch_name}'.", icon=":material/check_circle:")
            st.rerun()
    with no:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


experiments = db.list_experiments()
if not experiments:
    render_empty_experiment_state("Create a prompt first, then use branches to explore different versions.")
    st.stop()

exp_by_id = {exp["id"]: exp for exp in experiments}
default_exp = st.session_state.get("current_experiment_id")
if default_exp not in exp_by_id:
    default_exp = experiments[0]["id"]

selected_exp_id = st.selectbox(
    "Prompt",
    list(exp_by_id),
    index=list(exp_by_id).index(default_exp),
    format_func=lambda exp_id: exp_by_id[exp_id]["name"],
    key="branches_experiment_selector",
)
st.session_state["current_experiment_id"] = selected_exp_id

versions = db.get_prompt_versions(selected_exp_id)
branches = db.get_prompt_branches(selected_exp_id)
version_by_id = {version["id"]: version for version in versions}

st.markdown("#### Branches")
if not branches:
    st.info("This prompt has no saved versions yet. Save it in the Prompt Workshop to create the main branch.")
else:
    for branch in branches:
        head = version_by_id.get(branch["head_version_id"], {})
        base = version_by_id.get(branch["base_version_id"], {})
        with st.container(border=True):
            info, actions = st.columns([4, 1.5])
            with info:
                title = f"{branch['name']}  ·  v{head.get('version_number', '?')} {head.get('version_label', '')}"
                st.markdown(f"**{title.strip()}**")
                if branch["name"].lower() == "main":
                    st.caption("Starting point for this prompt")
                else:
                    st.caption(f"Started from v{base.get('version_number', '?')} · {branch.get('description') or 'No note'}")
            with actions:
                if st.button("Open in Workshop", key=f"open_branch_{branch['id']}", use_container_width=True):
                    if head:
                        st.session_state["current_branch_id"] = branch["id"]
                        st.session_state["current_experiment_id"] = selected_exp_id
                        st.session_state["current_version_id"] = head["id"]
                        st.session_state.pop(f"ws_branch_selector_{selected_exp_id}", None)
                        load_version_into_workshop(db, exp_by_id[selected_exp_id], head)
                        st.switch_page("views/1_Prompt_Workshop.py")
                if branch["name"].lower() != "main":
                    if st.button("Remove", key=f"remove_branch_{branch['id']}", use_container_width=True):
                        confirm_remove_branch(branch["id"], branch["name"])

            history = db.get_prompt_branch_history(branch["id"])
            with st.expander(f"Versions on {branch['name']} ({len(history)})"):
                for version in history:
                    marker = " · current" if version["id"] == branch["head_version_id"] else ""
                    st.markdown(f"- **v{version['version_number']} · {version['version_label']}**{marker}")

st.divider()
st.markdown("#### Start a branch")
if not versions:
    st.info("Save a prompt version before starting a branch.")
else:
    version_labels = {
        version["id"]: f"v{version['version_number']} · {version['version_label']}"
        for version in versions
    }
    default_source = st.session_state.get("current_version_id")
    if default_source not in version_labels:
        default_source = versions[-1]["id"]
    source_index = list(version_labels).index(default_source)

    with st.form("create_prompt_branch_form"):
        branch_name = st.text_input("Branch name", placeholder="e.g. shorter-replies", max_chars=60)
        source_id = st.selectbox(
            "Start from version",
            list(version_labels),
            index=source_index,
            format_func=lambda version_id: version_labels[version_id],
        )
        description = st.text_input("What are you exploring? (optional)", placeholder="e.g. Keep answers to one sentence")
        create = st.form_submit_button("Create branch", type="primary")

    if create:
        try:
            branch_id = db.create_prompt_branch(selected_exp_id, branch_name, source_id, description)
            st.session_state["current_branch_id"] = branch_id
            st.session_state["current_experiment_id"] = selected_exp_id
            st.session_state["current_version_id"] = source_id
            st.session_state.pop(f"ws_branch_selector_{selected_exp_id}", None)
            st.toast(f"Created branch '{branch_name.strip()}'.", icon=":material/call_split:")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
