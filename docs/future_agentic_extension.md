# Shabd.Craft — Future Agentic Extension

## Overview

Shabd.Craft is designed to evolve into a multi-agent prompt engineering system using [LangGraph](https://github.com/langchain-ai/langgraph). This document describes the upgrade path, the role of each future agent, and the minimal code changes required.

The current architecture already uses a clean service layer, validated schemas, and swappable providers — all of which will serve as the foundation for the agentic extension.

---

## Target Agentic Workflow

```
User Task
    │
    ▼
┌───────────────┐
│ Planner Agent │  Analyzes task, defines strategy, sets stopping conditions
└──────┬────────┘
       │
       ▼
┌───────────────────┐
│ Candidate Generator│  Generates N prompt candidates with diverse strategies
└──────┬────────────┘
       │  (for each candidate)
       ▼
┌───────────────┐
│ Tester Agent  │  Executes prompt on test dataset, collects raw outputs
└──────┬────────┘
       │
       ▼
┌─────────────────┐
│ Evaluator Agent │  Scores outputs with rule-based + LLM judge
└──────┬──────────┘
       │
       ▼
┌─────────────────────┐
│ Quality Gate        │  Checks if best candidate meets threshold
└──────┬──────────────┘
       │
       ├─── YES ──► Save best candidate, report to user, STOP
       │
       └─── NO  ──► 
                    ┌───────────────────┐
                    │ Optimizer Agent   │  Analyses feedback, mutates prompts
                    └──────┬────────────┘
                           │
                           ▼
                    (loop back to Tester, up to max_iterations)
```

### Stopping Conditions

The agentic loop must stop when:
1. A candidate exceeds the configured quality threshold (e.g., overall score ≥ 85)
2. The maximum iteration count is reached (configurable, default 5)
3. No candidate improves on the previous best by more than 2 points for 2 consecutive rounds
4. The estimated cost budget is exhausted

---

## Current vs Future Architecture

| Component | Current (v1) | Agentic (v2) |
|---|---|---|
| Planner | User selects strategy | `PlannerAgent` analyzes task and auto-selects strategy |
| Candidate generation | `optimizer.py` (single call) | `MutationAgent` with iterative refinement |
| Testing | `evaluation_engine.evaluate_batch()` | `TesterAgent` node in LangGraph graph |
| Evaluation | `evaluation_engine.py` | `EvaluatorAgent` node with structured feedback |
| Comparison | `comparison_engine.py` | Integrated into graph state |
| Orchestration | Manual (user clicks) | LangGraph `StateGraph` with checkpointing |
| Stopping | User decides | Quality gate with configurable threshold |

---

## Interfaces Ready for Agentic Upgrade

### Provider Interface (already agent-compatible)

```python
# providers/base.py — already abstract
class BaseLLMProvider:
    def generate(self, request: LLMRequest) -> LLMResponse: ...
```

Each agent will use this interface through `get_provider()`.

### Evaluation Interface (already agent-compatible)

```python
# evaluation_engine.py
def evaluate_single(version, test_case, experiment_id, weights, method, ...) -> EvaluationResult: ...
def evaluate_batch(version, test_cases, ...) -> list[EvaluationResult]: ...
```

The `TesterAgent` and `EvaluatorAgent` will call these directly.

### Optimization Interface (already agent-compatible)

```python
# optimizer.py
def generate_candidates(original_version, evaluation_results, ...) -> list[OptimizationCandidate]: ...
def recommend_best(original_score, candidate_scores, test_case_count) -> dict: ...
```

The `MutationAgent` wraps `generate_candidates()`.

---

## Planned LangGraph State Schema

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class PromptOptimizationState(TypedDict):
    # Experiment context
    experiment_id: str
    original_version_id: str
    test_case_ids: list[str]
    evaluation_weights: dict[str, float]

    # Planning
    strategy: str
    quality_threshold: float
    max_iterations: int
    budget_usd: float

    # Current state
    iteration: int
    best_version_id: str | None
    best_score: float
    cost_so_far: float

    # Agent outputs
    candidates: list[dict]
    evaluation_results: list[dict]
    recommendations: list[str]

    # Termination
    stop_reason: str | None
    messages: Annotated[list, add_messages]
```

---

## Implementation Plan for v2

### Step 1: Install LangGraph

```bash
pip install langgraph langchain-openai
```

Add to `requirements.txt`.

### Step 2: Create Agent Nodes

Create `src/agents/` directory:

```
src/agents/
├── __init__.py
├── planner_agent.py      # Analyzes task, selects strategy
├── tester_agent.py       # Wraps evaluate_batch()
├── evaluator_agent.py    # Wraps evaluation_engine + llm_judge
├── mutation_agent.py     # Wraps optimizer.generate_candidates()
└── quality_gate.py       # Checks threshold and stopping conditions
```

### Step 3: Build the Graph

```python
# src/agents/optimization_graph.py
from langgraph.graph import StateGraph, END
from .planner_agent import plan
from .tester_agent import test_candidates
from .evaluator_agent import evaluate_candidates
from .mutation_agent import mutate_candidates
from .quality_gate import check_quality

graph = StateGraph(PromptOptimizationState)

graph.add_node("planner", plan)
graph.add_node("tester", test_candidates)
graph.add_node("evaluator", evaluate_candidates)
graph.add_node("mutation", mutate_candidates)
graph.add_node("quality_gate", check_quality)

graph.set_entry_point("planner")
graph.add_edge("planner", "tester")
graph.add_edge("tester", "evaluator")
graph.add_edge("evaluator", "quality_gate")
graph.add_conditional_edges(
    "quality_gate",
    lambda state: "done" if state["stop_reason"] else "mutation",
    {"done": END, "mutation": "tester"},
)

app = graph.compile()
```

### Step 4: Add Checkpointing

```python
from langgraph.checkpoint.sqlite import SqliteSaver

memory = SqliteSaver.from_conn_string(settings.db_path)
app = graph.compile(checkpointer=memory)
```

This reuses the existing SQLite database for agent state persistence.

### Step 5: Integrate with Streamlit

Add a new page `pages/9_Auto_Optimizer.py` that:
- Accepts experiment ID, quality threshold, and budget
- Streams the LangGraph execution state
- Displays live iteration progress using `st.status`
- Shows the best candidate when the graph completes

---

## Cost and Safety Controls

```python
# Enforced in quality_gate.py
def check_quality(state: PromptOptimizationState) -> PromptOptimizationState:
    if state["cost_so_far"] >= state["budget_usd"]:
        state["stop_reason"] = "Budget exhausted"
    elif state["iteration"] >= state["max_iterations"]:
        state["stop_reason"] = "Max iterations reached"
    elif state["best_score"] >= state["quality_threshold"]:
        state["stop_reason"] = "Quality threshold met"
    elif _no_progress(state):
        state["stop_reason"] = "No improvement for 2 consecutive rounds"
    return state
```

---

## Timeline Estimate

| Phase | Effort | Prerequisite |
|---|---|---|
| LangGraph installation & state schema | 1 day | v1 complete |
| Agent node implementations | 2–3 days | Agent state schema |
| Graph wiring & conditional edges | 1 day | Agent nodes |
| Checkpointing & resume support | 1 day | Graph wiring |
| Streamlit integration page | 1–2 days | Graph complete |
| Testing & edge cases | 2 days | Integration page |
| **Total** | **8–10 days** | |

---

## No Breaking Changes Required

The v2 agentic extension will:

- **Not modify** any existing source modules (they are used as libraries by agents)
- **Not change** the database schema (LangGraph checkpoints are stored separately)
- **Not affect** existing Streamlit pages (new page is additive)
- **Add** the `src/agents/` directory and `pages/9_Auto_Optimizer.py`
- **Extend** `requirements.txt` with `langgraph` and `langchain-openai`

The current architecture was designed with this extension in mind.
