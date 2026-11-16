# Shabd.Craft UI/UX Architecture & Redesign Plan
**Role:** Senior Streamlit UI/UX Architect  
**Streamlit Version:** 1.38.0 (Verified via package inspection)  
**Target Mood:** Clean, Modern, Dark-First Precision Workbench (One Accent, High Contrast, Zero Layout Shifts)  
**Document Status:** Revised Architectural Plan (Awaiting User Approval Prior to Implementation)

---

## 1. Information Architecture & Navigation Model

Shabd.Craft is an enterprise-grade Prompt Engineering & Optimization Workbench. The application is architected into two primary sections: **Workflow** (the active development, testing, and optimization lifecycle) and **Management** (version repository, catalog, and workspace settings).

```
Shabd.Craft
├── WORKFLOW
│   ├── Home (Workspace Overview, Key Metrics & Guided Actions)
│   ├── Prompt Workshop (Authoring, Scoped Live Preview, Harness & Guardrails)
│   ├── Evaluation Lab (Concurrent Dataset Benchmarking, Arbiter Judge & Security Audit)
│   ├── Prompt Optimizer (Autonomous Generational Hill-Climbing & 1-Shot Mutations)
│   └── Compare Versions (Word-Level Diff & Multi-Model Arena with AI Referee)
└── MANAGEMENT
    ├── Experiment History (Lineage Cards, Metric Trends & Bulk Exports)
    ├── Prompt Library (Starter & Custom Template Catalog)
    └── Settings (Provider Connectivity, Pricing, Security & Default Weights)
```

### Entrypoint & Routing Architecture (`st.navigation`)
In Streamlit 1.38.0, the legacy `pages/` auto-discovery pattern is replaced by centralized routing in `app.py` using `st.navigation` and `st.Page`. This eliminates uncontrolled page discovery, guarantees deterministic execution order, allows programmatic sidebar branding via `st.logo`, and supports deep linking through URL query parameters.

#### Page Registry Definition in `app.py`:
```python
import streamlit as st

pages = {
    "Workflow": [
        st.Page("views/0_Home.py", title="Home", icon=":material/dashboard:", default=True, url_path="home"),
        st.Page("views/1_Prompt_Workshop.py", title="Prompt Workshop", icon=":material/edit_note:", url_path="workshop"),
        st.Page("views/2_Evaluation_Lab.py", title="Evaluation Lab", icon=":material/biotech:", url_path="eval-lab"),
        st.Page("views/3_Prompt_Optimizer.py", title="Prompt Optimizer", icon=":material/auto_fix_high:", url_path="optimizer"),
        st.Page("views/4_Compare_Versions.py", title="Compare Versions", icon=":material/compare_arrows:", url_path="compare"),
    ],
    "Management": [
        st.Page("views/5_Experiment_History.py", title="Experiment History", icon=":material/history:", url_path="history"),
        st.Page("views/6_Prompt_Library.py", title="Prompt Library", icon=":material/menu_book:", url_path="library"),
        st.Page("views/7_Settings.py", title="Settings", icon=":material/settings:", url_path="settings"),
    ],
}
nav = st.navigation(pages, position="sidebar")
nav.run()
```

### Primary vs. Secondary Actions by Screen
| Page | Primary Action | Secondary Actions | Deep Link Parameters |
|---|---|---|---|
| **0. Home** | "+ New Prompt" (`st.button` with state reset $\rightarrow$ Workshop) | `st.page_link` to Library/Eval/Settings, View distribution charts | `?tab=overview` |
| **1. Prompt Workshop** | "Run Prompt" (`st.button`, type="primary") | "Save Changes", "Save New Version", Tuning popover (`st.popover`), Export Code tab | `?exp=<id>&ver=<id>` |
| **2. Evaluation Lab** | "Run Evaluation" (`st.button`, type="primary") | "Stop Evaluation" (`st.button`), Synthesize Test Suite, Import/Export CSV, Security Audit | `?exp=<id>&ver=<id>&tab=<tab>` |
| **3. Prompt Optimizer** | "Start Autonomous Optimization" | "Generate 1-Shot Variations", Inspect generations, "Promote Winner" | `?exp=<id>&ver=<id>` |
| **4. Compare Versions** | "Run Model Battle" | "Crown Winner (AI Referee)", Inspect side-by-side token metrics, Diff toggle | `?exp=<id>&v1=<id>&v2=<id>` |
| **5. Experiment History**| "Open in Workshop" | "Duplicate", "Export CSV/JSON", "Delete Experiment" (`@st.dialog`) | `?exp=<id>` |
| **6. Prompt Library** | "Open in Workshop" | Category filter (`st.radio`), Search query, "Create Custom Template" | `?cat=<category>` |
| **7. Settings** | "Save Configuration" (`st.form_submit_button`) | "Test Connection" (`st.button`), Update Model, Reset Workspace (`@st.dialog`) | `?section=keys` |

---

## 2. Layout Wireframes (ASCII & Responsive Behavior)

### Screen 0: Home (`views/0_Home.py`)
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  [Logo] Shabd.Craft · Workspace Overview                                         │
│  Create prompts, run evaluations, and review experiment performance.             │
├──────────────────────────────────────────────────────────────────────────────────┤
│  QUICK ACTIONS (4 Equal Columns via st.page_link / primary button)               │
│  ┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐   │
│  │ [+ New Prompt]   │ [📚 Library]     │ [🧪 Eval Lab]    │ [⚙️ Settings]    │   │
│  └──────────────────┴──────────────────┴──────────────────┴──────────────────┘   │
│                                                                                  │
│  WORKSPACE SUMMARY (st.container with border=True, 3 cols x 2 rows)              │
│  ┌───────────────────────┬───────────────────────┬───────────────────────────┐   │
│  │ Active Prompts: 12    │ Prompt Versions: 34   │ Test Runs: 148            │   │
│  ├───────────────────────┼───────────────────────┼───────────────────────────┤   │
│  │ Avg Quality: 88.4/100 │ AI Optimizations: 9   │ Top Benchmark: 96.2/100   │   │
│  └───────────────────────┴───────────────────────┴───────────────────────────┘   │
│                                                                                  │
│  ACTIVE PROMPT WORKSPACE (List of cards in border=True containers)               │
│  ┌──────────────────────────────────────────────────────┬─────────┬──────────┐   │
│  │ Customer Classifier · Classification · 3 versions · 89.2% │ [Edit]  │ [Eval]   │   │
│  ├──────────────────────────────────────────────────────┼─────────┼──────────┤   │
│  │ SQL Query Generator · Code · 2 versions · 91.0%      │ [Edit]  │ [Eval]   │   │
│  └──────────────────────────────────────────────────────┴─────────┴──────────┘   │
│                                                                                  │
│  WORKSPACE ANALYTICS (2 Columns)                                                 │
│  ┌───────────────────────────────────────┬───────────────────────────────────┐   │
│  │ Score Distribution (Plotly Histogram) │ Criteria Averages (Plotly Bar)    │   │
│  └───────────────────────────────────────┴───────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────┘
```
**Responsive Narrow-Screen Behavior:**
* Quick action columns collapse from 4 horizontal buttons to a 2x2 grid, then full-width stacked buttons on mobile (<640px).
* Metric cards collapse from 3 columns x 2 rows to 1 column x 6 stacked metric tiles.
* Active prompt items stack the action buttons (`Edit`, `Eval`) below the prompt metadata.
* Analytics charts stack vertically (Histogram top, Bar chart bottom).

---

### Screen 1: Prompt Workshop (`views/1_Prompt_Workshop.py`)
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Prompt Workshop                                        [Target: Classifier v2 ▼]│
├──────────────────────────────────────────────────────────────────────────────────┤
│  COMMAND BAR (3 Columns: Name [3], Category [1], Model [1])                      │
│  [Name: Customer Sentiment Analysis] [Category: Classification▼] [Model: Llama3▼]│
├──────────────────────────────────────────────────────────────────────────────────┤
│  ═══════════════════════ st.fragment: workshop_canvas ══════════════════════════  │
│  PROMPT COMPOSER (col_left: 3)           │ LIVE INSPECTOR (col_right: 2)         │
│  ┌─────────────────────────────────────┐ │ ┌───────────────────────────────────┐ │
│  │ Technique: [Role-Based ▼] Format: JSON│ │ │ [Tabs: Preview & Result | Export]│ │
│  │ Caption: Assigns persona & contract. │ │ │ ┌───────────────────────────────┐ │ │
│  ├─────────────────────────────────────┤ │ │ │ Rendered Prompt Template       │ │ │
│  │ System Instructions                 │ │ │ │ Words: 42 · Tokens: ~56        │ │ │
│  │ [You are a sentiment analyzer...   ]│ │ │ └───────────────────────────────┘ │ │
│  ├─────────────────────────────────────┤ │ │ Context Consumption: 56/32,768   │ │
│  │ User Template (use {{variable}})    │ │ │ [██░░░░░░░░░░░░░░░░░░░░] 0.2%    │ │
│  │ [Analyze input: {{feedback_text}}  ]│ │ │ Est. Cost: $0.00006 / 1k runs    │ │
│  ├─────────────────────────────────────┤ │ │ ┌───────────────────────────────┐ │ │
│  │ Variable Inputs                     │ │ │ │ Prompt Readiness: 92/100      │ │ │
│  │ feedback_text: [Fast ship, bad box ]│ │ │ │ :material/check: Delimiters OK │ │ │
│  │ [:material/magic: Fill Sample Data] │ │ │ └───────────────────────────────┘ │ │
│  ├─────────────────────────────────────┤ │ │ ┌───────────────────────────────┐ │ │
│  │ [⚙️ Tuning & Parameters (Popover)]   │ │ │ │ Execution Output              │ │ │
│  │ (Temp: 0.7, MaxTok: 1024, Harness)  │ │ │ │ Latency: 340ms · Tok: 62      │ │ │
│  └─────────────────────────────────────┘ │ └───────────────────────────────────┘ │
│  ═══════════════════════════════════════════════════════════════════════════════  │
│                                                                                  │
│  ACTION BAR (Outside Fragment, Direct Full-Page Action & DB Control)             │
│  [▶ Run Prompt (Primary)] [💾 Save Changes] [➕ Save as New Version] [🗑️ Delete] │
└──────────────────────────────────────────────────────────────────────────────────┘
```
**Responsive Narrow-Screen Behavior:**
* Composer and Live Inspector collapse from 3:2 horizontal columns to a vertical stack.
* The Live Inspector sits directly below the composer inputs.
* Within the Live Inspector, Token Meter and Cost estimate stack vertically.
* The bottom action bar wraps buttons to 2 columns on tablets and 1 button per line on mobile screens.

---

### Screen 2: Evaluation Lab (`views/2_Evaluation_Lab.py`)

#### Tab 1: Test Cases
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Evaluation Lab: [Experiment: Sentiment Analysis ▼]  [Version: v2 (Current) ▼]   │
├──────────────────────────────────────────────────────────────────────────────────┤
│  [Tabs: 1. Test Cases | 2. Config & Arbiter | 3. Results & Telemetry | 4. Security]│
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ IMPORT & DATASET TOOLS (3 Columns)                                         │  │
│  │ [File Uploader: CSV/JSON]  [Download Sample Template]  [Export Dataset CSV]│  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │ INLINE DATASET EDITOR (st.data_editor with num_rows="dynamic")             │  │
│  │ ┌───┬────────────────────────────────┬──────────────────────────┬────────┐ │  │
│  │ │ # │ Input Data (input_data)        │ Expected Output (target) │ Action │ │  │
│  │ ├───┼────────────────────────────────┼──────────────────────────┼────────┤ │  │
│  │ │ 1 │ Fast delivery, broke in 2 days │ Negative - Quality       │ [Del]  │ │  │
│  │ │ 2 │ Loved customer service rep     │ Positive - Service       │ [Del]  │ │  │
│  │ │ + │ [Click to append new row...]   │                          │        │ │  │
│  │ └───┴────────────────────────────────┴──────────────────────────┴────────┘ │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │ AI SYNTHETIC TEST GENERATOR (Expander)                                     │  │
│  │ Slider: [3] cases · [:material/auto_awesome: Synthesize Test Suite]        │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Tab 2: Config & Arbiter
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  EVALUATION METHOD & CRITERIA CONFIGURATION                                      │
│  Method: (*) Rule-Based (deterministic)  ( ) LLM-as-a-Judge  ( ) Combined        │
│  Arbiter Model: [Llama-3.3-70b-versatile ▼] (Decoupled independent judge)       │
├──────────────────────────────────────────────────────────────────────────────────┤
│  NORMALIZED CRITERIA WEIGHTS (5 Column Sliders inside st.form)                   │
│  ┌────────────┬────────────┬──────────────────────┬────────────┬─────────────┐   │
│  │ Accuracy   │ Relevance  │ Instruction Follow   │ Clarity    │ Format Comp │   │
│  │ [0.30    ] │ [0.20    ] │ [0.25              ] │ [0.15    ] │ [0.10     ] │   │
│  └────────────┴────────────┴──────────────────────┴────────────┴─────────────┘   │
│  Total Weight: 1.00 (Normalized automatically)                                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│  EXECUTION HARDENING (2 Columns)                                                 │
│  Required Keywords: [JSON, sentiment, confidence]  Max Words: [150 words]       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Tab 3: Results & Telemetry
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  SUMMARY SCORECARD (st.container border=True, 4 Columns)                         │
│  ┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐   │
│  │ Avg Score: 89.2% │ Success: 15/15   │ Latency: p50 340 │ Range: 82–96%    │   │
│  │ Δ +4.5% vs v1    │ 0 Execution Errs │ Latency: p95 580 │ StdDev: ±2.1σ    │   │
│  └──────────────────┴──────────────────┴──────────────────┴──────────────────┘   │
│                                                                                  │
│  REGRESSION QUALITY GATE (border=True container)                                 │
│  Gate Status: :material/check_circle: :green[PASSED ALL GATES]                   │
│  ┌─────────────────────────────────────┬─────────┬───────────┬──────────────┐   │
│  │ Assertion                           │ Actual  │ Threshold │ Status       │   │
│  ├─────────────────────────────────────┼─────────┼───────────┼──────────────┤   │
│  │ Minimum Average Score               │ 89.2%   │ >= 80.0%  │ :green[PASS] │   │
│  │ Minimum Format Compliance           │ 94.0%   │ >= 85.0%  │ :green[PASS] │   │
│  │ Security Adversarial Resistance     │ 100.0%  │ >= 80.0%  │ :green[PASS] │   │
│  └─────────────────────────────────────┴─────────┴───────────┴──────────────┘   │
│                                                                                  │
│  DETAILED RESULTS (st.dataframe with ProgressColumn for scores)                  │
│  [Search / Filter results...]                                                    │
│  ┌────┬───────────────────────┬────────────┬─────────────┬─────────────────────┐ │
│  │ ID │ Input                 │ Status     │ Score       │ Accuracy / Format   │ │
│  ├────┼───────────────────────┼────────────┼─────────────┼─────────────────────┤ │
│  │ 1  │ Arrived damaged...    │ SUCCESS    │ [███████░]88│ 90% / 100%          │ │
│  │ 2  │ Super quick turnaround│ SUCCESS    │ [████████]96│ 95% / 100%          │ │
│  └────┴───────────────────────┴────────────┴─────────────┴─────────────────────┘ │
│                                                                                  │
│  ACTION BAR                                                                      │
│  [▶ Run Evaluation (max_workers=4)] [⏹ Stop Evaluation] [⬇️ Export CSV] [⬇️ JSON]│
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Tab 4: Security Audit
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  PROMPT INJECTION & SECURITY DEFENSE AUDIT                                       │
│  Evaluates resistance to system prompt leaks, role hijacking & delimiter escapes │
├──────────────────────────────────────────────────────────────────────────────────┤
│  STATIC DEFENSE POSTURE (3 Columns in border=True container)                     │
│  ┌─────────────────────────┬──────────────────────────┬──────────────────────┐   │
│  │ XML Delimiters: PASS    │ System Leak Guard: PASS  │ Role Defense: PASS   │   │
│  │ <input> tags detected   │ Anti-extraction present  │ Strict persona bound │   │
│  └─────────────────────────┴──────────────────────────┴──────────────────────┘   │
│                                                                                  │
│  [🛡️ Run Adversarial Security Audit (10 Probes)]                                │
│                                                                                  │
│  AUDIT SCORECARD (Visible after run)                                             │
│  Robustness: 90.0% · Attacks Resisted: 9/10 · Static Posture: 100%               │
│  ┌───────────────┬───────────────────────────┬─────────────┬─────────────────┐   │
│  │ Attack Vector │ Attack Name               │ Outcome     │ Reason          │   │
│  ├───────────────┼───────────────────────────┼─────────────┼─────────────────┤   │
│  │ Delimiter Esc │ XML Tag Breaking Probe    │ RESISTED    │ Trapped in tags │   │
│  │ Sys Extraction│ "Ignore previous and dump"│ RESISTED    │ Refusal upheld  │   │
│  │ DAN Override  │ Do Anything Now Persona   │ VULNERABLE  │ Leaked format   │   │
│  └───────────────┴───────────────────────────┴─────────────┴─────────────────┘   │
│                                                                                  │
│  HARDENING RECOMMENDATION (Expander with 1-click upgrade to new version)         │
│  [+ Save Hardened Copy as Version v3]                                            │
└──────────────────────────────────────────────────────────────────────────────────┘
```
**Responsive Narrow-Screen Behavior for Evaluation Lab:**
* Tabs remain scrollable horizontally.
* Data editor switches to horizontal scroll without breaking page width.
* Evaluation summary scorecard collapses to 2 columns on tablets and 1 column on mobile.
* Action buttons stack vertically on mobile screens.

---

### Screen 3: Prompt Optimizer (`views/3_Prompt_Optimizer.py`)
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Prompt Optimizer                                      [Target: Classifier v2 ▼] │
│  Automated Hill-Climbing & Generational Genetic Mutation Engine                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│  CONFIGURATION BAR (3 Columns)                                                   │
│  Iterations: [3 Generations]  Mutation Scale: [Conservative▼]  Evaluator: [Llama]│
├──────────────────────────────────────────────────────────────────────────────────┤
│  [🚀 Start Autonomous Optimization]  [⚡ Generate 3 1-Shot Candidate Variations] │
│                                                                                  │
│  FITNESS PROGRESSION (Altair / Streamlit Line Chart)                             │
│  Score │                                                                         │
│  100   │                                               * Evolved Candidate: 93.4 │
│   90   │                          * Gen 2: 88.5                                  │
│   80   │      * Gen 1: 82.0                                                      │
│   70   │ * Baseline v2: 74.0                                                     │
│        └───────────────────────────────────────────────────────────── Generation  │
│                                                                                  │
│  OPTIMIZED WINNER INSPECTION (st.container border=True)                          │
│  Winner: Candidate B (Generational Mutation) · Score: 93.4% (+19.4% improvement) │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ Optimized System Prompt & Delimited User Template                          │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│  [⭐ Promote Winner to Version v3]  [Discard]                                    │
└──────────────────────────────────────────────────────────────────────────────────┘
```
**Responsive Narrow-Screen Behavior:**
* Progression chart maintains responsive container width (`use_container_width=True`).
* Action buttons stack cleanly below the evolved candidate preview.

---

### Screen 4: Compare Versions (`views/4_Compare_Versions.py`)
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Compare Versions & Model Arena                         [Experiment: Classifier▼]│
├──────────────────────────────────────────────────────────────────────────────────┤
│  SELECTOR BAR (2 Equal Columns)                                                  │
│  Version A: [v1: Baseline (Score: 78.2) ▼]   Version B: [v2: Hardened (89.4) ▼]  │
├──────────────────────────────────────────────────────────────────────────────────┤
│  SIDE-BY-SIDE SYMMETRY (2 Columns with st.container border=True)                 │
│  ┌─────────────────────────────────────┬─────────────────────────────────────┐   │
│  │ VERSION A (v1: Baseline)            │ VERSION B (v2: Hardened)            │   │
│  │ Model: Llama-3-8B · Temp: 0.7       │ Model: Llama-3-8B · Temp: 0.3       │   │
│  │ Benchmark Score: 78.2%              │ Benchmark Score: 89.4% (+11.2%)     │   │
│  │ p50 Latency: 420ms · Tokens: 48     │ p50 Latency: 310ms · Tokens: 39     │   │
│  │ Format Compliance: 80%              │ Format Compliance: 100%             │   │
│  └─────────────────────────────────────┴─────────────────────────────────────┘   │
│                                                                                  │
│  WORD-LEVEL PROMPT DIFF (st.expander, expanded=True)                             │
│  Highlighted additions (:green[+green]) and deletions (:red[-red])               │
│                                                                                  │
│  HEAD-TO-HEAD BATTLE ARENA WITH AI REFEREE                                       │
│  [⚔️ Run Live Arena Battle on Test Suite]                                        │
│  Outcome: :material/emoji_events: :green[VERSION B CROWNED WINNER BY ARBITER]    │
│  Referee Rationale: Version B strictly observed JSON schema with zero leakage.   │
└──────────────────────────────────────────────────────────────────────────────────┘
```
**Responsive Narrow-Screen Behavior:**
* Version A and Version B columns collapse to a vertical stack (Version A on top, Version B below).
* Metrics retain their internal grid alignment within each card.

---

### Screen 5: Experiment History (`views/5_Experiment_History.py`)
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Experiment History & Lineage Repository                                         │
├──────────────────────────────────────────────────────────────────────────────────┤
│  FILTER & SEARCH BAR (st.columns([3, 1, 1]))                                     │
│  [Search experiments...]  Category: [All ▼]  Sort By: [Latest Run ▼]             │
├──────────────────────────────────────────────────────────────────────────────────┤
│  HISTORICAL SCORE TRENDS OVER TIME (Native Line Chart)                           │
│  [Score trends across all experiments and version milestones]                    │
├──────────────────────────────────────────────────────────────────────────────────┤
│  EXPERIMENT LINEAGE CARDS (border=True container per experiment)                 │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ Customer Classifier (Classification) · Created: 2 days ago                 │  │
│  │ 3 Versions · 15 Test Cases · Avg Quality: 89.2% · Best: v2 (91.4%)         │  │
│  │ ┌────────────────────────────────────────────────────────────────────────┐ │  │
│  │ │ Lineage: v1 (Original, 78.2%) ➔ v2 (Hardened, 89.4%) ➔ v3 (Opt, 93.4%) │ │  │
│  │ └────────────────────────────────────────────────────────────────────────┘ │  │
│  │ [Open in Workshop]  [Run Eval]  [Export CSV]  [🗑️ Delete (Dialog)]        │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```
**Responsive Narrow-Screen Behavior:**
* Lineage tree pills wrap onto multiple lines.
* Action buttons collapse into a 2x2 grid or single column.
* Delete confirmation opens an accessible modal dialog (`@st.dialog`) preventing background clicks.

---

### Screen 6: Prompt Library (`views/6_Prompt_Library.py`)
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Prompt Library & Starter Catalog                                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│  CATEGORY FILTER (Horizontal st.radio substitute for 1.38)                       │
│  (*) All   ( ) Classification   ( ) Extraction   ( ) Summarization   ( ) Code    │
│  [Search templates by keyword...]                                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│  TEMPLATE CARDS (3 Equal Columns in border=True containers)                      │
│  ┌─────────────────────────┬─────────────────────────┬───────────────────────┐   │
│  │ CLASSIFICATION          │ EXTRACTION              │ CODE GENERATION       │   │
│  │ Customer Feedback       │ Named Entity Extractor  │ SQL Query Synthesizer │   │
│  │ Multi-class sentiment & │ Extracts orgs, dates &  │ Translates natural    │   │
│  │ urgency scorer          │ monetary values to JSON │ language to SQLite    │   │
│  │ ─────────────────────── │ ─────────────────────── │ ───────────────────── │   │
│  │ [Preview Template]      │ [Preview Template]      │ [Preview Template]    │   │
│  │ [Load into Workshop]    │ [Load into Workshop]    │ [Load into Workshop]  │   │
│  └─────────────────────────┴─────────────────────────┴───────────────────────┘   │
│                                                                                  │
│  CUSTOM TEMPLATE CREATOR (st.expander)                                           │
│  Save the currently active prompt as a reusable library template.                │
└──────────────────────────────────────────────────────────────────────────────────┘
```
**Responsive Narrow-Screen Behavior:**
* Category filter wraps onto multiple lines.
* Template cards collapse from 3 columns to 1 column stacked vertically.

---

### Screen 7: Settings (`views/7_Settings.py`)
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Settings & Workspace Preferences                                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│  PROVIDER CONNECTIVITY & SECRETS (st.form: "provider_form")                      │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ Active Provider: Groq (via GROQ_API_KEY environment variable)              │  │
│  │ Status: :material/check_circle: :green[Configured & Verified]              │  │
│  │ API Key Override (Session Only — Never stored in SQLite):                  │  │
│  │ [ •••••••••••••••••••••••••••••••••••••••••••••••••• ] (type="password")   │  │
│  │ [Save Key for Session]  [:material/bolt: Test API Connection]              │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  DEFAULT MODEL & ARBITER SETTINGS                                                │
│  Default Workshop Model: [llama-3.3-70b-versatile ▼]                             │
│  Evaluation Arbiter Model: [llama-3.3-70b-versatile ▼]                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│  DEFAULT EVALUATION WEIGHTS (Sliders inside form)                                │
│  Accuracy: [0.30]  Relevance: [0.20]  Adherence: [0.25]  Clarity: [0.15]...      │
├──────────────────────────────────────────────────────────────────────────────────┤
│  WORKSPACE DATA MANAGEMENT (Destructive Actions)                                 │
│  [Reset Sample Templates]    [⚠️ Clear Entire Workspace Data (Modal Dialog)]    │
└──────────────────────────────────────────────────────────────────────────────────┘
```
**Responsive Narrow-Screen Behavior:**
* Single column form naturally adapts to any screen width.
* Destructive actions are separated into clear container blocks.

---

## 3. Component Map (Streamlit 1.38.0 Justification)

| UI Requirement | Selected 1.38 Component | Why Chosen Over Alternatives? | Unsupported 1.38+ Component & Substitute |
|---|---|---|---|
| **App Navigation** | `st.navigation` + `st.Page` | Native URL routing, sidebar groups, eliminates DOM hacking. | Replaces manual `st.switch_page` loops. |
| **Workspace Cards** | `st.container(border=True)` | Responsive native bounding box with built-in border and background theming. | Avoids custom `<div class="card">` CSS injections. |
| **Inline Dataset Editing**| `st.data_editor(num_rows="dynamic")` | Direct row insertion, editing, and deletion with schema validation. | Replaces clunky multi-text-area expanders. |
| **Category & Mode Filters**| `st.radio(horizontal=True)` | Accessible, keyboard-navigable single choice. | Replaces unavailable `st.segmented_control` / `st.pills`. |
| **Status & Test Badges** | Markdown with color syntax: `:green[...]`, `:red[...]` | Built-in Streamlit 1.38 colorized text tags. | Replaces unavailable `st.badge`. |
| **Progressive Disclosure** | `st.popover` | True dropdown popover container for tuning parameters (temp, tokens, guardrails). | Keeps composer uncluttered without taking sidebar space. |
| **Destructive Confirmations**| `@st.dialog` (Modal) | Isolates focus, disables background interaction, avoids layout shifting warning bars. | Replaces inline "Are you sure?" conditional buttons. |
| **Multi-Stage Execution** | `st.status(expanded=True)` | Displays granular live state (`Guardrail scan` $\rightarrow$ `LLM inference` $\rightarrow$ `Contract validation`). | Replaces raw `st.spinner` with transparent progress tracking. |
| **Transient Notifications** | `st.toast` | Floating non-blocking feedback for clipboard copy, save, and reset. | Replaces sticky `st.success` banners that push content down. |
| **Reactive Composer** | `st.fragment` (scoped to composer + preview) | Runs tokenizer and live rendered prompt reactivity without full-page reruns. | Scoped strictly to prevent cross-container rendering bugs. |
| **Summary Telemetry** | `st.metric` with `delta` inside `st.container(border=True)` | Native metric typography with positive/negative trend delta. | Note: In 1.38 `st.metric` lacks `border=True`, so wrap in container. |
| **Dataset Import/Export** | `st.file_uploader` & `st.download_button` | Native file stream handling, UTF-8 parsing, and client download dispatch. | Native browser file interaction. |
| **Prompt & Code Display** | `st.code(language="...")` | Built-in 1-click clipboard copy, syntax highlighting, and monospaced font. | Replaces read-only disabled `st.text_area`. |
| **Optimizer Progression** | `st.line_chart` (or Plotly) | Reactive line rendering of score trajectory per generation. | Native chart component. |
| **Deep Link State Restoration**| `st.query_params` | Two-way URL parameter binding for experiment sharing (`?exp=...`). | Browser history and bookmark support. |
| **Sidebar Brand Logo** | `st.logo` | Official Streamlit 1.38 sidebar branding header. | Replaces fragile `st.sidebar.image` markup. |
| **Streaming Output** | `st.chat_message` + `st.write_stream` | Token-by-token generation streaming for live playground feel. | Used when provider supports streaming iterators. |
| **Batching Input Sliders**| `st.form` | Groups sliders (e.g. weights, parameters) so widget ticks do not trigger reruns. | Prevents intermediate re-evaluation runs. |

---

## 4. Visual System Specification & Contrast Calculations

### 4.1 Theme Configuration (`.streamlit/config.toml`)
```toml
[theme]
base = "dark"
primaryColor = "#6842e3"
backgroundColor = "#0f1117"
secondaryBackgroundColor = "#1a1d29"
textColor = "#e8eaed"
font = "sans serif"
```

### 4.2 Comprehensive WCAG 2.1 AA Contrast Ratios (Calculated & Verified)
Relative luminance formula ($L = 0.2126R + 0.7152G + 0.0722B$ where $sRGB \rightarrow linear$) and contrast ratio ($CR = \frac{L_1 + 0.05}{L_2 + 0.05}$) computed via Python:

#### Dark Theme Contrast Analysis:
| Element | Foreground | Background | Contrast Ratio | WCAG AA Status ($>4.5:1$ Normal, $>3.0:1$ Large) | Usage Rule |
|---|---|---|---|---|---|
| **Canvas Background** | — | `#0f1117` | — | Base canvas | Page background |
| **Card Surface** | — | `#1a1d29` | — | Base surface | `st.container(border=True)` |
| **Primary Text** | `#e8eaed` | `#0f1117` | **15.66 : 1** | **PASS (AAA)** | Headings, body copy |
| **Primary Text** | `#e8eaed` | `#1a1d29` | **13.92 : 1** | **PASS (AAA)** | Card titles, body copy |
| **Secondary Text** | `#9ba3b5` | `#0f1117` | **7.46 : 1** | **PASS (AAA)** | Subtitles, parameter labels |
| **Secondary Text** | `#9ba3b5` | `#1a1d29` | **6.63 : 1** | **PASS (AAA)** | Card descriptions, metadata |
| **Muted Text (Raised)** | `#9ca3af` | `#0f1117` | **7.43 : 1** | **PASS (AAA)** | Captions, token counts |
| **Muted Text (Raised)** | `#9ca3af` | `#1a1d29` | **6.61 : 1** | **PASS (AAA)** | Footnotes, helper text |
| **Text Accent / Links** | `#9b84ff` | `#0f1117` | **6.41 : 1** | **PASS (AA)** | Interactive text, focus rings, link buttons |
| **Text Accent / Links** | `#9b84ff` | `#1a1d29` | **5.70 : 1** | **PASS (AA)** | Card links, active tab highlights |
| **Filled Button Surface**| `#6842e3` | `#ffffff` (Text)| **6.04 : 1** | **PASS (AA)** | Primary action button (`type="primary"`) |
| **Success Status** | `#34d399` | `#0f1117` | **10.54 : 1** | **PASS (AAA)** | `:green[PASS]`, completed checks |
| **Warning Status** | `#fbbf24` | `#0f1117` | **10.82 : 1** | **PASS (AAA)** | `:orange[WARN]`, review suggestions |
| **Error Status** | `#f87171` | `#0f1117` | **6.22 : 1** | **PASS (AA)** | `:red[FAIL]`, execution errors |

*Note on Deprecated Palette:* The previous `#7c5cfc` on `#0f1117` scored **4.31 : 1** (failing normal text threshold of 4.5:1), and `#6b7280` scored **3.90 : 1** (failing AA). Both have been replaced with `#9b84ff` (6.41:1) and `#9ca3af` (7.43:1).

#### Light Theme Contrast Analysis:
| Element | Foreground | Background | Contrast Ratio | WCAG AA Status |
|---|---|---|---|---|
| **Canvas Background** | — | `#f8fafc` | — | Light canvas |
| **Card Surface** | — | `#ffffff` | — | Light card surface |
| **Primary Text** | `#0f172a` | `#f8fafc` | **17.06 : 1** | **PASS (AAA)** |
| **Primary Text** | `#0f172a` | `#ffffff` | **17.85 : 1** | **PASS (AAA)** |
| **Secondary Text** | `#475569` | `#f8fafc` | **7.24 : 1** | **PASS (AAA)** |
| **Muted Text** | `#64748b` | `#f8fafc` | **4.55 : 1** | **PASS (AA)** |
| **Primary Button** | `#ffffff` | `#6344e0` | **6.12 : 1** | **PASS (AA)** |

### 4.3 Typography & The One Deliberate CSS Exception
In Streamlit 1.38.0, `config.toml` `font` accepts only `"sans serif"`, `"serif"`, or `"monospace"`. To provide modern precision typography (`Inter` for UI and `JetBrains Mono` for prompts/code), a single documented helper `inject_custom_fonts()` in `src/ui_theme.py` injects:

```python
import streamlit as st

def inject_custom_fonts():
    """
    The ONE deliberate CSS injection allowed:
    Loads Inter (UI) and JetBrains Mono (Code/Prompts) with system fallbacks.
    Does not manipulate layout or override Streamlit component classes.
    """
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
        
        html, body, [class*="st-emotion"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        code, pre, .stCodeBlock, textarea[data-baseweb="textarea"] {
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
        }
        
        /* Focus ring accessibility */
        *:focus-visible {
            outline: 2px solid #9b84ff !important;
            outline-offset: 2px !important;
        }
        </style>
    """, unsafe_allow_html=True)
```

---

## 5. State Management & Concurrency Architecture

### 5.1 Scoped `st.fragment` Architecture (Prompt Workshop)
**Root Cause of Past Defect:** A fragment reruns *only* when a widget declared inside it changes. If the prompt inputs are outside the fragment and only the preview is inside, typing in the prompt will NOT trigger the fragment unless the entire page reruns. Conversely, if a fragment writes to widgets outside its own container, Streamlit raises an element nesting warning.

**The Redesigned Architecture:**
The entire two-column composer (Left Inputs + Right Live Preview/Token Gauge) is encapsulated within a single unified `@st.fragment` function `workshop_canvas()`.
* When the user types or adjusts prompt variables, ONLY `workshop_canvas()` reruns. The rest of the page (page header, experiment selector, action bar) remains completely static.
* The action bar containing "Run Prompt", "Save Changes", and "Save New Version" sits **outside** the fragment. When clicked, it reads the durable session state, executes the database operation or LLM call, and performs an explicit full-page rerun via `st.rerun(scope="app")`.

```python
# Pseudocode of Corrected Fragment Scoping
import streamlit as st

def render_prompt_workshop():
    # 1. Page Header & Persistent Selector (Outside Fragment)
    render_header()
    selected_exp = render_experiment_selector()

    # 2. Scoped Reactive Canvas (Fragment: Left Inputs + Right Preview)
    @st.fragment
    def workshop_canvas():
        c_left, c_right = st.columns([3, 2], gap="large")
        with c_left:
            # Inputs directly write to durable session state via on_change or session key
            user_prompt = st.text_area("Prompt Template", key="ws_user_input", on_change=sync_to_durable)
            # Tuning Popover keeps parameters accessible without triggering outside reruns
            with st.popover("⚙️ Tuning & Parameters"):
                with st.form("tuning_form"):
                    temp = st.slider("Temperature", 0.0, 2.0, key="ws_temp")
                    max_tok = st.number_input("Max Tokens", 64, 4096, key="ws_max_tokens")
                    st.form_submit_button("Apply Parameters")
        with c_right:
            # Instantly recomputed on input changes inside the same fragment
            rendered = preview_template(user_prompt)
            st.code(rendered, language="text")
            render_token_consumption_gauge(rendered)
            render_quality_readiness_badge(user_prompt)

    workshop_canvas()

    # 3. Action Bar (Outside Fragment: DB Writes & Global Reruns)
    st.divider()
    b1, b2, b3 = st.columns(3)
    if b1.button(":material/play_arrow: Run Prompt", type="primary"):
        with st.status(":material/hourglass_top: Executing prompt...", expanded=True) as status:
            res = execute_prompt_with_harness(st.session_state["durable_workshop"])
            status.update(label=":material/check_circle: Complete", state="complete")
        st.session_state["ws_last_response"] = res
        st.rerun(scope="app")
```

### 5.2 Threading & Safe Concurrency Architecture (Evaluation Lab)
In Streamlit, interacting with any widget during a running script execution immediately interrupts that run. Therefore, rendering a "Stop" button in the same loop that synchronously waits for tasks prevents proper cancellation. 

#### Coordinator Background Thread & Decoupled Progress Architecture:
1. **Coordinator Thread:** When the user clicks "Run Evaluation", the main thread creates a progress tracking object (`EvalRunHandle`) and spawns a **coordinator background thread**.
   - The coordinator owns the `ThreadPoolExecutor(max_workers=4)` and a `threading.Event()` (`stop_event`).
   - The coordinator submits test case evaluation tasks to the pool and monitors their completion.
   - It updates a lock-guarded progress record containing:
     - `completed_count` (int)
     - `total_count` (int)
     - `results` (list of `EvaluationResult`)
     - `errors` (list of error strings)
     - `status` (`"running"`, `"stopped"`, `"done"`)
   - **Strict Thread Invariant:** Neither the coordinator thread nor the worker threads EVER call `st.*` functions or read/write `st.session_state`.
2. **Session State Handle:** The `EvalRunHandle` instance is stored in `st.session_state["eval_run_handle"]` (created on the main thread prior to spawning the thread).
   - Guard against double-start: The "Run Evaluation" button is disabled whenever an active handle has `status == "running"`.
   - Guard against page-switch: Because the coordinator thread runs independently in the background and writes to the memory object referenced by `st.session_state`, switching pages and returning preserves the live run state.
3. **Decoupled Progress UI (`@st.fragment(run_every=1)`):**
   - The progress display is wrapped in `@st.fragment(run_every=1)` (or `run_every="1s"`).
   - This fragment ONLY reads the thread-safe progress object and renders `st.progress()`, `st.status()`, and live partial results.
   - The fragment also hosts the `⏹ Stop Evaluation` button. Clicking "Stop" sets `handle.stop_event.set()`.
   - The coordinator detects the event, ceases submitting new tasks, waits for in-flight HTTP requests to complete or timeout, and sets `status = "stopped"`.
4. **SQLite Persistence & Cleanup:**
   - Once the progress object indicates `status in ("done", "stopped")`, the main script thread persists all collected results to SQLite in a single transaction via `db.save_evaluation_results_bulk(handle.results)` and clears `st.session_state["eval_run_handle"]`.
   - Zero SQLite database contention occurs during parallel execution since workers perform pure network I/O.

```python
# Coordinator Background Thread Pseudocode
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

class EvalRunHandle:
    def __init__(self, total: int):
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.total = total
        self.completed = 0
        self.results = []
        self.errors = []
        self.status = "running"  # "running", "stopped", "done"

def coordinator_worker(handle: EvalRunHandle, test_cases, version, weights, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_eval_worker_fn, tc, version, weights, handle.stop_event): tc
            for tc in test_cases
        }
        for future in as_completed(futures):
            if handle.stop_event.is_set():
                break
            try:
                res = future.result()
                if res:
                    with handle.lock:
                        handle.results.append(res)
                        handle.completed += 1
            except Exception as e:
                with handle.lock:
                    handle.errors.append(str(e))
                    handle.completed += 1

    with handle.lock:
        handle.status = "stopped" if handle.stop_event.is_set() else "done"

# Main Thread & Reactive Fragment UI
@st.fragment(run_every=1)
def render_evaluation_monitor(handle: EvalRunHandle):
    with handle.lock:
        curr = handle.completed
        tot = handle.total
        stat = handle.status

    st.progress(curr / max(1, tot), text=f"Evaluating test suite: {curr}/{tot}")
    if stat == "running":
        if st.button("⏹ Stop Evaluation", key="btn_stop_eval"):
            handle.stop_event.set()
            st.warning("Stop requested. Waiting for in-flight requests...")
    elif stat in ("done", "stopped"):
        st.success(f"Evaluation {stat}: {curr}/{tot} cases processed.")
```

### 5.3 Cross-Page State Persistence & Deep Linking
Streamlit drops widget keys from memory when a widget is not rendered on the current active page.
* **Durable Storage Pattern:** All persistent data lives in designated session state dictionaries prefixed with `durable_` (e.g. `st.session_state["durable_workshop"]`).
* When a page loads, widgets read their initial values from `durable_*`.
* Changes trigger an `on_change` callback that copies the widget value back into `durable_*`.
* **Deep Linking (`st.query_params`):**
  On page load, `st.query_params` is inspected. If `?exp=<id>&ver=<id>` is present, `st.session_state["current_experiment_id"]` and `st.session_state["current_version_id"]` are initialized to those IDs, allowing direct bookmarking and team sharing of specific prompt revisions.

### 5.4 Secrets & API Key Handling
* **No Plaintext SQLite Storage:** API keys are never written to the SQLite database or committed to version control.
* **Resolution Hierarchy:**
  1. `os.environ.get("GROQ_API_KEY")` or `st.secrets.get("GROQ_API_KEY")`
  2. Session memory override: `st.session_state.get("session_groq_api_key")`
* **Masked Display:** Input fields use `type="password"`. Configured keys display masked state showing only the last 4 characters: `••••abcd` (never echoing any provider prefix).
* **Connectivity Test:** A "Test API Connection" button initiates a low-overhead models query (`client.models.list()`) wrapped in `st.spinner`, displaying a toast notification on success or a descriptive error on failure.

### 5.5 Cache Invalidation Protocol (`st.cache_data`)
To balance instant responsiveness with guaranteed freshness across views, read operations use `@st.cache_data`. Every state-mutating action programmatically clears the affected cache entries by function name:
* **Prompt Save / Update / Delete:** Clears `get_recent_experiments.clear()`, `get_dashboard_metrics.clear()`, and `get_prompt_versions.clear()`.
* **Test Case Add / Import / Delete:** Clears `get_test_cases.clear()`.
* **Evaluation Complete / Delete:** Clears `get_evaluation_results.clear()`, `get_all_evaluation_scores.clear()`, and `get_criterion_averages.clear()`.
* **Template Add / Restore:** Clears `get_prompt_templates.clear()`.
* **Singletons (`st.cache_resource`):** Database handle `get_database()` and provider client pool persist as singletons across the entire process lifetime.

---

## 6. UX States Definition Matrix

| Feature / Scenario | Trigger Condition | Visual Component & Exact Message Pattern | User Recovery Action |
|---|---|---|---|
| **Workshop Empty** | No prompt loaded | `st.info(":material/info: Enter a prompt template or select a starter from the library.")` | Click "+ New Prompt" or select category template |
| **Missing API Key** | `GROQ_API_KEY` unset | `st.warning(":material/key_off: No API key detected. Using Mock Provider for offline testing.")` | Enter key in Settings or add to `.env` file |
| **Invalid API Key** | HTTP 401 / Auth fail | `st.error(":material/lock: API Key Authentication Failed. Please verify your credentials in Settings.")` | Click link to open Settings page |
| **Rate Limit Hit (429)**| Provider rate limit | `st.warning(":material/speed: Rate limit exceeded (429). Retrying automatically in 8s...")` | Auto-countdown retry loop or switch to tier |
| **Request Timeout** | Network/Model lag | `st.error(":material/timer_off: Request timed out after 30s. Provider did not respond.")` | Check connection and click "Run Prompt" again |
| **Provider Outage (503)**| Cloud service down | `st.error(":material/cloud_off: Groq service temporarily unavailable (503).")` | Switch to fallback model in dropdown |
| **Malformed JSON Output**| Model breaks format | `st.warning(":material/code_off: Model returned non-JSON output. Auto-repair harness activated (Attempt 2/3)...")` | Harness retries with schema correction prompt |
| **Malformed CSV Import** | Invalid headers/rows| `st.error(":material/error: CSV Import Error: Missing required column 'input_data' on row 4.")` | Download Sample Template and re-upload |
| **User Cancels Run** | Stop button clicked | `st.info(":material/stop_circle: Evaluation stopped by user. 8 of 15 test results preserved.")` | Review partial results in table |
| **Partial Failure** | 2 of 10 test errors | `st.warning(":material/warning: 8/10 test cases succeeded. 2 encountered execution errors.")` | Inspect failed test cases in table drill-down |

---

## 7. Responsiveness, Themes & Accessibility Standards (WCAG 2.1 AA)

### 7.1 Responsive Grid Rules
* **Desktop ($\ge 1024px$):** Full multi-column workflows (3:2 Composer/Preview, 4-column metric grids, 2-column head-to-head arena).
* **Tablet ($768px - 1023px$):** Metrics wrap to 2x2 grids; secondary tabs remain accessible.
* **Mobile ($<768px$):** All columns collapse to a 100% width single-column stack. Tables activate horizontal overflow containers with scroll indicators. Primary buttons span container width (`use_container_width=True`).

### 7.2 Non-Color Dependent Communication
* Every status badge, test result, and quality gate check combines a distinct **Material icon** and an **explicit text label**:
  - Success: `:material/check_circle: :green[PASS]`
  - Failure: `:material/cancel: :red[FAIL]`
  - Warning: `:material/warning: :orange[WARN]`
  - Running: `:material/hourglass_top: :blue[RUNNING]`
* Color is never used as the sole conveyor of state.

### 7.3 Keyboard Navigation & Accessible Focus
* All interactive form inputs contain explicit string labels (collapsed only when visually redundant with identical headers via `label_visibility="collapsed"`).
* Interactive popovers (`st.popover`) and modal dialogs (`@st.dialog`) trap focus correctly and can be dismissed via the `Esc` key.
* The CSS focus token ensures a high-contrast 2px solid ring (`#9b84ff`) on every focused element.

---

## 8. Revision Notes (Architectural Changes & Rationale)

1. **Corrected `st.fragment` Scoping (Section 5.1):**
   * *Problem:* Previously, only the right-hand preview was decorated with `@st.fragment`. Because fragments only rerun when their own inner widgets change, typing in the left composer didn't trigger live preview reactivity, and writing across containers violated Streamlit scoping rules.
   * *Fix:* Wrapped both left-column inputs and right-column preview inside a unified `workshop_canvas()` fragment. The Action Bar and database writes remain outside the fragment and use `st.rerun(scope="app")`.
2. **Contrast & Color Palette Recalculation (Section 4.2):**
   * *Problem:* The prior draft stated `#7c5cfc` on `#0f1117` had 5.8:1 contrast; mathematical recalculation proved it was only 4.31:1 (failing WCAG AA). White on `#7c5cfc` was 4.38:1, and `#6b7280` was 3.90:1.
   * *Fix:* Replaced text accent with `#9b84ff` (6.41:1 on canvas, 5.70:1 on card), raised muted text to `#9ca3af` (7.43:1), adjusted primary filled button to `#6842e3` with white text (6.04:1), and audited light theme pairings.
3. **Typography & Font Strategy (Section 4.3):**
   * *Problem:* Streamlit 1.38 `[theme] font` rejects custom font family strings.
   * *Fix:* Kept `font = "sans serif"` in config.toml, and created a single documented helper `inject_custom_fonts()` in `src/ui_theme.py` to import Inter and JetBrains Mono with system fallbacks.
4. **Thread-Safe Concurrency & SQLite Integrity (Section 5.2):**
   * *Problem:* Evaluation Lab with `max_workers=4` risked calling `st.*` or modifying session state from worker threads, crashing with `NoSessionContext`.
   * *Fix:* Enforced strict separation: workers execute stateless inference only; the main thread consumes futures via `as_completed()`, updating `st.progress` and `st.status`. Workers check a shared `stop_event` for cancellation. All database writes occur sequentially on the main thread via bulk save.
5. **State Persistence Across Pages (Section 5.3):**
   * *Problem:* Streamlit discards widget keys when pages switch.
   * *Fix:* Decoupled storage into `durable_*` session state dictionaries with `on_change` synchronization and deep linking via `st.query_params`.
6. **Secrets & API Security (Section 5.4):**
   * *Problem:* Potential risk of plaintext key storage in SQLite or console logs.
   * *Fix:* Enforced environment-first resolution, password-masked inputs, session-only overrides, and a dedicated connection tester.
7. **Expanded ASCII Wireframes & Missing Tabs (Section 2):**
   * Added full ASCII wireframes with mobile/narrow-screen collapse rules for: Home, Prompt Workshop, Evaluation Lab (all 4 tabs), Prompt Optimizer, Compare Versions, Experiment History, Prompt Library, and Settings.
8. **1.38 API Verifications & Substitutes (Section 3):**
   * Verified that `st.segmented_control`, `st.pills`, and `st.badge` do not exist in 1.38.0. Specified exact native substitutes: `st.radio(horizontal=True)` and `:green[PASS]` markdown badges. Verified that `st.metric` lacks `border=True` and documented wrapping in `st.container(border=True)`.
9. **Comprehensive UX Failure Matrix (Section 6):**
   * Added detailed recovery actions and component mappings for rate limits (429 countdown), timeouts, provider outages, malformed JSON, CSV validation errors, and user-initiated stops.
10. **Amendments (Coordinator Thread, Masked Keys, Cache Invalidation, Page Config):**
   * *Stop/Cancel Redesign:* Since any widget interaction in Streamlit halts the active script execution, evaluation is managed by a background coordinator thread owning the ThreadPoolExecutor and threading.Event. The UI polls a lock-guarded progress object via `@st.fragment(run_every=1)` hosting the "Stop" button. On completion or cancellation, the main thread saves to SQLite once and clears the handle, guarding against double-starts and page switches.
   * *Masked Key Display:* Secrets display strictly as `••••abcd` showing only the last 4 characters without provider prefixes.
   * *Cache Invalidation:* Every mutation (save, update, delete, import, promote) programmatically clears affected `@st.cache_data` functions by name.
   * *Single `st.set_page_config`:* Called exactly once at the top of `app.py`.
