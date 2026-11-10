"""
Shabd.Craft — Prompt Library

Reusable prompt templates with built-in and user-created templates.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import json
from src.config import settings
from src.database import Database
from src.schemas import (
    PromptTemplate, FewShotExample, TaskCategory,
    PromptingTechnique, OutputFormat, _now,
)

st.set_page_config(page_title="Prompt Library — Shabd.Craft", page_icon="✦", layout="wide")

@st.cache_resource
def get_db():
    return Database(settings.db_path)

db = get_db()

st.markdown("## Prompt Library")
st.caption("Browse, search, and manage reusable prompt templates.")
st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────
tab_browse, tab_create = st.tabs(["Browse Templates", "Create Template"])

# ── Browse Tab ─────────────────────────────────────────────────────────
with tab_browse:
    # Filters
    f1, f2, f3 = st.columns([3, 1, 1])
    with f1:
        search = st.text_input("Search", placeholder="Search templates...", key="lib_search")
    with f2:
        cat_options = ["All"] + [e.value for e in TaskCategory]
        cat_filter = st.selectbox("Category", cat_options,
                                  format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All",
                                  key="lib_cat")
    with f3:
        source_filter = st.selectbox("Source", ["All", "Built-in", "My Templates"], key="lib_source")

    # Fetch templates
    if source_filter == "Built-in":
        templates = db.get_prompt_templates(builtin_only=True)
    elif source_filter == "My Templates":
        templates = db.get_prompt_templates(user_only=True)
    else:
        templates = db.get_prompt_templates()

    # Apply filters
    if search:
        templates = [t for t in templates if search.lower() in t["name"].lower()
                     or search.lower() in t.get("description", "").lower()]
    if cat_filter != "All":
        templates = [t for t in templates if t["category"] == cat_filter]

    st.caption(f"Showing {len(templates)} templates")
    st.markdown("")

    if not templates:
        st.info("No templates match your filters.")
    else:
        # Display in grid
        cols = st.columns(2)
        for i, tmpl in enumerate(templates):
            with cols[i % 2]:
                cat_tag = tmpl["category"].replace("_", " ").upper()
                is_builtin = tmpl.get("is_builtin", False)
                badge = "Built-in" if is_builtin else "Custom"
                badge_color = "#7c5cfc" if is_builtin else "#22d3ee"

                with st.container():
                    st.markdown(f"""
                    <div style="background:#1e2130;border:1px solid #2a2d3e;border-radius:12px;padding:1.2rem;margin-bottom:0.8rem;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                            <span style="font-size:0.7rem;font-weight:600;letter-spacing:0.08em;color:#22d3ee;">{cat_tag}</span>
                            <span style="font-size:0.68rem;padding:2px 8px;border-radius:12px;background:rgba({','.join(['124,92,252' if is_builtin else '34,211,238'])},0.15);color:{badge_color};">{badge}</span>
                        </div>
                        <div style="font-size:1.05rem;font-weight:600;color:#e8eaed;margin-bottom:0.3rem;">{tmpl['name']}</div>
                        <p style="color:#9ba3b5;font-size:0.82rem;margin:0.3rem 0;">{tmpl.get('description', '')[:120]}</p>
                        <div style="color:#6b7280;font-size:0.72rem;margin-top:0.4rem;">
                            Technique: {tmpl.get('technique', 'zero_shot').replace('_',' ').title()}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    bc1, bc2, bc3 = st.columns(3)
                    with bc1:
                        if st.button("Use", key=f"use_{tmpl['id']}"):
                            st.session_state["prompt_system"] = tmpl.get("system_prompt", "")
                            st.session_state["prompt_user"] = tmpl["user_prompt_template"]
                            st.session_state["prompt_technique"] = tmpl.get("technique", "zero_shot")
                            st.session_state["prompt_output_format"] = tmpl.get("output_format", "text")
                            st.session_state["ws_system"] = tmpl.get("system_prompt", "")
                            st.session_state["ws_user"] = tmpl["user_prompt_template"]
                            st.session_state["ws_technique"] = tmpl.get("technique", "zero_shot")
                            st.session_state["ws_format"] = tmpl.get("output_format", "text")
                            st.switch_page("pages/1_Prompt_Workshop.py")
                    with bc2:
                        if st.button("Preview", key=f"prev_{tmpl['id']}"):
                            st.session_state[f"preview_{tmpl['id']}"] = True
                    with bc3:
                        if not is_builtin:
                            if st.button("Delete", key=f"del_t_{tmpl['id']}"):
                                db.delete_prompt_template(tmpl["id"])
                                st.rerun()

                    # Preview section
                    if st.session_state.get(f"preview_{tmpl['id']}"):
                        with st.container():
                            if tmpl.get("system_prompt"):
                                st.markdown("**System Prompt:**")
                                st.code(tmpl["system_prompt"], language="text")
                            st.markdown("**User Prompt Template:**")
                            st.code(tmpl["user_prompt_template"], language="text")

                            variables = json.loads(tmpl.get("variables", "[]")) if isinstance(tmpl.get("variables"), str) else tmpl.get("variables", [])
                            if variables:
                                st.caption(f"Variables: `{'`, `'.join(variables)}`")

                            if tmpl.get("example_input"):
                                st.markdown("**Example Input:**")
                                st.code(tmpl["example_input"][:300], language="text")
                            if tmpl.get("example_output"):
                                st.markdown("**Example Output:**")
                                st.code(tmpl["example_output"][:300], language="text")

                            if st.button("Close preview", key=f"close_{tmpl['id']}"):
                                del st.session_state[f"preview_{tmpl['id']}"]
                                st.rerun()

# ── Create Template Tab ────────────────────────────────────────────────
with tab_create:
    st.markdown("##### Create New Template")

    with st.form("create_template"):
        ct_name = st.text_input("Template Name", placeholder="My Custom Template")
        ct_desc = st.text_area("Description", height=60, placeholder="What does this template do?")

        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            ct_category = st.selectbox("Category", [e.value for e in TaskCategory],
                                       format_func=lambda x: x.replace("_", " ").title(),
                                       key="ct_cat")
        with cc2:
            ct_technique = st.selectbox("Technique", [e.value for e in PromptingTechnique],
                                        format_func=lambda x: x.replace("_", " ").title(),
                                        key="ct_tech")
        with cc3:
            ct_format = st.selectbox("Output Format", [e.value for e in OutputFormat],
                                     format_func=lambda x: x.replace("_", " ").title(),
                                     key="ct_fmt")

        ct_system = st.text_area("System Prompt", height=80, placeholder="You are a helpful assistant...")
        ct_user = st.text_area("User Prompt Template", height=120, placeholder="Analyze the following:\n\n{{input_text}}")
        ct_example_in = st.text_area("Example Input", height=60)
        ct_example_out = st.text_area("Example Output", height=60)

        if st.form_submit_button("Save Template", type="primary"):
            if not ct_name.strip():
                st.error("Template name is required.")
            elif not ct_user.strip():
                st.error("User prompt template is required.")
            else:
                from src.template_engine import extract_variables
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
                st.success(f"Template '{ct_name}' saved!")
                st.rerun()
