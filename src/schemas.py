"""
Shabd.Craft — Pydantic Schemas

Validated data models for prompts, experiments, evaluations, and optimization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Enums ──────────────────────────────────────────────────────────────

class TaskCategory(str, Enum):
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    SENTIMENT = "sentiment"
    QA = "question_answering"
    EMAIL = "email_generation"
    CLASSIFICATION = "classification"
    JSON_GENERATION = "json_generation"
    CUSTOMER_SUPPORT = "customer_support"
    DATA_ANALYSIS = "data_analysis"
    GENERAL = "general"


class PromptingTechnique(str, Enum):
    ZERO_SHOT = "zero_shot"
    ONE_SHOT = "one_shot"
    FEW_SHOT = "few_shot"
    ROLE_BASED = "role_based"
    STRUCTURED_OUTPUT = "structured_output"
    TASK_DECOMPOSITION = "task_decomposition"
    CHAIN_OF_THOUGHT = "chain_of_thought"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class EvaluationMethod(str, Enum):
    RULE_BASED = "rule_based"
    LLM_JUDGE = "llm_judge"
    COMBINED = "combined"


class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    CSV = "csv"
    BULLET_POINTS = "bullet_points"


# ── Helper ─────────────────────────────────────────────────────────────

def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Prompt Schemas ─────────────────────────────────────────────────────

class FewShotExample(BaseModel):
    input_text: str
    output_text: str


class PromptTemplate(BaseModel):
    """A reusable prompt template in the library."""
    id: str = Field(default_factory=_new_id)
    name: str
    description: str = ""
    category: TaskCategory = TaskCategory.GENERAL
    system_prompt: str = ""
    user_prompt_template: str
    variables: list[str] = Field(default_factory=list)
    technique: PromptingTechnique = PromptingTechnique.ZERO_SHOT
    few_shot_examples: list[FewShotExample] = Field(default_factory=list)
    output_format: OutputFormat = OutputFormat.TEXT
    example_input: str = ""
    example_output: str = ""
    eval_criteria: dict[str, float] = Field(default_factory=dict)
    is_builtin: bool = False
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class PromptVersion(BaseModel):
    """A specific version of a prompt within an experiment."""
    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(default_factory=_new_id)
    experiment_id: str
    version_number: int = 1
    version_label: str = "Original"
    system_prompt: str = ""
    user_prompt_template: str
    technique: PromptingTechnique = PromptingTechnique.ZERO_SHOT
    few_shot_examples: list[FewShotExample] = Field(default_factory=list)
    output_format: OutputFormat = OutputFormat.TEXT
    variables: list[str] = Field(default_factory=list)
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    is_optimized: bool = False
    optimization_strategy: str = ""
    created_at: str = Field(default_factory=_now)


# ── Test Case Schemas ──────────────────────────────────────────────────

class TestCase(BaseModel):
    """A single test case for prompt evaluation."""
    id: str = Field(default_factory=_new_id)
    input_data: str
    expected_output: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input_data")
    @classmethod
    def input_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Test case input must not be empty.")
        return v.strip()


class TestDataset(BaseModel):
    """Collection of test cases."""
    id: str = Field(default_factory=_new_id)
    name: str = "Default Dataset"
    test_cases: list[TestCase] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


# ── LLM Request / Response ────────────────────────────────────────────

class LLMRequest(BaseModel):
    """Request to send to an LLM provider."""
    system_prompt: str = ""
    user_prompt: str
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 1024


class LLMResponse(BaseModel):
    """Response from an LLM provider."""
    content: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_estimate: float = 0.0
    is_demo: bool = False
    error: str = ""


# ── Evaluation Schemas ─────────────────────────────────────────────────

class EvaluationWeights(BaseModel):
    """Configurable weights for evaluation criteria."""
    accuracy: float = 0.25
    relevance: float = 0.20
    instruction_adherence: float = 0.25
    clarity: float = 0.15
    format_compliance: float = 0.15

    @field_validator("accuracy", "relevance", "instruction_adherence", "clarity", "format_compliance")
    @classmethod
    def weight_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Evaluation weight must be non-negative.")
        return v

    def normalized(self) -> dict[str, float]:
        """Return weights normalized to sum to 1.0."""
        raw = {
            "accuracy": self.accuracy,
            "relevance": self.relevance,
            "instruction_adherence": self.instruction_adherence,
            "clarity": self.clarity,
            "format_compliance": self.format_compliance,
        }
        total = sum(raw.values())
        if total == 0:
            raise ValueError("At least one evaluation weight must be greater than zero.")
        return {k: v / total for k, v in raw.items()}


class CriterionScore(BaseModel):
    """Score for a single evaluation criterion."""
    name: str
    score: float = Field(ge=0, le=100)
    explanation: str = ""


class EvaluationResult(BaseModel):
    """Full evaluation result for a single test case execution."""
    id: str = Field(default_factory=_new_id)
    test_case_id: str
    prompt_version_id: str
    experiment_id: str
    generated_output: str = ""
    criterion_scores: list[CriterionScore] = Field(default_factory=list)
    overall_score: float = Field(default=0.0, ge=0, le=100)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    evaluation_method: EvaluationMethod = EvaluationMethod.RULE_BASED
    is_reference_verified: bool = False
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    error_message: str = ""
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_estimate: float = 0.0
    is_demo: bool = False
    created_at: str = Field(default_factory=_now)


# ── Experiment Schemas ─────────────────────────────────────────────────

class Experiment(BaseModel):
    """A prompt engineering experiment."""
    id: str = Field(default_factory=_new_id)
    name: str
    category: TaskCategory = TaskCategory.GENERAL
    description: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Experiment name must not be empty.")
        return v.strip()


# ── Optimization Schemas ───────────────────────────────────────────────

class OptimizationCandidate(BaseModel):
    """A candidate prompt generated by the optimizer."""
    id: str = Field(default_factory=_new_id)
    experiment_id: str
    original_version_id: str
    candidate_label: str = "Candidate A"
    strategy: str = ""
    system_prompt: str = ""
    user_prompt_template: str
    changes_description: str = ""
    rationale: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    overall_score: float = 0.0
    is_accepted: bool = False
    created_at: str = Field(default_factory=_now)


class OptimizationRound(BaseModel):
    """A single round of optimization."""
    round_number: int
    original_score: float = 0.0
    candidates: list[OptimizationCandidate] = Field(default_factory=list)
    best_candidate_id: Optional[str] = None
    improvement_found: bool = False


# ── Comparison Schemas ─────────────────────────────────────────────────

class VersionComparison(BaseModel):
    """Comparison between two prompt versions."""
    version_a_id: str
    version_b_id: str
    version_a_label: str = ""
    version_b_label: str = ""
    version_a_scores: dict[str, float] = Field(default_factory=dict)
    version_b_scores: dict[str, float] = Field(default_factory=dict)
    version_a_overall: float = 0.0
    version_b_overall: float = 0.0
    winner: Optional[str] = None
    recommendation: str = ""
    limitations: list[str] = Field(default_factory=list)
    test_case_count: int = 0
