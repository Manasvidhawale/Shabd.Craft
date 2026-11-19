"""
Shabd.Craft — Prompt Workshop

Author, test, version, and inspect prompts with live token analytics,
auto-repair harness, and guardrail validation.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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
from src.template_engine import (
    analyze_prompt_structure,
    extract_variables,
    preview_template,
    validate_template,
)
from src.ui_helpers import (
    clear_workshop_widgets,
    get_database,
    load_template_into_workshop,
    load_version_into_workshop,
    render_page_header,
)
from src.ui_theme import status_badge

db = get_database()

# ── Session Defaults ───────────────────────────────────────────────────
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
    ("ws_use_harness", False),
    ("ws_use_guardrails", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

render_page_header("Prompt Workshop", "Create, edit, test, and version prompts with live token analytics.")

# ── Delete Dialog ──────────────────────────────────────────────────────
@st.dialog("Delete Prompt")
def confirm_delete_dialog(exp_id: str, ver_id: str | None, versions_count: int):
    st.warning("Choose whether to delete only this version or the entire prompt experiment.")
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        if versions_count > 1 and ver_id:
            if st.button("Delete This Version", type="primary", use_container_width=True):
                try:
                    db.delete_prompt_version(ver_id)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    remaining = db.get_prompt_versions(exp_id)
                    if remaining:
                        exp = db.get_experiment(exp_id)
                        if exp:
                            load_version_into_workshop(db, exp, remaining[0])
                    st.toast("Version deleted.", icon=":material/delete:")
                    st.rerun()
        else:
            st.caption("Only 1 version in experiment.")
    with dc2:
        if st.button("Delete Entire Experiment", use_container_width=True):
            db.delete_experiment(exp_id)
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
            st.session_state["ws_last_response"] = None
            clear_workshop_widgets()
            st.toast("Experiment deleted.", icon=":material/delete:")
            st.rerun()
    with dc3:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


# ── Target Switcher ────────────────────────────────────────────────────
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

# Handle switching between New Prompt and existing Experiments
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
selected_branch_id = None
if selected_target != "__new__":
    selected_versions = db.get_prompt_versions(selected_target)
    ver_map = {v["id"]: v for v in selected_versions}
    branches = db.get_prompt_branches(selected_target)
    branch_map = {branch["id"]: branch for branch in branches}
    if branches:
        current_branch = st.session_state.get("current_branch_id")
        if current_branch not in branch_map:
            current_branch = next((b["id"] for b in branches if b["name"].lower() == "main"), branches[0]["id"])
        with sw2:
            selected_branch_id = st.selectbox(
                "Branch",
                list(branch_map),
                index=list(branch_map).index(current_branch),
                format_func=lambda branch_id: f"{branch_map[branch_id]['name']} · v{branch_map[branch_id].get('head_version_number', '?')}",
                key=f"ws_branch_selector_{selected_target}",
            )
        st.session_state["current_branch_id"] = selected_branch_id
        selected_branch = branch_map[selected_branch_id]
        selected_ver_id = selected_branch.get("head_version_id")
        with sw3:
            if st.button("Manage branches", use_container_width=True):
                st.session_state["current_experiment_id"] = selected_target
                st.switch_page("views/8_Branches.py")
        if selected_ver_id and (
            st.session_state.get("ws_editing_exp_id") != selected_target
            or st.session_state.get("ws_editing_ver_id") != selected_ver_id
        ):
            load_version_into_workshop(db, exp_map[selected_target], ver_map[selected_ver_id])
            st.rerun()
        elif not selected_ver_id:
            st.info("This branch has no saved version yet. Create a prompt version in the Workshop.")
    else:
        with sw2:
            st.caption("No versions yet")
    with sw3:
        if not branches and st.button("+ New Prompt", use_container_width=True):
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
    prev_cat = st.session_state.get("ws_category", "general")
    cat_idx = categories.index(prev_cat) if prev_cat in categories else 0
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


# ── The Unified Scoped Canvas (@st.fragment) ───────────────────────────
# Encapsulates both left composer inputs and right live preview/token meter
# so typing recomputes preview reactively without whole-page reruns.
@st.fragment
def workshop_canvas():
    left_col, right_col = st.columns([3, 2], gap="large")

    with left_col:
        with st.container(border=True):
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
                height=150,
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

            # Variable Inputs
            detected_vars = extract_variables(user_prompt) if user_prompt else []
            var_values: dict[str, str] = {}
            if detected_vars:
                st.markdown("##### Variable Inputs")
                for v in detected_vars:
                    key_name = f"ws_var_{v}"
                    if key_name not in st.session_state:
                        st.session_state[key_name] = st.session_state.get("ws_sample_input", "")
                    val = st.text_area(
                        f"Input for {{{{{v}}}}}",
                        value=st.session_state[key_name],
                        height=75,
                        placeholder=f"Enter test value for {v}...",
                        key=f"ta_var_{v}",
                    )
                    var_values[v] = val
                    st.session_state[key_name] = val

                sample_input = var_values.get(detected_vars[0], "")
                st.session_state["ws_sample_input"] = sample_input

                sample_defaults = {
                    "customer_feedback": "The product arrived on time, but customer support took 3 days to reply to my urgent ticket.",
                    "input": "Quarterly earnings report showed a 14% increase in operating margin.",
                    "text": "The quick brown fox jumps over the lazy dog.",
                    "code": "def process_data(items):\n    return [x.strip() for x in items if x]",
                    "query": "How do I configure OAuth2 with JWT authentication in FastAPI?",
                }
                if st.button(":material/auto_fix_high: Fill Sample Data for Testing", key="btn_fill_sample"):
                    for v in detected_vars:
                        cand = sample_defaults.get(v, "Sample test value demonstrating production prompt behavior.")
                        st.session_state[f"ws_var_{v}"] = cand
                    st.session_state["ws_sample_input"] = st.session_state.get(f"ws_var_{detected_vars[0]}", "")
                    st.rerun()
            else:
                sample_input = st.text_area(
                    "Sample Input Data",
                    value=st.session_state["ws_sample_input"],
                    height=80,
                    placeholder="Enter sample data to test your prompt...",
                    key="ta_sample",
                )
                st.session_state["ws_sample_input"] = sample_input

            # Tuning & Parameters Popover
            with st.popover("⚙️ Tuning & Validation Harness"):
                with st.form("tuning_form"):
                    p1, p2 = st.columns(2)
                    with p1:
                        temp = st.slider("Temperature", 0.0, 2.0, float(st.session_state["ws_temp"]), 0.1)
                    with p2:
                        max_tok = st.number_input("Max Tokens", 64, 4096, int(st.session_state["ws_max_tokens"]), 64)
                    expected = st.text_area(
                        "Expected Output (Optional)",
                        value=st.session_state["ws_expected"],
                        height=60,
                        placeholder="What should ideal response look like?",
                    )
                    st.divider()
                    use_harness = st.checkbox(
                        "Enable Auto-Repair Harness",
                        value=st.session_state.get("ws_use_harness", False),
                    )
                    use_guardrails = st.checkbox(
                        "Enable Input/Output Guardrails (PII & Injection)",
                        value=st.session_state.get("ws_use_guardrails", False),
                    )
                    if st.form_submit_button(":material/check: Apply Parameters", type="primary"):
                        st.session_state["ws_temp"] = temp
                        st.session_state["ws_max_tokens"] = max_tok
                        st.session_state["ws_expected"] = expected
                        st.session_state["ws_use_harness"] = use_harness
                        st.session_state["ws_use_guardrails"] = use_guardrails
                        st.toast("Parameters updated.", icon=":material/check:")

    with right_col:
        tab_preview, tab_export = st.tabs(["Preview & Results", "Export Code"])

        with tab_preview:
            with st.container(border=True):
                st.markdown("##### Live Inspection")
                if user_prompt:
                    validation = validate_template(user_prompt)
                    variables = validation["variables"]
                    if variables:
                        st.caption(f"Variables: `{'`, `'.join(variables)}`")

                    for w in validation["warnings"]:
                        st.warning(w)

                    rendered = preview_template(user_prompt, var_values)
                    st.markdown("**Rendered Prompt:**")
                    st.code(rendered[:2000], language="text")

                    # Token analytics
                    est_tokens = max(1, int(len(rendered.split()) * 1.33))
                    max_ctx = settings.MODEL_CONTEXT_WINDOWS.get(model, 32768)
                    ctx_ratio = min(1.0, est_tokens / max_ctx)

                    tok_c1, tok_c2 = st.columns([3, 2])
                    with tok_c1:
                        st.caption(f"Words: {len(rendered.split())} · Tokens: ~{est_tokens:,}")
                    with tok_c2:
                        pricing = settings.MODEL_PRICING.get(model, {"input": 0.001, "output": 0.002})
                        cost_per_1k = (est_tokens / 1000.0) * pricing.get("input", 0.001) * 1000.0
                        st.caption(f"Input Cost: ${cost_per_1k:.4f} / 1k runs")

                    st.progress(ctx_ratio, text=f"Context: {est_tokens:,} / {max_ctx:,} tokens ({ctx_ratio:.1%})")

                    # Quality check
                    filled_fs = len([
                        ex for ex in st.session_state.get("ws_few_shots", [])
                        if ex.get("input_text") and ex.get("output_text")
                    ])
                    analysis = analyze_prompt_structure(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        technique=tech,
                        output_format=fmt,
                        few_shot_count=filled_fs,
                    )
                    sc_val = analysis["score"]
                    grade = analysis["grade"]
                    st.markdown(f"**Readiness Score:** {sc_val}/100 ({status_badge('success' if sc_val >= 80 else 'warn', grade)})")
                else:
                    st.info(":material/info: Enter a prompt template on the left to see the live preview.")

            # Execution Console Card (Always present to balance layout)
            with st.container(border=True):
                st.markdown("##### Execution Console")
                if st.session_state.get("ws_last_response"):
                    resp = st.session_state["ws_last_response"]
                    st.code(resp.get("content", ""), language="text")

                    rc1, rc2, rc3 = st.columns(3)
                    with rc1:
                        st.metric("Latency", f"{resp.get('latency_ms', 0):.0f}ms")
                    with rc2:
                        st.metric("Tokens", resp.get("total_tokens", 0))
                    with rc3:
                        cost_val = resp.get("cost_estimate", 0)
                        st.metric("Cost", f"${cost_val:.5f}" if cost_val > 0 else "$0.00")

                    h_meta = resp.get("harness_meta")
                    if h_meta:
                        stat_badge = status_badge("pass" if h_meta["passed_contract"] else "fail", "PASS" if h_meta["passed_contract"] else "FAIL")
                        st.caption(f"Harness: {stat_badge} · Attempts: **{h_meta['attempts']}** · Repaired: **{h_meta['repaired']}**")
                else:
                    st.info(":material/play_circle: **Console Idle** — Click **Run Prompt** below to execute against the model. Streaming output, latency, token metrics, and auto-repair validations will appear here.")

        with tab_export:
            with st.container(border=True):
                st.markdown("##### Export Production Code")
                if not user_prompt.strip():
                    st.info("Enter a prompt template to generate production code snippets.")
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
                        temperature=float(st.session_state["ws_temp"]),
                        max_tokens=int(st.session_state["ws_max_tokens"]),
                        few_shot_examples=few_shots_export,
                    )
                    built_sys, built_user = construct_prompt(export_ver, input_data=st.session_state.get("ws_sample_input", ""))
                    snippets = generate_production_code(
                        system_prompt=built_sys,
                        user_prompt=built_user,
                        model=model,
                        temperature=float(st.session_state["ws_temp"]),
                        max_tokens=int(st.session_state["ws_max_tokens"]),
                        include_harness=bool(st.session_state.get("ws_use_harness")),
                        output_format=fmt,
                    )
                    fmt_choice = st.radio(
                        "Target SDK",
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


workshop_canvas()

# ── Action Bar (Outside Fragment: DB Writes & Global Operations) ───────
st.divider()
editing_exp_id = st.session_state.get("ws_editing_exp_id")
editing_ver_id = st.session_state.get("ws_editing_ver_id")

user_prompt_val = st.session_state.get("ws_user", "").strip()
sys_prompt_val = st.session_state.get("ws_system", "")
tech_val = st.session_state.get("ws_technique", "zero_shot")
fmt_val = st.session_state.get("ws_format", "text")
model_val = st.session_state.get("ws_model", settings.default_model)
temp_val = float(st.session_state.get("ws_temp", 0.7))
max_tok_val = int(st.session_state.get("ws_max_tokens", 1024))
sample_input_val = st.session_state.get("ws_sample_input", "")
expected_val = st.session_state.get("ws_expected", "")


def _collect_few_shots() -> list[dict]:
    if tech_val not in ("one_shot", "few_shot"):
        return []
    return [
        ex for ex in st.session_state.get("ws_few_shots", [])
        if ex.get("input_text") and ex.get("output_text")
    ]


with st.container(border=True):
    if editing_exp_id and editing_ver_id:
        ver_label_val = st.text_input(
            "Version Label",
            value=db.get_prompt_version(editing_ver_id).get("version_label", "Updated") if db.get_prompt_version(editing_ver_id) else "Updated",
            key="ws_ver_label_input",
        )
        b1, b2, b3, b4 = st.columns([2, 1.5, 1.5, 1])
        with b1:
            run_clicked = st.button(":material/play_arrow: Run Prompt", type="primary", use_container_width=True)
        with b2:
            save_revision_clicked = st.button(":material/save: Save as New Version", use_container_width=True)
        with b3:
            eval_clicked = st.button(":material/biotech: Evaluate", use_container_width=True)
        with b4:
            delete_clicked = st.button(":material/delete: Delete", use_container_width=True)
        save_new_clicked = False
        reset_clicked = False
    else:
        b1, b2, b3, b4 = st.columns([2, 1.5, 1.5, 1])
        with b1:
            run_clicked = st.button(":material/play_arrow: Run Prompt", type="primary", use_container_width=True)
        with b2:
            save_new_clicked = st.button(":material/save: Save Prompt", use_container_width=True)
        with b3:
            eval_clicked = st.button(":material/biotech: Send to Evaluation", use_container_width=True)
        with b4:
            reset_clicked = st.button(":material/restart_alt: Clear Form", use_container_width=True)
        save_revision_clicked = False
        delete_clicked = False
        ver_label_val = "Initial"

if delete_clicked and editing_exp_id:
    confirm_delete_dialog(editing_exp_id, editing_ver_id, len(selected_versions))

if reset_clicked:
    for key in ["ws_system", "ws_user", "ws_sample_input", "ws_expected", "ws_last_response", "ws_exp_name", "ws_few_shots"]:
        st.session_state[key] = "" if isinstance(st.session_state.get(key), str) else ([] if isinstance(st.session_state.get(key), list) else None)
    st.session_state["ws_technique"] = "zero_shot"
    st.session_state["ws_format"] = "text"
    clear_workshop_widgets()
    st.toast("Form cleared.", icon=":material/restart_alt:")
    st.rerun()

if run_clicked:
    if not user_prompt_val:
        st.error("Please enter a user prompt template.")
    else:
        few_shots = [FewShotExample(**ex) for ex in _collect_few_shots()]
        version = PromptVersion(
            experiment_id="preview",
            system_prompt=sys_prompt_val,
            user_prompt_template=user_prompt_val,
            technique=PromptingTechnique(tech_val),
            output_format=OutputFormat(fmt_val),
            model_name=model_val,
            temperature=temp_val,
            max_tokens=max_tok_val,
            few_shot_examples=few_shots,
        )
        with st.status(":material/hourglass_top: Executing prompt...", expanded=True) as status_box:
            status_box.write(":material/shield: Scanning guardrails & checking contracts...")
            if st.session_state.get("ws_use_harness") or st.session_state.get("ws_use_guardrails"):
                h_res = execute_with_harness(
                    version,
                    input_data=sample_input_val,
                    max_retries=2 if st.session_state.get("ws_use_harness") else 0,
                    enable_guardrails=bool(st.session_state.get("ws_use_guardrails")),
                )
                response = h_res["response"]
                resp_payload = response.model_dump()
                resp_payload["harness_meta"] = {
                    "attempts": h_res["attempts"],
                    "repaired": h_res["repaired"],
                    "passed_contract": h_res["passed_contract"],
                    "validation_errors": h_res["validation_errors"],
                    "input_sanitized": h_res["input_sanitized"],
                }
            else:
                response = execute_prompt(version, input_data=sample_input_val)
                resp_payload = response.model_dump()

            if response.error:
                status_box.update(label=":material/error: Execution failed", state="error")
                st.error(f"Execution failed: {response.error}")
            else:
                status_box.update(label=":material/check_circle: Execution complete", state="complete")
                st.session_state["ws_last_response"] = resp_payload
                st.toast("Prompt executed successfully.", icon=":material/check_circle:")
                st.rerun()

if save_new_clicked:
    name = st.session_state["ws_exp_name"].strip()
    if not name:
        st.error("Please enter a prompt name.")
    elif not user_prompt_val:
        st.error("Please enter a user prompt template.")
    else:
        exp_id, ver_id = create_experiment_with_version(
            db=db,
            name=name,
            category=category,
            system_prompt=sys_prompt_val,
            user_prompt=user_prompt_val,
            technique=tech_val,
            output_format=fmt_val,
            model_name=model_val,
            temperature=temp_val,
            max_tokens=max_tok_val,
            few_shot_examples=_collect_few_shots(),
        )
        if sample_input_val:
            db.save_test_case(TestCase(input_data=sample_input_val, expected_output=expected_val), exp_id)

        st.session_state["current_experiment_id"] = exp_id
        st.session_state["current_version_id"] = ver_id
        st.session_state["ws_editing_exp_id"] = exp_id
        st.session_state["ws_editing_ver_id"] = ver_id
        st.session_state["current_branch_id"] = db.get_prompt_branches(exp_id)[0]["id"]
        st.session_state.pop(f"ws_branch_selector_{exp_id}", None)
        st.toast(f"Prompt '{name}' saved.", icon=":material/save:")
        st.rerun()

if save_revision_clicked and editing_exp_id and editing_ver_id:
    active_branch = db.get_prompt_branch(selected_branch_id) if selected_branch_id else None
    if not active_branch:
        st.error("Select an active branch before saving a version.")
    elif not user_prompt_val:
        st.error("Please enter a user prompt template.")
    else:
        next_num = db.get_next_version_number(editing_exp_id)
        label = (ver_label_val or "").strip()
        if not label or label == "Original":
            label = f"Revision v{next_num}"
        new_pv = PromptVersion(
            experiment_id=editing_exp_id,
            branch_id=selected_branch_id,
            version_number=next_num,
            parent_version_id=active_branch["head_version_id"],
            version_label=label,
            system_prompt=sys_prompt_val,
            user_prompt_template=user_prompt_val,
            technique=PromptingTechnique(tech_val),
            output_format=OutputFormat(fmt_val),
            model_name=model_val,
            temperature=temp_val,
            max_tokens=max_tok_val,
            few_shot_examples=[FewShotExample(**ex) for ex in _collect_few_shots()],
            variables=extract_variables(user_prompt_val),
        )
        new_vid = db.save_prompt_version(new_pv)
        st.session_state["current_experiment_id"] = editing_exp_id
        st.session_state["current_version_id"] = new_vid
        st.session_state["current_branch_id"] = selected_branch_id
        st.session_state["ws_editing_ver_id"] = new_vid
        st.toast(f"Saved as v{next_num}: {label}.", icon=":material/add_circle:")
        st.rerun()

if eval_clicked:
    if not editing_exp_id:
        name = st.session_state["ws_exp_name"].strip() or "Untitled Experiment"
        if not user_prompt_val:
            st.error("Please enter a user prompt template first.")
        else:
            exp_id, ver_id = create_experiment_with_version(
                db=db,
                name=name,
                category=category,
                system_prompt=sys_prompt_val,
                user_prompt=user_prompt_val,
                technique=tech_val,
                output_format=fmt_val,
                model_name=model_val,
                temperature=temp_val,
                max_tokens=max_tok_val,
                few_shot_examples=_collect_few_shots(),
            )
            if sample_input_val:
                db.save_test_case(TestCase(input_data=sample_input_val, expected_output=expected_val), exp_id)
            st.session_state["current_experiment_id"] = exp_id
            st.session_state["current_version_id"] = ver_id
            st.session_state["ws_editing_exp_id"] = exp_id
            st.session_state["ws_editing_ver_id"] = ver_id
            st.session_state["current_branch_id"] = db.get_prompt_branches(exp_id)[0]["id"]
            st.session_state.pop(f"ws_branch_selector_{exp_id}", None)
            st.switch_page("views/2_Evaluation_Lab.py")
    else:
        st.switch_page("views/2_Evaluation_Lab.py")
