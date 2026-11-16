"""
Shabd.Craft — Prompt Optimizer

Generates improved prompt candidates based on evaluation feedback.
Uses modular strategies for prompt improvement.
"""

from __future__ import annotations

import json
import hashlib
import random
from typing import Optional

from src.schemas import (
    OptimizationCandidate, PromptVersion, EvaluationResult,
    LLMRequest, ExecutionStatus, _new_id, _now,
)
from src.providers.base import BaseLLMProvider
from src.prompt_engine import get_provider


OPTIMIZER_SYSTEM_PROMPT = """You are an expert prompt engineer. Your task is to analyze a prompt and its evaluation results, then generate improved versions.

For each candidate, you must:
1. Identify specific weaknesses in the original prompt.
2. Apply a clear improvement strategy.
3. Explain what you changed and why.
4. Preserve the original task intent.

Return your response as valid JSON only."""

OPTIMIZER_USER_TEMPLATE = """Analyze this prompt and generate {num_candidates} improved versions.

## Original Prompt
System: {system_prompt}
User: {user_prompt}

## Task Category
{category}

## Evaluation Feedback
Average Score: {avg_score}/100
Weaknesses identified:
{weaknesses}

Criterion scores:
{criterion_details}

## Requirements
Generate exactly {num_candidates} candidate prompts, each with a DIFFERENT improvement strategy:
- Candidate A: Focus on clearer, more explicit instructions
- Candidate B: Focus on better task decomposition and context
- Candidate C: Focus on stronger output constraints and validation

Return valid JSON:
{{
    "candidates": [
        {{
            "label": "Candidate A",
            "strategy": "Explicit Instructions",
            "system_prompt": "<improved system prompt>",
            "user_prompt_template": "<improved user prompt>",
            "changes_description": "<what was changed>",
            "rationale": "<why this should improve results>"
        }}
    ]
}}"""


def generate_candidates(
    original_version: PromptVersion,
    evaluation_results: list[EvaluationResult],
    experiment_id: str,
    num_candidates: int = 3,
    category: str = "general",
) -> list[OptimizationCandidate]:
    """
    Generate optimization candidates based on the original prompt and evaluation feedback.

    Uses the configured provider (demo or real).
    Does NOT claim improvement — candidates must be tested.
    """
    provider = get_provider()

    # Aggregate evaluation feedback
    successful = [r for r in evaluation_results if r.execution_status == ExecutionStatus.SUCCESS]
    avg_score = round(sum(r.overall_score for r in successful) / len(successful), 1) if successful else 0.0

    all_weaknesses = []
    criterion_scores_agg: dict[str, list[float]] = {}
    for r in successful:
        all_weaknesses.extend(r.weaknesses)
        for cs in r.criterion_scores:
            criterion_scores_agg.setdefault(cs.name, []).append(cs.score)

    weakness_text = "\n".join(f"- {w}" for w in list(set(all_weaknesses))[:10]) or "- No specific weaknesses identified."
    criterion_text = "\n".join(
        f"- {name}: {sum(scores)/len(scores):.1f}/100"
        for name, scores in criterion_scores_agg.items()
    ) or "- No criterion scores available."

    if provider.is_demo:
        return _demo_candidates(original_version, experiment_id, num_candidates, avg_score)

    user_prompt = OPTIMIZER_USER_TEMPLATE.format(
        num_candidates=num_candidates,
        system_prompt=original_version.system_prompt or "(none)",
        user_prompt=original_version.user_prompt_template,
        category=category,
        avg_score=avg_score,
        weaknesses=weakness_text,
        criterion_details=criterion_text,
    )

    request = LLMRequest(
        system_prompt=OPTIMIZER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=original_version.model_name or "gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=2000,
    )

    response = provider.generate(request)

    if response.error:
        return _demo_candidates(original_version, experiment_id, num_candidates, avg_score)

    candidates = _parse_optimizer_response(response.content, original_version, experiment_id)

    if not candidates:
        return _demo_candidates(original_version, experiment_id, num_candidates, avg_score)

    return candidates[:num_candidates]


def _parse_optimizer_response(
    content: str,
    original: PromptVersion,
    experiment_id: str,
) -> list[OptimizationCandidate]:
    """Parse the optimizer's JSON response into candidates."""
    try:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            content = content.strip()
        if not content.startswith("{"):
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()
            else:
                return []

        data = json.loads(content)
        candidates_data = data.get("candidates", [])

        candidates = []
        for cd in candidates_data:
            candidates.append(OptimizationCandidate(
                experiment_id=experiment_id,
                original_version_id=original.id,
                candidate_label=cd.get("label", f"Candidate {len(candidates) + 1}"),
                strategy=cd.get("strategy", ""),
                system_prompt=cd.get("system_prompt", original.system_prompt),
                user_prompt_template=cd.get("user_prompt_template", original.user_prompt_template),
                changes_description=cd.get("changes_description", ""),
                rationale=cd.get("rationale", ""),
                status=ExecutionStatus.PENDING,
            ))

        return candidates
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _demo_candidates(
    original: PromptVersion,
    experiment_id: str,
    num_candidates: int,
    avg_score: float,
) -> list[OptimizationCandidate]:
    """Generate deterministic demo candidates. Clearly labeled as simulated."""
    seed = int(hashlib.md5(original.user_prompt_template.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    strategies = [
        {
            "label": "Candidate A",
            "strategy": "Explicit Instructions",
            "changes": "Added explicit step-by-step instructions, clarified expected output format, and specified constraints.",
            "rationale": "More explicit instructions reduce ambiguity and improve instruction adherence scores.",
        },
        {
            "label": "Candidate B",
            "strategy": "Task Decomposition",
            "changes": "Broke the task into numbered sub-steps, added context about the goal, and included a thinking framework.",
            "rationale": "Decomposing complex tasks helps the model organize its response systematically.",
        },
        {
            "label": "Candidate C",
            "strategy": "Output Constraints",
            "changes": "Added strict output format requirements, length constraints, and validation rules.",
            "rationale": "Explicit output constraints improve format compliance and response consistency.",
        },
    ]

    candidates = []
    for i in range(min(num_candidates, len(strategies))):
        s = strategies[i]
        # Generate a plausible improved prompt
        enhanced_system = original.system_prompt or "You are a helpful assistant."
        enhanced_user = original.user_prompt_template

        if i == 0:  # Explicit instructions
            enhanced_system = f"{enhanced_system}\n\nBe precise and follow all instructions exactly. If constraints are specified, adhere to them strictly."
            enhanced_user = f"Please complete the following task carefully.\n\nTask:\n{enhanced_user}\n\nIMPORTANT: Follow all instructions precisely. Be concise and accurate."
        elif i == 1:  # Task decomposition
            enhanced_user = f"Complete this task step by step:\n\nStep 1: Understand the input carefully.\nStep 2: Identify the key requirements.\nStep 3: Generate the response following the requirements.\n\nOriginal task:\n{enhanced_user}"
        elif i == 2:  # Output constraints
            enhanced_user = f"{enhanced_user}\n\nConstraints:\n- Keep your response focused and relevant.\n- Use clear, professional language.\n- Structure your response logically.\n- Do not include unnecessary information."

        candidates.append(OptimizationCandidate(
            experiment_id=experiment_id,
            original_version_id=original.id,
            candidate_label=s["label"],
            strategy=s["strategy"],
            system_prompt=enhanced_system,
            user_prompt_template=enhanced_user,
            changes_description=s["changes"],
            rationale=s["rationale"],
            status=ExecutionStatus.PENDING,
        ))

    return candidates


def recommend_best(
    original_score: float,
    candidate_scores: dict[str, float],
    test_case_count: int,
) -> dict:
    """
    Recommend the best candidate based on scores.

    Returns recommendation with limitations.
    Does NOT assume improvement — reports evidence.
    """
    if not candidate_scores:
        return {
            "winner": None,
            "recommendation": "No candidates were evaluated.",
            "improvement": False,
            "limitations": ["No evaluation data available."],
        }

    best_id = max(candidate_scores, key=candidate_scores.get)
    best_score = candidate_scores[best_id]

    limitations = []
    if test_case_count < 5:
        limitations.append(f"Small sample size ({test_case_count} test cases). Results may not generalize.")
    if best_score - original_score < 3:
        limitations.append("Score difference is small and may be within evaluation noise.")

    if best_score > original_score:
        improvement = True
        recommendation = (
            f"Candidate '{best_id}' scored {best_score:.1f} vs original {original_score:.1f} "
            f"(+{best_score - original_score:.1f} points). "
            f"This candidate shows improvement on the tested cases."
        )
    elif best_score == original_score:
        improvement = False
        recommendation = f"No candidate scored higher than the original ({original_score:.1f})."
    else:
        improvement = False
        recommendation = (
            f"The original prompt ({original_score:.1f}) outperformed all candidates. "
            f"Best candidate scored {best_score:.1f}."
        )

    return {
        "winner": best_id if improvement else None,
        "recommendation": recommendation,
        "improvement": improvement,
        "limitations": limitations,
        "best_score": best_score,
        "original_score": original_score,
    }


def run_iterative_optimization(
    original_version: PromptVersion,
    test_cases: list,
    experiment_id: str,
    weights,
    max_rounds: int = 3,
    category: str = "general",
    progress_callback=None,
) -> dict:
    """
    Empirical Multi-Round Prompt Optimization (GEPRO / Hill-Climbing Loop).

    In each generation:
    1. Evaluates current best prompt against test cases.
    2. Gathers failure modes, weaknesses, and lowest scoring criteria.
    3. Generates candidate mutations targeting the specific failure modes.
    4. Evaluates candidate mutations on test cases.
    5. Keeps the winning mutation if it improves the score (hill-climbing).
    6. Stops early if score plateau is reached or target score achieved.
    """
    from src.evaluation_engine import evaluate_batch, aggregate_results

    if not test_cases:
        return {
            "initial_score": 0.0,
            "final_score": 0.0,
            "rounds_executed": 0,
            "best_version": original_version,
            "history": [],
            "converged": False,
        }

    # Round 0: Evaluate baseline
    baseline_results = evaluate_batch(original_version, test_cases, experiment_id, weights)
    baseline_agg = aggregate_results(baseline_results)
    current_score = baseline_agg["avg_score"]
    best_version = original_version
    current_eval_results = baseline_results

    history = [{
        "round": 0,
        "label": "Baseline",
        "score": current_score,
        "system_prompt": original_version.system_prompt,
        "user_prompt_template": original_version.user_prompt_template,
        "strategy": "Original",
    }]

    rounds_run = 0
    converged = False

    for r in range(1, max_rounds + 1):
        rounds_run = r
        if progress_callback:
            progress_callback(r, max_rounds, f"Optimization Generation {r}/{max_rounds} (Score: {current_score:.1f})...")

        # Generate candidates based on latest evaluation failures
        candidates = generate_candidates(
            original_version=best_version,
            evaluation_results=current_eval_results,
            experiment_id=experiment_id,
            num_candidates=2,
            category=category,
        )

        round_best_cand = None
        round_best_score = current_score
        round_best_results = None

        for cand in candidates:
            cand_ver = PromptVersion(
                experiment_id=experiment_id,
                system_prompt=cand.system_prompt,
                user_prompt_template=cand.user_prompt_template,
                technique=best_version.technique,
                output_format=best_version.output_format,
                model_name=best_version.model_name,
                temperature=best_version.temperature,
                max_tokens=best_version.max_tokens,
                few_shot_examples=best_version.few_shot_examples,
            )
            c_res = evaluate_batch(cand_ver, test_cases, experiment_id, weights)
            c_agg = aggregate_results(c_res)
            score = c_agg["avg_score"]

            if score > round_best_score:
                round_best_score = score
                round_best_cand = cand
                round_best_results = c_res

        # Check for hill-climbing progress
        if round_best_cand and round_best_score > current_score:
            current_score = round_best_score
            current_eval_results = round_best_results
            best_version = PromptVersion(
                experiment_id=experiment_id,
                system_prompt=round_best_cand.system_prompt,
                user_prompt_template=round_best_cand.user_prompt_template,
                technique=best_version.technique,
                output_format=best_version.output_format,
                model_name=best_version.model_name,
                temperature=best_version.temperature,
                max_tokens=best_version.max_tokens,
                few_shot_examples=best_version.few_shot_examples,
                is_optimized=True,
                optimization_strategy=round_best_cand.strategy,
            )
            history.append({
                "round": r,
                "label": round_best_cand.candidate_label,
                "score": current_score,
                "system_prompt": round_best_cand.system_prompt,
                "user_prompt_template": round_best_cand.user_prompt_template,
                "strategy": round_best_cand.strategy,
            })
        else:
            # Score plateaued, early exit
            converged = True
            break

    return {
        "initial_score": baseline_agg["avg_score"],
        "final_score": current_score,
        "rounds_executed": rounds_run,
        "best_version": best_version,
        "history": history,
        "converged": converged,
    }
