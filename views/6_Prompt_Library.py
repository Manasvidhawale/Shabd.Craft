"""
Shabd.Craft — Prompt Library

Create, edit, delete, preview, and launch reusable prompt templates.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
import streamlit as st

from src.schemas import (
    OutputFormat,
    PromptTemplate,
    PromptingTechnique,
    TaskCategory,
    _now,
)
from src.template_engine import extract_variables
from src.ui_helpers import (
    get_database,
    load_template_into_workshop,
    render_page_header,
    restore_starter_templates,
)
from src.ui_theme import status_badge

db = get_database()

render_page_header("Templates", "Start with a ready-made prompt or manage your own templates.")


# ── Delete Template Dialog ─────────────────────────────────────────────
@st.dialog("Delete Template")
def delete_template_dialog(tmpl_id: str, tmpl_name: str):
    st.warning(f"Are you sure you want to permanently delete template **{tmpl_name}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button(":material/delete: Yes, Delete", type="primary", use_container_width=True):
            db.delete_prompt_template(tmpl_id, allow_builtin=True)
            if st.session_state.get("lib_editing_id") == tmpl_id:
                st.session_state.pop("lib_editing_id", None)
            st.toast(f"Deleted template '{tmpl_name}'.", icon=":material/delete:")
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


tab_browse, tab_create = st.tabs(["Browse Catalog", "Add New Template"])

# ── Browse Tab ─────────────────────────────────────────────────────────
with tab_browse:
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns([3, 1.2, 1.2, 1.2])
        with f1:
            search = st.text_input("Search", placeholder="Search templates by keyword...", label_visibility="collapsed", key="lib_search")
        with f2:
            cat_options = ["All"] + [e.value for e in TaskCategory]
            cat_filter = st.selectbox(
                "Category",
                cat_options,
                format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All Categories",
                label_visibility="collapsed",
                key="lib_cat",
            )
        with f3:
            source_filter = st.selectbox("Source", ["All", "Starter", "Custom"], label_visibility="collapsed", key="lib_source")
        with f4:
            if st.button(":material/refresh: Restore Starters", use_container_width=True):
                added = restore_starter_templates(db)
                if added:
                    st.toast(f"Restored {added} starter prompts.", icon=":material/check_circle:")
                else:
                    st.toast("All starter prompts already present.", icon=":material/info:")
                st.rerun()

    if source_filter == "Starter":
        templates = db.get_prompt_templates(builtin_only=True)
    elif source_filter == "Custom":
        templates = db.get_prompt_templates(user_only=True)
    else:
        templates = db.get_prompt_templates()

    if search:
        q = search.lower()
        templates = [t for t in templates if q in t["name"].lower() or q in t.get("description", "").lower()]
    if cat_filter != "All":
        templates = [t for t in templates if t["category"] == cat_filter]

    st.caption(f"Showing {len(templates)} templates")

    # Inline edit panel if editing a template
    edit_id = st.session_state.get("lib_editing_id")
    if edit_id:
        edit_tmpl = next((t for t in db.get_prompt_templates() if t["id"] == edit_id), None)
        if edit_tmpl:
            with st.container(border=True):
                st.markdown(f"##### Edit Template: {edit_tmpl['name']}")
                with st.form(f"edit_tmpl_form_{edit_id}"):
                    et_name = st.text_input("Template Name", value=edit_tmpl["name"])
                    et_desc = st.text_area("Description", value=edit_tmpl.get("description", ""), height=60)
                    ec1, ec2, ec3 = st.columns(3)
                    cats = [e.value for e in TaskCategory]
                    techs = [e.value for e in PromptingTechnique]
                    fmts = [e.value for e in OutputFormat]
                    with ec1:
                        et_cat = st.selectbox(
                            "Category",
                            cats,
                            index=cats.index(edit_tmpl["category"]) if edit_tmpl["category"] in cats else 0,
                            format_func=lambda x: x.replace("_", " ").title(),
                        )
                    with ec2:
                        t_val = edit_tmpl.get("technique", "zero_shot")
                        et_tech = st.selectbox(
                            "Technique",
                            techs,
                            index=techs.index(t_val) if t_val in techs else 0,
                            format_func=lambda x: x.replace("_", " ").title(),
                        )
                    with ec3:
                        f_val = edit_tmpl.get("output_format", "text")
                        et_fmt = st.selectbox(
                            "Output Format",
                            fmts,
                            index=fmts.index(f_val) if f_val in fmts else 0,
                            format_func=lambda x: x.replace("_", " ").title(),
                        )
                    et_sys = st.text_area("System Prompt", value=edit_tmpl.get("system_prompt", ""), height=80)
                    et_usr = st.text_area("User Prompt Template", value=edit_tmpl["user_prompt_template"], height=120)
                    es1, es2 = st.columns(2)
                    save_edit = es1.form_submit_button(":material/save: Save Changes", type="primary", use_container_width=True)
                    cancel_edit = es2.form_submit_button("Cancel", use_container_width=True)

                if save_edit:
                    if not et_name.strip() or not et_usr.strip():
                        st.error("Name and user prompt template are required.")
                    else:
                        updated = PromptTemplate(
                            id=edit_tmpl["id"],
                            name=et_name.strip(),
                            description=et_desc.strip(),
                            category=TaskCategory(et_cat),
                            system_prompt=et_sys,
                            user_prompt_template=et_usr,
                            variables=extract_variables(et_usr),
                            technique=PromptingTechnique(et_tech),
                            output_format=OutputFormat(et_fmt),
                            example_input=edit_tmpl.get("example_input", ""),
                            example_output=edit_tmpl.get("example_output", ""),
                            is_builtin=bool(edit_tmpl.get("is_builtin", False)),
                            created_at=edit_tmpl.get("created_at", _now()),
                            updated_at=_now(),
                        )
                        db.save_prompt_template(updated)
                        st.session_state.pop("lib_editing_id", None)
                        st.toast("Template updated.", icon=":material/check_circle:")
                        st.rerun()
                elif cancel_edit:
                    st.session_state.pop("lib_editing_id", None)
                    st.rerun()

    if not templates:
        st.info(":material/info: No templates match your filters. Add one in the 'Add New Template' tab or click 'Restore Starters'.")
    else:
        cols = st.columns(2, gap="medium")
        for i, tmpl in enumerate(templates):
            with cols[i % 2]:
                with st.container(border=True):
                    is_builtin = bool(tmpl.get("is_builtin", False))
                    head_l, head_r = st.columns([3, 1])
                    with head_l:
                        cat_tag = tmpl["category"].replace("_", " ").upper()
                        st.caption(f":material/tag: {cat_tag}")
                        st.markdown(f"#### {tmpl['name']}")
                    with head_r:
                        badge_label = "STARTER" if is_builtin else "CUSTOM"
                        st.markdown(status_badge("success" if is_builtin else "info", badge_label))

                    desc = tmpl.get("description", "")
                    st.caption((desc[:120] + "…") if len(desc) > 120 else desc)
                    tech_label = tmpl.get("technique", "zero_shot").replace("_", " ").title()
                    st.caption(f"Technique: **{tech_label}**")

                    bc1, bc2, bc3 = st.columns(3)
                    with bc1:
                        if st.button(":material/edit_note: Open", key=f"use_{tmpl['id']}", use_container_width=True):
                            load_template_into_workshop(tmpl)
                            st.switch_page("views/1_Prompt_Workshop.py")
                    with bc2:
                        if st.button(":material/edit: Edit", key=f"edit_t_{tmpl['id']}", use_container_width=True):
                            st.session_state["lib_editing_id"] = tmpl["id"]
                            st.rerun()
                    with bc3:
                        if st.button(":material/delete: Delete", key=f"del_t_{tmpl['id']}", use_container_width=True):
                            delete_template_dialog(tmpl["id"], tmpl["name"])

# ── Add New Template Tab ───────────────────────────────────────────────
with tab_create:
    st.markdown("##### Create Custom Prompt Template")

    with st.container(border=True):
        with st.form("create_template_form", clear_on_submit=True):
            ct_name = st.text_input("Template Name", placeholder="e.g., Support Ticket Classifier", key="ct_name")
            ct_desc = st.text_area("Description", height=60, placeholder="What does this prompt do?", key="ct_desc")

            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                ct_category = st.selectbox(
                    "Category",
                    [e.value for e in TaskCategory],
                    format_func=lambda x: x.replace("_", " ").title(),
                    key="ct_cat",
                )
            with cc2:
                ct_technique = st.selectbox(
                    "Technique",
                    [e.value for e in PromptingTechnique],
                    format_func=lambda x: x.replace("_", " ").title(),
                    key="ct_tech",
                )
            with cc3:
                ct_format = st.selectbox(
                    "Output Format",
                    [e.value for e in OutputFormat],
                    format_func=lambda x: x.replace("_", " ").title(),
                    key="ct_fmt",
                )

            ct_system = st.text_area("System Prompt", height=80, placeholder="You are a helpful assistant...", key="ct_system")
            ct_user = st.text_area("User Prompt Template", height=120, placeholder="Analyze the following:\n\n{{input_text}}", key="ct_user")
            ct_example_in = st.text_area("Sample Input (Optional)", height=60, key="ct_example_in")
            ct_example_out = st.text_area("Expected Output (Optional)", height=60, key="ct_example_out")

            if st.form_submit_button(":material/save: Save Template to Library", type="primary"):
                if not ct_name.strip():
                    st.error("Template name is required.")
                elif not ct_user.strip():
                    st.error("User prompt template is required.")
                else:
                    variables = extract_variables(ct_user)
                    template = PromptTemplate(
                        name=ct_name.strip(),
                        description=ct_desc.strip(),
                        category=TaskCategory(ct_category),
                        system_prompt=ct_system,
                        user_prompt_template=ct_user,
                        variables=variables,
                        technique=PromptingTechnique(ct_technique),
                        output_format=OutputFormat(ct_format),
                        example_input=ct_example_in,
                        example_output=ct_example_out,
                        is_builtin=False,
                    )
                    db.save_prompt_template(template)
                    st.toast(f"Template '{ct_name.strip()}' saved to library.", icon=":material/check_circle:")
                    st.rerun()
