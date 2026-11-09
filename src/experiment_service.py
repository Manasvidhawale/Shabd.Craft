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

    # Copy versions
    versions = db.get_prompt_versions(exp_id)
    for v in versions:
        examples = json.loads(v.get("few_shot_examples", "[]"))
        pv = PromptVersion(
            experiment_id=new_exp_id,
            version_number=v["version_number"],
            version_label=v["version_label"],
            system_prompt=v["system_prompt"],
            user_prompt_template=v["user_prompt_template"],
            technique=PromptingTechnique(v["technique"]),
            output_format=OutputFormat(v["output_format"]),
            variables=json.loads(v.get("variables", "[]")),
            model_name=v["model_name"],
            temperature=v["temperature"],
            max_tokens=v["max_tokens"],
            few_shot_examples=[FewShotExample(**e) for e in examples],
        )
        db.save_prompt_version(pv)

    # Copy test cases
    test_cases = db.get_test_cases(exp_id)
    for tc_data in test_cases:
        tc = TestCase(
            input_data=tc_data["input_data"],
            expected_output=tc_data["expected_output"],
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
    candidates = db.get_optimization_candidates(exp_id)

    successful = [r for r in results if r.get("execution_status") == "success"]
    avg_score = round(sum(r["overall_score"] for r in successful) / len(successful), 1) if successful else 0.0

    return {
        "experiment": exp,
        "versions": versions,
        "test_cases": test_cases,
        "results": results,
        "candidates": candidates,
        "version_count": len(versions),
        "test_case_count": len(test_cases),
        "evaluation_count": len(results),
        "success_count": len(successful),
        "failed_count": len(results) - len(successful),
        "avg_score": avg_score,
    }
