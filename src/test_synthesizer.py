"""
Shabd.Craft — Synthetic Test Case Synthesizer

Automatically generates high-coverage, diverse test suites (happy path,
edge case, adversarial probe, and format stress) tailored to a prompt version.
"""

from __future__ import annotations

import json
import random
import hashlib
from typing import Optional

from src.schemas import PromptVersion, TestCase, LLMRequest
from src.template_engine import extract_variables
from src.prompt_engine import get_provider
from src.config import settings


_SYNTHESIS_SYSTEM_PROMPT = """You are a Principal AI QA and Evaluation Engineer.
Your task is to generate realistic, rigorous test cases to benchmark and evaluate a prompt template.
For the given prompt template, generate diverse test cases covering:
1. Standard Happy Path (typical realistic user input)
2. Edge Case (subtle, terse, ambiguous, or boundary condition input)
3. Adversarial / Injection Probe (testing constraint adherence and instruction boundaries)
4. Format / Stress Test (complex or challenging real-world input)

Respond ONLY with valid JSON matching this schema:
{
  "test_cases": [
    {
      "input_data": "The exact input text that replaces the template placeholder",
      "expected_output": "Ideal, high-quality ground-truth reference output"
    }
  ]
}
Do not include any markdown formatting, code blocks, or text outside the JSON object."""


def generate_synthetic_test_cases(
    version: PromptVersion,
    count: int = 3,
    category: str = "general",
) -> list[TestCase]:
    """
    Generate synthetic test cases for a given prompt version.

    Uses the active LLM provider (Groq / OpenAI) if available,
    or falls back to high-quality deterministic category-specific generators.
    """
    provider = get_provider()

    if not provider.is_demo:
        try:
            llm_cases = _generate_with_llm(provider, version, count, category)
            if llm_cases:
                return llm_cases
        except Exception:
            pass

    return _generate_deterministic_cases(version, count, category)


def _generate_with_llm(
    provider,
    version: PromptVersion,
    count: int,
    category: str,
) -> list[TestCase]:
    """Call LLM provider to synthesize test cases."""
    variables = extract_variables(version.user_prompt_template)
    var_str = ", ".join(variables) if variables else "general input"

    user_msg = (
        f"Generate {count} test cases for the following prompt configuration:\n\n"
        f"Task Category: {category}\n"
        f"System Prompt: {version.system_prompt or 'None'}\n"
        f"User Prompt Template:\n{version.user_prompt_template}\n\n"
        f"Declared Template Variables: {var_str}\n\n"
        f"Generate exactly {count} test cases in valid JSON."
    )

    req = LLMRequest(
        system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
        user_prompt=user_msg,
        model=version.model_name or settings.default_model,
        temperature=0.7,
        max_tokens=1500,
    )

    resp = provider.generate(req)
    if resp.error or not resp.content:
        return []

    content = resp.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(content)
        items = data.get("test_cases", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        results = []
        for item in items[:count]:
            inp = item.get("input_data", "").strip()
            exp = item.get("expected_output", "").strip()
            if inp:
                results.append(TestCase(input_data=inp, expected_output=exp))
        return results
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _generate_deterministic_cases(
    version: PromptVersion,
    count: int,
    category: str,
) -> list[TestCase]:
    """Generate deterministic domain-specific synthetic test cases."""
    seed = int(hashlib.md5((version.user_prompt_template + category).encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    pool = {
        "classification": [
            ("The application crashed immediately when I clicked the export button.", "Bug Report"),
            ("Would love an option to schedule automated summary exports every Monday.", "Feature Request"),
            ("Where can I find your API documentation for team tier accounts?", "General Inquiry"),
            ("Billing charged me twice for last month's subscription.", "Complaint"),
            ("Your customer support team resolved my ticket in under 5 minutes, fantastic job!", "Praise"),
        ],
        "summarization": [
            ("Q3 revenue reached $14.2M, representing a 22% year-over-year increase, driven primarily by enterprise software adoption in APAC markets. Operating margin expanded by 340 bps.",
             "Q3 revenue rose 22% YoY to $14.2M with enterprise software adoption in APAC expanding operating margins by 340 bps."),
            ("Customer reported that delivery arrived three days behind schedule, packaging was dented, but inner hardware was undamaged and functional.",
             "Customer noted a 3-day delivery delay and dented packaging, though the hardware was functional."),
            ("Security patch 4.12 resolves three CVEs in SSL handshake verification and updates the cryptographic cipher suite for TLS 1.3 compliance.",
             "Security patch 4.12 fixes three SSL verification vulnerabilities and updates the TLS 1.3 cipher suite."),
        ],
        "sentiment": [
            ("The dashboard loads instantly and the new charts save us hours every week.", "Positive"),
            ("It works as expected, nothing particularly noteworthy or frustrating.", "Neutral"),
            ("The latest update completely ruined my established workflow, very disappointed.", "Negative"),
            ("Great concept and UI design, but currently riddled with sync lag and freezing.", "Mixed"),
        ],
        "extraction": [
            ("On October 24, 2024, Acme Corp acquired BetaSoft in Berlin for $450 million.",
             '{"acquirer": "Acme Corp", "target": "BetaSoft", "location": "Berlin", "value": "$450 million", "date": "October 24, 2024"}'),
            ("Dr. Angela Davis will deliver the keynote address at Stanford Auditorium on Friday at 4 PM.",
             '{"speaker": "Dr. Angela Davis", "venue": "Stanford Auditorium", "time": "Friday 4 PM"}'),
        ],
    }

    category_key = category.lower() if category.lower() in pool else "summarization"
    candidates = pool.get(category_key, pool["summarization"])

    cases = []
    for i in range(min(count, len(candidates))):
        inp, exp = candidates[i % len(candidates)]
        cases.append(TestCase(input_data=inp, expected_output=exp))

    while len(cases) < count:
        idx = len(cases) + 1
        cases.append(TestCase(
            input_data=f"Synthetic test scenario #{idx} evaluating prompt performance under constraint boundary condition.",
            expected_output=f"Expected synthetic benchmark output for scenario #{idx}.",
        ))

    return cases[:count]
