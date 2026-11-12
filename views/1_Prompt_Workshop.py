"""
Shabd.Craft — Prompt Workshop

Create, load, edit, version, execute, and delete prompts.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import streamlit as st

from src.config import settings
from src.experiment_service import create_experiment_with_version
from src.export_service import generate_production_code
from src.harness import execute_with_harness
from src.prompt_engine import TECHNIQUE_INFO, construct_prompt, execute_prompt
from src.schemas import (
    FewShotExample,
    OutputFormat,
    PromptVersion,
    PromptingTechnique,
    TaskCategory,
    TestCase,
)
from src.template_engine import extract_variables, preview_template, validate_template
from src.ui_helpers import (
    clear_workshop_widgets,
    get_database,
    load_version_into_workshop,
    render_page_header,
)

db = get_database()

# ── Session defaults ───────────────────────────────────────────────────
for key, default in [
    ("ws_editing_exp_id", None),
    ("ws_editing_ver_id", None),
    ("ws_system", st.session_state.get("prompt_system", "")),
    ("ws_user", st.session_state.get("prompt_user", "")),
    ("ws_technique", st.session_state.get("prompt_technique", "zero_shot")),
    ("ws_format", st.session_state.get("prompt_output_format", "text")),
    ("ws_model", settings.default_model),
    ("ws_temp", 0.7),
    ("ws_max_tokens", 1024),
    ("ws_few_shots", []),
    ("ws_sample_input", ""),
    ("ws_expected", ""),
    ("ws_exp_name", ""),
    ("ws_category", "general"),
    ("ws_last_response", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

render_page_header("Prompt Workshop", "Create, edit, test, and version prompts.")

# ── Prompt / Experiment Switcher ───────────────────────────────────────
experiments = db.list_experiments(limit=100)
exp_map = {e["id"]: e for e in experiments}
switcher_options = ["__new__"] + [e["id"] for e in experiments]

current_edit_exp = st.session_state.get("ws_editing_exp_id")
if current_edit_exp not in exp_map:
    current_edit_exp = "__new__"

sw1, sw2, sw3 = st.columns([2, 2, 1])
with sw1:
    selected_target = st.selectbox(
        "Workspace Target",
        switcher_options,
        index=switcher_options.index(current_edit_exp),
        format_func=lambda x: "+ New Prompt" if x == "__new__" else f"{exp_map[x]['name']} ({exp_map[x]['category'].replace('_', ' ').title()})",
        key="ws_target_selector",
    )

# Handle switching between New Prompt and existing Experiments cleanly
if selected_target == "__new__" and st.session_state.get("ws_editing_exp_id") is not None:
    st.session_state["ws_editing_exp_id"] = None
    st.session_state["ws_editing_ver_id"] = None
    st.session_state["ws_exp_name"] = ""
    st.session_state["ws_system"] = ""
    st.session_state["ws_user"] = ""
    st.session_state["ws_sample_input"] = ""
    st.session_state["ws_expected"] = ""
    st.session_state["ws_few_shots"] = []
    st.session_state["ws_last_response"] = None
    clear_workshop_widgets()
    st.rerun()

selected_versions = []
selected_ver_id = None
if selected_target != "__new__":
    selected_versions = db.get_prompt_versions(selected_target)
    ver_map = {v["id"]: v for v in selected_versions}
    with sw2:
        if selected_versions:
            cur_ver = st.session_state.get("ws_editing_ver_id")
            if cur_ver not in ver_map:
                cur_ver = selected_versions[0]["id"]
            selected_ver_id = st.selectbox(
                "Prompt Version",
                [v["id"] for v in selected_versions],
                index=[v["id"] for v in selected_versions].index(cur_ver),
                format_func=lambda vid: f"v{ver_map[vid]['version_number']}: {ver_map[vid]['version_label']}",
                key="ws_version_selector",
            )
    with sw3:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if selected_ver_id and (
            st.session_state.get("ws_editing_exp_id") != selected_target
            or st.session_state.get("ws_editing_ver_id") != selected_ver_id
        ):
            load_version_into_workshop(db, exp_map[selected_target], ver_map[selected_ver_id])
            st.rerun()
        elif selected_target != "__new__" and st.button("+ New Prompt", use_container_width=True):
            st.session_state["ws_editing_exp_id"] = None
            st.session_state["ws_editing_ver_id"] = None
            st.session_state["ws_exp_name"] = ""
            st.session_state["ws_system"] = ""
            st.session_state["ws_user"] = ""
            st.session_state["ws_sample_input"] = ""
            st.session_state["ws_expected"] = ""
            st.session_state["ws_few_shots"] = []
            st.session_state["ws_last_response"] = None
            clear_workshop_widgets()
            st.rerun()

# ── Command Bar ────────────────────────────────────────────────────────
bar1, bar2, bar3 = st.columns([2, 1, 1])
with bar1:
    exp_name = st.text_input(
        "Prompt / Experiment Name",
        value=st.session_state["ws_exp_name"],
        placeholder="e.g., Customer Feedback Summarizer",
        key="input_exp_name",
    )
    st.session_state["ws_exp_name"] = exp_name
with bar2:
    categories = [e.value for e in TaskCategory]
    cat_idx = categories.index(st.session_state["ws_category"]) if st.session_state["ws_category"] in categories else 0
    category = st.selectbox(
        "Task Category",
        categories,
        format_func=lambda x: x.replace("_", " ").title(),
        index=cat_idx,
        key="sel_category",
    )
    st.session_state["ws_category"] = category
with bar3:
    model_list = settings.AVAILABLE_MODELS
    cur_model = st.session_state.get("ws_model", settings.default_model)
    model_idx = model_list.index(cur_model) if cur_model in model_list else 0
    model = st.selectbox("Model", model_list, index=model_idx, key="sel_model")
    st.session_state["ws_model"] = model

# ── Main Layout: Composer + Preview ────────────────────────────────────
left_col, right_col = st.columns([3, 2], gap="large")

with left_col:
    techniques = [e.value for e in PromptingTechnique]
    technique_labels = {t.value: TECHNIQUE_INFO[t]["name"] for t in PromptingTechnique}
    formats = [e.value for e in OutputFormat]

    cfg_c1, cfg_c2 = st.columns(2)
    with cfg_c1:
        tech_idx = techniques.index(st.session_state["ws_technique"]) if st.session_state["ws_technique"] in techniques else 0
        tech = st.selectbox(
            "Prompting Technique",
            techniques,
            format_func=lambda x: technique_labels.get(x, x),
            index=tech_idx,
            key="sel_technique",
        )
        st.session_state["ws_technique"] = tech
    with cfg_c2:
        fmt_idx = formats.index(st.session_state["ws_format"]) if st.session_state["ws_format"] in formats else 0
        fmt = st.selectbox(
            "Output Format",
            formats,
            format_func=lambda x: x.replace("_", " ").title(),
            index=fmt_idx,
            key="sel_format",
        )
        st.session_state["ws_format"] = fmt

    tech_enum = PromptingTechnique(tech)
    st.caption(TECHNIQUE_INFO[tech_enum]["description"])

    system_prompt = st.text_area(
        "System Instructions",
        value=st.session_state["ws_system"],
        height=90,
        placeholder="You are a helpful assistant...",
        key="ta_system",
    )
    st.session_state["ws_system"] = system_prompt

    user_prompt = st.text_area(
        "User Prompt Template (use {{variable_name}} for inputs)",
        value=st.session_state["ws_user"],
        height=155,
        placeholder="Summarize the following feedback:\n\n{{customer_feedback}}",
        key="ta_user",
    )
    st.session_state["ws_user"] = user_prompt

    if tech in ("one_shot", "few_shot"):
        st.markdown("##### Few-Shot Examples")
        num = 1 if tech == "one_shot" else st.number_input("Number of examples", 2, 10, 3)

        examples = st.session_state.get("ws_few_shots", [])
        while len(examples) < num:
            examples.append({"input_text": "", "output_text": ""})
        examples = examples[:num]

        for i in range(num):
            with st.expander(f"Example {i + 1}", expanded=(i == 0)):
                inp = st.text_area(f"Input {i + 1}", value=examples[i].get("input_text", ""), height=60, key=f"fs_in_{i}")
                out = st.text_area(f"Output {i + 1}", value=examples[i].get("output_text", ""), height=60, key=f"fs_out_{i}")
                examples[i] = {"input_text": inp, "output_text": out}

        st.session_state["ws_few_shots"] = examples

    sample_input = st.text_area(
        "Sample Input Data",
        value=st.session_state["ws_sample_input"],
        height=85,
        placeholder="Enter sample data to test your prompt...",
        key="ta_sample",
    )
    st.session_state["ws_sample_input"] = sample_input

    with st.expander("Parameters & Expected Output (Optional)", expanded=False):
        p1, p2 = st.columns(2)
        with p1:
            temp = st.slider("Temperature", 0.0, 2.0, st.session_state["ws_temp"], 0.1)
            st.session_state["ws_temp"] = temp
        with p2:
            max_tok = st.number_input("Max Tokens", 64, 4096, st.session_state["ws_max_tokens"], 64)
            st.session_state["ws_max_tokens"] = max_tok
        expected = st.text_area(
            "Expected Output",
            value=st.session_state["ws_expected"],
            height=70,
            placeholder="What should the ideal response look like?",
            key="ta_expected",
        )
        st.session_state["ws_expected"] = expected

        st.divider()
        use_harness = st.checkbox(
            "Enable Validation & Auto-Repair Harness",
            value=st.session_state.get("ws_use_harness", False),
            help="Validates output format/constraints and automatically retries on failure.",
        )
        st.session_state["ws_use_harness"] = use_harness
        harness_keywords = None
        harness_max_words = None
        if use_harness:
            hc1, hc2 = st.columns(2)
            with hc1:
                kw_raw = st.text_input("Required Keywords (comma-separated)", key="ws_harness_kw")
                harness_keywords = [k.strip() for k in kw_raw.split(",") if k.strip()] if kw_raw else None
            with hc2:
                mw_raw = st.number_input("Max Words (0 = no limit)", 0, 5000, 0, key="ws_harness_mw")
                harness_max_words = mw_raw if mw_raw > 0 else None

        use_guardrails = st.checkbox(
            "Enable Input/Output Guardrails (PII, Injection & Leak Filter)",
            value=st.session_state.get("ws_use_guardrails", False),
            help="Redacts PII/API keys, blocks prompt injections pre-execution, and blocks system prompt leaks.",
        )
        st.session_state["ws_use_guardrails"] = use_guardrails
        guard_block_inj = True
        guard_redact_pii = True
        guard_banned = None
        if use_guardrails:
            gc1, gc2 = st.columns(2)
            with gc1:
                guard_block_inj = st.checkbox("Block prompt injection attempts", value=True, key="ws_guard_inj")
            with gc2:
                guard_redact_pii = st.checkbox("Auto-redact PII & API keys", value=True, key="ws_guard_pii")
            banned_raw = st.text_input("Restricted Terms (comma-separated, optional)", key="ws_guard_banned")
            guard_banned = [b.strip() for b in banned_raw.split(",") if b.strip()] if banned_raw else None

# ── Right Pane: Preview, Results & Export ──────────────────────────────
with right_col:
    tab_preview, tab_export = st.tabs(["Preview & Results", "Export Code"])

    with tab_preview:
        st.markdown("##### Live Preview")

        if user_prompt:
            validation = validate_template(user_prompt)
            variables = validation["variables"]

            if variables:
                st.caption(f"Template variables: `{'`, `'.join(variables)}`")

            for w in validation["warnings"]:
                st.warning(w)

            var_values = {v: sample_input for v in variables} if sample_input else {}
            rendered = preview_template(user_prompt, var_values)

            st.markdown("**Rendered Prompt:**")
            st.code(rendered[:2000], language="text")
            st.caption(f"Words: {len(rendered.split())} · Characters: {len(rendered)}")
        else:
            st.info("Enter a prompt template to see the live preview.")

        if user_prompt:
            st.markdown("##### Prompt Checks")
            issues = []
            if not system_prompt:
                issues.append("No system prompt — consider adding role or context instructions.")
            if len(user_prompt) < 20:
                issues.append("Very short prompt — may lack specificity.")
            if "{{" not in user_prompt and tech == "zero_shot":
                issues.append("No template variables — prompt will be static.")
            if fmt == "json" and "json" not in user_prompt.lower():
                issues.append("JSON output selected but not mentioned in prompt.")
            if tech == "role_based" and (not system_prompt.strip() or system_prompt.strip().lower() == "you are a helpful assistant."):
                issues.append("Role-based selected with a generic or empty system prompt — define a specific expert role and domain.")
            if tech == "structured_output" and not any(kw in user_prompt.lower() for kw in ["json", "field", "schema", "format", "key", "column"]):
                issues.append("Structured output selected — specify expected fields or output schema in the prompt.")
            if tech == "task_decomposition" and not any(kw in user_prompt.lower() for kw in ["step", "1.", "first", "then", "finally"]):
                issues.append("No explicit steps detected — a default 3-step decomposition scaffold will be prepended automatically.")

            if issues:
                for issue in issues:
                    st.markdown(f"- {issue}")
            else:
                st.success("Prompt looks well-structured.")

        st.divider()

        if st.session_state.get("ws_last_response"):
            resp = st.session_state["ws_last_response"]
            st.markdown("##### Execution Result")

            st.text_area("Generated Output", value=resp.get("content", ""), height=180, disabled=True, key="result_output")

            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Latency", f"{resp.get('latency_ms', 0):.0f}ms")
            rc2.metric("Tokens", resp.get("total_tokens", 0))
            cost_val = resp.get("cost_estimate", 0)
            rc3.metric("Cost", f"${cost_val:.5f}" if cost_val > 0 else "$0.00")

            h_meta = resp.get("harness_meta")
            if h_meta:
                status_str = "PASS" if h_meta["passed_contract"] else "FAIL"
                repaired_str = "Yes" if h_meta["repaired"] else "No"
                st.caption(
                    f"Harness Contract: **{status_str}** · Attempts: **{h_meta['attempts']}** · "
                    f"Auto-Repaired: **{repaired_str}**"
                )
                g_rep = h_meta.get("guardrail_report")
                if g_rep:
                    in_g = g_rep.get("input") or {}
                    out_g = g_rep.get("output") or {}
                    in_stat = "PASS" if in_g.get("allowed", True) else "BLOCKED"
                    out_stat = "SKIPPED" if not out_g else ("PASS" if out_g.get("allowed", True) else "BLOCKED")
                    redactions = (in_g.get("redactions") or []) + (out_g.get("redactions") or [])
                    red_str = ", ".join(redactions) if redactions else "None"
                    st.caption(f"Guardrails — Input: **{in_stat}** · Output: **{out_stat}** · Redactions: **{red_str}**")
                if h_meta.get("input_sanitized"):
                    st.info("Input sanitizer neutralized boundary-escape tags or redacted sensitive tokens before execution.")
                for v_err in h_meta.get("validation_errors", []):
                    st.warning(v_err)

    with tab_export:
        st.markdown("##### Export Production Code")
        st.caption("Copy-pasteable API snippets for your current prompt configuration.")

        if not user_prompt.strip():
            st.info("Enter a user prompt template on the left to generate code snippets.")
        else:
            few_shots_export = []
            if tech in ("one_shot", "few_shot"):
                for ex in st.session_state.get("ws_few_shots", []):
                    if ex.get("input_text") and ex.get("output_text"):
                        few_shots_export.append(FewShotExample(**ex))

            export_ver = PromptVersion(
                experiment_id="export",
                system_prompt=system_prompt,
                user_prompt_template=user_prompt,
                technique=PromptingTechnique(tech),
                output_format=OutputFormat(fmt),
                model_name=model,
                temperature=temp,
                max_tokens=max_tok,
                few_shot_examples=few_shots_export,
            )
            built_sys, built_user = construct_prompt(export_ver, input_data=sample_input)
            snippets = generate_production_code(
                system_prompt=built_sys,
                user_prompt=built_user,
                model=model,
                temperature=temp,
                max_tokens=max_tok,
            )

            fmt_choice = st.radio(
                "Target Format",
                ["openai_python", "langchain_python", "curl"],
                format_func=lambda x: {
                    "openai_python": "Python (OpenAI SDK)",
                    "langchain_python": "Python (LangChain)",
                    "curl": "cURL (REST API)",
                }[x],
                horizontal=True,
                key="export_fmt_radio",
            )
            lang = "bash" if fmt_choice == "curl" else "python"
            st.code(snippets[fmt_choice], language=lang)

# ── Action Bar ─────────────────────────────────────────────────────────
st.divider()
editing_exp_id = st.session_state.get("ws_editing_exp_id")
editing_ver_id = st.session_state.get("ws_editing_ver_id")


def _collect_few_shots() -> list[dict]:
    if tech not in ("one_shot", "few_shot"):
        return []
    return [
        ex for ex in st.session_state.get("ws_few_shots", [])
        if ex.get("input_text") and ex.get("output_text")
    ]


if editing_exp_id and editing_ver_id:
    new_ver_label = st.text_input(
        "Version Label (used when saving changes or adding a new version)",
        value=db.get_prompt_version(editing_ver_id).get("version_label", "Original") if db.get_prompt_version(editing_ver_id) else "Updated",
        key="ws_ver_label_input",
    )
    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        run_clicked = st.button("Run Prompt", type="primary", use_container_width=True)
    with b2:
        update_clicked = st.button("Save Changes", use_container_width=True)
    with b3:
        new_ver_clicked = st.button("Save as New Version", use_container_width=True)
    with b4:
        eval_clicked = st.button("Evaluate", use_container_width=True)
    with b5:
        delete_clicked = st.button("Delete", use_container_width=True)
    save_new_clicked = False
    reset_clicked = False
else:
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        run_clicked = st.button("Run Prompt", type="primary", use_container_width=True)
    with b2:
        save_new_clicked = st.button("Save Prompt", use_container_width=True)
    with b3:
        eval_clicked = st.button("Send to Evaluation Lab", use_container_width=True)
    with b4:
        reset_clicked = st.button("Clear", use_container_width=True)
    update_clicked = False
    new_ver_clicked = False
    delete_clicked = False

if delete_clicked and editing_exp_id:
    st.session_state["ws_confirm_delete"] = True

if st.session_state.get("ws_confirm_delete") and editing_exp_id:
    st.warning("Choose whether to delete only this version or the entire prompt experiment.")
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        if len(selected_versions) > 1 and editing_ver_id:
            if st.button("Delete This Version", type="primary", use_container_width=True):
                db.delete_prompt_version(editing_ver_id)
                st.session_state.pop("ws_confirm_delete", None)
                remaining = db.get_prompt_versions(editing_exp_id)
                if remaining:
                    load_version_into_workshop(db, exp_map[editing_exp_id], remaining[0])
                st.rerun()
        else:
            st.caption("Only 1 version in this experiment.")
    with dc2:
        if st.button("Delete Entire Experiment", use_container_width=True):
            db.delete_experiment(editing_exp_id)
            st.session_state.pop("ws_confirm_delete", None)
            st.session_state["ws_editing_exp_id"] = None
            st.session_state["ws_editing_ver_id"] = None
            st.session_state["current_experiment_id"] = None
            st.session_state["current_version_id"] = None
            st.session_state["ws_exp_name"] = ""
            st.session_state["ws_system"] = ""
            st.session_state["ws_user"] = ""
            st.session_state["ws_sample_input"] = ""
            st.session_state["ws_expected"] = ""
            st.session_state["ws_few_shots"] = []
            clear_workshop_widgets()
            st.rerun()
    with dc3:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("ws_confirm_delete", None)
            st.rerun()

# ── Handle Actions ─────────────────────────────────────────────────────
if reset_clicked:
    for key in ["ws_system", "ws_user", "ws_sample_input", "ws_expected", "ws_last_response", "ws_exp_name", "ws_few_shots"]:
        st.session_state[key] = "" if isinstance(st.session_state.get(key), str) else ([] if isinstance(st.session_state.get(key), list) else None)
    st.session_state["ws_technique"] = "zero_shot"
    st.session_state["ws_format"] = "text"
    clear_workshop_widgets()
    st.rerun()

if run_clicked:
    if not user_prompt.strip():
        st.error("Please enter a user prompt template.")
    else:
        few_shots = [FewShotExample(**ex) for ex in _collect_few_shots()]
        version = PromptVersion(
            experiment_id="preview",
            system_prompt=system_prompt,
            user_prompt_template=user_prompt,
            technique=PromptingTechnique(tech),
            output_format=OutputFormat(fmt),
            model_name=model,
            temperature=temp,
            max_tokens=max_tok,
            few_shot_examples=few_shots,
        )
        with st.spinner("Executing prompt..."):
            if use_harness or use_guardrails:
                h_res = execute_with_harness(
                    version,
                    input_data=sample_input,
                    required_keywords=harness_keywords,
                    max_words=harness_max_words,
                    max_retries=None if use_harness else 0,
                    enable_guardrails=use_guardrails,
                    block_injection=guard_block_inj,
                    redact_pii=guard_redact_pii,
                    banned_terms=guard_banned,
                )
                response = h_res["response"]
                resp_payload = response.model_dump()
                resp_payload["harness_meta"] = {
                    "attempts": h_res["attempts"],
                    "repaired": h_res["repaired"],
                    "passed_contract": h_res["passed_contract"],
                    "validation_errors": h_res["validation_errors"],
                    "input_sanitized": h_res["input_sanitized"],
                    "guardrail_report": h_res.get("guardrail_report"),
                }
            else:
                response = execute_prompt(version, input_data=sample_input)
                resp_payload = response.model_dump()

        if response.error:
            st.error(f"Execution failed: {response.error}")
        else:
            st.session_state["ws_last_response"] = resp_payload
            st.rerun()

if save_new_clicked:
    name = st.session_state["ws_exp_name"].strip()
    if not name:
        st.error("Please enter a prompt name.")
    elif not user_prompt.strip():
        st.error("Please enter a user prompt template.")
    else:
        exp_id, ver_id = create_experiment_with_version(
            db=db,
            name=name,
            category=category,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            technique=tech,
            output_format=fmt,
            model_name=model,
            temperature=temp,
            max_tokens=max_tok,
            few_shot_examples=_collect_few_shots(),
        )
        if sample_input.strip():
            db.save_test_case(TestCase(input_data=sample_input, expected_output=expected), exp_id)

        st.session_state["current_experiment_id"] = exp_id
        st.session_state["current_version_id"] = ver_id
        st.session_state["ws_editing_exp_id"] = exp_id
        st.session_state["ws_editing_ver_id"] = ver_id
        st.success(f"Prompt **{name}** saved.")
        st.rerun()

if update_clicked and editing_exp_id and editing_ver_id:
    if not user_prompt.strip():
        st.error("Please enter a user prompt template.")
    else:
        db.update_prompt_version(
            version_id=editing_ver_id,
            version_label=(new_ver_label or "Original").strip(),
            system_prompt=system_prompt,
            user_prompt_template=user_prompt,
            technique=tech,
            output_format=fmt,
            model_name=model,
            temperature=temp,
            max_tokens=max_tok,
            few_shot_examples=_collect_few_shots(),
            variables=extract_variables(user_prompt),
        )
        st.success("Prompt version updated.")

if new_ver_clicked and editing_exp_id:
    if not user_prompt.strip():
        st.error("Please enter a user prompt template.")
    else:
        next_num = db.get_next_version_number(editing_exp_id)
        label = (new_ver_label or "").strip()
        if not label or label == "Original":
            label = f"Revision v{next_num}"
        new_pv = PromptVersion(
            experiment_id=editing_exp_id,
            version_number=next_num,
            version_label=label,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt,
            technique=PromptingTechnique(tech),
            output_format=OutputFormat(fmt),
            model_name=model,
            temperature=temp,
            max_tokens=max_tok,
            few_shot_examples=[FewShotExample(**ex) for ex in _collect_few_shots()],
            variables=extract_variables(user_prompt),
        )
        new_vid = db.save_prompt_version(new_pv)
        st.session_state["current_experiment_id"] = editing_exp_id
        st.session_state["current_version_id"] = new_vid
        st.session_state["ws_editing_ver_id"] = new_vid
        st.success(f"Saved as v{next_num}: {label}.")
        st.rerun()

if eval_clicked:
    if not st.session_state.get("current_experiment_id"):
        st.warning("Save the prompt first before opening Evaluation Lab.")
    else:
        st.switch_page("views/2_Evaluation_Lab.py")
