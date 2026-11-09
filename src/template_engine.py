"""
Shabd.Craft — Template Engine

Handles prompt template rendering with safe variable substitution.
Supports {{variable}} syntax with validation.
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
