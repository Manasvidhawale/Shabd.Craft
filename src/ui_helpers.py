"""
Shabd.Craft — Shared UI Helpers

Centralizes database initialization, template seeding, standardized headers,
cross-page state loaders, and user preferences.
"""

from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

from src.config import settings
from src.database import Database
from src.schemas import (
    EvaluationWeights,
    FewShotExample,
    OutputFormat,
    PromptTemplate,
    PromptingTechnique,
    TaskCategory,
)

_WORKSHOP_WIDGET_KEYS = (
    "ta_system",
    "ta_user",
    "sel_technique",
    "sel_format",
    "sel_category",
    "sel_model",
    "input_exp_name",
    "ta_sample",
    "ta_expected",
)


@st.cache_resource
def get_database() -> Database:
    """Return cached SQLite Database instance and seed starter templates once."""
    db = Database(settings.db_path)
    if db.get_meta("templates_seeded") != "1":
        _seed_builtin_templates(db)
        db.set_meta("templates_seeded", "1")
    return db


def _seed_builtin_templates(db: Database) -> int:
    """Seed starter prompt templates from data/sample_prompts.json if absent."""
    existing_names = {t["name"] for t in db.get_prompt_templates()}
    data_path = Path(__file__).parent.parent / "data" / "sample_prompts.json"
    if not data_path.exists():
        return 0

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    added = 0
    for t in data.get("builtin_templates", []):
        if t["name"] in existing_names:
            continue
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
        added += 1
    return added


def restore_starter_templates(db: Database) -> int:
    """Restore any deleted starter templates on explicit user request."""
    added = _seed_builtin_templates(db)
    db.set_meta("templates_seeded", "1")
    return added


def render_page_header(title: str, subtitle: str) -> None:
    """Render a consistent header and divider across every view."""
    st.markdown(f"## {title}")
    st.caption(subtitle)
    st.divider()


def render_empty_experiment_state(message: str) -> None:
    """Render a consistent empty state with a direct link to Prompt Workshop."""
    st.info(message)
    if st.button("New Prompt in Workshop", type="primary"):
        st.switch_page("views/1_Prompt_Workshop.py")


def clear_workshop_widgets() -> None:
    """Clear widget-bound keys so programmatic workshop state updates render immediately."""
    for widget_key in _WORKSHOP_WIDGET_KEYS:
        st.session_state.pop(widget_key, None)


def load_template_into_workshop(tmpl: dict) -> None:
    """Populate Prompt Workshop session state from a library template."""
    system_prompt = tmpl.get("system_prompt", "") or ""
    user_prompt = tmpl.get("user_prompt_template", "") or ""
    technique = tmpl.get("technique", "zero_shot") or "zero_shot"
    output_format = tmpl.get("output_format", "text") or "text"
    category = tmpl.get("category", "general") or "general"

    st.session_state["prompt_system"] = system_prompt
    st.session_state["prompt_user"] = user_prompt
    st.session_state["prompt_technique"] = technique
    st.session_state["prompt_output_format"] = output_format

    st.session_state["ws_editing_exp_id"] = None
    st.session_state["ws_editing_ver_id"] = None
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
    clear_workshop_widgets()


def load_version_into_workshop(db: Database, exp: dict, ver: dict) -> None:
    """Load an existing saved experiment and prompt version into Prompt Workshop."""
    raw_fs = ver.get("few_shot_examples", "[]")
    if isinstance(raw_fs, str):
        try:
            raw_fs = json.loads(raw_fs)
        except json.JSONDecodeError:
            raw_fs = []

    test_cases = db.get_test_cases(exp["id"])
    first_input = test_cases[0]["input_data"] if test_cases else ""
    first_expected = test_cases[0].get("expected_output", "") if test_cases else ""

    st.session_state["current_experiment_id"] = exp["id"]
    st.session_state["current_version_id"] = ver["id"]
    st.session_state["ws_editing_exp_id"] = exp["id"]
    st.session_state["ws_editing_ver_id"] = ver["id"]

    st.session_state["ws_exp_name"] = exp.get("name", "")
    st.session_state["ws_category"] = exp.get("category", "general")
    st.session_state["ws_system"] = ver.get("system_prompt", "") or ""
    st.session_state["ws_user"] = ver.get("user_prompt_template", "") or ""
    st.session_state["ws_technique"] = ver.get("technique", "zero_shot") or "zero_shot"
    st.session_state["ws_format"] = ver.get("output_format", "text") or "text"
    st.session_state["ws_temp"] = float(ver.get("temperature", 0.7))
    st.session_state["ws_max_tokens"] = int(ver.get("max_tokens", 1024))
    st.session_state["ws_model"] = ver.get("model_name") or settings.default_model
    st.session_state["ws_few_shots"] = raw_fs
    st.session_state["ws_sample_input"] = first_input
    st.session_state["ws_expected"] = first_expected
    st.session_state["ws_last_response"] = None
    clear_workshop_widgets()


def get_active_eval_weights() -> EvaluationWeights:
    """Return user-configured evaluation weights from session state or defaults."""
    saved = st.session_state.get("user_eval_weights")
    if isinstance(saved, dict):
        return EvaluationWeights(**saved)
    return EvaluationWeights(**settings.DEFAULT_EVAL_WEIGHTS)


def apply_user_settings_to_runtime() -> None:
    """Apply in-session user preferences (API key, default model) to runtime settings."""
    api_key = st.session_state.get("user_openai_api_key")
    if api_key is not None:
        settings.openai_api_key = api_key
    default_model = st.session_state.get("user_default_model")
    if default_model in settings.AVAILABLE_MODELS:
        settings.default_model = default_model
