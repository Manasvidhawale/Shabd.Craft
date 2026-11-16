# Changelog & Design Implementation Summary

## Overview
This release implements the revised UI/UX architecture specified in [`DESIGN_PLAN.md`](DESIGN_PLAN.md) for **Shabd.Craft** targeting **Streamlit 1.38.0**. The interface has been elevated from default Streamlit elements into a clean, modern, dark-first precision workbench with verified WCAG 2.1 AA contrast compliance, seamless keyboard navigation, robust threaded concurrency, and zero layout shifts.

---

## What to Look at First

1. **Prompt Workshop (`views/1_Prompt_Workshop.py`):**
   - **Unified `@st.fragment` Scope:** The entire two-column composer (Left Inputs + Right Live Preview/Token Meter) is wrapped inside a single reactive canvas. Typing or testing variable values reactively updates the token consumption gauge, estimated cost, and quality readiness score without triggering full-page reruns.
   - **Tuning Popover (`st.popover`):** Temperature, max tokens, validation harness, and guardrail checkboxes are tucked inside a non-disruptive popover with an internal `st.form`.
   - **Multi-Step Status:** Clicking "Run Prompt" displays native `st.status` tracking guardrails and LLM inference.

2. **Evaluation Lab (`views/2_Evaluation_Lab.py`):**
   - **Background Coordinator Thread & Decoupled Stop:** Clicking "Run Evaluation" dispatches a background coordinator thread owning a `ThreadPoolExecutor(max_workers=4)`. Workers do pure, stateless inference (never touching `st.*` or `st.session_state`).
   - **Reactive Monitor Fragment:** An `@st.fragment(run_every=1)` displays live progress and hosts a working `⏹ Stop Evaluation` button. Clicking Stop signals workers to stop submitting work, preserves completed partial results, and saves them safely to SQLite once.
   - **Inline Test Suite Data Editor (`st.data_editor`):** Tabular inline test case editing with `num_rows="dynamic"` and column configuration.
   - **Scorecard Progress Columns (`st.dataframe`):** Criterion scores rendered with native progress bars.

3. **Workspace Overview (`views/0_Home.py`):**
   - Replaced cramped 6-column layout with responsive 3-column / 2-row metric grid wrapped in `st.container(border=True)`.
   - Replaced raw HTML `<div class="card-surface">` with native containers, typography, and Material icons.

4. **Settings & Secrets (`views/7_Settings.py`):**
   - **Masked Display:** Configured API keys display strictly as `••••abcd` (showing only the last 4 characters without provider prefixes).
   - **Connection Tester:** Interactive `:material/bolt: Test Connection` button testing endpoint reachability.
   - **Modal Dialog:** Replaced inline warning bars with `@st.dialog("Clear Workspace Experiments")`.

---

## Components Added & Rationale

| Streamlit Component | Location | Architectural Purpose & Rationale |
|---|---|---|
| `st.navigation` + `st.Page` | `app.py` | Centralized URL routing with sidebar sections (`Workflow`, `Management`), replacing legacy file auto-discovery. |
| `st.container(border=True)` | Across all views | Clean, theme-aware card surfaces and visual containment; eliminates custom CSS border overrides. |
| `st.popover` | `1_Prompt_Workshop.py` | Progressive disclosure for secondary parameters (temperature, max tokens, harness) without cluttering composer. |
| `@st.dialog` | `1_Prompt_Workshop.py`, `5_Experiment_History.py`, `6_Prompt_Library.py`, `7_Settings.py` | Focus-trapping accessible modal confirmation dialogs for destructive actions (deletes, clears); eliminates layout shift. |
| `st.data_editor` | `2_Evaluation_Lab.py` | Native inline spreadsheet-like editing for test datasets with `num_rows="dynamic"`. |
| `st.status` | `1_Prompt_Workshop.py`, `2_Evaluation_Lab.py`, `3_Prompt_Optimizer.py`, `4_Compare_Versions.py` | Multi-step live execution feedback (guardrails $\rightarrow$ inference $\rightarrow$ contract validation) replacing indefinite spinners. |
| `st.toast` | Across all views | Floating, non-blocking transient alerts for clipboard copies, version updates, and cache refreshes. |
| `@st.fragment` | `1_Prompt_Workshop.py`, `2_Evaluation_Lab.py` | Scoped reactive rerun boundaries: isolated prompt preview/tokenizer reactivity and background evaluation progress monitoring. |
| `st.code` | Across all views | Syntax-highlighted output and template display with native 1-click clipboard copy button. |
| `st.dataframe` + `st.column_config` | `2_Evaluation_Lab.py` | Native tabular presentation with embedded `ProgressColumn` for test scores. |
| `st.logo` | `app.py` | Native top-left brand identity in sidebar. |
| `st.radio(horizontal=True)` | Across all views | Accessible 1.38-compatible substitute for unavailable `st.segmented_control` / `st.pills`. |
| Colorized text markdown (`:green[...]`, `:red[...]`) | Across all views | Accessible 1.38-compatible substitute for unavailable `st.badge`. |

---

## Backend Changes & Tradeoffs

1. **No Math or Schema Changes:**
   - Database schema, mathematical weighted scoring, evaluation criteria, and LLM inference logic remain intact.
2. **Evaluation Concurrency Model:**
   - Switched from synchronous inline script execution to a decoupled coordinator background thread pattern with a thread-safe `EvalRunHandle`.
   - Prevented SQLite file-lock conflicts by ensuring worker threads perform network I/O only, while the main thread performs a single bulk write sequentially upon completion or cancellation.
3. **Streamlit 1.38 Tradeoffs & Substitutes:**
   - `st.metric` in 1.38 lacks the `border` parameter: solved by wrapping tiles inside `with st.container(border=True): st.metric(...)`.
   - `st.button` in 1.38 does not take `icon=`: solved by prefixing labels with `:material/icon_name:` markdown syntax.
   - `config.toml [theme] font` rejects custom family names: solved by keeping `font = "sans serif"` and injecting a single documented CSS `@import` in `src/ui_theme.py`.
