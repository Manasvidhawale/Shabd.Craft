# Shabd.Craft — Intelligent Prompt Engineering & Optimization Platform

> **"Craft Better Prompts. Measure Better Intelligence."**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38-red)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen)](#testing)

---

## 📌 Overview

**Shabd.Craft** is a professional-grade, web-based Prompt Engineering platform that helps AI practitioners systematically design, test, evaluate, compare, and optimize prompts for Large Language Models.

From raw instructions to tested intelligence — Shabd.Craft treats prompts as engineering artifacts, not guesswork. Every prompt version is evaluated with measurable criteria, every optimization candidate is tested before being recommended, and every experiment is persisted for review.

---

## 🎯 Problem Statement

Prompt engineering is widely practiced but rarely systematic. Most practitioners:

- Write prompts intuitively without measurable baselines.
- Have no way to compare two prompt versions on identical test cases.
- Cannot tell whether a "better-sounding" prompt actually performs better.
- Lose experimental history between sessions.
- Have no tooling for iterative, evidence-based prompt improvement.

**Shabd.Craft** solves this by treating prompts as software: versioned, evaluated, compared, and optimized with repeatable methodology.

---

## 🔑 Key Features

| Feature | Description |
|---|---|
| **Prompt Workshop** | Reactive IDE-like canvas with live token meter, cost estimation, 7 techniques & production SDK code export |
| **Evaluation Lab** | Multi-worker background coordinator thread, Stop/Cancel support, rubric evaluator & adversarial security audit |
| **Prompt Optimizer** | Autonomous generational hill-climbing mutations & 1-shot candidate generation with benchmark tracking |
| **Version Comparison** | Inline word-level HTML diff, side-by-side outputs, and Multi-Model Arena with position-swap AI referee |
| **Runtime Harness** | Self-repairing contract enforcement with reflection loops and CI/CD quality gate CLI |
| **Guardrails** | Input/output PII redaction, prompt injection neutralization, and system prompt leakage filters |
| **Experiment History** | SQLite-backed persistent experiment lineage, duplication, and bulk JSON/CSV exports |
| **Prompt Library** | 9 built-in starter templates + user custom template repository |
| **Universal Connectivity** | Native support for OpenAI models, Groq endpoints, custom base URLs, or offline simulated demo mode |

---

## 🛠 Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Frontend | Streamlit 1.38 |
| LLM Integration | OpenAI API (official SDK) |
| Data Validation | Pydantic 2.9 |
| Data Processing | Pandas 2.2 |
| Visualization | Plotly 5.24 |
| Persistence | SQLite (built-in) |
| Configuration | python-dotenv |
| Testing | pytest 8.3 + pytest-mock |

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit UI                       │
│  app.py (Navigation Shell) + views/ (8 views)       │
└────────────────────┬────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   Application Layer    │
         │  experiment_service.py │
         │  export_service.py     │
         └───────────┬───────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
┌──────────┐  ┌───────────┐  ┌─────────────┐
│  Prompt  │  │ Evaluation │  │  Optimizer  │
│  Engine  │  │  Engine   │  │             │
│          │  │           │  │             │
│template_ │  │rule_based_│  │ optimizer.py│
│engine.py │  │evaluator  │  │             │
│prompt_   │  │llm_judge  │  │             │
│engine.py │  │security_  │  │comparison_  │
│          │  │evaluator  │  │engine.py    │
└────┬─────┘  └─────┬─────┘  └──────┬──────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
         ┌───────────▼───────────┐
         │    Provider Layer      │
         │  base.py               │
         │  openai_provider.py    │
         │  demo_provider.py      │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │    Persistence Layer   │
         │  database.py (SQLite)  │
         │  schemas.py (Pydantic) │
         └───────────────────────┘
```

---

## 📁 Project Structure

```
Shabd.Craft/
├── app.py                          # Main entry point + dashboard
├── requirements.txt
├── .env.example
├── .gitignore
├── pytest.ini
├── README.md
│
├── views/
│   ├── 0_Home.py                   # Overview dashboard & workflow guide
│   ├── 1_Prompt_Workshop.py        # Prompt creation, execution & code export
│   ├── 2_Evaluation_Lab.py         # Batch evaluation & security audit
│   ├── 3_Prompt_Optimizer.py       # AI-powered optimization
│   ├── 4_Compare_Versions.py       # Inline diff & side-by-side comparison
│   ├── 5_Experiment_History.py     # Persistent history
│   ├── 6_Prompt_Library.py         # Template library
│   └── 7_Settings.py               # Configuration
│
├── src/
│   ├── config.py                   # Settings, Groq detection & environment
│   ├── schemas.py                  # Pydantic data models & validators
│   ├── database.py                 # SQLite persistence layer & transactions
│   ├── prompt_engine.py            # Prompt construction & provider execution
│   ├── template_engine.py          # {{variable}} extraction & substitution
│   ├── evaluation_engine.py        # Evaluation orchestration & aggregation
│   ├── rule_based_evaluator.py     # Deterministic evaluation checks
│   ├── llm_judge.py                # LLM-as-a-Judge & position-swap referee
│   ├── security_evaluator.py       # Prompt injection & defense audit suite
│   ├── guardrails.py               # Input/output PII, injection & leak filters
│   ├── harness.py                  # Runtime auto-repair & CI quality gate CLI
│   ├── test_synthesizer.py         # Multi-column CSV mapping & case synthesis
│   ├── ui_helpers.py               # Shared UI state & header helpers
│   ├── ui_theme.py                 # Central WCAG AA tokens, fonts & focus rings
│   ├── optimizer.py                # Autonomous hill-climbing & candidates
│   ├── comparison_engine.py        # Version comparison & HTML word diff
│   ├── experiment_service.py       # Experiment lifecycle & duplication
│   ├── export_service.py           # Production SDK code generation & exports
│   └── providers/
│       ├── base.py                 # Abstract provider interface
│       ├── openai_provider.py      # OpenAI & Groq API integration
│       └── demo_provider.py        # Offline simulated provider
│
├── data/
│   ├── sample_prompts.json         # 9 built-in prompt templates
│   └── sample_test_cases.json      # Sample test dataset
│
├── tests/
│   ├── test_prompt_engine.py       # Template & prompt construction
│   ├── test_evaluation.py          # Evaluation engine & rule-based
│   ├── test_security_evaluator.py  # Prompt injection & hardening checks
│   ├── test_guardrails.py          # PII redaction, injection & leak guardrails
│   ├── test_harness.py             # Auto-repair harness, quality gate & CLI
│   ├── test_comparison_engine.py   # Version comparison & word diff
│   ├── test_export_service.py      # Production code generation
│   ├── test_optimizer.py           # Optimizer candidates & recommendation
│   ├── test_database.py            # SQLite persistence
│   └── test_schemas.py             # Pydantic schema validation
│
└── docs/
    ├── architecture.md             # Detailed architecture guide
    ├── evaluation_methodology.md   # Evaluation design & limitations
    └── future_agentic_extension.md # LangGraph upgrade path
```

---

## ⚡ Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/your-username/shabd-craft.git
cd shabd-craft
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your-key-here
```

### 5. Run the application

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## 🎭 Demo Mode

Shabd.Craft works completely without an API key in **Demo Mode**.

- All prompts execute with clearly labeled `[DEMO]` responses.
- Evaluation scores are deterministic and reproducible.
- Optimizer candidates are rule-based (not AI-generated).
- All UI features, experiment persistence, and exports work normally.

To force demo mode even with an API key:

```
SHABDCRAFT_DEMO_MODE=true
```

Demo outputs are clearly labeled throughout the UI. They are never presented as real LLM responses.

---

## 🔧 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required for live mode)* | OpenAI API key |
| `SHABDCRAFT_DEFAULT_MODEL` | `gpt-3.5-turbo` | Default model |
| `SHABDCRAFT_DEMO_MODE` | `false` | Force demo mode |
| `SHABDCRAFT_DB_PATH` | `data/shabdcraft.db` | SQLite database path |
| `SHABDCRAFT_MAX_TEST_CASES` | `50` | Max test cases per experiment |
| `SHABDCRAFT_MAX_OPTIMIZATION_ROUNDS` | `5` | Max optimizer rounds |
| `SHABDCRAFT_MAX_RETRIES` | `3` | API call retry limit |
| `SHABDCRAFT_TIMEOUT` | `60` | Request timeout (seconds) |

---

## 🧪 Testing

```bash
# Run all tests
py -m pytest tests/ -v

# Run with deprecation warnings as errors (clean run)
py -m pytest tests/ -v -W error::DeprecationWarning

# Run specific test file
py -m pytest tests/test_evaluation.py -v

# Run CLI regression harness gate for an experiment
python -m src.harness --experiment "My Experiment" --min-score 75 --min-security 80
```

**Test coverage (177 tests passing):**

| Test File | Tests | Covers |
|---|---|---|
| `test_prompt_engine.py` | 25 | Template engine, 7 prompting techniques, variables & Groq detection |
| `test_evaluation.py` | 22 | Multi-criteria weights, scoring, rule-based checks, position bias & verbosity |
| `test_schemas.py` | 36 | All Pydantic data schemas, enums, validators and serialization |
| `test_database.py` | 20 | All SQLite CRUD operations, version deletion & dependencies cleanup |
| `test_optimizer.py` | 17 | Autonomous generational hill-climbing mutations & recommendations |
| `test_guardrails.py` | 14 | Input/output PII redaction, prompt injection & system leak filters |
| `test_harness.py` | 13 | Input sanitization, auto-repair retry reflection, quality gate & CLI |
| `test_ui_smoke.py` | 10 | Streamlit AppTest across all 8 views + app.py entrypoint + Python 3.11 AST validation |
| `test_security_evaluator.py` | 9 | Multi-vector prompt injection attacks, static posture & hardening |
| `test_comparison_engine.py` | 4 | Version comparison, HTML word-level diffing & arena battles |
| `test_synthesizer.py` | 4 | Multi-column CSV variable packing and test case synthesis |
| `test_export_service.py` | 3 | Production SDK code generation (OpenAI Python, LangChain, cURL) |

All tests run **without network access or API keys** (LLM calls are mocked).

---

## 🔬 Prompt Engineering Techniques

| Technique | When to use |
|---|---|
| **Zero-Shot** | Straightforward tasks with strong model priors |
| **One-Shot** | When a single example clarifies the output format |
| **Few-Shot** | Complex tasks requiring consistent formatting |
| **Role-Based** | Domain-specific tasks needing expert framing |
| **Structured Output** | When downstream systems need parseable JSON |
| **Task Decomposition** | Multi-step tasks broken into sequential subtasks |
| **Chain-of-Thought (CoT)** | Reasoning tasks requiring explicit step-by-step thinking |

---

## 📊 Evaluation Methodology

### Rule-Based Evaluation (Deterministic)

- JSON validity and field presence
- Required keyword detection
- Word-count compliance
- Empty response detection
- Exact match when reference answers are available

### LLM-as-a-Judge (Rubric-Based)

Uses a separate LLM call with an explicit 5-criterion rubric:

| Criterion | Default Weight |
|---|---|
| Accuracy | 25% |
| Relevance | 20% |
| Instruction Adherence | 25% |
| Clarity | 15% |
| Format Compliance | 15% |

**Overall Score** = Σ (Criterion Score × Normalized Weight)

> ⚠️ LLM-as-a-Judge scores can vary between runs and should not be treated as objective ground truth. Always evaluate on consistent test cases with consistent weights.

See [`docs/evaluation_methodology.md`](docs/evaluation_methodology.md) for full methodology details.

---

## 🚀 Supported Models

| Model | Input Cost (per 1K tokens) | Output Cost |
|---|---|---|
| gpt-3.5-turbo | $0.0005 | $0.0015 |
| gpt-4 | $0.030 | $0.060 |
| gpt-4-turbo | $0.010 | $0.030 |
| gpt-4o | $0.005 | $0.015 |
| gpt-4o-mini | $0.000150 | $0.000600 |

*Pricing is approximate and for estimation purposes only.*

---

## ⚠️ Known Limitations & Boundaries

1. **Single-user architecture** — Local embedded persistence without multi-tenant authentication.
2. **Provider Scope** — Native live execution supports OpenAI models, Groq API, and compatible OpenAI-spec endpoints (Ollama, vLLM, LiteLLM). Anthropic and Gemini require proxy routing or export code.
3. **LLM Judge Variance** — Evaluation scores can naturally vary between runs due to model non-determinism (mitigated via temperature=0 and position-swap bias detection).
4. **Demo Mode Simulation** — Offline demo scores are deterministic approximations for evaluation without live API keys.

---

## 🔮 Future Enhancements

1. **Multi-agent orchestration** via LangGraph (see `docs/future_agentic_extension.md`)
2. **Multi-provider support** — Anthropic Claude, Google Gemini, Mistral
3. **Async batch evaluation** — Non-blocking parallel test case execution
4. **User authentication** — Multi-user support with isolated workspaces
5. **Automated A/B testing** — Statistical significance testing for prompt comparisons
6. **Semantic similarity scoring** — Using embedding models for relevance evaluation
7. **Prompt versioning diffs** — Visual word-level diff between prompt versions
8. **CI/CD integration** — Programmatic evaluation via REST API

---

## 📸 Suggested Screenshots

After running the app, capture:

1. **Dashboard** — With experiments showing metrics and charts
2. **Prompt Workshop** — A prompt being composed with live preview
3. **Evaluation Lab** — Results table with criterion scores
4. **Prompt Optimizer** — Three candidates with comparison
5. **Compare Versions** — Grouped bar chart and side-by-side outputs
6. **Prompt Library** — Template cards grid

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

Built with [Streamlit](https://streamlit.io), [OpenAI Python SDK](https://github.com/openai/openai-python), [Pydantic](https://pydantic.dev), and [Plotly](https://plotly.com).
