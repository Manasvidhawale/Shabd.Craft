"""
Shabd.Craft — User Settings

Interactive preferences for API keys, default models, evaluation weights,
and workspace data management.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from src.config import settings
from src.ui_helpers import (
    apply_user_settings_to_runtime,
    get_active_eval_weights,
    get_database,
    render_page_header,
    restore_starter_templates,
)

db = get_database()
apply_user_settings_to_runtime()

render_page_header("Settings", "Manage your API connection, default model, evaluation preferences, and workspace data.")

tab_api, tab_eval, tab_data = st.tabs(["API & Model", "Evaluation Preferences", "Workspace Data"])

# ── Tab 1: API & Model ─────────────────────────────────────────────────
with tab_api:
    st.markdown("##### OpenAI API Connection")

    if settings.has_api_key and not settings.demo_mode:
        st.success("OpenAI API key is active for this session.")
    else:
        st.info("No OpenAI API key is active. Prompts run using the built-in local fallback.")

    with st.form("api_key_form"):
        new_key = st.text_input(
            "OpenAI API Key",
            value="",
            type="password",
            placeholder="sk-... (stored in session only; never logged or saved to database)",
        )
        col_k1, col_k2 = st.columns(2)
        save_key = col_k1.form_submit_button("Save API Key", type="primary", use_container_width=True)
        clear_key = col_k2.form_submit_button("Clear Session Key", use_container_width=True)

    if save_key:
        if not new_key.strip():
            st.error("Enter an API key before saving.")
        else:
            st.session_state["user_openai_api_key"] = new_key.strip()
            apply_user_settings_to_runtime()
            st.success("API key saved for this session.")
            st.rerun()
    elif clear_key:
        st.session_state["user_openai_api_key"] = ""
        settings._reload()
        st.info("Session API key cleared.")
        st.rerun()

    st.divider()

    st.markdown("##### Default Model")
    cur_model = st.session_state.get("user_default_model", settings.default_model)
    if cur_model not in settings.AVAILABLE_MODELS:
        cur_model = settings.AVAILABLE_MODELS[0]

    chosen_model = st.selectbox(
        "Preferred Default Model",
        settings.AVAILABLE_MODELS,
        index=settings.AVAILABLE_MODELS.index(cur_model),
    )
    if chosen_model != cur_model:
        st.session_state["user_default_model"] = chosen_model
        st.session_state["ws_model"] = chosen_model
        apply_user_settings_to_runtime()
        st.success(f"Default model updated to `{chosen_model}`.")

    pricing_rows = [
        {
            "Model": m,
            "Input ($ / 1K tokens)": f"${settings.MODEL_PRICING[m]['input']:.5f}",
            "Output ($ / 1K tokens)": f"${settings.MODEL_PRICING[m]['output']:.5f}",
        }
        for m in settings.AVAILABLE_MODELS
        if m in settings.MODEL_PRICING
    ]
    if pricing_rows:
        st.dataframe(pd.DataFrame(pricing_rows), use_container_width=True, hide_index=True)

# ── Tab 2: Evaluation Preferences ──────────────────────────────────────
with tab_eval:
    st.markdown("##### Default Evaluation Weights")
    st.caption("These weights are used automatically in Evaluation Lab and Prompt Optimizer.")

    active_w = get_active_eval_weights()
    with st.form("eval_weights_form"):
        w1, w2 = st.columns(2)
        with w1:
            acc = st.slider("Accuracy", 0.0, 1.0, float(active_w.accuracy), 0.05)
            rel = st.slider("Relevance", 0.0, 1.0, float(active_w.relevance), 0.05)
            ins = st.slider("Instruction Adherence", 0.0, 1.0, float(active_w.instruction_adherence), 0.05)
        with w2:
            cla = st.slider("Clarity", 0.0, 1.0, float(active_w.clarity), 0.05)
            fmt = st.slider("Format Compliance", 0.0, 1.0, float(active_w.format_compliance), 0.05)

        b1, b2 = st.columns(2)
        save_w = b1.form_submit_button("Save Preferences", type="primary", use_container_width=True)
        reset_w = b2.form_submit_button("Reset to Defaults", use_container_width=True)

    if save_w:
        if acc + rel + ins + cla + fmt == 0:
            st.error("At least one weight must be greater than zero.")
        else:
            st.session_state["user_eval_weights"] = {
                "accuracy": acc,
                "relevance": rel,
                "instruction_adherence": ins,
                "clarity": cla,
                "format_compliance": fmt,
            }
            st.success("Default evaluation weights saved.")
    elif reset_w:
        st.session_state.pop("user_eval_weights", None)
        st.info("Evaluation weights reset to defaults.")
        st.rerun()

# ── Tab 3: Workspace Data ──────────────────────────────────────────────
with tab_data:
    st.markdown("##### Workspace Storage")

    metrics = db.get_dashboard_metrics()
    tmpls = db.get_prompt_templates()
    d1, d2, d3 = st.columns(3)
    d1.metric("Saved Experiments", metrics["total_experiments"])
    d2.metric("Prompt Versions", metrics["total_versions"])
    d3.metric("Library Prompts", len(tmpls))

    st.divider()

    st.markdown("##### Manage Library & History")
    wd1, wd2 = st.columns(2)
    with wd1:
        if st.button("Restore Starter Prompts", use_container_width=True):
            added = restore_starter_templates(db)
            st.success(f"Restored {added} starter prompts." if added else "All starter prompts are already present.")
    with wd2:
        if st.button("Clear All Experiments", use_container_width=True):
            st.session_state["settings_confirm_clear"] = True

    if st.session_state.get("settings_confirm_clear"):
        st.warning("This will permanently remove all saved experiments, versions, test cases, and results. Library prompts are kept.")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("Yes, Clear Experiments", type="primary", use_container_width=True):
                db.clear_all_experiments()
                st.session_state["current_experiment_id"] = None
                st.session_state["current_version_id"] = None
                st.session_state["ws_editing_exp_id"] = None
                st.session_state["ws_editing_ver_id"] = None
                st.session_state.pop("settings_confirm_clear", None)
                st.success("All experiments cleared.")
                st.rerun()
        with cc2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.pop("settings_confirm_clear", None)
                st.rerun()
