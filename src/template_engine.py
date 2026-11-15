"""
Shabd.Craft — Template Engine

Handles prompt template rendering with safe variable substitution.
Supports {{variable}} syntax with validation and structural quality analysis.
"""

from __future__ import annotations

import re
from typing import Optional


# Pattern for {{variable_name}} placeholders
_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def extract_variables(template: str) -> list[str]:
    """Extract all {{variable}} names from a template string."""
    return list(dict.fromkeys(_VAR_PATTERN.findall(template)))


def render_template(template: str, variables: dict[str, str]) -> str:
    """
    Render a template by substituting {{variable}} placeholders.

    Raises ValueError if required variables are missing.
    Uses safe substitution — no code execution.
    """
    required = extract_variables(template)
    missing = [v for v in required if v not in variables]
    if missing:
        raise ValueError(f"Missing template variables: {', '.join(missing)}")

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        return str(variables.get(var_name, match.group(0)))

    return _VAR_PATTERN.sub(_replace, template)


def validate_template(template: str) -> dict:
    """
    Validate a template string and return analysis.

    Returns dict with:
      - is_valid: bool
      - variables: list of variable names
      - warnings: list of warning messages
    """
    warnings = []
    variables = extract_variables(template)

    # Check for unmatched braces
    single_open = template.count("{") - template.count("{{") * 2
    single_close = template.count("}") - template.count("}}") * 2
    if single_open > 0 or single_close > 0:
        warnings.append("Template contains unmatched curly braces.")

    if not template.strip():
        warnings.append("Template is empty.")

    if len(template) > 10000:
        warnings.append("Template is very long (>10,000 characters). Consider shortening.")

    return {
        "is_valid": len(warnings) == 0 or (len(warnings) == 0 and bool(template.strip())),
        "variables": variables,
        "warnings": warnings,
    }


def preview_template(template: str, sample_values: Optional[dict[str, str]] = None) -> str:
    """
    Preview a template with sample values or placeholder indicators.
    Does not raise on missing variables — shows [variable_name] instead.
    """
    values = sample_values or {}

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in values:
            return values[var_name]
        return f"[{var_name}]"

    return _VAR_PATTERN.sub(_replace, template)


def analyze_prompt_structure(
    system_prompt: str,
    user_prompt: str,
    technique: str = "zero_shot",
    output_format: str = "text",
    few_shot_count: int = 0,
) -> dict:
    """
    Evaluate prompt structural quality dynamically across 6 engineering dimensions.

    Returns a dict with:
      - score: int (0-100)
      - grade: str ('Strong', 'Moderate', or 'Weak')
      - issues: list[str]
      - passed: list[str]
    """
    sys_clean = (system_prompt or "").strip()
    usr_clean = (user_prompt or "").strip()
    sys_lower = sys_clean.lower()
    usr_lower = usr_clean.lower()
    combined_lower = f"{sys_lower}\n{usr_lower}"

    score = 0
    issues: list[str] = []
    passed: list[str] = []

    # 1. System vs User separation (20 pts)
    if not sys_clean:
        issues.append("Missing system prompt — define the assistant's role and boundaries.")
    elif sys_lower == usr_lower:
        score += 5
        issues.append("System prompt and user prompt are identical — separate persona/rules from task input.")
    elif len(sys_clean) < 15:
        score += 10
        issues.append("System prompt is very brief — expand role or constraint instructions.")
    else:
        score += 20
        passed.append("System instructions cleanly separated from user template.")

    # 2. Template parameterization (20 pts)
    variables = extract_variables(usr_clean)
    if variables:
        score += 20
        passed.append(f"Parameterized with {len(variables)} variable(s): {', '.join(variables)}.")
    else:
        issues.append("No {{variable}} placeholders — static prompts cannot run over test datasets.")

    # 3. Task specificity (15 pts)
    word_count = len(usr_clean.split())
    if word_count >= 8 and len(usr_clean) >= 30:
        score += 15
        passed.append("User prompt has sufficient task detail.")
    else:
        score += 5
        issues.append("User prompt is too short — add clearer task instructions.")

    # 4. Output constraints & format alignment (20 pts)
    constraint_markers = (
        "json", "bullet", "csv", "markdown", "table", "concise", "brief",
        "sentence", "word", "limit", "only", "strictly", "format", "schema",
        "field", "key", "step", "list", "max", "under",
    )
    has_constraints = any(m in combined_lower for m in constraint_markers)
    if output_format == "json" and "json" not in combined_lower:
        score += 5
        issues.append("JSON output format selected, but JSON structure is not mentioned in the prompt.")
    elif has_constraints:
        score += 20
        passed.append("Includes explicit output format or constraint cues.")
    else:
        issues.append("No output constraints detected (e.g. length, structure, or format rules).")

    # 5. Input boundary delimiters (10 pts)
    has_delimiters = bool(
        re.search(r"<[a-zA-Z_][a-zA-Z0-9_-]*>.*\{\{.*\}\}.*</[a-zA-Z_][a-zA-Z0-9_-]*>", usr_clean, re.DOTALL)
        or '"""' in usr_clean
        or "'''" in usr_clean
        or "---" in usr_clean
        or "```" in usr_clean
    )
    if not variables:
        pass
    elif has_delimiters:
        score += 10
        passed.append("Template variables are isolated with explicit delimiters.")
    else:
        issues.append("Wrap {{variables}} in delimiters (e.g. <user_input>{{var}}</user_input>) to guard against injection.")

    # 6. Technique alignment (15 pts)
    if technique == "role_based":
        if any(r in sys_lower for r in ("you are", "expert", "specialist", "analyst", "engineer", "as a")):
            score += 15
        else:
            score += 5
            issues.append("Role-Based selected — define an explicit expert persona in System Instructions.")
    elif technique == "structured_output":
        if any(k in combined_lower for k in ("json", "field", "schema", "key", "column", "format")):
            score += 15
        else:
            score += 5
            issues.append("Structured Output selected — specify target field names or schema in the prompt.")
    elif technique in ("one_shot", "few_shot"):
        needed = 1 if technique == "one_shot" else 2
        if few_shot_count >= needed:
            score += 15
        else:
            score += 5
            issues.append(f"{technique.replace('_', '-').title()} selected — fill in at least {needed} demonstration example(s).")
    elif technique == "task_decomposition":
        if any(s in usr_lower for s in ("step 1", "1.", "first", "subtask")):
            score += 15
        else:
            score += 10
            issues.append("No explicit steps written — a default 3-step decomposition scaffold will be prepended.")
    else:
        score += 15

    grade = "Strong" if score >= 80 else ("Moderate" if score >= 55 else "Weak")
    return {
        "score": min(score, 100),
        "grade": grade,
        "issues": issues,
        "passed": passed,
    }
