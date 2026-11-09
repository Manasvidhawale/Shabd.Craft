"""
Shabd.Craft — LLM-as-a-Judge Evaluator

Uses a separate LLM call with an explicit scoring rubric to evaluate
response quality. Validates judge responses via Pydantic.
"""

from __future__ import annotations

import json
import hashlib
import random
from typing import Optional

from src.schemas import (
    CriterionScore, LLMRequest, LLMResponse, EvaluationMethod,
)
from src.providers.base import BaseLLMProvider


JUDGE_SYSTEM_PROMPT = """You are an expert AI output evaluator. Your task is to evaluate the quality of an AI-generated response against specific criteria.

You must be objective, critical, and evidence-based. Do NOT simply agree with the response or reward longer answers. Evaluate based on the actual quality and correctness of the content.

When a reference/expected answer is provided, compare the response against it. When no reference is available, evaluate based on the task requirements and the scoring rubric only.

IMPORTANT: Return your evaluation as valid JSON only, with no text outside the JSON object."""

JUDGE_USER_TEMPLATE = """Evaluate the following AI-generated response.

## Task Instructions
{task_instructions}

## Input Data
{input_data}

## Expected Output
{expected_output}

## Actual AI Response
{actual_output}

## Evaluation Criteria (score each 0-100)
1. **accuracy**: Factual correctness and alignment with expected output (if provided)
2. **relevance**: How well the response addresses the specific input and task
3. **instruction_adherence**: How closely the response follows the task instructions
4. **clarity**: Readability, organization, and completeness of the response
5. **format_compliance**: Whether the response matches the required format

## Required JSON Response Format
{{
    "criterion_scores": [
        {{"name": "accuracy", "score": <0-100>, "explanation": "<brief reason>"}},
        {{"name": "relevance", "score": <0-100>, "explanation": "<brief reason>"}},
        {{"name": "instruction_adherence", "score": <0-100>, "explanation": "<brief reason>"}},
        {{"name": "clarity", "score": <0-100>, "explanation": "<brief reason>"}},
        {{"name": "format_compliance", "score": <0-100>, "explanation": "<brief reason>"}}
    ],
    "overall_score": <0-100>,
    "weaknesses": ["<weakness 1>", "<weakness 2>"],
    "suggestions": ["<improvement 1>", "<improvement 2>"]
}}"""


def evaluate_with_llm_judge(
    provider: BaseLLMProvider,
    task_instructions: str,
    input_data: str,
    expected_output: str,
    actual_output: str,
    model: str = "gpt-3.5-turbo",
    max_retries: int = 2,
) -> dict:
    """
    Evaluate a response using LLM-as-a-Judge.

    Returns a dict with criterion_scores, overall_score, weaknesses, suggestions.
    Uses bounded retries for malformed responses.
    """
    if provider.is_demo:
        return _demo_judge_evaluation(actual_output, expected_output)

    user_prompt = JUDGE_USER_TEMPLATE.format(
        task_instructions=task_instructions or "No specific instructions provided.",
        input_data=input_data or "No input data.",
        expected_output=expected_output or "No expected output provided. Evaluate based on task requirements only.",
        actual_output=actual_output or "(Empty response)",
    )

    request = LLMRequest(
        system_prompt=JUDGE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        temperature=0.1,  # Low temperature for consistent evaluation
        max_tokens=800,
    )

    for attempt in range(max_retries + 1):
        response = provider.generate(request)

        if response.error:
            if attempt == max_retries:
                return _fallback_evaluation(f"Judge API error: {response.error}")
            continue

        parsed = _parse_judge_response(response.content)
        if parsed is not None:
            return parsed

        if attempt == max_retries:
            return _fallback_evaluation("Judge returned malformed response after retries.")

    return _fallback_evaluation("Judge evaluation failed.")


def _parse_judge_response(content: str) -> Optional[dict]:
    """Parse and validate the judge's JSON response."""
    try:
        # Try to extract JSON from response
        content = content.strip()
        if not content.startswith("{"):
            # Look for JSON block
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()
            else:
                return None

        data = json.loads(content)

        # Validate structure
        if "criterion_scores" not in data:
            return None

        scores = []
        for cs in data["criterion_scores"]:
            score = float(cs.get("score", 0))
            score = max(0.0, min(100.0, score))  # Clamp to valid range
            scores.append(CriterionScore(
                name=cs.get("name", "unknown"),
                score=score,
                explanation=cs.get("explanation", ""),
            ))

        overall = float(data.get("overall_score", 0))
        overall = max(0.0, min(100.0, overall))

        return {
            "criterion_scores": scores,
            "overall_score": overall,
            "weaknesses": data.get("weaknesses", []),
            "suggestions": data.get("suggestions", []),
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def _fallback_evaluation(reason: str) -> dict:
    """Return a clearly-labeled fallback when judge evaluation fails."""
    return {
        "criterion_scores": [
            CriterionScore(name="accuracy", score=0, explanation=f"Evaluation failed: {reason}"),
            CriterionScore(name="relevance", score=0, explanation=f"Evaluation failed: {reason}"),
            CriterionScore(name="instruction_adherence", score=0, explanation=f"Evaluation failed: {reason}"),
            CriterionScore(name="clarity", score=0, explanation=f"Evaluation failed: {reason}"),
            CriterionScore(name="format_compliance", score=0, explanation=f"Evaluation failed: {reason}"),
        ],
        "overall_score": 0,
        "weaknesses": [reason],
        "suggestions": ["Re-run evaluation with a working API connection."],
        "error": reason,
    }


def _demo_judge_evaluation(actual_output: str, expected_output: str) -> dict:
    """
    Generate deterministic demo evaluation scores.
    Clearly labeled as simulated.
    """
    seed = int(hashlib.md5((actual_output + expected_output).encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    base_score = rng.randint(60, 90)

    scores = [
        CriterionScore(
            name="accuracy",
            score=min(100, base_score + rng.randint(-10, 10)),
            explanation="[DEMO] Simulated accuracy assessment.",
        ),
        CriterionScore(
            name="relevance",
            score=min(100, base_score + rng.randint(-5, 15)),
            explanation="[DEMO] Simulated relevance assessment.",
        ),
        CriterionScore(
            name="instruction_adherence",
            score=min(100, base_score + rng.randint(-8, 12)),
            explanation="[DEMO] Simulated instruction adherence assessment.",
        ),
        CriterionScore(
            name="clarity",
            score=min(100, base_score + rng.randint(-5, 10)),
            explanation="[DEMO] Simulated clarity assessment.",
        ),
        CriterionScore(
            name="format_compliance",
            score=min(100, base_score + rng.randint(-12, 15)),
            explanation="[DEMO] Simulated format compliance assessment.",
        ),
    ]

    overall = round(sum(s.score for s in scores) / len(scores), 1)

    return {
        "criterion_scores": scores,
        "overall_score": overall,
        "weaknesses": [
            "[DEMO] Simulated weakness: Instructions could be more specific.",
            "[DEMO] Simulated weakness: Output format could be more structured.",
        ],
        "suggestions": [
            "[DEMO] Simulated suggestion: Add explicit constraints to the prompt.",
            "[DEMO] Simulated suggestion: Include example output format.",
        ],
    }
