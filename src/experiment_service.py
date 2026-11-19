"""
Shabd.Craft — Experiment Service

High-level orchestration for experiment workflows.
"""

from __future__ import annotations

import json
from typing import Optional

from src.schemas import (
    Experiment, PromptVersion, TestCase, EvaluationWeights,
    EvaluationResult, ExecutionStatus, TaskCategory,
    PromptingTechnique, OutputFormat, FewShotExample,
    _new_id, _now,
)
from src.database import Database


def create_experiment_with_version(
    db: Database,
    name: str,
    category: str,
    system_prompt: str,
    user_prompt: str,
    technique: str = "zero_shot",
    output_format: str = "text",
    model_name: str = "",
    temperature: float = 0.7,
    max_tokens: int = 1024,
    few_shot_examples: list[dict] | None = None,
    description: str = "",
) -> tuple[str, str]:
    """
    Create an experiment and its first prompt version.
    Returns (experiment_id, version_id).
    """
    exp = Experiment(
        name=name,
        category=TaskCategory(category) if category in [e.value for e in TaskCategory] else TaskCategory.GENERAL,
        description=description,
        status=ExecutionStatus.PENDING,
    )
    exp_id = db.create_experiment(exp)

    examples = []
    if few_shot_examples:
        for ex in few_shot_examples:
            examples.append(FewShotExample(
                input_text=ex.get("input_text", ""),
                output_text=ex.get("output_text", ""),
            ))

    version = PromptVersion(
        experiment_id=exp_id,
        version_number=1,
        version_label="Original",
        system_prompt=system_prompt,
        user_prompt_template=user_prompt,
        technique=PromptingTechnique(technique) if technique in [e.value for e in PromptingTechnique] else PromptingTechnique.ZERO_SHOT,
        output_format=OutputFormat(output_format) if output_format in [e.value for e in OutputFormat] else OutputFormat.TEXT,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        few_shot_examples=examples,
    )
    ver_id = db.save_prompt_version(version)

    return exp_id, ver_id


def create_revision_branch(
    db: Database, experiment_id: str, source_version_id: str, name: str,
    description: str = "",
) -> tuple[str, str]:
    """Create a uniquely named branch from a revision for an optimization or audit result."""
    base_name = name.strip()[:60] or "revision"
    for suffix in range(1, 100):
        branch_name = base_name if suffix == 1 else f"{base_name[:54]}-{suffix}"
        try:
            branch_id = db.create_prompt_branch(
                experiment_id, branch_name, source_version_id, description
            )
            return branch_id, branch_name
        except ValueError as exc:
            if "already exists" not in str(exc):
                raise
    raise ValueError("Could not find an available branch name. Choose another name and try again.")


def duplicate_experiment(db: Database, exp_id: str, new_name: str) -> Optional[str]:
    """Duplicate an experiment with all its versions and test cases."""
    original = db.get_experiment(exp_id)
    if not original:
        return None

    new_exp = Experiment(
        name=new_name,
        category=TaskCategory(original["category"]),
        description=f"Duplicated from: {original['name']}",
        status=ExecutionStatus.PENDING,
    )
    new_exp_id = db.create_experiment(new_exp)

    db.duplicate_prompt_history(exp_id, new_exp_id)

    # Copy test cases
    test_cases = db.get_test_cases(exp_id)
    for tc_data in test_cases:
        tc = TestCase(
            input_data=tc_data["input_data"],
            expected_output=tc_data["expected_output"],
            metadata=json.loads(tc_data.get("metadata", "{}")) if isinstance(tc_data.get("metadata"), str) else tc_data.get("metadata", {}),
        )
        db.save_test_case(tc, new_exp_id)

    return new_exp_id


def get_experiment_summary(db: Database, exp_id: str) -> dict:
    """Get a summary of an experiment with all related data."""
    exp = db.get_experiment(exp_id)
    if not exp:
        return {}

    versions = db.get_prompt_versions(exp_id)
    test_cases = db.get_test_cases(exp_id)
    results = db.get_evaluation_results(exp_id)
    evaluation_runs = db.get_evaluation_runs(exp_id)
    candidates = db.get_optimization_candidates(exp_id)

    successful = [r for r in results if r.get("execution_status") == "success"]
    avg_score = round(sum(r["overall_score"] for r in successful) / len(successful), 1) if successful else 0.0

    return {
        "experiment": exp,
        "versions": versions,
        "test_cases": test_cases,
        "results": results,
        "evaluation_runs": evaluation_runs,
        "candidates": candidates,
        "version_count": len(versions),
        "test_case_count": len(test_cases),
        "evaluation_count": len(results),
        "success_count": len(successful),
        "failed_count": len(results) - len(successful),
        "avg_score": avg_score,
    }
