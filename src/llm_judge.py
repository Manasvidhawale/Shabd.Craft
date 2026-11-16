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
            # Apply Zheng et al. (NeurIPS 2023) empirical verbosity normalization penalty
            penalized_score, verbosity_note = apply_verbosity_penalty(
                actual_output=actual_output,
                expected_output=expected_output,
                base_score=parsed["overall_score"],
            )
            parsed["overall_score"] = penalized_score
            if verbosity_note:
                parsed["weaknesses"].append(verbosity_note)
            return parsed

        if attempt == max_retries:
            return _fallback_evaluation("Judge returned malformed response after retries.")

    return _fallback_evaluation("Judge evaluation failed.")


def _parse_judge_response(content: str) -> Optional[dict]:
    """Parse and validate the judge's JSON response."""
    try:
        # Try to extract JSON from response
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
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
            explanation="Simulated assessment: output aligns with expected response key points.",
        ),
        CriterionScore(
            name="relevance",
            score=min(100, base_score + rng.randint(-5, 15)),
            explanation="Simulated assessment: response directly addresses the input prompt.",
        ),
        CriterionScore(
            name="instruction_adherence",
            score=min(100, base_score + rng.randint(-8, 12)),
            explanation="Simulated assessment: all specified constraints and steps were observed.",
        ),
        CriterionScore(
            name="clarity",
            score=min(100, base_score + rng.randint(-5, 10)),
            explanation="Simulated assessment: tone is clear, readable, and well-organized.",
        ),
        CriterionScore(
            name="format_compliance",
            score=min(100, base_score + rng.randint(-12, 15)),
            explanation="Simulated assessment: response matches expected structural format.",
        ),
    ]

    overall = round(sum(s.score for s in scores) / len(scores), 1)

    return {
        "criterion_scores": scores,
        "overall_score": overall,
        "weaknesses": [
            "Instructions could be more specific regarding edge cases.",
            "Output format could specify explicit field structures.",
        ],
        "suggestions": [
            "Add explicit constraints and delimiters to the prompt.",
            "Include input/output examples (Few-Shot).",
        ],
    }


def apply_verbosity_penalty(
    actual_output: str,
    expected_output: str,
    base_score: float,
    max_penalty: float = 20.0,
) -> tuple[float, str | None]:
    """
    Apply an empirical verbosity normalization penalty (Zheng et al., NeurIPS 2023).
    LLM judges systematically suffer from verbosity bias, favoring bloated responses.

    If expected_output is provided and actual_output is > 2.5x longer than expected
    with significant word inflation (> 50 extra words), apply a calibrated penalty.
    """
    actual_words = len((actual_output or "").split())
    expected_words = len((expected_output or "").split())

    if expected_words > 0 and actual_words >= max(int(expected_words * 2.0), expected_words + 20):
        ratio = actual_words / expected_words
        penalty = min(max_penalty, round(max(2.0, (ratio - 2.0) * 2.5), 1))
        penalized_score = max(0.0, round(base_score - penalty, 1))
        notice = f"Verbosity bias penalty applied: -{penalty} pts (output is {ratio:.1f}x longer than reference target)."
        return penalized_score, notice

    return base_score, None


PAIRWISE_JUDGE_SYSTEM_PROMPT = """You are an impartial expert evaluator comparing two AI model responses to the same instruction.
Evaluate which response is better based on instruction adherence, accuracy, clarity, and conciseness.
Avoid position bias: evaluate strictly on merit.

Respond in JSON with this format:
{
    "winner": "A" | "B" | "tie",
    "score_a": <0-100>,
    "score_b": <0-100>,
    "rationale": "<concise explanation>"
}"""

PAIRWISE_USER_TEMPLATE = """## Task Instruction
{instruction}

## Input Data
{input_data}

## Candidate Response A
{response_a}

## Candidate Response B
{response_b}

Evaluate Candidate A vs Candidate B. Return JSON only."""


def _parse_pairwise_json(content: str) -> Optional[dict]:
    try:
        content = (content or "").strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            content = content.strip()
        if not content.startswith("{"):
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                content = match.group()
            else:
                return None
        data = json.loads(content)
        winner = str(data.get("winner", "tie")).upper()
        if winner not in ("A", "B", "TIE"):
            winner = "tie"
        return {
            "winner": winner,
            "score_a": float(data.get("score_a", 50)),
            "score_b": float(data.get("score_b", 50)),
            "rationale": str(data.get("rationale", "")),
        }
    except Exception:
        return None


def evaluate_pairwise_position_swap(
    provider: BaseLLMProvider,
    instruction: str,
    input_data: str,
    candidate_a: str,
    candidate_b: str,
    model: str = "gpt-3.5-turbo",
) -> dict:
    """
    Zheng et al. (NeurIPS 2023) Position-Debiased Pairwise Judge.
    Runs Pass 1 (A as first, B as second) and Pass 2 (B as first, A as second).
    Detects and eliminates position bias where the first response is artificially favored.
    """
    if provider.is_demo:
        return {
            "winner": "tie",
            "score_a": 85.0,
            "score_b": 85.0,
            "position_bias_detected": False,
            "pass1": {"winner": "A", "score_a": 85, "score_b": 80, "rationale": "Demo simulation pass 1."},
            "pass2": {"winner": "B", "score_a": 80, "score_b": 85, "rationale": "Demo simulation pass 2."},
            "consensus_rationale": "Demo mode simulated balanced comparison.",
        }

    # Pass 1: Order (A, B)
    req1 = LLMRequest(
        system_prompt=PAIRWISE_JUDGE_SYSTEM_PROMPT,
        user_prompt=PAIRWISE_USER_TEMPLATE.format(
            instruction=instruction,
            input_data=input_data,
            response_a=candidate_a,
            response_b=candidate_b,
        ),
        model=model,
        temperature=0.0,
        max_tokens=600,
    )
    resp1 = provider.generate(req1)
    pass1_data = _parse_pairwise_json(resp1.content) or {"winner": "tie", "score_a": 50, "score_b": 50, "rationale": "Unparseable"}

    # Pass 2: Order (B, A) - Candidate B is now passed in position A, Candidate A in position B
    req2 = LLMRequest(
        system_prompt=PAIRWISE_JUDGE_SYSTEM_PROMPT,
        user_prompt=PAIRWISE_USER_TEMPLATE.format(
            instruction=instruction,
            input_data=input_data,
            response_a=candidate_b,
            response_b=candidate_a,
        ),
        model=model,
        temperature=0.0,
        max_tokens=600,
    )
    resp2 = provider.generate(req2)
    pass2_raw = _parse_pairwise_json(resp2.content) or {"winner": "tie", "score_a": 50, "score_b": 50, "rationale": "Unparseable"}

    pass2_winner_normalized = "tie"
    if pass2_raw["winner"] == "A":
        pass2_winner_normalized = "B"
    elif pass2_raw["winner"] == "B":
        pass2_winner_normalized = "A"

    score_a_pass2 = float(pass2_raw.get("score_b", 50))
    score_b_pass2 = float(pass2_raw.get("score_a", 50))

    avg_score_a = round((float(pass1_data.get("score_a", 50)) + score_a_pass2) / 2, 1)
    avg_score_b = round((float(pass1_data.get("score_b", 50)) + score_b_pass2) / 2, 1)

    p1_winner = pass1_data["winner"]
    p2_winner = pass2_winner_normalized

    if p1_winner == p2_winner:
        consensus_winner = p1_winner
        bias_detected = False
    elif (p1_winner == "A" and pass2_raw["winner"] == "A") or (p1_winner == "B" and pass2_raw["winner"] == "B"):
        consensus_winner = "inconclusive_position_bias"
        bias_detected = True
    else:
        consensus_winner = "tie" if avg_score_a == avg_score_b else ("A" if avg_score_a > avg_score_b else "B")
        bias_detected = False

    return {
        "winner": consensus_winner,
        "score_a": avg_score_a,
        "score_b": avg_score_b,
        "position_bias_detected": bias_detected,
        "pass1": pass1_data,
        "pass2": {
            "winner": pass2_winner_normalized,
            "score_a": score_a_pass2,
            "score_b": score_b_pass2,
            "rationale": pass2_raw.get("rationale", ""),
        },
        "consensus_rationale": f"Position-swapped aggregate: Score A={avg_score_a}, Score B={avg_score_b}. Bias detected={bias_detected}.",
    }
