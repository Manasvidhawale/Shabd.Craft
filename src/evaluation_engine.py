"""
Shabd.Craft — Evaluation Engine

Orchestrates rule-based and LLM-as-a-Judge evaluation for test cases.
Calculates weighted scores and manages evaluation workflows.
"""

from __future__ import annotations

from typing import Optional

from src.schemas import (
    CriterionScore, EvaluationResult, EvaluationWeights,
    EvaluationMethod, ExecutionStatus, PromptVersion,
    TestCase, LLMResponse, OutputFormat, _new_id, _now,
)
from src.rule_based_evaluator import evaluate_rule_based
from src.llm_judge import evaluate_with_llm_judge
from src.prompt_engine import execute_prompt, get_provider


def calculate_weighted_score(
    criterion_scores: list[CriterionScore],
    weights: EvaluationWeights,
) -> float:
    """
    Calculate overall weighted score from criterion scores.

    Normalizes weights to sum to 1.0 before calculation.
    """
    normalized = weights.normalized()
    total = 0.0
    for cs in criterion_scores:
        w = normalized.get(cs.name, 0.0)
        total += cs.score * w
    return round(total, 1)


def evaluate_single(
    version: PromptVersion,
    test_case: TestCase,
    experiment_id: str,
    weights: EvaluationWeights,
    method: EvaluationMethod = EvaluationMethod.RULE_BASED,
    required_keywords: list[str] | None = None,
    max_words: int | None = None,
    required_fields: list[str] | None = None,
) -> EvaluationResult:
    """
    Evaluate a single test case against a prompt version.

    Steps:
    1. Execute the prompt with test case input.
    2. Evaluate the response using the configured method.
    3. Calculate weighted score.
    4. Return a complete EvaluationResult.
    """
    result_id = _new_id()

    # Step 1: Execute prompt
    llm_response = execute_prompt(version, input_data=test_case.input_data)

    if llm_response.error:
        return EvaluationResult(
            id=result_id,
            test_case_id=test_case.id,
            prompt_version_id=version.id,
            experiment_id=experiment_id,
            generated_output="",
            execution_status=ExecutionStatus.FAILED,
            error_message=llm_response.error,
            is_demo=llm_response.is_demo,
            created_at=_now(),
        )

    generated_output = llm_response.content

    # Step 2: Evaluate
    criterion_scores = []

    if method in (EvaluationMethod.RULE_BASED, EvaluationMethod.COMBINED):
        rule_scores = evaluate_rule_based(
            generated_output=generated_output,
            expected_output=test_case.expected_output,
            output_format=version.output_format,
            required_keywords=required_keywords,
            max_words=max_words,
            required_fields=required_fields,
        )
        criterion_scores = rule_scores

    if method in (EvaluationMethod.LLM_JUDGE, EvaluationMethod.COMBINED):
        provider = get_provider()
        task_instructions = f"{version.system_prompt}\n{version.user_prompt_template}"
        judge_result = evaluate_with_llm_judge(
            provider=provider,
            task_instructions=task_instructions,
            input_data=test_case.input_data,
            expected_output=test_case.expected_output,
            actual_output=generated_output,
            model=version.model_name or "gpt-3.5-turbo",
        )

        if method == EvaluationMethod.COMBINED and criterion_scores:
            # Average rule-based and LLM judge scores
            rule_map = {s.name: s for s in criterion_scores}
            judge_scores = judge_result.get("criterion_scores", [])
            combined = []
            for js in judge_scores:
                rs = rule_map.get(js.name)
                if rs:
                    avg = round((rs.score + js.score) / 2, 1)
                    combined.append(CriterionScore(
                        name=js.name,
                        score=avg,
                        explanation=f"Rule: {rs.explanation} | Judge: {js.explanation}",
                    ))
                else:
                    combined.append(js)
            criterion_scores = combined
            weaknesses = judge_result.get("weaknesses", [])
            suggestions = judge_result.get("suggestions", [])
        else:
            criterion_scores = judge_result.get("criterion_scores", [])
            weaknesses = judge_result.get("weaknesses", [])
            suggestions = judge_result.get("suggestions", [])
    else:
        weaknesses = []
        suggestions = []

    # Step 3: Calculate weighted score
    overall_score = calculate_weighted_score(criterion_scores, weights)

    is_reference_verified = bool(test_case.expected_output and test_case.expected_output.strip())

    return EvaluationResult(
        id=result_id,
        test_case_id=test_case.id,
        prompt_version_id=version.id,
        experiment_id=experiment_id,
        generated_output=generated_output,
        criterion_scores=criterion_scores,
        overall_score=overall_score,
        weaknesses=weaknesses if method != EvaluationMethod.RULE_BASED else [],
        suggestions=suggestions if method != EvaluationMethod.RULE_BASED else [],
        evaluation_method=method,
        is_reference_verified=is_reference_verified,
        execution_status=ExecutionStatus.SUCCESS,
        latency_ms=llm_response.latency_ms,
        tokens_used=llm_response.total_tokens,
        cost_estimate=llm_response.cost_estimate,
        is_demo=llm_response.is_demo,
        created_at=_now(),
    )


def evaluate_batch(
    version: PromptVersion,
    test_cases: list[TestCase],
    experiment_id: str,
    weights: EvaluationWeights,
    method: EvaluationMethod = EvaluationMethod.RULE_BASED,
    required_keywords: list[str] | None = None,
    max_words: int | None = None,
    required_fields: list[str] | None = None,
    progress_callback=None,
) -> list[EvaluationResult]:
    """
    Evaluate a batch of test cases.

    Continues on individual failures — partial results are preserved.
    """
    results = []
    for i, tc in enumerate(test_cases):
        try:
            result = evaluate_single(
                version=version,
                test_case=tc,
                experiment_id=experiment_id,
                weights=weights,
                method=method,
                required_keywords=required_keywords,
                max_words=max_words,
                required_fields=required_fields,
            )
            results.append(result)
        except Exception as e:
            results.append(EvaluationResult(
                test_case_id=tc.id,
                prompt_version_id=version.id,
                experiment_id=experiment_id,
                execution_status=ExecutionStatus.FAILED,
                error_message=str(e),
                created_at=_now(),
            ))

        if progress_callback:
            progress_callback(i + 1, len(test_cases))

    return results


def aggregate_results(results: list[EvaluationResult]) -> dict:
    """Aggregate evaluation results into summary statistics."""
    if not results:
        return {
            "total": 0, "success": 0, "failed": 0,
            "avg_score": 0, "min_score": 0, "max_score": 0,
            "criterion_averages": {},
        }

    successful = [r for r in results if r.execution_status == ExecutionStatus.SUCCESS]
    failed = [r for r in results if r.execution_status == ExecutionStatus.FAILED]

    scores = [r.overall_score for r in successful]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    # Criterion averages
    criterion_totals: dict[str, list[float]] = {}
    for r in successful:
        for cs in r.criterion_scores:
            criterion_totals.setdefault(cs.name, []).append(cs.score)

    criterion_averages = {
        k: round(sum(v) / len(v), 1) for k, v in criterion_totals.items()
    }

    return {
        "total": len(results),
        "success": len(successful),
        "failed": len(failed),
        "avg_score": avg_score,
        "min_score": round(min(scores), 1) if scores else 0.0,
        "max_score": round(max(scores), 1) if scores else 0.0,
        "criterion_averages": criterion_averages,
    }
