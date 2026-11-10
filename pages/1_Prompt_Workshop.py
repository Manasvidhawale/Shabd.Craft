"""
Shabd.Craft — Prompt Workshop

Interactive workspace for crafting, previewing, and executing prompts.
Supports all 6 prompting techniques with live preview.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import json
from src.config import settings
from src.database import Database
from src.schemas import (
    PromptVersion, Experiment, FewShotExample, TestCase,
    PromptingTechnique, TaskCategory, OutputFormat, ExecutionStatus,
    EvaluationWeights, _new_id, _now,
)
from src.prompt_engine import (
    construct_prompt, execute_prompt, get_provider, TECHNIQUE_INFO,
)
from src.template_engine import extract_variables, preview_template, validate_template
from src.experiment_service import create_experiment_with_version
from src.export_service import generate_production_code

st.set_page_config(page_title="Prompt Workshop — Shabd.Craft", page_icon="✦", layout="wide")

@st.cache_resource
def get_db():
    return Database(settings.db_path)

db = get_db()

# ── Session defaults ───────────────────────────────────────────────────
for key, default in [
    ("ws_system", st.session_state.get("prompt_system", "")),
    ("ws_user", st.session_state.get("prompt_user", "")),
    ("ws_technique", st.session_state.get("prompt_technique", "zero_shot")),
    ("ws_format", st.session_state.get("prompt_output_format", "text")),
    ("ws_temp", 0.7),
    ("ws_max_tokens", 1024),
    ("ws_few_shots", []),
    ("ws_sample_input", ""),
    ("ws_expected", ""),
    ("ws_exp_name", ""),
    ("ws_category", "general"),
    ("ws_last_response", None),
    ("ws_unsaved", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Header ─────────────────────────────────────────────────────────────
st.markdown("## Prompt Workshop")
st.caption("Craft, preview, and execute prompts with different techniques.")

# Mode indicator
if settings.is_demo_mode:
    st.markdown('<span class="status-badge badge-demo" style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;background:rgba(251,191,36,0.15);color:#fbbf24;border:1px solid rgba(251,191,36,0.3);">Demo Mode — responses are simulated</span>', unsafe_allow_html=True)

st.divider()

# ── Command Bar ────────────────────────────────────────────────────────
bar1, bar2, bar3, bar4 = st.columns([2, 1, 1, 1])
with bar1:
    exp_name = st.text_input("Experiment Name", value=st.session_state["ws_exp_name"],
                             placeholder="e.g., Customer Feedback Summarizer v1",
                             key="input_exp_name")
    st.session_state["ws_exp_name"] = exp_name
with bar2:
    categories = [e.value for e in TaskCategory]
    cat_idx = categories.index(st.session_state["ws_category"]) if st.session_state["ws_category"] in categories else 0
    category = st.selectbox("Task Category", categories,
                           format_func=lambda x: x.replace("_", " ").title(),
                           index=cat_idx)
    st.session_state["ws_category"] = category
with bar3:
    model = st.selectbox("Model", settings.AVAILABLE_MODELS if not settings.is_demo_mode else ["demo-simulator"],
                         index=0)
with bar4:
    st.markdown(f"**Provider:** {settings.active_provider}")
    st.markdown(f"**Status:** {'Ready' if get_provider().is_available() else 'Unavailable'}")

st.markdown("")

# ── Main Layout: Composer + Preview ────────────────────────────────────
left_col, right_col = st.columns([3, 2])

with left_col:
    # Technique selector
    st.markdown("##### Prompting Technique")
    techniques = [e.value for e in PromptingTechnique]
    technique_labels = {t.value: TECHNIQUE_INFO[t]["name"] for t in PromptingTechnique}
    tech = st.selectbox("Select Technique", techniques,
                       format_func=lambda x: technique_labels.get(x, x),
                       index=techniques.index(st.session_state["ws_technique"]),
                       key="sel_technique")
    st.session_state["ws_technique"] = tech

    # Technique info
    tech_enum = PromptingTechnique(tech)
    with st.expander(f"About {TECHNIQUE_INFO[tech_enum]['name']}", expanded=False):
        st.markdown(TECHNIQUE_INFO[tech_enum]["description"])
        st.code(TECHNIQUE_INFO[tech_enum]["example_user"][:300], language="text")

    st.markdown("##### System Instructions")
    system_prompt = st.text_area("System Prompt", value=st.session_state["ws_system"],
                                 height=100, placeholder="You are a helpful assistant...",
                                 key="ta_system")
    st.session_state["ws_system"] = system_prompt

    st.markdown("##### User Prompt Template")
    st.caption("Use `{{variable_name}}` for template variables.")
    user_prompt = st.text_area("User Prompt", value=st.session_state["ws_user"],
                               height=200,
                               placeholder="Summarize the following feedback:\n\n{{customer_feedback}}",
                               key="ta_user")
    st.session_state["ws_user"] = user_prompt
    st.session_state["ws_unsaved"] = True

    # Few-shot examples
    if tech in ("one_shot", "few_shot"):
        st.markdown("##### Few-Shot Examples")
        num = 1 if tech == "one_shot" else st.number_input("Number of examples", 2, 10, 3)

        examples = st.session_state.get("ws_few_shots", [])
        while len(examples) < num:
            examples.append({"input_text": "", "output_text": ""})
        examples = examples[:num]

        for i in range(num):
            with st.expander(f"Example {i+1}", expanded=(i == 0)):
                inp = st.text_area(f"Input {i+1}", value=examples[i].get("input_text", ""),
                                   height=60, key=f"fs_in_{i}")
                out = st.text_area(f"Output {i+1}", value=examples[i].get("output_text", ""),
                                   height=60, key=f"fs_out_{i}")
                examples[i] = {"input_text": inp, "output_text": out}

        st.session_state["ws_few_shots"] = examples

    # Output format
    fmt_col, temp_col, tok_col = st.columns(3)
    with fmt_col:
        formats = [e.value for e in OutputFormat]
        fmt = st.selectbox("Output Format", formats,
                          format_func=lambda x: x.replace("_", " ").title(),
                          index=formats.index(st.session_state["ws_format"]))
        st.session_state["ws_format"] = fmt
    with temp_col:
        temp = st.slider("Temperature", 0.0, 2.0, st.session_state["ws_temp"], 0.1)
        st.session_state["ws_temp"] = temp
    with tok_col:
        max_tok = st.number_input("Max Tokens", 64, 4096, st.session_state["ws_max_tokens"], 64)
        st.session_state["ws_max_tokens"] = max_tok

    st.markdown("")

    # Sample input
    st.markdown("##### Test Input")
    sample_input = st.text_area("Sample Input Data", value=st.session_state["ws_sample_input"],
                                height=100,
                                placeholder="Enter sample data to test your prompt...",
                                key="ta_sample")
    st.session_state["ws_sample_input"] = sample_input

    expected = st.text_area("Expected Output (optional)", value=st.session_state["ws_expected"],
                            height=80, placeholder="What should the ideal response look like?",
                            key="ta_expected")
    st.session_state["ws_expected"] = expected

# ── Right Pane: Preview, Results & Export ──────────────────────────────
with right_col:
    tab_preview, tab_export = st.tabs(["Preview & Results", "Export Code"])

    with tab_preview:
        st.markdown("##### Live Preview")

        # Template validation
        if user_prompt:
            validation = validate_template(user_prompt)
            variables = validation["variables"]

            if variables:
                st.caption(f"Template variables: `{'`, `'.join(variables)}`")

            if validation["warnings"]:
                for w in validation["warnings"]:
                    st.warning(w)

            # Preview with sample data
            var_values = {}
            if sample_input:
                for v in variables:
                    var_values[v] = sample_input

            rendered = preview_template(user_prompt, var_values)

            st.markdown("**Rendered Prompt:**")
            st.code(rendered[:2000], language="text")

            # Word & char counts
            wc = len(rendered.split())
            cc = len(rendered)
            st.caption(f"Words: {wc} · Characters: {cc}")
        else:
            st.info("Enter a prompt template to see the preview.")

        # Prompt analysis
        if user_prompt:
            st.markdown("##### Prompt Analysis")
            issues = []
            if not system_prompt:
                issues.append("No system prompt — consider adding role/context instructions.")
            if len(user_prompt) < 20:
                issues.append("Very short prompt — may lack specificity.")
            if "{{" not in user_prompt and tech == "zero_shot":
                issues.append("No template variables — prompt will be static.")
            if fmt == "json" and "json" not in user_prompt.lower():
                issues.append("JSON output selected but not mentioned in prompt.")
            if tech == "role_based" and (not system_prompt.strip() or system_prompt.strip().lower() == "you are a helpful assistant."):
                issues.append("Role-based selected with a generic or empty system prompt — define a specific expert role and domain.")
            if tech == "structured_output" and not any(kw in user_prompt.lower() for kw in ["json", "field", "schema", "format", "key", "column"]):
                issues.append("Structured output selected — specify the expected fields or output schema in the prompt.")
            if not any(kw in user_prompt.lower() for kw in ["step", "1.", "first", "then", "finally"]):
                if tech == "task_decomposition":
                    issues.append("No explicit steps detected — a default 3-step decomposition scaffold will be prepended automatically.")

            if issues:
                for issue in issues:
                    st.markdown(f"- {issue}")
            else:
                st.success("Prompt looks well-structured.")

        st.divider()

        # Execution results
        if st.session_state.get("ws_last_response"):
            resp = st.session_state["ws_last_response"]
            st.markdown("##### Execution Result")

            if resp.get("is_demo"):
                st.caption("Simulated demo response")

            st.text_area("Generated Output", value=resp.get("content", ""),
                         height=200, disabled=True, key="result_output")

            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Latency", f"{resp.get('latency_ms', 0):.0f}ms")
            rc2.metric("Tokens", resp.get("total_tokens", 0))
            if resp.get("cost_estimate", 0) > 0:
                rc3.metric("Cost", f"${resp['cost_estimate']:.5f}")
            else:
                rc3.metric("Cost", "—" if resp.get("is_demo") else "$0.00")

    with tab_export:
        st.markdown("##### Export Production Code")
        st.caption("Copy-pasteable API integration snippets for your current prompt configuration.")

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

# ── Action Buttons ─────────────────────────────────────────────────────
st.divider()
act1, act2, act3, act4 = st.columns(4)

with act1:
    run_clicked = st.button("Run Prompt", type="primary", use_container_width=True)

with act2:
    save_clicked = st.button("Save Experiment", use_container_width=True)

with act3:
    eval_clicked = st.button("Send to Evaluation Lab", use_container_width=True)

with act4:
    reset_clicked = st.button("Reset", use_container_width=True)

# ── Handle Actions ─────────────────────────────────────────────────────

if reset_clicked:
    for key in ["ws_system", "ws_user", "ws_sample_input", "ws_expected",
                "ws_last_response", "ws_exp_name", "ws_few_shots"]:
        st.session_state[key] = "" if isinstance(st.session_state.get(key), str) else ([] if isinstance(st.session_state.get(key), list) else None)
    st.rerun()

if run_clicked:
    if not user_prompt.strip():
        st.error("Please enter a user prompt template.")
    else:
        few_shots = []
        if tech in ("one_shot", "few_shot"):
            for ex in st.session_state.get("ws_few_shots", []):
                if ex.get("input_text") and ex.get("output_text"):
                    few_shots.append(FewShotExample(**ex))

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
            response = execute_prompt(version, input_data=sample_input)

        if response.error:
            st.error(f"Execution failed: {response.error}")
        else:
            st.session_state["ws_last_response"] = response.model_dump()
            st.success("Prompt executed successfully.")
            st.rerun()

if save_clicked:
    name = st.session_state["ws_exp_name"].strip()
    if not name:
        st.error("Please enter an experiment name.")
    elif not user_prompt.strip():
        st.error("Please enter a user prompt template.")
    else:
        few_shots_data = []
        if tech in ("one_shot", "few_shot"):
            for ex in st.session_state.get("ws_few_shots", []):
                if ex.get("input_text") and ex.get("output_text"):
                    few_shots_data.append(ex)

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
            few_shot_examples=few_shots_data,
        )

        # Save sample input as test case if provided
        if sample_input.strip():
            tc = TestCase(input_data=sample_input, expected_output=expected)
            db.save_test_case(tc, exp_id)

        st.session_state["current_experiment_id"] = exp_id
        st.session_state["current_version_id"] = ver_id
        st.session_state["ws_unsaved"] = False
        st.success(f"Experiment **{name}** saved.")

if eval_clicked:
    if not st.session_state.get("current_experiment_id"):
        st.warning("Save the experiment first before sending to Evaluation Lab.")
    else:
        st.switch_page("pages/2_Evaluation_Lab.py")
