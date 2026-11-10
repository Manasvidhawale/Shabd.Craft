# Shabd.Craft — System Architecture

## Overview

Shabd.Craft is designed with strict separation of concerns between the UI, business logic, provider integration, and persistence layers. This makes individual components testable, replaceable, and extensible.

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                    │
│                                                         │
│  app.py (Unified Home Dashboard & Workflow Guide)       │
│  pages/1_Prompt_Workshop    pages/5_Experiment_History  │
│  pages/2_Evaluation_Lab     pages/6_Prompt_Library      │
│  pages/3_Prompt_Optimizer   pages/7_Settings            │
│  pages/4_Compare_Versions                               │
│                                                         │
│  Technology: Streamlit + Plotly + Custom CSS            │
└────────────────────────┬────────────────────────────────┘
                         │ reads/writes session state
                         │ calls service functions
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                         │
│                                                         │
│  experiment_service.py   — experiment lifecycle         │
│  export_service.py       — CSV/JSON import & export     │
│  comparison_engine.py    — version comparison           │
│                                                         │
│  Technology: Python, Pydantic                           │
└────────────────────────┬────────────────────────────────┘
                         │
           ┌─────────────┼──────────────┐
           ▼             ▼              ▼
┌──────────────┐  ┌───────────┐  ┌───────────────┐
│ PROMPT LAYER │  │ EVAL LAYER│  │ OPTIM LAYER   │
│              │  │           │  │               │
│ prompt_      │  │evaluation_│  │ optimizer.py  │
│ engine.py    │  │engine.py  │  │               │
│              │  │           │  │               │
│ template_    │  │rule_based_│  │               │
│ engine.py    │  │evaluator  │  │               │
│              │  │           │  │               │
│              │  │llm_judge  │  │               │
│              │  │security_  │  │               │
│              │  │evaluator  │  │               │
└──────┬───────┘  └─────┬─────┘  └───────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   PROVIDER LAYER                         │
│                                                         │
│  providers/base.py           — abstract interface       │
│  providers/openai_provider   — real OpenAI API          │
│  providers/demo_provider     — deterministic demo       │
│                                                         │
│  Technology: openai SDK, Python                         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  PERSISTENCE LAYER                       │
│                                                         │
│  database.py   — SQLite manager (WAL mode, FK support)  │
│  schemas.py    — Pydantic models for all entities        │
│  config.py     — Environment variable management         │
│                                                         │
│  Technology: sqlite3 (stdlib), Pydantic, python-dotenv  │
└─────────────────────────────────────────────────────────┘
```

## Data Flow: Prompt Execution

```
User Input (Streamlit)
    │
    ▼
validate_template() — checks {{variable}} syntax
    │
    ▼
render_template() — substitutes variables safely
    │
    ▼
construct_prompt() — applies technique (zero-shot, few-shot, etc.)
    │
    ▼
provider.generate() — calls OpenAI or Demo provider
    │
    ▼
LLMResponse — content, tokens, latency, cost
    │
    ▼
db.save_evaluation_result() — persists result
    │
    ▼
Streamlit displays response
```

## Data Flow: Evaluation

```
Test Cases (from DB or upload)
    │
    ▼
evaluate_batch() — iterates test cases
    │
    ├──► execute_prompt() — runs the prompt
    │
    ├──► evaluate_rule_based() — deterministic checks
    │        │ JSON validity
    │        │ keyword presence
    │        │ word count
    │        │ exact match
    │
    ├──► evaluate_with_llm_judge() — rubric-based scoring
    │        │ 5-criterion evaluation
    │        │ Pydantic-validated JSON response
    │        │ bounded retries
    │
    ├──► calculate_weighted_score() — normalized weights
    │
    └──► EvaluationResult saved to SQLite
```

## Database Schema

```
experiments
  id, name, category, description, status, created_at, updated_at

prompt_versions
  id, experiment_id→, version_number, version_label,
  system_prompt, user_prompt_template, technique,
  few_shot_examples (JSON), output_format, variables (JSON),
  model_name, temperature, max_tokens, is_optimized,
  optimization_strategy, created_at

test_cases
  id, experiment_id→, input_data, expected_output,
  metadata (JSON)

evaluation_results
  id, test_case_id→, prompt_version_id→, experiment_id→,
  generated_output, criterion_scores (JSON), overall_score,
  weaknesses (JSON), suggestions (JSON), evaluation_method,
  is_reference_verified, execution_status, error_message,
  latency_ms, tokens_used, cost_estimate, is_demo, created_at

optimization_candidates
  id, experiment_id→, original_version_id→, candidate_label,
  strategy, system_prompt, user_prompt_template,
  changes_description, rationale, status, overall_score,
  is_accepted, created_at

prompt_library
  id, name, description, category, system_prompt,
  user_prompt_template, variables (JSON), technique,
  few_shot_examples (JSON), output_format, example_input,
  example_output, eval_criteria (JSON), is_builtin,
  created_at, updated_at
```

## Design Decisions

### Why SQLite?
Simple, zero-infrastructure persistence appropriate for a single-user tool. Easily replaceable with PostgreSQL for multi-user deployments.

### Why Pydantic?
All data crossing layer boundaries is validated. Malformed LLM judge responses are caught at parse time, not at render time.

### Why separate rule-based and LLM judge evaluation?
Rule-based evaluation is deterministic and cheap. LLM-based evaluation captures semantic quality but is expensive and variable. Together they provide a more complete picture.

### Why demo mode?
Demo mode allows the application to be demonstrated and tested without consuming API credits, while keeping the codebase paths identical (same interface, different provider).

### Why `{{variable}}` syntax?
Double-brace syntax avoids conflicts with Python f-string syntax and Jinja2, while being clearly visible in prompt text.
