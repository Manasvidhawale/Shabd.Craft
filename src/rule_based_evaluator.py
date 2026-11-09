"""
Shabd.Craft — Rule-Based Evaluator

Deterministic checks for prompt output quality.
These checks complement LLM-as-a-Judge by providing objective, repeatable metrics.
"""

from __future__ import annotations

import json
import re
from src.schemas import CriterionScore, OutputFormat


def evaluate_rule_based(
    generated_output: str,
    expected_output: str = "",
    output_format: OutputFormat = OutputFormat.TEXT,
    required_keywords: list[str] | None = None,
    max_words: int | None = None,
    required_fields: list[str] | None = None,
) -> list[CriterionScore]:
    """
    Perform rule-based evaluation on generated output.

    Returns a list of CriterionScore objects.
    """
    scores = []

    # 1. Non-empty response check (contributes to accuracy)
    if not generated_output or not generated_output.strip():
        return [
            CriterionScore(name="accuracy", score=0, explanation="Output is empty."),
            CriterionScore(name="relevance", score=0, explanation="Output is empty."),
            CriterionScore(name="instruction_adherence", score=0, explanation="Output is empty."),
            CriterionScore(name="clarity", score=0, explanation="Output is empty."),
            CriterionScore(name="format_compliance", score=0, explanation="Output is empty."),
        ]

    # 2. Format compliance
    format_score, format_explanation = _check_format(generated_output, output_format, required_fields)
    scores.append(CriterionScore(name="format_compliance", score=format_score, explanation=format_explanation))

    # 3. Keyword/phrase presence (instruction adherence proxy)
    adherence_score, adherence_explanation = _check_keywords(generated_output, required_keywords)
    scores.append(CriterionScore(name="instruction_adherence", score=adherence_score, explanation=adherence_explanation))

    # 4. Word count check (clarity and conciseness proxy)
    clarity_score, clarity_explanation = _check_word_count(generated_output, max_words)
    scores.append(CriterionScore(name="clarity", score=clarity_score, explanation=clarity_explanation))

    # 5. Accuracy — exact match when expected output is available
    accuracy_score, accuracy_explanation = _check_accuracy(generated_output, expected_output)
    scores.append(CriterionScore(name="accuracy", score=accuracy_score, explanation=accuracy_explanation))

    # 6. Relevance — basic relevance heuristic
    relevance_score, relevance_explanation = _check_relevance(generated_output, expected_output)
    scores.append(CriterionScore(name="relevance", score=relevance_score, explanation=relevance_explanation))

    return scores


def _check_format(output: str, expected_format: OutputFormat, required_fields: list[str] | None) -> tuple[float, str]:
    """Check if the output matches the expected format."""
    if expected_format == OutputFormat.JSON:
        try:
            parsed = json.loads(output)
            if required_fields:
                missing = [f for f in required_fields if f not in parsed]
                if missing:
                    return 60.0, f"Valid JSON but missing fields: {', '.join(missing)}"
            return 100.0, "Valid JSON format."
        except json.JSONDecodeError:
            # Check if JSON is embedded in text
            json_match = re.search(r'\{[\s\S]*\}', output)
            if json_match:
                try:
                    json.loads(json_match.group())
                    return 50.0, "JSON found but embedded in non-JSON text."
                except json.JSONDecodeError:
                    pass
            return 20.0, "Expected JSON format but output is not valid JSON."

    elif expected_format == OutputFormat.MARKDOWN:
        has_headers = bool(re.search(r'^#{1,6}\s', output, re.MULTILINE))
        has_lists = bool(re.search(r'^[\-\*]\s', output, re.MULTILINE))
        has_formatting = has_headers or has_lists or "**" in output or "__" in output
        if has_formatting:
            return 90.0, "Output contains Markdown formatting."
        return 50.0, "Output lacks Markdown formatting elements."

    elif expected_format == OutputFormat.BULLET_POINTS:
        bullet_lines = len(re.findall(r'^[\-\*•]\s', output, re.MULTILINE))
        if bullet_lines >= 2:
            return 90.0, f"Output contains {bullet_lines} bullet points."
        elif bullet_lines == 1:
            return 60.0, "Output contains only 1 bullet point."
        return 30.0, "Output does not use bullet point format."

    elif expected_format == OutputFormat.CSV:
        lines = output.strip().split("\n")
        if len(lines) >= 2 and "," in lines[0]:
            return 85.0, "Output appears to be CSV format."
        return 40.0, "Output does not appear to be CSV format."

    # Plain text — always passes
    return 80.0, "Plain text format (no specific format required)."


def _check_keywords(output: str, required_keywords: list[str] | None) -> tuple[float, str]:
    """Check if required keywords are present."""
    if not required_keywords:
        return 75.0, "No specific keywords required."

    output_lower = output.lower()
    found = [kw for kw in required_keywords if kw.lower() in output_lower]
    ratio = len(found) / len(required_keywords) if required_keywords else 1.0
    score = round(ratio * 100, 1)

    if ratio == 1.0:
        return score, f"All {len(required_keywords)} required keywords found."
    missing = [kw for kw in required_keywords if kw.lower() not in output_lower]
    return score, f"Found {len(found)}/{len(required_keywords)} keywords. Missing: {', '.join(missing[:5])}"


def _check_word_count(output: str, max_words: int | None) -> tuple[float, str]:
    """Check word count against limit."""
    word_count = len(output.split())

    if max_words is None:
        # No limit — score based on reasonable length
        if 10 <= word_count <= 500:
            return 85.0, f"Response has {word_count} words (reasonable length)."
        elif word_count < 10:
            return 50.0, f"Response is very short ({word_count} words)."
        else:
            return 65.0, f"Response is lengthy ({word_count} words)."

    if word_count <= max_words:
        return 95.0, f"Word count ({word_count}) within limit ({max_words})."
    overage = word_count - max_words
    penalty = min(overage / max_words * 100, 70)
    score = max(95.0 - penalty, 10.0)
    return round(score, 1), f"Word count ({word_count}) exceeds limit ({max_words}) by {overage} words."


def _check_accuracy(output: str, expected: str) -> tuple[float, str]:
    """Check accuracy against expected output if available."""
    if not expected or not expected.strip():
        return 70.0, "No expected output provided for accuracy comparison (rubric-based only)."

    output_clean = output.strip().lower()
    expected_clean = expected.strip().lower()

    if output_clean == expected_clean:
        return 100.0, "Output exactly matches expected output."

    # Check if expected content is contained
    if expected_clean in output_clean:
        return 85.0, "Expected output found within the generated response."

    # Word overlap ratio
    output_words = set(output_clean.split())
    expected_words = set(expected_clean.split())
    if expected_words:
        overlap = len(output_words & expected_words) / len(expected_words)
        score = round(overlap * 80, 1)
        return max(score, 20.0), f"Word overlap with expected output: {overlap:.0%}."

    return 40.0, "Output differs significantly from expected output."


def _check_relevance(output: str, expected: str) -> tuple[float, str]:
    """Basic relevance check using content overlap."""
    if not expected or not expected.strip():
        # Without expected output, assume moderate relevance if response is substantive
        word_count = len(output.split())
        if word_count > 20:
            return 70.0, "Response is substantive; relevance cannot be verified without expected output."
        return 50.0, "Short response; relevance cannot be verified without expected output."

    output_words = set(output.lower().split())
    expected_words = set(expected.lower().split())
    if expected_words:
        overlap = len(output_words & expected_words) / len(expected_words)
        score = min(round(overlap * 100, 1), 95.0)
        return max(score, 25.0), f"Content overlap with expected output: {overlap:.0%}."

    return 50.0, "Unable to determine relevance."
