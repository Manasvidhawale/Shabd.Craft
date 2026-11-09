"""
Shabd.Craft — Prompt Engine

Constructs prompts using various prompting techniques (zero-shot, one-shot,
few-shot, role-based, structured-output, task-decomposition).
Manages prompt execution through the configured provider.
"""

from __future__ import annotations

from src.schemas import (
    LLMRequest, LLMResponse, PromptVersion, FewShotExample,
    PromptingTechnique, OutputFormat,
)
from src.template_engine import render_template
from src.providers.base import BaseLLMProvider
from src.providers.demo_provider import DemoProvider
from src.providers.openai_provider import OpenAIProvider
from src.config import settings


# ── Technique descriptions (for UI help text) ─────────────────────────

TECHNIQUE_INFO = {
    PromptingTechnique.ZERO_SHOT: {
        "name": "Zero-Shot",
        "description": "Give the model instructions without any examples. Best for straightforward tasks where the model has strong prior knowledge.",
        "example_system": "You are a helpful assistant.",
        "example_user": "Classify the following text as positive, negative, or neutral:\n\n\"The product works well but shipping was slow.\"",
    },
    PromptingTechnique.ONE_SHOT: {
        "name": "One-Shot",
        "description": "Provide one demonstration example to guide the model's output format and style. Useful when you need a specific output pattern.",
        "example_system": "You are a text classifier.",
        "example_user": (
            "Example:\nInput: \"Great product, fast delivery!\"\nOutput: positive\n\n"
            "Now classify:\nInput: \"The product works well but shipping was slow.\"\nOutput:"
        ),
    },
    PromptingTechnique.FEW_SHOT: {
        "name": "Few-Shot",
        "description": "Provide multiple input-output examples. Best for complex tasks requiring consistent formatting or nuanced understanding.",
        "example_system": "You are a sentiment classifier.",
        "example_user": (
            "Example 1:\nInput: \"Amazing quality!\"\nOutput: positive\n\n"
            "Example 2:\nInput: \"Terrible experience.\"\nOutput: negative\n\n"
            "Example 3:\nInput: \"It's okay, nothing special.\"\nOutput: neutral\n\n"
            "Now classify:\nInput: \"The product works well but shipping was slow.\"\nOutput:"
        ),
    },
    PromptingTechnique.ROLE_BASED: {
        "name": "Role-Based",
        "description": "Assign a specific role, expertise, and context to the model. Useful for domain-specific tasks requiring expert knowledge.",
        "example_system": "You are a senior customer experience analyst with 10 years of experience in e-commerce feedback analysis. You specialize in identifying actionable insights from customer reviews.",
        "example_user": "Analyze this customer feedback and identify the top 3 actionable improvements:\n\n\"{{customer_feedback}}\"",
    },
    PromptingTechnique.STRUCTURED_OUTPUT: {
        "name": "Structured Output",
        "description": "Require a specific output structure (JSON, table, etc.). Best when downstream systems need parseable, consistent output.",
        "example_system": "You are a data extraction assistant. Always respond with valid JSON.",
        "example_user": (
            "Extract the following information and return it as JSON:\n"
            "- sentiment (positive/negative/neutral)\n"
            "- key_topics (list of strings)\n"
            "- urgency (low/medium/high)\n\n"
            "Text: \"{{input_text}}\""
        ),
    },
    PromptingTechnique.TASK_DECOMPOSITION: {
        "name": "Task Decomposition",
        "description": "Break a complex task into clearly defined subtasks. Best for multi-step analysis, reasoning, or generation tasks.",
        "example_system": "You are a thorough analyst. Complete each step before moving to the next.",
        "example_user": (
            "Analyze the following customer feedback in these steps:\n\n"
            "Step 1: Identify the main topic of the feedback.\n"
            "Step 2: Determine the customer's sentiment (positive/negative/neutral).\n"
            "Step 3: List specific issues or praise mentioned.\n"
            "Step 4: Suggest one actionable improvement.\n"
            "Step 5: Write a brief professional summary.\n\n"
            "Feedback: \"{{customer_feedback}}\""
        ),
    },
}


# ── Prompt Construction ───────────────────────────────────────────────

def build_few_shot_section(examples: list[FewShotExample]) -> str:
    """Build the few-shot examples section of a prompt."""
    if not examples:
        return ""

    parts = []
    for i, ex in enumerate(examples, 1):
        parts.append(f"Example {i}:\nInput: {ex.input_text}\nOutput: {ex.output_text}")

    return "\n\n".join(parts) + "\n\nNow process the following:\n"


def build_output_format_instruction(output_format: OutputFormat) -> str:
    """Build output format instruction text."""
    instructions = {
        OutputFormat.TEXT: "",
        OutputFormat.JSON: "\n\nRespond with valid JSON only. Do not include any text outside the JSON object.",
        OutputFormat.MARKDOWN: "\n\nFormat your response using Markdown with appropriate headings, lists, and emphasis.",
        OutputFormat.CSV: "\n\nFormat your response as CSV with a header row.",
        OutputFormat.BULLET_POINTS: "\n\nFormat your response as a bulleted list.",
    }
    return instructions.get(output_format, "")


def construct_prompt(
    version: PromptVersion,
    input_data: str = "",
    variables: dict[str, str] | None = None,
) -> tuple[str, str]:
    """
    Construct system and user prompts from a PromptVersion.

    Returns (system_prompt, user_prompt) tuple.
    """
    system_prompt = version.system_prompt
    user_template = version.user_prompt_template

    # Merge variables with input data
    all_vars = dict(variables or {})
    if input_data:
        # Auto-assign input_data to common variable names if not already set
        for var_name in ["input", "input_text", "text", "customer_feedback", "data", "content", "query"]:
            if var_name not in all_vars:
                all_vars[var_name] = input_data

    # Render template variables
    try:
        user_prompt = render_template(user_template, all_vars)
    except ValueError:
        # If variables are missing, use the template as-is with input appended
        user_prompt = user_template
        if input_data and input_data not in user_prompt:
            user_prompt += f"\n\n{input_data}"

    # Add few-shot examples
    if version.technique in (PromptingTechnique.ONE_SHOT, PromptingTechnique.FEW_SHOT):
        few_shot_section = build_few_shot_section(version.few_shot_examples)
        if few_shot_section:
            user_prompt = few_shot_section + user_prompt

    # Add output format instruction
    format_instruction = build_output_format_instruction(version.output_format)
    if format_instruction:
        user_prompt += format_instruction

    return system_prompt, user_prompt


# ── Provider Management ───────────────────────────────────────────────

def get_provider() -> BaseLLMProvider:
    """Get the appropriate LLM provider based on configuration."""
    if settings.is_demo_mode:
        return DemoProvider()
    return OpenAIProvider()


def execute_prompt(
    version: PromptVersion,
    input_data: str = "",
    variables: dict[str, str] | None = None,
) -> LLMResponse:
    """
    Execute a prompt version against the configured LLM provider.

    Returns an LLMResponse with content or error information.
    """
    system_prompt, user_prompt = construct_prompt(version, input_data, variables)

    provider = get_provider()
    request = LLMRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=version.model_name or settings.active_model,
        temperature=version.temperature,
        max_tokens=version.max_tokens,
    )

    return provider.generate(request)
