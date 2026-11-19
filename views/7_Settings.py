"""
Shabd.Craft — User Settings

Interactive preferences for API keys, default models, evaluation weights,
and workspace data management.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from src.config import settings
from src.providers.openai_provider import _get_openai_client
from src.ui_helpers import (
    apply_user_settings_to_runtime,
    get_active_eval_weights,
    get_database,
    render_page_header,
    restore_starter_templates,
)
from src.ui_theme import mask_api_key, status_badge

db = get_database()
apply_user_settings_to_runtime()

render_page_header("Settings", "Set your API key, default model, test preferences, and data options.")


# ── Dialog for Destructive Clear ─────────────────────────────────────────
@st.dialog("Clear Workspace Experiments")
def confirm_clear_dialog():
    st.warning("This will permanently remove all saved experiments, versions, test cases, and results. Library prompts will be kept.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Clear Experiments", type="primary", use_container_width=True):
            db.clear_all_experiments()
            st.session_state["current_experiment_id"] = None
            st.session_state["current_version_id"] = None
            st.session_state["ws_editing_exp_id"] = None
            st.session_state["ws_editing_ver_id"] = None
            st.toast("All experiments cleared.", icon=":material/delete:")
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


tab_api, tab_eval, tab_data = st.tabs(["API & Model", "Evaluation Preferences", "Workspace Data"])

# ── Tab 1: API & Model ─────────────────────────────────────────────────
with tab_api:
    st.markdown("##### LLM API Connection")
    with st.container(border=True):
        active_key = settings.openai_api_key
        has_key = bool(active_key and active_key != "your_openai_api_key_here")

        if has_key:
            provider_lbl = "Groq" if settings.is_groq else "OpenAI"
            st.markdown(
                f"{status_badge('success', 'Configured & Active')} · "
                f"**Provider:** {provider_lbl} · **Key:** `{mask_api_key(active_key)}`"
            )
        else:
            st.markdown(
                f"{status_badge('warning', 'No API Key Configured')} · "
                f"Prompts will run using built-in local fallback."
            )

        col_t1, col_t2 = st.columns([3, 1])
        with col_t2:
            if st.button(":material/bolt: Test Connection", use_container_width=True):
                if not has_key:
                    st.error("Cannot test: No API key configured.")
                else:
                    with st.spinner("Testing provider connection..."):
                        try:
                            is_groq = bool(active_key and active_key.startswith("gsk_"))
                            base_url = "https://api.groq.com/openai/v1" if is_groq else (settings.openai_base_url or None)
                            client = _get_openai_client(active_key, base_url)
                            client.models.list()
                            st.toast("Provider connection verified successfully!", icon=":material/check_circle:")
                            st.success(":material/check_circle: Successfully connected to LLM endpoint.")
                        except Exception as e:
                            st.error(f":material/error: Connection test failed: {e}")

        with st.form("api_key_form"):
            new_key = st.text_input(
                "Update API Key for this Session",
                value="",
                type="password",
                placeholder="sk-... or gsk-... (stored in session memory only; never written to database)",
            )
            col_k1, col_k2 = st.columns(2)
            save_key = col_k1.form_submit_button(":material/save: Save Key for Session", type="primary", use_container_width=True)
            clear_key = col_k2.form_submit_button(":material/clear: Clear Session Key", use_container_width=True)

        if save_key:
            if not new_key.strip():
                st.error("Enter an API key before saving.")
            else:
                st.session_state["user_openai_api_key"] = new_key.strip()
                apply_user_settings_to_runtime()
                st.toast("API key saved for this session.", icon=":material/key:")
                st.rerun()
        elif clear_key:
            st.session_state["user_openai_api_key"] = ""
            settings._reload()
            st.toast("Session API key cleared.", icon=":material/delete:")
            st.rerun()

    st.markdown("")
    st.markdown("##### Preferred Model Configuration")
    with st.container(border=True):
        cur_model = st.session_state.get("user_default_model", settings.default_model)
        if cur_model not in settings.AVAILABLE_MODELS:
            cur_model = settings.AVAILABLE_MODELS[0]

        chosen_model = st.selectbox(
            "Default Workshop & Inference Model",
            settings.AVAILABLE_MODELS,
            index=settings.AVAILABLE_MODELS.index(cur_model),
        )
        if chosen_model != cur_model:
            st.session_state["user_default_model"] = chosen_model
            st.session_state["ws_model"] = chosen_model
            apply_user_settings_to_runtime()
            st.toast(f"Default model updated to {chosen_model}.", icon=":material/check:")

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
            st.caption("Pricing Matrix")
            st.dataframe(pd.DataFrame(pricing_rows), use_container_width=True, hide_index=True)

# ── Tab 2: Evaluation Preferences ──────────────────────────────────────
with tab_eval:
    st.markdown("##### Default Evaluation Weights")
    st.caption("These weights are loaded automatically in Evaluation Lab and Prompt Optimizer.")

    active_w = get_active_eval_weights()
    with st.container(border=True):
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
            save_w = b1.form_submit_button(":material/save: Save Weights", type="primary", use_container_width=True)
            reset_w = b2.form_submit_button(":material/restart_alt: Reset to Defaults", use_container_width=True)

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
                st.toast("Evaluation weights saved.", icon=":material/check:")
                st.rerun()
        elif reset_w:
            st.session_state.pop("user_eval_weights", None)
            st.toast("Evaluation weights reset to default.", icon=":material/restart_alt:")
            st.rerun()

# ── Tab 3: Workspace Data ──────────────────────────────────────────────
with tab_data:
    st.markdown("##### Workspace Storage Summary")

    metrics = db.get_dashboard_metrics()
    tmpls = db.get_prompt_templates()

    m1, m2, m3 = st.columns(3)
    with m1:
        with st.container(border=True):
            st.metric("Saved Experiments", metrics["total_experiments"])
    with m2:
        with st.container(border=True):
            st.metric("Prompt Versions", metrics["total_versions"])
    with m3:
        with st.container(border=True):
            st.metric("Library Templates", len(tmpls))

    st.markdown("")
    st.markdown("##### Data Management")
    with st.container(border=True):
        wd1, wd2 = st.columns(2)
        with wd1:
            if st.button(":material/refresh: Restore Starter Prompts", use_container_width=True):
                added = restore_starter_templates(db)
                if added:
                    st.toast(f"Restored {added} starter prompts.", icon=":material/check:")
                else:
                    st.toast("All starter prompts are already present.", icon=":material/info:")
                st.rerun()
        with wd2:
            if st.button(":material/delete_forever: Clear All Experiments", type="secondary", use_container_width=True):
                confirm_clear_dialog()
