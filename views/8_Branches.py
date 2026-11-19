"""Manage named prompt branches, merge branch histories, and resolve conflicts."""

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

tab_branches, tab_merge, tab_create = st.tabs(["Active Branches", "Merge Branches", "Start a Branch"])

# ── Tab 1: Active Branches ─────────────────────────────────────────────
with tab_branches:
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
                        merge_badge = " · :violet[merged]" if version.get("parent_2_version_id") else ""
                        st.markdown(f"- **v{version['version_number']} · {version['version_label']}**{marker}{merge_badge}")

# ── Tab 2: Merge Branches ──────────────────────────────────────────────
with tab_merge:
    st.markdown("#### Merge Branches")
    st.caption("Safely combine changes from one branch into another with 3-way analysis and conflict resolution.")

    if len(branches) < 2:
        st.info("You need at least two branches to perform a merge. Create a new branch in the 'Start a Branch' tab first.")
    else:
        branch_options = {b["id"]: b["name"] for b in branches}
        main_branch = next((b for b in branches if b["name"].lower() == "main"), None)
        default_dest_id = main_branch["id"] if main_branch else branches[0]["id"]

        c_dest, c_src = st.columns(2)
        with c_dest:
            dest_id = st.selectbox(
                "Destination branch (merge into)",
                list(branch_options.keys()),
                index=list(branch_options.keys()).index(default_dest_id),
                format_func=lambda bid: branch_options[bid],
                key="merge_dest_branch_sel",
            )
        with c_src:
            avail_src = [bid for bid in branch_options.keys() if bid != dest_id]
            if not avail_src:
                avail_src = [dest_id]
            src_id = st.selectbox(
                "Source branch (merge from)",
                avail_src,
                index=0,
                format_func=lambda bid: branch_options[bid],
                key="merge_src_branch_sel",
            )

        if dest_id == src_id:
            st.warning("Destination and source branches must be different.")
        else:
            dest_branch = next(b for b in branches if b["id"] == dest_id)
            src_branch = next(b for b in branches if b["id"] == src_id)
            dest_head_id = dest_branch["head_version_id"]
            src_head_id = src_branch["head_version_id"]

            dest_ver = version_by_id.get(dest_head_id, {})
            src_ver = version_by_id.get(src_head_id, {})

            st.caption(
                f"Preparing merge: **{src_branch['name']}** (head: v{src_ver.get('version_number', '?')}) "
                f"→ **{dest_branch['name']}** (head: v{dest_ver.get('version_number', '?')})"
            )

            if dest_head_id == src_head_id:
                st.info(f"Both branches already point to the same revision (v{dest_ver.get('version_number', '?')}). Nothing to merge.")
            else:
                ancestor = db.find_lowest_common_ancestor(selected_exp_id, dest_head_id, src_head_id)
                if not ancestor:
                    st.error(
                        f":material/block: Branches '{dest_branch['name']}' and '{src_branch['name']}' do not share a common ancestor. "
                        "Their histories are completely disjoint and they cannot be merged."
                    )
                elif ancestor["id"] == src_head_id:
                    st.info(
                        f"Branch '{dest_branch['name']}' already contains all changes from '{src_branch['name']}' "
                        f"(v{src_ver.get('version_number', '?')} is an ancestor of v{dest_ver.get('version_number', '?')}). Nothing to merge."
                    )
                elif ancestor["id"] == dest_head_id:
                    # Fast-forward merge case
                    st.success(
                        f":material/fast_forward: **Fast-forward merge available**\n\n"
                        f"Destination branch **{dest_branch['name']}** has not diverged from **{src_branch['name']}**. "
                        f"Its head can be advanced directly to v{src_ver.get('version_number', '?')}."
                    )
                    if st.button(
                        f"Fast-forward merge '{src_branch['name']}' into '{dest_branch['name']}'",
                        type="primary",
                        key="btn_execute_fast_forward",
                    ):
                        try:
                            res = db.execute_fast_forward_merge(
                                selected_exp_id,
                                dest_branch["id"],
                                src_branch["id"],
                                expected_dest_head_id=dest_head_id,
                                expected_source_head_id=src_head_id,
                            )
                            st.toast(
                                f"Fast-forwarded '{dest_branch['name']}' to v{res['version_number']}.",
                                icon=":material/check_circle:",
                            )
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                else:
                    # True 3-Way Merge
                    merge_analysis = db.compute_three_way_merge(ancestor, dest_ver, src_ver)
                    anc_label = f"v{ancestor.get('version_number', '?')} · {ancestor.get('version_label', '')}"
                    st.info(f":material/history: Shared ancestor: **{anc_label}**")

                    if merge_analysis["has_conflicts"]:
                        st.warning(
                            f":material/warning: **{len(merge_analysis['conflicts'])} conflict(s) detected.** "
                            "Choose or edit the resolved value for each conflicted field below before finalizing."
                        )
                    else:
                        st.success(":material/check_circle: **Clean merge:** All fields merged cleanly without conflicts.")

                    with st.form("three_way_merge_form"):
                        resolved_values = {}
                        st.markdown("##### Field Breakdown & Conflict Resolution")

                        for field_name, info in merge_analysis["fields"].items():
                            label = field_name.replace("_", " ").title()
                            status = info["status"]

                            if status == "conflict":
                                st.markdown(f"**{label}** :material/warning: :red[Conflict]")
                                choice = st.radio(
                                    f"Resolution for {label}",
                                    [
                                        f"Keep Destination ({dest_branch['name']})",
                                        f"Take Source ({src_branch['name']})",
                                        "Custom resolution",
                                    ],
                                    key=f"conflict_choice_{field_name}",
                                    horizontal=True,
                                )
                                c_d, c_s = st.columns(2)
                                with c_d:
                                    st.caption(f"**{dest_branch['name']} (dest):**")
                                    st.code(str(info["destination"]) if info["destination"] is not None else "(empty)")
                                with c_s:
                                    st.caption(f"**{src_branch['name']} (source):**")
                                    st.code(str(info["source"]) if info["source"] is not None else "(empty)")

                                if choice == f"Keep Destination ({dest_branch['name']})":
                                    resolved_values[field_name] = info["destination"]
                                elif choice == f"Take Source ({src_branch['name']})":
                                    resolved_values[field_name] = info["source"]
                                else:
                                    if field_name in ("system_prompt", "user_prompt_template"):
                                        resolved_values[field_name] = st.text_area(
                                            f"Custom {label}",
                                            value=str(info["destination"] or ""),
                                            key=f"custom_input_{field_name}",
                                            height=140,
                                        )
                                    else:
                                        resolved_values[field_name] = st.text_input(
                                            f"Custom {label}",
                                            value=str(info["destination"] or ""),
                                            key=f"custom_input_{field_name}",
                                        )
                                st.divider()
                            elif status == "auto_source":
                                st.markdown(f"**{label}** · :material/check_circle: :green[Auto-Merged from {src_branch['name']}]")
                                st.caption("Updated on source branch only; taken automatically.")
                                resolved_values[field_name] = info["proposed"]
                            elif status == "auto_dest":
                                st.markdown(f"**{label}** · :material/check_circle: :blue[Retained from {dest_branch['name']}]")
                                st.caption("Updated on destination branch only; destination value preserved.")
                                resolved_values[field_name] = info["proposed"]
                            elif status == "auto_same":
                                st.markdown(f"**{label}** · :material/check_circle: :green[Identical changes on both branches]")
                                resolved_values[field_name] = info["proposed"]
                            else:  # unchanged
                                resolved_values[field_name] = info["proposed"]

                        st.markdown("##### Merge Version Details")
                        custom_label = st.text_input(
                            "Version label",
                            value=f"Merge branch '{src_branch['name']}' into '{dest_branch['name']}'",
                            help="Label given to the new immutable merge revision.",
                        )

                        submitted = st.form_submit_button("Confirm & Merge Branches", type="primary")

                    if submitted:
                        try:
                            res = db.execute_branch_merge(
                                experiment_id=selected_exp_id,
                                dest_branch_id=dest_branch["id"],
                                source_branch_id=src_branch["id"],
                                resolved_fields=resolved_values,
                                custom_label=custom_label,
                                expected_dest_head_id=dest_head_id,
                                expected_source_head_id=src_head_id,
                            )
                            st.toast(
                                f"Created merge revision v{res['version_number']} on '{dest_branch['name']}'.",
                                icon=":material/call_merge:",
                            )
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

# ── Tab 3: Start a Branch ──────────────────────────────────────────────
with tab_create:
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
