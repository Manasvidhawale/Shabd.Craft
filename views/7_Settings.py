"""
Shabd.Craft — Settings & Configuration

Provider setup, evaluation defaults, execution limits, and documentation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from src.config import settings

st.markdown("## Settings & Configuration")
st.caption("Configure providers, evaluation defaults, and execution limits.")
st.divider()

tab_config, tab_eval, tab_docs = st.tabs(["Provider & Model", "Evaluation Defaults", "Documentation"])

# ── Provider Config ────────────────────────────────────────────────────
with tab_config:
    st.markdown("##### LLM Provider Configuration")

    # API Key status
    if settings.has_api_key and not settings.demo_mode:
        st.success("OpenAI API key is configured.")
    else:
        st.info("No OpenAI API key configured — using local offline fallback engine.")
        st.markdown("""
        **Enable Live API Calls:**
        1. Open `.env` in the project root.
        2. Set `OPENAI_API_KEY=your_actual_key_here`
        3. Restart the application.
        """)

    st.markdown(f"**Default Model:** `{settings.default_model}`")

    st.divider()

    st.markdown("##### Available Models")
    for model in settings.AVAILABLE_MODELS:
        pricing = settings.MODEL_PRICING.get(model, {})
        if pricing:
            st.markdown(f"- `{model}` — Input: ${pricing['input']}/1K tokens, Output: ${pricing['output']}/1K tokens")
        else:
            st.markdown(f"- `{model}`")

    st.caption("Change the startup default model by setting `SHABDCRAFT_DEFAULT_MODEL` in your .env file. In Live Mode, you can also pick any model per run directly from the Model dropdown in the Prompt Workshop.")

    st.divider()

    st.markdown("##### Execution Limits")
    st.markdown(f"- **Max test cases per experiment:** {settings.max_test_cases}")
    st.markdown(f"- **Max optimization rounds:** {settings.max_optimization_rounds}")
    st.markdown(f"- **Max retry attempts:** {settings.max_retries}")
    st.markdown(f"- **Request timeout:** {settings.timeout}s")
    st.caption("Adjust these in your .env file.")

# ── Evaluation Defaults ────────────────────────────────────────────────
with tab_eval:
    st.markdown("##### Default Evaluation Weights")
    st.caption("These are the default weights used when starting a new evaluation. You can override them per experiment.")

    for criterion, weight in settings.DEFAULT_EVAL_WEIGHTS.items():
        st.markdown(f"- **{criterion.replace('_', ' ').title()}:** {weight:.0%}")

    st.divider()

    st.markdown("##### Default Generation Settings")
    st.markdown(f"- **Temperature:** {settings.DEFAULT_TEMPERATURE}")
    st.markdown(f"- **Max Tokens:** {settings.DEFAULT_MAX_TOKENS}")

    st.divider()

    st.markdown("##### Evaluation Methodology")
    st.markdown("""
    Shabd.Craft uses two complementary evaluation approaches:

    **1. Rule-Based Evaluation (Deterministic)**
    - JSON format validation
    - Required keyword presence
    - Word count compliance
    - Empty response detection
    - Output schema validation
    - Content overlap with expected output

    Rule-based checks are repeatable and objective but cannot assess semantic quality.

    **2. LLM-as-a-Judge**
    - Uses a separate LLM call with an explicit scoring rubric
    - Evaluates accuracy, relevance, instruction adherence, clarity, and format compliance
    - Returns structured JSON scores with explanations
    - Validated via Pydantic with bounded retries

    **Important:** LLM-as-a-Judge scores may vary between runs. They reflect the judge model's assessment, not objective ground truth. Use them as complementary signals alongside rule-based checks.

    **Combined Mode** averages both methods for each criterion, providing a balanced view.

    **Weighted Scoring:**
    `Overall Score = Σ (Criterion Score × Normalized Weight)`

    Weights are normalized so they sum to 1.0. At least one weight must be > 0.
    """)

# ── Documentation ──────────────────────────────────────────────────────
with tab_docs:
    st.markdown("##### Shabd.Craft Documentation")

    st.markdown("""
    ### Architecture

    ```
    Streamlit UI → Application Services → Prompt Engine → LLM Provider
                                        ↓
                                  Evaluator (Rule + LLM Judge)
                                        ↓
                                    Optimizer
                                        ↓
                                  SQLite Database
    ```

    ### Prompting Techniques

    | Technique | Description | Best For |
    |-----------|-------------|----------|
    | Zero-Shot | Instructions only, no examples | Simple, well-defined tasks |
    | One-Shot | One demonstration example | Tasks needing a specific output format |
    | Few-Shot | Multiple examples | Complex tasks with nuanced patterns |
    | Role-Based | Assigns expertise and context | Domain-specific analysis |
    | Structured Output | Requires specific format (JSON, etc.) | Machine-parseable outputs |
    | Task Decomposition | Breaks task into steps | Multi-step workflows |
    | Chain-of-Thought (CoT) | Elicits step-by-step reasoning before final answer | Logic, math, and multi-step inference |

    ### Evaluation Criteria

    | Criterion | Description | Scale |
    |-----------|-------------|-------|
    | Accuracy | Factual correctness and alignment with expected output | 0-100 |
    | Relevance | How well the response addresses the input | 0-100 |
    | Instruction Adherence | Compliance with task instructions | 0-100 |
    | Clarity | Readability, organization, completeness | 0-100 |
    | Format Compliance | Matches required output format | 0-100 |

    ### Offline Fallback Provider

    When no `OPENAI_API_KEY` is configured in `.env`, Shabd.Craft automatically uses a deterministic local provider so all evaluation, optimization, security audit, and export workflows remain functional offline.

    ### Future: Multi-Agent Extension

    The architecture is designed for future LangGraph integration:

    - **Planner Agent** — analyzes task, defines strategy
    - **Tester Agent** — executes prompts against test data
    - **Evaluator Agent** — structured evaluation with feedback
    - **Optimizer Agent** — generates improved candidates

    See `docs/future_agentic_extension.md` for the upgrade path.
    """)
