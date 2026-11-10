"""
Shabd.Craft — Shared UI Helpers

Centralizes database initialization, template seeding, and cross-page state helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

from src.config import settings
from src.database import Database
from src.schemas import (
    FewShotExample,
    OutputFormat,
    PromptTemplate,
    PromptingTechnique,
    TaskCategory,
)


@st.cache_resource
def get_database() -> Database:
    """Return cached SQLite Database instance and seed built-in templates once."""
    db = Database(settings.db_path)
    _seed_builtin_templates(db)
    return db


def _seed_builtin_templates(db: Database) -> None:
    """Seed built-in prompt templates on first run."""
    existing = db.get_prompt_templates(builtin_only=True)
    if existing:
        return

    data_path = Path(__file__).parent.parent / "data" / "sample_prompts.json"
    if not data_path.exists():
        return

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for t in data.get("builtin_templates", []):
        examples = [FewShotExample(**e) for e in t.get("few_shot_examples", [])]
        template = PromptTemplate(
            name=t["name"],
            description=t.get("description", ""),
            category=TaskCategory(t.get("category", "general")),
            system_prompt=t.get("system_prompt", ""),
            user_prompt_template=t["user_prompt_template"],
            variables=t.get("variables", []),
            technique=PromptingTechnique(t.get("technique", "zero_shot")),
            few_shot_examples=examples,
            output_format=OutputFormat(t.get("output_format", "text")),
            example_input=t.get("example_input", ""),
            example_output=t.get("example_output", ""),
            eval_criteria=t.get("eval_criteria", {}),
            is_builtin=True,
        )
        db.save_prompt_template(template)


def load_template_into_workshop(tmpl: dict) -> None:
    """Populate Prompt Workshop session state and clear stale widget keys."""
    system_prompt = tmpl.get("system_prompt", "") or ""
    user_prompt = tmpl.get("user_prompt_template", "") or ""
    technique = tmpl.get("technique", "zero_shot") or "zero_shot"
    output_format = tmpl.get("output_format", "text") or "text"
    category = tmpl.get("category", "general") or "general"

    st.session_state["prompt_system"] = system_prompt
    st.session_state["prompt_user"] = user_prompt
    st.session_state["prompt_technique"] = technique
    st.session_state["prompt_output_format"] = output_format

    st.session_state["ws_system"] = system_prompt
    st.session_state["ws_user"] = user_prompt
    st.session_state["ws_technique"] = technique
    st.session_state["ws_format"] = output_format
    st.session_state["ws_category"] = category
    st.session_state["ws_exp_name"] = tmpl.get("name", "")
    st.session_state["ws_sample_input"] = tmpl.get("example_input", "") or ""
    st.session_state["ws_expected"] = tmpl.get("example_output", "") or ""
    st.session_state["ws_last_response"] = None

    raw_fs = tmpl.get("few_shot_examples", [])
    if isinstance(raw_fs, str):
        try:
            raw_fs = json.loads(raw_fs)
        except json.JSONDecodeError:
            raw_fs = []
    st.session_state["ws_few_shots"] = raw_fs

    # Clear widget-bound keys so text areas/selectboxes pick up the new values
    for widget_key in ("ta_system", "ta_user", "sel_technique", "input_exp_name", "ta_sample", "ta_expected"):
        st.session_state.pop(widget_key, None)

