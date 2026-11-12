"""
Shabd.Craft — Prompt Library

Create, edit, delete, preview, and launch reusable prompt templates.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

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

db = get_database()

render_page_header("Prompt Library", "Create, edit, delete, and launch reusable prompt templates.")

tab_browse, tab_create = st.tabs(["Browse Prompts", "Add New Prompt"])

# ── Browse Tab ─────────────────────────────────────────────────────────
with tab_browse:
    f1, f2, f3, f4 = st.columns([3, 1.2, 1.2, 1.2])
    with f1:
        search = st.text_input("Search", placeholder="Search prompts...", key="lib_search")
    with f2:
        cat_options = ["All"] + [e.value for e in TaskCategory]
        cat_filter = st.selectbox(
            "Category",
            cat_options,
            format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All",
            key="lib_cat",
        )
    with f3:
        source_filter = st.selectbox("Source", ["All", "Starter", "Custom"], key="lib_source")
    with f4:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("Restore Starters", use_container_width=True):
            added = restore_starter_templates(db)
            st.success(f"Restored {added} starter prompts." if added else "All starter prompts are already present.")
            st.rerun()

    if source_filter == "Starter":
        templates = db.get_prompt_templates(builtin_only=True)
    elif source_filter == "Custom":
        templates = db.get_prompt_templates(user_only=True)
    else:
        templates = db.get_prompt_templates()

    if search:
        q = search.lower()
        templates = [
            t for t in templates
            if q in t["name"].lower() or q in t.get("description", "").lower()
        ]
    if cat_filter != "All":
        templates = [t for t in templates if t["category"] == cat_filter]

    st.caption(f"Showing {len(templates)} prompts")

    # Inline edit panel if a user clicked Edit on a card
    edit_id = st.session_state.get("lib_editing_id")
    if edit_id:
        edit_tmpl = next((t for t in db.get_prompt_templates() if t["id"] == edit_id), None)
        if edit_tmpl:
            with st.container(border=True):
                st.markdown(f"##### Edit Prompt: {edit_tmpl['name']}")
                with st.form(f"edit_tmpl_form_{edit_id}"):
                    et_name = st.text_input("Prompt Name", value=edit_tmpl["name"])
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
                    save_edit = es1.form_submit_button("Save Changes", type="primary", use_container_width=True)
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
                        st.success("Prompt updated.")
                        st.rerun()
                elif cancel_edit:
                    st.session_state.pop("lib_editing_id", None)
                    st.rerun()

    if not templates:
        st.info("No prompts match your filters. Add one in the 'Add New Prompt' tab or click 'Restore Starters'.")
    else:
        cols = st.columns(2, gap="medium")
        for i, tmpl in enumerate(templates):
            with cols[i % 2]:
                cat_tag = tmpl["category"].replace("_", " ").upper()
                is_builtin = bool(tmpl.get("is_builtin", False))
                badge = "Starter" if is_builtin else "Custom"
                badge_color = "#7c5cfc" if is_builtin else "#22d3ee"
                badge_rgb = "124,92,252" if is_builtin else "34,211,238"
                desc = tmpl.get("description", "")
                desc_short = (desc[:110] + "...") if len(desc) > 110 else desc

                st.markdown(f"""
                <div class="card-surface" style="min-height:142px;display:flex;flex-direction:column;justify-content:space-between;">
                    <div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                            <span style="font-size:0.7rem;font-weight:600;letter-spacing:0.08em;color:var(--accent-cyan);">{cat_tag}</span>
                            <span style="font-size:0.68rem;padding:2px 8px;border-radius:12px;background:rgba({badge_rgb},0.15);color:{badge_color};">{badge}</span>
                        </div>
                        <div style="font-size:1.02rem;font-weight:600;color:var(--text-primary);margin-bottom:0.25rem;">{tmpl['name']}</div>
                        <p style="color:var(--text-secondary);font-size:0.82rem;margin:0.2rem 0;">{desc_short}</p>
                    </div>
                    <div style="color:var(--text-muted);font-size:0.72rem;margin-top:0.5rem;">
                        Technique: {tmpl.get('technique', 'zero_shot').replace('_', ' ').title()}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                bc1, bc2, bc3 = st.columns(3)
                with bc1:
                    if st.button("Open", key=f"use_{tmpl['id']}", use_container_width=True):
                        load_template_into_workshop(tmpl)
                        st.switch_page("views/1_Prompt_Workshop.py")
                with bc2:
                    if st.button("Edit", key=f"edit_t_{tmpl['id']}", use_container_width=True):
                        st.session_state["lib_editing_id"] = tmpl["id"]
                        st.rerun()
                with bc3:
                    if st.button("Delete", key=f"del_t_{tmpl['id']}", use_container_width=True):
                        st.session_state[f"confirm_del_t_{tmpl['id']}"] = True

                if st.session_state.get(f"confirm_del_t_{tmpl['id']}"):
                    cd1, cd2 = st.columns(2)
                    with cd1:
                        if st.button("Confirm Delete", key=f"yes_t_{tmpl['id']}", type="primary", use_container_width=True):
                            db.delete_prompt_template(tmpl["id"], allow_builtin=True)
                            st.session_state.pop(f"confirm_del_t_{tmpl['id']}", None)
                            if st.session_state.get("lib_editing_id") == tmpl["id"]:
                                st.session_state.pop("lib_editing_id", None)
                            st.rerun()
                    with cd2:
                        if st.button("Cancel", key=f"no_t_{tmpl['id']}", use_container_width=True):
                            st.session_state.pop(f"confirm_del_t_{tmpl['id']}", None)
                            st.rerun()

# ── Add New Prompt Tab ─────────────────────────────────────────────────
with tab_create:
    st.markdown("##### Add New Prompt")

    with st.form("create_template"):
        ct_name = st.text_input("Prompt Name", placeholder="e.g., Support Ticket Classifier")
        ct_desc = st.text_area("Description", height=60, placeholder="What does this prompt do?")

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

        ct_system = st.text_area("System Prompt", height=80, placeholder="You are a helpful assistant...")
        ct_user = st.text_area("User Prompt Template", height=120, placeholder="Analyze the following:\n\n{{input_text}}")
        ct_example_in = st.text_area("Sample Input (optional)", height=60)
        ct_example_out = st.text_area("Expected Output (optional)", height=60)

        if st.form_submit_button("Save Prompt", type="primary"):
            if not ct_name.strip():
                st.error("Prompt name is required.")
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
                st.success(f"Prompt '{ct_name.strip()}' added to your library.")
                st.rerun()
